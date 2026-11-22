"""Plain-assert tests for the Telegram client and its store (relief stage 4): .venv/bin/python tests/test_relief_telegram.py"""
import os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16))
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("RELIEF_JOBS", None)
os.environ.pop("RAILWAY_PUBLIC_DOMAIN", None)
sys.path.insert(0, ROOT)
import app as A, store  # noqa: E402,F401
from relief import tg, tgdb  # noqa: E402
import json, logging, urllib.error  # noqa: E402

KINDS = logging.getLogger("relief.telegram")           # what it logs is not printed here: the tests that check it attach their own handler
KINDS.addHandler(logging.NullHandler()); KINDS.propagate = False

REAL = []
def never(url, data, headers, timeout):
    REAL.append(1); raise AssertionError("a test reached the network")
tg._send = never

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

def answer(status, body):
    if not isinstance(body, bytes): body = json.dumps(body).encode()
    return lambda url, data, headers, timeout: (status, body)

def failing(exc):
    def f(url, data, headers, timeout): raise exc
    return f

def with_send(fake, f):
    real = tg._send
    tg._send = fake
    try: return f()
    finally: tg._send = real

class Grab(logging.Handler):
    def __init__(self): super().__init__(); self.records = []
    def emit(self, r): self.records.append(r)

@t
def without_a_token_it_is_off_and_calls_nothing():
    assert tg.token() == "" and not tg.on() and not tg.practice()
    r = tg.call("getMe")
    assert r["ok"] is False and r["kind"] == "refused" and r["result"] is None, r
    assert tg.download("x", 100) is None
    assert REAL == []

@t
def the_hook_secret_depends_on_the_token_and_the_key():
    old = os.environ.get("SECRET_KEY")
    try:
        os.environ["TELEGRAM_BOT_TOKEN"] = "tok-" + secrets.token_hex(8)
        a = tg.hook_secret()
        assert len(a) == 64 and int(a, 16) >= 0
        os.environ["TELEGRAM_BOT_TOKEN"] = "tok-" + secrets.token_hex(8)
        b = tg.hook_secret()
        assert b != a
        os.environ["SECRET_KEY"] = secrets.token_hex(16)
        assert tg.hook_secret() not in (a, b)
        assert tg.hook_secret() == tg.hook_secret()
        os.environ.pop("SECRET_KEY")
        assert tg.hook_secret() == ""
    finally:
        os.environ["SECRET_KEY"] = old
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)

@t
def every_failure_becomes_its_kind():
    os.environ["TELEGRAM_BOT_TOKEN"] = secrets.token_hex(12)
    try:
        assert tg.on() and not tg.practice()
        def kind(fake): return with_send(fake, lambda: tg.call("sendMessage", dict(chat_id=1, text="hi")))
        ok = kind(answer(200, dict(ok=True, result=dict(message_id=7))))
        assert ok["ok"] and ok["kind"] is None and ok["result"] == dict(message_id=7), ok
        r = kind(answer(403, dict(ok=False, description="blocked")))
        assert not r["ok"] and r["kind"] == "blocked", r
        r = kind(answer(429, dict(ok=False, parameters=dict(retry_after=12))))
        assert r["kind"] == "slow" and r["retry_after"] == 12, r
        r = kind(answer(429, dict(ok=False)))
        assert r["kind"] == "slow" and r["retry_after"] == 5, r
        assert kind(answer(400, dict(ok=False)))["kind"] == "refused"
        for status in (500, 504): assert kind(answer(status, b"late"))["kind"] == "unsure" and kind(answer(status, dict(ok=True, result=1)))["kind"] == "unsure", status
        for status in (501, 502, 503, 505, 520, 599): assert kind(answer(status, b"bad gateway"))["kind"] == "network", status
        assert kind(failing(urllib.error.HTTPError("u", 504, "x", {}, None)))["kind"] == "unsure"
        assert kind(answer(200, dict(ok=False)))["kind"] == "refused"
        assert kind(answer(200, b"<html>"))["kind"] == "refused"
        assert kind(failing(urllib.error.URLError("no route")))["kind"] == "network"
        assert kind(failing(urllib.error.HTTPError("u", 403, "x", {}, None)))["kind"] == "blocked"
        assert kind(failing(TimeoutError()))["kind"] == "unsure"
        assert kind(failing(ConnectionResetError()))["kind"] == "unsure"
        import http.client
        assert kind(failing(http.client.IncompleteRead(b"")))["kind"] == "unsure"
        assert kind(failing(ValueError("odd")))["kind"] == "network"
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)

@t
def no_failure_text_is_logged():
    tok = secrets.token_hex(12)
    os.environ["TELEGRAM_BOT_TOKEN"] = tok
    h, lg = Grab(), logging.getLogger("relief.telegram")
    lg.addHandler(h); old = lg.level; lg.setLevel(logging.DEBUG)
    try:
        for exc in (urllib.error.URLError("https://api.telegram.org/bot%s/x" % tok), TimeoutError(tok), RuntimeError(tok)):
            with_send(failing(exc), lambda: tg.call("sendMessage", dict(chat_id=1, text="hi")))
        with_send(answer(400, dict(ok=False, description=tok)), lambda: tg.call("sendMessage", dict(chat_id=1, text="hi")))
        assert h.records, "failures are logged by kind"
        for r in h.records:
            text = r.getMessage()
            assert tok not in text and r.exc_info is None and not r.args, text
            assert text in ("network", "unsure", "refused", "blocked", "slow"), text
    finally:
        lg.removeHandler(h); lg.setLevel(old)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)

@t
def files_go_as_multipart():
    os.environ["TELEGRAM_BOT_TOKEN"] = secrets.token_hex(12)
    seen = []
    def fake(url, data, headers, timeout):
        seen.append((url, data, headers)); return 200, b'{"ok": true, "result": {"message_id": 3}}'
    try:
        body = b"\x00\x01plain bytes " + secrets.token_bytes(8)
        r = with_send(fake, lambda: tg.call("sendDocument", dict(chat_id=5), files=[("document", "work sheet.pdf", body)]))
        assert r["ok"], r
        url, data, headers = seen[0]
        ct = {k.lower(): v for k, v in headers.items()}["content-type"]
        assert ct.startswith("multipart/form-data; boundary=")
        assert b"work sheet.pdf" in data and body in data and b'name="chat_id"' in data
        assert ct.split("boundary=")[1].encode() in data
        assert url.endswith("/sendDocument")
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)

@t
def practice_never_reaches_the_network():
    os.environ["TELEGRAM_BOT_TOKEN"] = "practice"
    try:
        assert tg.on() and tg.practice()
        tg.PRACTICE_LOG.clear()
        me = tg.call("getMe")
        assert me["ok"] and me["result"] == dict(username="practice_bot", first_name="Practice"), me
        a = tg.call("sendMessage", dict(chat_id=1, text="x"))
        b = tg.call("sendMessage", dict(chat_id=1, text="y"))
        assert a["ok"] and b["result"]["message_id"] == a["result"]["message_id"] + 1
        assert [m for m, p in tg.PRACTICE_LOG] == ["getMe", "sendMessage", "sendMessage"]
        assert tg.PRACTICE_LOG[1][1]["text"] == "x"
        assert tg.download("f", 1000) == b"practice file" and tg.download("f", 3) is None
        assert tg.hook_secret() != ""
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    assert REAL == []

@t
def downloads_check_the_limit():
    os.environ["TELEGRAM_BOT_TOKEN"] = secrets.token_hex(12)
    calls = []
    def fake(url, data, headers, timeout):
        calls.append(url)
        if url.endswith("/getFile"): return 200, b'{"ok": true, "result": {"file_path": "docs/a.pdf", "file_size": 4}}'
        return 200, b"abcd"
    try:
        assert with_send(fake, lambda: tg.download("id", 10)) == b"abcd"
        assert with_send(fake, lambda: tg.download("id", 3)) is None
        assert with_send(failing(TimeoutError()), lambda: tg.download("id", 10)) is None
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)

@t
def state_and_seen_updates_survive_a_reopen():
    assert tgdb.PATH == os.path.join(store.DATA, "relief", "telegram.db")
    assert tgdb.get_state("k") is None and os.path.exists(tgdb.PATH) and tgdb.get_state("k", 3) == 3
    tgdb.set_state("k", dict(a=[1, 2], b="é"))
    assert tgdb.get_state("k") == dict(a=[1, 2], b="é")
    tgdb.set_state("k", 9); assert tgdb.get_state("k") == 9
    assert tgdb.first_time(5) is True and tgdb.first_time(5) is False
    with tgdb.db() as c:
        assert c.execute("select count(*) from updates where id=5").fetchone()[0] == 1
    assert tgdb.first_time(5) is False
    for i in range(10, 1210): tgdb.first_time(i)
    with tgdb.db() as c:
        ids = [r["id"] for r in c.execute("select id from updates order by id")]
    assert len(ids) == 1000 and ids[-1] == 1209 and ids[0] == 210, (len(ids), ids[:2])
    assert tgdb.first_time(1209) is False and tgdb.first_time(5) is True       # 5 had fallen out of the last 1000
    assert tgdb.first_time(5) is False
    try:
        with tgdb.db() as c:
            c.execute("insert into state(k, v) values ('boom', '1')"); raise KeyError("x")
    except KeyError: pass
    assert tgdb.get_state("boom") is None
    with tgdb.db() as c:
        names = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    assert {"links", "codes", "outbox", "buttons", "talks", "updates", "state"} <= names

@t
def a_random_restart_of_update_ids_is_never_forgotten():
    for i in range(5000, 6100): tgdb.first_time(i)
    assert tgdb.first_time(42) is True and tgdb.first_time(42) is False         # a low id after high ones
    assert tgdb.first_time(43) is True and tgdb.first_time(43) is False and tgdb.first_time(42) is False
    assert tgdb.first_time(9_000_000) is True and tgdb.first_time(9_000_000) is False and tgdb.first_time(43) is False
    with tgdb.db(read=True) as c:
        assert c.execute("select count(*) from updates").fetchone()[0] == 1000

@t
def unsure_covers_what_may_have_gone_out():
    import http.client, socket, ssl
    os.environ["TELEGRAM_BOT_TOKEN"] = secrets.token_hex(12)
    U = urllib.error.URLError
    cases = [(BrokenPipeError(), "unsure"), (ConnectionAbortedError(), "unsure"), (ConnectionResetError(), "unsure"),
             (socket.timeout(), "unsure"), (http.client.RemoteDisconnected("x"), "unsure"), (ConnectionRefusedError(), "network"),
             (U(socket.gaierror(8, "nodename")), "network"), (U(ConnectionRefusedError()), "network"),
             (U(TimeoutError()), "unsure"), (U(ConnectionResetError()), "unsure"), (U(BrokenPipeError()), "unsure"),
             (U(OSError("odd")), "unsure"), (U("plain text"), "network"), (U(ssl.SSLCertVerificationError("bad")), "network"),
             (ssl.SSLCertVerificationError("bad"), "network"), (U(ssl.SSLError("handshake")), "unsure"),
             (ssl.SSLError("mid-read"), "unsure"), (ssl.SSLEOFError("eof"), "unsure"), (ssl.SSLZeroReturnError("zero"), "unsure"),
             (RuntimeError("odd"), "network")]
    try:
        for exc, want in cases:
            got = with_send(failing(exc), lambda: tg.call("sendMessage", dict(chat_id=1, text="hi")))["kind"]
            assert got == want, (repr(exc), got, want)
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)

@t
def a_failed_download_logs_a_kind_only_once():
    tok = secrets.token_hex(12)
    os.environ["TELEGRAM_BOT_TOKEN"] = tok
    h, lg = Grab(), logging.getLogger("relief.telegram")
    lg.addHandler(h)
    def run(fake):
        h.records.clear()
        assert with_send(fake, lambda: tg.download("id", 10)) is None
        return [r.getMessage() for r in h.records]
    def second_fails(url, data, headers, timeout):
        if url.endswith("/getFile"): return 200, b'{"ok": true, "result": {"file_path": "a/b", "file_size": 1}}'
        raise TimeoutError(tok)
    def big(url, data, headers, timeout):
        if url.endswith("/getFile"): return 200, b'{"ok": true, "result": {"file_path": "a/b"}}'
        return 200, b"x" * 50
    def second_403(url, data, headers, timeout):
        if url.endswith("/getFile"): return 200, b'{"ok": true, "result": {"file_path": "a/b"}}'
        return 403, tok.encode()
    try:
        assert run(failing(urllib.error.URLError(tok))) == ["network"]
        assert run(answer(429, dict(ok=False))) == ["slow"]
        assert run(second_fails) == ["unsure"]
        assert run(big) == ["refused"]
        assert run(second_403) == ["blocked"]
    finally:
        lg.removeHandler(h); os.environ.pop("TELEGRAM_BOT_TOKEN", None)

@t
def two_threads_reading_then_writing_never_lock():
    import threading
    tgdb.set_state("ctr", 0)
    errs = []
    def work():
        try:
            for _ in range(20):
                with tgdb.db() as c:
                    v = json.loads(c.execute("select v from state where k='ctr'").fetchone()["v"])
                    c.execute("update state set v=? where k='ctr'", (json.dumps(v + 1),))
        except Exception as e: errs.append(repr(e))
    ts = [threading.Thread(target=work) for _ in range(2)]
    [x.start() for x in ts]; [x.join() for x in ts]
    assert errs == [] and tgdb.get_state("ctr") == 40, (errs, tgdb.get_state("ctr"))

# ---- Task 2: linking a person, the hook, connecting the bot ----
import collections, contextlib, hashlib, itertools, re, sqlite3, threading, time  # noqa: E402
import access, history  # noqa: E402
from accounts import people as AP, rights as AR  # noqa: E402
from relief import bot, links, outbox as OB, people as RP, tell as TE, tgweb, web as WB  # noqa: E402
TE.SYNC = True                                        # a sweep asked for (after a save, after linking) runs inline here, in no thread

TIA, HUGO, CORA, EXE, TEAM, ROSA, GONE_, OFFIE = ("Ms Tia Teo", "Mr Hugo Ong", "Ms Cora Lim", "Mdm Exe Sim", "Ms Team Tan", "Ms Rosa Ng",
                                                  "Mr Gone Goh", "Mr Offie Foo")
PUB = RP.fake_pub([dict(name=TIA, dept="Science"), dict(name=HUGO, dept="Science", role="HOD"), dict(name=TEAM, dept="Mathematics"),
                   dict(name=ROSA, dept="English"), dict(name=OFFIE, dept="English")])
PW = "not a real hash"
AP.update(lambda d: d["people"].update({
    HUGO: dict(group="hod", depts=["Science"], username="hugo.ong", pw=PW),
    CORA: dict(group="committee", added=True, username="cora.lim", pw=PW, extras=dict(relief=False, exams=None, admin=True)),
    EXE: dict(group="executive", added=True),
    TEAM: dict(extras=dict(relief=True, exams=None, admin=False)),
    OFFIE: dict(off=True)}))
store.published = lambda: PUB                         # what is published, for every test below (no_pub() takes it away)
AGAIN = {"error": "Please sign in again."}
CODE_SHAPE = re.compile(r"^[%s]{4}-[%s]{4}$" % (access.ALPHABET, access.ALPHABET))
CONNECTED = dict(username="practice_bot", base="http://localhost", at="2026-11-22T08:00:00+08:00")
HOOK = "/telegram/hook"
_ids = itertools.count(700_000_000)

@contextlib.contextmanager
def telegram(token="practice", connected=True):
    """the bot on (in practice unless a made-up token is given) and connected, with nobody linked and nothing sent"""
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    wipe()
    if connected: bot_on("practice_bot" if token == "practice" else "ctss_made_up_bot")
    try: yield
    finally:
        wipe(); os.environ.pop("TELEGRAM_BOT_TOKEN", None)

def digest(text): return hashlib.sha256(text.encode()).hexdigest()

def bot_on(username="practice_bot"):
    """the bot connected, as Connect saves it under the token and the SECRET_KEY there are now"""
    tgdb.set_state("bot", dict(CONNECTED, username=username, key=digest(tg.hook_secret())))

def wipe():
    with tgdb.db() as c:
        for table in ("links", "codes", "talks", "updates", "outbox", "buttons"): c.execute(f"DELETE FROM {table}")
        c.execute("DELETE FROM state WHERE k='bot'")
    tg.PRACTICE_LOG.clear(); links.tries.fails.clear(); OB._doubt.clear(); OB._hold[0] = 0.0

@contextlib.contextmanager
def no_pub(pub=None):
    old = store.published; store.published = lambda: pub
    try: yield
    finally: store.published = old

@contextlib.contextmanager
def record(name, **changes):
    """name's account record changed for the block, then put back"""
    old = AP.load()["people"].get(name)
    AP.update(lambda d: d["people"].__setitem__(name, dict(AP.record(d, name), **changes)))
    def back(d):
        if old is None: d["people"].pop(name, None)
        else: d["people"][name] = old
    try: yield
    finally: AP.update(back)

@contextlib.contextmanager
def broken_accounts():
    """the accounts file there but not readable"""
    good = open(AP.PATH, encoding="utf-8").read()
    open(AP.PATH, "w", encoding="utf-8").write("{ not json")
    try: yield
    finally: open(AP.PATH, "w", encoding="utf-8").write(good)

def rows(table):
    with tgdb.db(read=True) as c: return [dict(r) for r in c.execute(f"SELECT * FROM {table}")]

def msg(text, chat=501, kind="private", user="tia_t", id=None, message_id=77, **more):
    m = dict(message_id=message_id, date=0, chat=dict(id=chat, type=kind), text=text, **more)
    m["from"] = dict(id=chat, is_bot=False, first_name="T", username=user)
    return dict(update_id=next(_ids) if id is None else id, message=m)

def hook(update, secret=True, raw=None, **kw):
    """one update posted to the hook as Telegram does (secret: True for the right one, None for no header, or a given one)"""
    headers = dict(kw.pop("headers", {}))
    if secret is True: secret = tg.hook_secret()
    if secret is not None: headers["X-Telegram-Bot-Api-Secret-Token"] = secret
    body = json.dumps(update).encode() if raw is None else raw
    return A.app.test_client().post(HOOK, data=body, content_type="application/json", headers=headers, **kw)

def sent(chat=None):
    """(chat, text) of every message sent in practice"""
    return [(p["chat_id"], p["text"]) for m, p in tg.PRACTICE_LOG if m == "sendMessage" and chat in (None, p["chat_id"])]

def deleted(): return [(p["chat_id"], p["message_id"]) for m, p in tg.PRACTICE_LOG if m == "deleteMessage"]

def who(name, via="code"):
    s = dict(who=name, via=via, n=0)
    if via == "password": s["exp"] = time.time() + 3600
    return client(s)

def client(keys):
    c = A.app.test_client()
    if keys:
        with c.session_transaction() as s: s.update(keys)
    return c

def entries(n=5000): return history.read(kinds=["relief"], limit=n)

HELLO = "Linked: {name}. You'll get your reliefs here. Send /relief to ask for relief, /stop to unlink."
NOT_LINKED = "This Telegram is not linked. Open Relief in the school's app, press Link Telegram and follow the link there."
BAD_CODE = "That code is not right or has run out. Get a new one in the app. If it was your personal code, do not send it here: it opens the app. I have deleted your message."
MOVED_LINK = "Your relief messages now go to another Telegram. If this was not you, tell the relief team."
TAKEN = "This Telegram was linked to someone else before. Their relief messages no longer come here."
STOPPED = "Unlinked. Your relief messages stop here. To link again, open Relief in the school's app and press Link Telegram."
BAD_CODE_KEPT = "That code is not right or has run out. Get a new one in the app. If it was your personal code, do not send it here: it opens the app. Please delete your message now."

@t
def the_bots_sentences_are_the_plans():
    assert (bot.HELLO, bot.NOT_LINKED, bot.BAD_CODE, bot.MOVED_LINK, bot.TAKEN, bot.STOPPED) == (HELLO, NOT_LINKED, BAD_CODE, MOVED_LINK, TAKEN, STOPPED)
    assert bot.BAD_CODE_KEPT == BAD_CODE_KEPT                                          # not in the plan's table
    plan = open(os.path.join(ROOT, "docs", "superpowers", "plans", "2026-11-22-relief-stage-4-telegram.md"), encoding="utf-8").read()
    for text in (HELLO, NOT_LINKED, BAD_CODE, MOVED_LINK, TAKEN, STOPPED): assert f"`{text}`" in plan, text

@t
def a_code_links_once_and_then_is_gone():
    with telegram():
        before = time.time()
        c = links.new_code(TIA)
        assert set(c) == {"code", "until"} and CODE_SHAPE.match(c["code"]) and links.CODE_MINUTES == 15, set(c)
        assert 899 <= c["until"] - before <= 901, c["until"] - before
        got = rows("codes")
        assert got == [dict(hash=hashlib.sha256(access.norm(c["code"]).encode()).hexdigest(), name=TIA, until=c["until"], chat=None)], "only a hash is kept"
        assert c["code"] not in str(got) and access.norm(c["code"]) not in str(got)
        assert links.use("ZZZZ-9999", 501, "tia_t") is None and links.use("", 501, None) is None and links.use(None, 501, None) is None
        assert links.chat_of(TIA) is None
        assert links.use(" " + c["code"].lower().replace("-", " ") + " ", 501, "tia_t") == TIA      # any case, spaces, dashes
        assert links.chat_of(TIA) == 501 and links.name_of(501) == TIA and rows("codes") == [dict(got[0], chat=501)], "kept, with the chat that used it"
        assert links.use(c["code"], 502, "x") is None and links.name_of(502) is None and links.use(c["code"], 501, "x") is None, "one use"
        assert links.linked()[TIA]["handle"] == "tia_t" and rows("codes") == [dict(got[0], chat=501)]
        # expired
        c = links.new_code(HUGO); real = links._clock
        links._clock = lambda: c["until"] + 1
        try:
            assert links.use(c["code"], 503, "h") is None and links.chat_of(HUGO) is None
            links.new_code(ROSA)
            assert [r["name"] for r in rows("codes")] == [ROSA], "codes that have run out are cleared away"
        finally: links._clock = real
        # a new code replaces that person's earlier one, and nobody else's
        a, b, other = links.new_code(HUGO), None, links.new_code(ROSA)
        b = links.new_code(HUGO)
        assert links.use(a["code"], 503, "h") is None and links.chat_of(HUGO) is None
        assert links.use(b["code"], 503, "h") == HUGO and links.use(other["code"], 504, "r") == ROSA

@t
def pressing_the_same_link_twice_says_the_same():
    with telegram():
        def bad(text, chat):
            """BAD_CODE, the message deleted, one try counted, and nothing linked or unlinked"""
            links.tries.fails.clear(); tg.PRACTICE_LOG.clear(); was, n = rows("links"), len(entries())
            hook(msg(text, chat, message_id=9))
            return (sent(), deleted(), len(links.tries.fails[f"tg:{chat}"]), rows("links") == was, len(entries()) - n) == ([(chat, BAD_CODE)], [(chat, 9)], 1, True, 0)
        c = links.new_code(TIA)["code"]
        hook(msg(f"/start {c}", 501, user="tia_t"))
        was, kept_codes, n = rows("links"), rows("codes"), len(entries()); tg.PRACTICE_LOG.clear()
        for text in (f"/start {c}", c, c.lower(), f"/start {c}") * 2: hook(msg(text, 501, user="another_name"))
        assert sent() == [(501, HELLO.format(name=TIA))] * 8 and deleted() == [], sent()
        assert rows("links") == was and rows("codes") == kept_codes and len(entries()) == n and not links.tries.fails.get("tg:501"), "nothing changed, nothing counted"
        assert links.again(c, 501) == TIA and links.again(c, 502) is None and links.again("ABCD-EFGH", 501) is None and links.again("x", 501) is None
        assert bad(c, 502) and links.chat_of(TIA) == 501, "another chat"                           # somebody who saw the code
        hook(msg("/stop", 501)); assert bad(f"/start {c}", 501) and links.linked() == {}, "after /stop the same chat needs a new code"
        c = links.new_code(TIA)["code"]; hook(msg(c, 501)); links.unlink(TIA); assert bad(c, 501), "after the settings page unlinked them"
        c = links.new_code(TIA)["code"]; hook(msg(c, 501)); hook(msg(links.new_code(HUGO)["code"], 501))
        assert links.name_of(501) == HUGO and bad(c, 501) and links.name_of(501) == HUGO, "after the chat became Hugo's"
        # a new code removes the earlier ones, used ones too
        c = links.new_code(ROSA)["code"]; hook(msg(c, 503)); assert links.again(c, 503) == ROSA
        d = links.new_code(ROSA)["code"]
        assert [(r["chat"], r["until"] > 0) for r in rows("codes") if r["name"] == ROSA] == [(None, True)] and bad(c, 503) and links.chat_of(ROSA) == 503
        links.tries.fails.clear(); hook(msg(d, 504)); assert links.chat_of(ROSA) == 504 and bad(d, 503), "moved: the old chat's press is refused"
        # run out, switched off, over the limit
        c = links.new_code(TIA); hook(msg(c["code"], 505)); real = links._clock
        links._clock = lambda: c["until"] + 1
        try: assert links.again(c["code"], 505) is None and bad(c["code"], 505) and links.chat_of(TIA) == 505
        finally: links._clock = real
        assert links.again(c["code"], 505) == TIA
        with record(TIA, off=True): assert links.again(c["code"], 505) is None and bad(c["code"], 505)
        with broken_accounts(): assert links.again(c["code"], 505) is None
        links.tries.fails.clear()
        for _ in range(5): hook(msg("ABCD-EFGH", 505))
        tg.PRACTICE_LOG.clear(); hook(msg(c["code"], 505)); assert tg.PRACTICE_LOG == [], "over the limit: nothing"
        # at once: every press is answered, one link, one history entry
        links.tries.fails.clear(); c = links.new_code(HUGO)["code"]; n = len(entries()); tg.PRACTICE_LOG.clear()
        ts = [threading.Thread(target=hook, args=(msg(f"/start {c}", 506),)) for _ in range(4)]
        [x.start() for x in ts]; [x.join() for x in ts]
        assert sent(506) == [(506, HELLO.format(name=HUGO))] * 4 and len(entries()) == n + 1 and links.chat_of(HUGO) == 506, (sent(506), len(entries()) - n)

@t
def one_code_used_twice_at_once_links_one_chat():
    with telegram():
        for _ in range(5):
            c, got = links.new_code(TIA), []
            ts = [threading.Thread(target=lambda chat=chat: got.append(links.use(c["code"], chat, None))) for chat in (601, 602, 603, 604)]
            [x.start() for x in ts]; [x.join() for x in ts]
            assert sorted(got, key=str) == sorted([TIA, None, None, None], key=str), got
            assert len(rows("links")) == 1

@t
def linking_again_moves_it_and_tells_the_old_chat():
    with telegram():
        c = links.new_code(TIA)
        assert hook(msg(f"/start {c['code']}", 501)).status_code == 200
        assert sent() == [(501, HELLO.format(name=TIA))], sent()
        p = [p for m, p in tg.PRACTICE_LOG if m == "sendMessage"][0]
        assert p["disable_web_page_preview"] is True
        c = links.new_code(TIA); tg.PRACTICE_LOG.clear()
        hook(msg(c["code"], 502, user=None))                                       # a bare code, from another phone
        assert sent() == [(501, MOVED_LINK), (502, HELLO.format(name=TIA))], sent()
        assert links.chat_of(TIA) == 502 and links.name_of(501) is None and links.linked()[TIA]["handle"] is None
        c = links.new_code(TIA); tg.PRACTICE_LOG.clear()
        hook(msg(c["code"], 502, user="tia_new"))                                  # the same phone again: nothing moved
        assert sent() == [(502, HELLO.format(name=TIA))], sent()
        assert links.linked()[TIA]["handle"] == "tia_new" and len(rows("links")) == 1
        assert links.link(TIA, 503, "x") == 502 and links.link(TIA, 503, "x") is None and links.link(ROSA, 504, None) is None
        assert deleted() == []

@t
def only_a_telegram_username_is_kept_as_the_handle():
    with telegram():
        for user, want in (("tia_t9", "tia_t9"), (None, None), ("", None), ("<b>x</b>", None), ("a b", None), ("x" * 65, None), (7, None), (["x"], None), ("Tïa", None)):
            hook(msg(links.new_code(TIA)["code"], 501, user=user))
            assert links.linked()[TIA]["handle"] == want, (user, links.linked())

@t
def a_chat_links_one_person_and_a_person_one_chat():
    with telegram():
        links.link(TIA, 501, "tia_t")
        with tgdb.db() as c: c.execute("INSERT INTO talks(chat, kind, data, until) VALUES (501, 'change', '{}', ?)", (time.time() + 600,))
        code = links.new_code(HUGO)["code"]
        hook(msg(code, 501))
        assert links.name_of(501) == HUGO and links.chat_of(TIA) is None and links.linked().keys() == {HUGO}, rows("links")
        assert sent() == [(501, TAKEN), (501, HELLO.format(name=HUGO))], "what Tia got here comes no longer; nothing of hers went to another Telegram"
        assert TIA not in str(sent()), "who it was is not said"
        assert rows("talks") == [], "a conversation Tia began is not Hugo's to finish"
        # both at once: Rosa is on 502, Hugo moves from 501 to 502
        links.link(ROSA, 502, None); tg.PRACTICE_LOG.clear()
        hook(msg(links.new_code(HUGO)["code"], 502))
        assert links.linked().keys() == {HUGO} and links.chat_of(HUGO) == 502 and links.name_of(501) is None
        assert sorted(sent()[:2]) == sorted([(501, MOVED_LINK), (502, TAKEN)]) and sent()[2:] == [(502, HELLO.format(name=HUGO))], sent()
        assert len({r["chat"] for r in rows("links")}) == len(rows("links"))

@t
def unlinking_forgets_the_chat():
    with telegram():
        links.link(TIA, 501, "tia_t"); links.link(ROSA, 502, None)
        with tgdb.db() as c: c.executemany("INSERT INTO talks(chat, kind, data, until) VALUES (?, 'x', '{}', 9e9)", [(501,), (502,)])
        assert links.unlink(TIA) == 501 and links.unlink(TIA) is None and links.chat_of(TIA) is None
        assert [r["chat"] for r in rows("talks")] == [502]
        assert links.unlink_chat(502) == ROSA and links.unlink_chat(502) is None and rows("talks") == []
        links.link(TIA, 501, None)
        hook(msg("/stop", 501))
        assert links.linked() == {} and sent() == [(501, STOPPED)], sent()
        tg.PRACTICE_LOG.clear(); hook(msg("/stop", 501)); assert sent() == [(501, NOT_LINKED)], sent()

@t
def a_linked_chat_is_answered_with_who_it_is():
    with telegram():
        links.link(TIA, 501, None)
        for text in ("/start", "/help", "/help@practice_bot", "/HELP", "hello there", "/start something long that is not a code"):
            tg.PRACTICE_LOG.clear(); hook(msg(text, 501)); assert sent() == [(501, HELLO.format(name=TIA))], (text, sent())
        assert not links.tries.fails.get("tg:501") and links.name_of(501) == TIA

@t
def an_off_or_gone_person_is_not_reachable():
    with telegram():
        for name, chat in ((TIA, 501), (OFFIE, 502), (GONE_, 503), (HUGO, 504)): links.link(name, chat, None)
        assert links.chat_of(TIA) == 501 and links.chat_of(HUGO) == 504
        assert links.chat_of(OFFIE) is None and links.name_of(502) is None and links.person(502) is None and links.rights_of(502) == frozenset()
        assert links.chat_of(GONE_) is None and links.name_of(503) is None and links.person(503) is None and links.rights_of(503) == frozenset()
        assert links.reachable() == {TIA: 501, HUGO: 504} == links.reachable(PUB), links.reachable()
        assert set(links.linked()) == {TIA, OFFIE, GONE_, HUGO}, "the links are still there for the settings page"
        with record(TIA, off=True):                                                     # switched off now: at once
            assert links.chat_of(TIA) is None and links.reachable() == {HUGO: 504}
            tg.PRACTICE_LOG.clear(); hook(msg("/help", 501)); assert sent() == [(501, NOT_LINKED)], sent()
        assert links.chat_of(TIA) == 501
        with record(TIA, n=99): assert links.chat_of(TIA) == 501, "a link is never tied to the sign-in number"
        with no_pub():                                                                   # nothing published (a publish swaps folders)
            assert links.chat_of(TIA) == 501 and links.name_of(503) == GONE_ and links.chat_of(OFFIE) is None
            assert links.reachable() == {TIA: 501, HUGO: 504, GONE_: 503}, links.reachable()
            assert links.reachable(PUB) == {TIA: 501, HUGO: 504}
        with broken_accounts():                                                          # unreadable: nobody can be reached
            assert links.chat_of(TIA) is None and links.name_of(501) is None and links.reachable() == {} and links.rights_of(501) == frozenset()
            assert links.person(501) is None
            c = links.new_code(ROSA); assert links.use(c["code"], 505, None) is None and links.chat_of(ROSA) is None
        # a code made by someone since switched off links nobody, and takes nobody's chat
        c = links.new_code(ROSA)
        with record(ROSA, off=True): assert links.use(c["code"], 501, None) is None and links.name_of(501) == TIA
        assert links.use(links.new_code(OFFIE)["code"], 501, None) is None and links.use(links.new_code(GONE_)["code"], 501, None) is None
        # /stop from a switched-off person's chat still takes the link away, and says only that it is not linked
        tg.PRACTICE_LOG.clear(); hook(msg("/stop", 502))
        assert OFFIE not in links.linked() and sent() == [(502, NOT_LINKED)], sent()

@t
def reachable_reads_the_accounts_once():
    with telegram():
        for i, name in enumerate((TIA, HUGO, TEAM, ROSA)): links.link(name, 900 + i, None)
        n, real = [], store.read_json
        store.read_json = lambda path, default=None: (n.append(path), real(path, default))[1]
        try: assert len(links.reachable()) == 4
        finally: store.read_json = real
        assert n.count(AP.PATH) == 1, n

@t
def rights_from_telegram_are_the_codes_rights():
    with telegram():
        for i, name in enumerate((TIA, HUGO, CORA, TEAM, EXE)): links.link(name, 500 + i, None)
        for i, name in enumerate((TIA, HUGO, CORA, TEAM, EXE)):
            p = links.person(500 + i)
            assert p["name"] == name and "pw" not in p, "no password hash leaves the accounts"
            assert links.rights_of(500 + i) == AR.rights(p, "code") == AR.rights(p, "telegram"), name
        assert "relief.plan" in links.rights_of(501) and "setup" not in links.rights_of(501)                   # HOD
        cora = links.rights_of(502)
        assert "relief.save" in cora and not cora & {"admin", "committee", "setup", "history", "codes"}, cora    # an admin by password
        assert "admin" in AR.rights(links.person(502), "password")
        assert "relief.team" in links.rights_of(503) and "relief" not in links.rights_of(504)
        assert links.rights_of(999) == frozenset() and links.person(999) is None and links.name_of(999) is None
        with record(TEAM, extras=dict(relief=False, exams=None, admin=False)): assert "relief.team" not in links.rights_of(503)
        with no_pub():                                                # the stand-in is app.py's (a code session's person while nothing is published)
            got, want = links.person(500), A._stand_in(TIA, AP.load())
            assert got == want, (got, want)
            assert links.rights_of(500) == AR.rights(want, "code")

class Counted:
    """a body of 5 MB that comes in pieces, as a socket gives it, and counts what is read of it"""
    def __init__(self): self.left, self.taken = 5_000_000, 0
    def read(self, k=-1):
        k = self.left if k is None or k < 0 else min(k, self.left, 1000)
        self.left -= k; self.taken += k
        return b"x" * k

def stream(length, secret):
    """(the status, the bytes read) of a 5 MB body that says it is length bytes long (None: chunked)"""
    s = Counted()
    env = {"wsgi.input": s, "CONTENT_LENGTH": length} if length else {"wsgi.input": s, "HTTP_TRANSFER_ENCODING": "chunked", "wsgi.input_terminated": True}
    r = A.app.test_client().post(HOOK, environ_overrides=env, headers={"X-Telegram-Bot-Api-Secret-Token": secret})
    return r.status_code, s.taken

@t
def the_hook_needs_the_secret():
    real = os.environ["SECRET_KEY"]
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    assert hook(msg("hi"), secret="x").status_code == 404                       # no token
    with telegram(connected=False): assert hook(msg("hi")).status_code == 404    # no bot connected
    with telegram():
        links.link(TIA, 501, None)
        for wrong in (None, "", "x", tg.hook_secret()[:-1], tg.hook_secret().upper() + "x", tg.hook_secret() + "0", "é" * 64, "\xff\xfe"):
            r = hook(msg("/stop", 501), secret=wrong)
            assert r.status_code == 403 and tg.hook_secret() not in r.get_data(as_text=True), (wrong, r.status_code)
        for name in ("token", "secret", "secret_token"):                          # the header alone counts, never the address
            assert A.app.test_client().post(f"{HOOK}?{name}={tg.hook_secret()}", json=msg("/stop", 501)).status_code == 403
        assert links.chat_of(TIA) == 501 and rows("updates") == [] and tg.PRACTICE_LOG == [], "a refused update is not even remembered"
        os.environ.pop("SECRET_KEY")
        try:
            assert tg.hook_secret() == "" and links.connected() is None
            for s in (None, "", "x"): assert hook(msg("/stop", 501), secret=s).status_code == 404
            for headers in ({}, {"X-Telegram-Bot-Api-Secret-Token": ""}, {"X-Telegram-Bot-Api-Secret-Token": "x"}):        # and no header is ever right then
                with A.app.test_request_context(HOOK, method="POST", headers=headers): assert tgweb._right_secret() is False, headers
        finally: os.environ["SECRET_KEY"] = real
        # too big: refused, read no more than one byte past the limit, whatever the length says
        big = tgweb.LIMIT + 1
        assert tgweb.LIMIT == 256 * 1024
        assert hook(None, raw=b"x" * big).status_code == 413 and hook(None, raw=b" " * tgweb.LIMIT).status_code == 200
        assert stream(None, tg.hook_secret()) == (413, big), stream(None, tg.hook_secret())
        assert stream(str(big), tg.hook_secret()) == (413, 0) == stream(str(50 * 1024 * 1024), tg.hook_secret())
        assert stream("10", tg.hook_secret()) == (200, 10)
        for length in (None, "1000", str(tgweb.LIMIT)): assert stream(length, "x") == (403, 0), "a wrong secret: nothing of the body is read"
        # not an update: 200, so that Telegram does not send it again, and nothing done
        for raw in (b"", b"not json", b"[]", b"3", b"null", b'"x"', b"\xff\xfe\x00", b"[" * 200_000, b"{}", b'{"update_id": "7"}', b'{"update_id": true}',
                    b'{"update_id": 1.5}', b'{"update_id": 99999999999999999999999}', b'{"message": {"chat": {"id": 501, "type": "private"}, "text": "/stop"}}'):
            assert hook(None, raw=raw).status_code == 200, raw[:60]
        assert rows("updates") == [] and tg.PRACTICE_LOG == [] and links.chat_of(TIA) == 501
        for method in ("GET", "PUT", "DELETE"):
            assert A.app.test_client().open(HOOK, method=method, headers={"X-Telegram-Bot-Api-Secret-Token": tg.hook_secret()}).status_code == 405
        assert hook(msg("/stop", 501), headers={"Origin": "https://elsewhere.example"}).status_code == 403 and links.chat_of(TIA) == 501
        assert hook(msg("/stop", 501)).status_code == 200 and links.linked() == {}                                        # the right one
    with telegram(token="made-up-" + secrets.token_hex(6)):                          # practice's bot is no bot under a real token
        assert links.connected()["username"] == "ctss_made_up_bot"
        bot_on("practice_bot"); assert links.connected() is None and hook(msg("hi")).status_code == 404
    assert REAL == []

@t
def the_same_update_acts_once():
    with telegram():
        u = msg("/help", 501)
        for _ in range(3): assert hook(u).status_code == 200
        assert sent() == [(501, NOT_LINKED)] and len(links.tries.fails["tg:501"]) == 1, sent()
        c = links.new_code(TIA)["code"]; u = msg(c, 502)
        codes = []
        ts = [threading.Thread(target=lambda: codes.append(hook(u).status_code)) for _ in range(4)]
        [x.start() for x in ts]; [x.join() for x in ts]
        assert codes == [200] * 4 and sent(502) == [(502, HELLO.format(name=TIA))] and deleted() == [], (codes, sent(502))
        hook(msg("/stop", 502, id=u["update_id"]))                                   # another text under an update already acted on
        assert links.chat_of(TIA) == 502

@t
def a_store_that_fails_lets_telegram_try_again():
    with telegram():
        real = tgdb.first_time
        def boom(i): raise RuntimeError("the store is busy")
        tgdb.first_time = boom
        A.app.config["PROPAGATE_EXCEPTIONS"] = False
        try: r = hook(msg("/help", 501))
        finally: tgdb.first_time = real; A.app.config["PROPAGATE_EXCEPTIONS"] = None
        assert r.status_code == 503 and "busy" not in r.get_data(as_text=True) and sent() == [], r.status_code

@t
def handle_never_raises():
    with telegram():
        odd = [None, 3, [], "x", {}, dict(message=None), dict(message=[]), dict(message={}), dict(message=dict(chat=None)), dict(message=dict(chat=dict(type="private"))),
               dict(message=dict(chat=dict(id="501", type="private"), text="/help")), dict(message=dict(chat=dict(id=True, type="private"), text="/help")),
               dict(message=dict(chat=dict(id=None, type="private"), text="/help")), dict(message=dict(chat=dict(id=10 ** 30, type="private"), text="ABCD-EFGH")),
               dict(message=dict(chat=dict(id=-501, type="private"), text="/help")), dict(message=dict(chat=dict(id=0, type="private"), text="/help")),
               dict(callback_query=dict(id="1", data="x", message=dict(chat=dict(id=501, type="private")))), dict(callback_query=None)]
        for u in odd: assert bot.handle(u) is None, u
        assert sent() == [] and rows("links") == []
        for text in (None, 7, ["x"], "", "   ", "\x00", "/", "//", "@", "/start", "/start\n", "/start  x", "a" * 5000):       # no text (a photo, a sticker) or odd text
            links.tries.fails.clear(); tg.PRACTICE_LOG.clear()
            bot.handle(dict(message=dict(chat=dict(id=501, type="private"), text=text)))
            assert sent() == [(501, NOT_LINKED)], (text, sent())
        real = tg.call; tg.call = lambda *a, **k: 1 / 0
        try: assert bot.handle(msg("/help", 501)) is None
        finally: tg.call = real

@t
def only_private_chats_are_answered():
    with telegram():
        code, staff = links.new_code(TIA)["code"], access.staff_code(TIA)
        for kind in ("group", "supergroup", "channel", "sender", None, "Private", ["private"]):
            for text in ("/start", "/help", "/stop", "hello", code, f"/start {code}", staff):
                assert hook(msg(text, -100777, kind=kind)).status_code == 200
                assert hook(msg(text, 501, kind=kind)).status_code == 200
        u = msg("/help", 501); hook(dict(update_id=next(_ids), edited_message=u["message"]))
        hook(dict(update_id=next(_ids), channel_post=u["message"])); hook(dict(update_id=next(_ids), business_message=u["message"]))
        b = msg(code, 501); b["message"]["from"]["is_bot"] = True; hook(b)
        assert tg.PRACTICE_LOG == [] and rows("links") == [] and not any(links.tries.fails.values()), tg.PRACTICE_LOG
        assert links.use(code, 501, None) == TIA, "a code shown in a group is not used there"

@t
def a_stranger_gets_five_replies():
    with telegram():
        for i in range(8): hook(msg(f"hello {i}", 666))
        assert sent() == [(666, NOT_LINKED)] * 5, sent()
        hook(msg("hello", 667)); assert sent(667) == [(667, NOT_LINKED)], "another chat is not held back"
        # over the limit: no answer, no deleteMessage, and a code is not even tried
        tg.PRACTICE_LOG.clear()
        code = links.new_code(TIA)["code"]
        for text in (code, f"/start {code}", "ABCD-EFGH", "/stop", "/help", "/start"): hook(msg(text, 666))
        assert tg.PRACTICE_LOG == [] and links.linked() == {} and len(rows("codes")) == 1 and len(links.tries.fails["tg:666"]) == 5
        # ten minutes later
        links.tries.fails["tg:666"] = collections.deque(x - 601 for x in links.tries.fails["tg:666"])
        hook(msg(code, 666)); assert links.chat_of(TIA) == 666 and sent() == [(666, HELLO.format(name=TIA))], sent()
        # wrong codes and other messages count together
        wipe(); bot_on()
        for text in ("hello", "ABCD-EFGH", "/start ABCD-EFGJ", "/stop", "WXYZ 2345", "ABCD-EFGH", "hello"): hook(msg(text, 668))
        assert [x for _, x in sent()] == [NOT_LINKED, BAD_CODE, BAD_CODE, NOT_LINKED, BAD_CODE] and len(deleted()) == 3, sent()
        # all at once: still five
        wipe(); bot_on()
        ts = [threading.Thread(target=hook, args=(msg("ABCD-EFGH" if i % 2 else "hello", 669),)) for i in range(16)]
        [x.start() for x in ts]; [x.join() for x in ts]
        assert len(sent()) == 5 and len(links.tries.fails["tg:669"]) == 5, (len(sent()), len(links.tries.fails["tg:669"]))
        # a linked person who guesses codes is held back too, and a right code does not count
        wipe(); bot_on()
        hook(msg(links.new_code(TIA)["code"], 670)); assert not links.tries.fails.get("tg:670")
        for _ in range(7): hook(msg("ABCD-EFGH", 670))
        assert len(sent(670)) == 6 and len(deleted()) == 5, sent(670)
        tg.PRACTICE_LOG.clear(); hook(msg(links.new_code(HUGO)["code"], 670)); hook(msg("/stop", 670))
        assert tg.PRACTICE_LOG == [] and links.name_of(670) == TIA

@t
def a_code_that_is_not_a_link_code_is_deleted():
    with telegram():
        assert access.personal_codes_on()
        student = access.personal_code("S001")
        shapes = [access.staff_code(TIA), access.staff_code(HUGO), student, "ABCD-EFGH", "abcd efgh", access.norm(access.staff_code(TIA)).lower()]
        for i, text in enumerate(shapes + [f"/start {access.staff_code(TIA)}", "/start ABCDEFGH", "/START@practice_bot abcd-efgh"]):
            links.tries.fails.clear(); tg.PRACTICE_LOG.clear()
            hook(msg(text, 501, message_id=1000 + i))
            assert [m for m, p in tg.PRACTICE_LOG] == ["deleteMessage", "sendMessage"], (text[:7], [m for m, p in tg.PRACTICE_LOG])
            assert deleted() == [(501, 1000 + i)] and sent() == [(501, BAD_CODE)], "a real code and a made-up one read the same"
            assert len(links.tries.fails["tg:501"]) == 1
        assert links.linked() == {} and links.name_of(501) is None
        # the real codes are never worked out, so nothing can tell them apart
        real = access.staff_code, access.personal_code, access.match
        def never_(*a, **k): raise AssertionError("a personal code was compared")
        access.staff_code = access.personal_code = access.match = never_
        try:
            links.tries.fails.clear(); tg.PRACTICE_LOG.clear(); hook(msg(shapes[0], 501)); assert sent() == [(501, BAD_CODE)]
        finally: access.staff_code, access.personal_code, access.match = real
        # not shaped like a code: left alone
        for text in ("ABCD-EFG", "ABCD-EFGHJ", "ABCD-EFG0", "ABCD-EFGI", "my code is " + shapes[0]):
            links.tries.fails.clear(); tg.PRACTICE_LOG.clear(); hook(msg(text, 501)); assert sent() == [(501, NOT_LINKED)] and deleted() == [], text
        # a message with no id that can be deleted is still answered
        links.tries.fails.clear(); tg.PRACTICE_LOG.clear(); hook(msg("ABCD-EFGH", 501, message_id="x")); assert sent() == [(501, BAD_CODE_KEPT)] and deleted() == []
        # a linked chat too, and the link stays
        links.tries.fails.clear(); links.link(TIA, 501, None); tg.PRACTICE_LOG.clear()
        hook(msg(access.staff_code(TIA), 501)); assert sent() == [(501, BAD_CODE)] and len(deleted()) == 1 and links.name_of(501) == TIA

def fake_bot(answers):
    """a _send that answers each Bot API method from answers (status, body) and keeps what was sent"""
    seen = []
    def f(url, data, headers, timeout):
        method = url.rsplit("/", 1)[1]; seen.append((method, json.loads(data)))
        got = answers.get(method, (200, dict(ok=True, result=True)))
        if isinstance(got, Exception): raise got
        return got[0], json.dumps(got[1]).encode()
    return f, seen

ME_OK = (200, dict(ok=True, result=dict(id=1, is_bot=True, username="ctss_made_up_bot", first_name="CTSS")))

@t
def a_message_that_could_not_be_deleted_is_never_said_to_be():
    with telegram(token="made-up-" + secrets.token_hex(10)):
        links.link(HUGO, 502, None)
        bad = dict(ok=False, description="made up reason")
        for failed in ((400, bad), (403, bad), (429, bad), (502, bad), (200, bad), TimeoutError(), ConnectionResetError()):
            for text, chat in (("ABCD-EFGH", 501), ("/start abcd efgh", 501), (access.staff_code(TIA), 501), (access.staff_code(HUGO), 502)):
                links.tries.fails.clear(); f, seen = fake_bot(dict(deleteMessage=failed))
                with_send(f, lambda: hook(msg(text, chat, message_id=31)))
                assert [m for m, d in seen] == ["deleteMessage", "sendMessage"] and seen[0][1] == dict(chat_id=chat, message_id=31), seen
                assert seen[1][1]["text"] == BAD_CODE_KEPT and seen[1][1]["chat_id"] == chat, (failed, seen[1])
                assert len(links.tries.fails[f"tg:{chat}"]) == 1 and set(links.linked()) == {HUGO}
        links.tries.fails.clear(); f, seen = fake_bot({})                                # deleted: said so
        with_send(f, lambda: hook(msg("ABCD-EFGH", 501, message_id=31))); assert seen[1][1]["text"] == BAD_CODE, seen
        links.tries.fails.clear(); f, seen = fake_bot(dict(deleteMessage=(400, bad)))     # five all told, then nothing
        for _ in range(8): with_send(f, lambda: hook(msg("ABCD-EFGH", 501)))
        assert [m for m, d in seen] == ["deleteMessage", "sendMessage"] * 5, seen
    assert REAL == []

@t
def a_code_needs_relief_when_it_is_used():
    with telegram():
        c = links.new_code(TIA)["code"]
        with record(TIA, group="executive"):                                              # no relief now
            assert "relief" not in AR.rights(AP.find(TIA, PUB), "telegram") and links.use(c, 501, None) is None and links.linked() == {}
            links.link(HUGO, 502, None); tg.PRACTICE_LOG.clear(); hook(msg(f"/start {c}", 502, message_id=8))
            assert sent() == [(502, BAD_CODE)] and deleted() == [(502, 8)] and len(links.tries.fails["tg:502"]) == 1 and links.name_of(502) == HUGO, "nobody is put off the chat"
            assert rows("codes")[0]["chat"] is None, "the code is not used up by it"
        assert links.use(c, 501, None) == TIA                                             # a teacher again: the code is still good
        c = links.new_code(EXE)["code"]; assert links.use(c, 503, None) is None
        with record(EXE, extras=dict(relief=True, exams=None, admin=False)): assert links.use(c, 503, None) == EXE, "an executive on the relief team links"
        with record(EXE, extras=dict(relief=True, exams=None, admin=False), off=True): assert links.use(links.new_code(EXE)["code"], 504, None) is None

@t
def the_code_route_needs_a_person_and_a_connection():
    API = "/api/relief/telegram"
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    tia = who(TIA)
    off = dict(on=False, connected=False, bot=None, linked=False, handle=None, since=None)
    assert tia.get(API).get_json() == off and tia.get(API).status_code == 200
    assert (tia.post(API + "/code").status_code, tia.post(API + "/code").get_json()) == (409, {"error": "Telegram is not connected yet."})
    with telegram(connected=False):
        assert tia.get(API).get_json() == dict(off, on=True) and tia.post(API + "/code").status_code == 409
    with telegram():
        for c in (client({}), client(dict(role="committee")), client(dict(role="teacher")), client(dict(role="student")), client(dict(role="head")),
                  client(dict(role="personal", sid="S001")), who(EXE), who(OFFIE), who(GONE_)):
            for method, url in (("GET", API), ("POST", API + "/code"), ("DELETE", API + "/link")):
                r = c.open(url, method=method); assert r.status_code == 401 and r.get_json() == AGAIN, (method, url, r.status_code)
        assert rows("codes") == []
        r = tia.post(API + "/code"); j = r.get_json()
        assert r.status_code == 200 and set(j) == {"code", "url", "until"} and CODE_SHAPE.match(j["code"]), j
        assert j["url"] == f"https://t.me/practice_bot?start={j['code']}" and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", j["code"])
        assert [r["name"] for r in rows("codes")] == [TIA]
        assert hook(msg(f"/start {j['code']}", 501, user="tia_t")).status_code == 200
        j = tia.get(API).get_json()
        assert (j["on"], j["connected"], j["bot"], j["linked"], j["handle"]) == (True, True, "practice_bot", True, "tia_t") and j["since"][:4] >= "2026", j
        assert set(j) == {"on", "connected", "bot", "linked", "handle", "since"} and "501" not in json.dumps(j)
        assert who(HUGO).get(API).get_json()["linked"] is False, "each person sees their own link only"
        r = tia.delete(API + "/link"); assert r.status_code == 200 and r.get_json()["linked"] is False and links.linked() == {}
        assert tia.delete(API + "/link").status_code == 200                             # nothing to take away: the same answer
        links.link(TIA, 501, None)
        with record(TIA, off=True): assert who(TIA).get(API).status_code == 401

@t
def connect_saves_the_bot_and_points_the_hook_here():
    API = "/api/relief/telegram/"
    com = client(dict(role="committee"))
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    r = com.post(API + "connect"); assert r.status_code == 409 and "TELEGRAM_BOT_TOKEN" in r.get_json()["error"], r.get_json()
    with telegram(connected=False):                                                      # practice: http is fine, nothing leaves
        for c in (client({}), who(TIA), who(HUGO), who(EXE), client(dict(role="teacher")), client(dict(role="head")), client(dict(role="student"))):
            for url in ("connect", "disconnect", "unlink"):
                r = c.post(API + url, json={}); assert r.status_code == 401 and r.get_json() == AGAIN, (url, r.status_code)
            assert c.get(API + "admin").status_code == 401
        assert tg.PRACTICE_LOG == [] and tgdb.get_state("bot") is None
        r = com.post(API + "connect"); j = r.get_json()
        assert r.status_code == 200 and j["connected"] is True and j["bot"] == "practice_bot" and j["base"] == "http://localhost", j
        b = tgdb.get_state("bot"); assert set(b) == {"username", "base", "at", "key"} and (b["username"], b["base"]) == ("practice_bot", "http://localhost"), b
        assert b["key"] == digest(tg.hook_secret()) and tg.hook_secret() not in json.dumps(b) and b["key"] not in r.get_data(as_text=True), "a digest alone is kept"
        assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+", b["at"]) and links.connected() == {k: b[k] for k in ("username", "base", "at")}
        assert [m for m, p in tg.PRACTICE_LOG] == ["getMe", "setWebhook", "setMyCommands"], tg.PRACTICE_LOG
        assert tg.PRACTICE_LOG[1][1] == dict(url="http://localhost/telegram/hook", secret_token=tg.hook_secret(), allowed_updates=["message", "callback_query"],
                                             max_connections=4, drop_pending_updates=True)
        assert [x["command"] for x in tg.PRACTICE_LOG[2][1]["commands"]] == ["relief", "stop", "help"] and all(x["description"] for x in tg.PRACTICE_LOG[2][1]["commands"])
        assert tg.hook_secret() not in json.dumps(j) and hook(msg("/help", 501)).status_code == 200
        tg.PRACTICE_LOG.clear()
        r = com.post(API + "disconnect"); assert r.status_code == 200 and r.get_json()["connected"] is False, r.get_json()
        assert [m for m, p in tg.PRACTICE_LOG] == ["deleteWebhook"] and tgdb.get_state("bot") is None and hook(msg("/help", 501)).status_code == 404
        assert who(TEAM).post(API + "connect").status_code == 200, "the relief team saves the relief settings"
    tok, https = "made-up-" + secrets.token_hex(10), {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "ctss.example"}
    def connect(answers, headers=https):
        f, seen = fake_bot(answers)
        r = with_send(f, lambda: com.post(API + "connect", headers=headers))
        body = r.get_data(as_text=True)
        for bad in (tok, "made up reason", tg.hook_secret() or tok): assert bad not in body, "nothing Telegram said, no token, no secret"
        return r, seen
    with telegram(token=tok, connected=False):
        r, seen = connect(dict(getMe=ME_OK), headers={})                                  # http: refused before anything is sent
        assert r.status_code == 409 and "https" in r.get_json()["error"] and seen == [] and tgdb.get_state("bot") is None, r.get_json()
        real = os.environ.pop("SECRET_KEY")
        try: r, seen = connect(dict(getMe=ME_OK))
        finally: os.environ["SECRET_KEY"] = real
        assert r.status_code == 409 and "SECRET_KEY" in r.get_json()["error"] and seen == [] and tgdb.get_state("bot") is None, (r.status_code, r.get_json())
        bad = dict(ok=False, description=f"made up reason {tok}")
        for answers in (dict(getMe=(401, bad)), dict(getMe=TimeoutError(tok)), dict(getMe=(200, dict(ok=True, result=True))), dict(getMe=(200, dict(ok=True, result=dict()))),
                        dict(getMe=(200, dict(ok=True, result=dict(username="x?start=1&y")))), dict(getMe=ME_OK, setWebhook=(400, bad)),
                        dict(getMe=ME_OK, setWebhook=TimeoutError(tok)), dict(getMe=ME_OK, setWebhook=(429, bad))):
            r, seen = connect(answers)
            assert r.status_code == 502 and r.get_json()["error"] and tgdb.get_state("bot") is None, (answers, r.status_code, r.get_json())
            assert hook(msg("/help", 501)).status_code == 404
        r, seen = connect(dict(getMe=ME_OK, setMyCommands=(400, bad)))                    # the menu failing does not fail connect
        assert r.status_code == 200 and [m for m, p in seen] == ["getMe", "setWebhook", "setMyCommands"], (r.status_code, seen)
        assert seen[1][1]["url"] == "https://ctss.example/telegram/hook" and seen[1][1]["secret_token"] == tg.hook_secret()
        b = tgdb.get_state("bot"); assert (b["username"], b["base"]) == ("ctss_made_up_bot", "https://ctss.example"), b
        r, seen = connect(dict(getMe=ME_OK, setWebhook=(502, bad)))                       # connecting again fails: the earlier one stays
        assert r.status_code == 502 and tgdb.get_state("bot") == b
        f, seen = fake_bot(dict(deleteWebhook=(502, bad)))
        r = with_send(f, lambda: com.post(API + "disconnect"))                            # Telegram does not answer: off here all the same, and said so
        assert r.status_code == 502 and tok not in r.get_data(as_text=True) and tgdb.get_state("bot") is None and [m for m, p in seen] == ["deleteWebhook"]
    tgdb.set_state("bot", CONNECTED)                                                       # the token taken out of Railway: Disconnect still clears it
    r = com.post(API + "disconnect"); assert r.status_code == 200 and tgdb.get_state("bot") is None and r.get_json()["token_set"] is False
    assert REAL == []

@t
def a_changed_token_or_key_is_not_connected():
    com, tia, API = client(dict(role="committee")), who(TIA), "/api/relief/telegram"
    def connect():
        f, seen = fake_bot(dict(getMe=ME_OK))
        r = with_send(f, lambda: com.post(API + "/connect", headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "ctss.example"}))
        assert r.status_code == 200 and r.get_json()["connected"] is True, r.get_json()
        assert hook(msg("/nothing", 501, kind="group")).status_code == 200 and tia.post(API + "/code").status_code == 200
    for var in ("TELEGRAM_BOT_TOKEN", "SECRET_KEY"):
        with telegram(token="made-up-" + secrets.token_hex(10), connected=False):
            connect()
            old, was = tg.hook_secret(), os.environ[var]
            try:
                for new in ("made-up-" + secrets.token_hex(10), was + "x"):
                    os.environ[var] = new
                    assert links.connected() is None, var
                    for secret in (True, old): assert hook(msg("/nothing", 501, kind="group"), secret=secret).status_code == 404, (var, "neither the new secret nor the old one")
                    r = tia.post(API + "/code"); assert (r.status_code, r.get_json()) == (409, {"error": "Telegram is not connected yet."}), var
                    j, k = tia.get(API).get_json(), com.get(API + "/admin").get_json()
                    assert (j["on"], j["connected"], j["bot"]) == (True, False, None) and (k["connected"], k["bot"], k["base"], k["at"]) == (False, None, None, None), (j, k)
                    assert "ctss_made_up_bot" not in json.dumps([j, k]), "an old bot's name is not said"
                os.environ[var] = was
                assert links.connected()["username"] == "ctss_made_up_bot", "the same token and key again: connected as before"
                os.environ[var] = "made-up-" + secrets.token_hex(10)
                connect(); assert links.connected()["username"] == "ctss_made_up_bot" and hook(msg("/nothing", 501, kind="group"), secret=old).status_code == 403
            finally: os.environ[var] = was
    with telegram():                                                                                # what an earlier version saved: no digest, or an odd one
        for key in (None, "", digest(""), tg.hook_secret(), 7, ["x"]):
            tgdb.set_state("bot", dict(CONNECTED, key=key)); assert links.connected() is None and hook(msg("hi")).status_code == 404, key
        tgdb.set_state("bot", CONNECTED); assert links.connected() is None
        key = os.environ.pop("SECRET_KEY")
        try:
            tgdb.set_state("bot", dict(CONNECTED, key=digest(""))); assert links.connected() is None, "no SECRET_KEY: never connected"
            tgdb.set_state("bot", CONNECTED); assert links.connected() is None and links.key() is None, "nor with no digest saved"
        finally: os.environ["SECRET_KEY"] = key
        os.environ.pop("TELEGRAM_BOT_TOKEN"); assert links.connected() is None and links.key() is None, "no token: never connected"
    assert REAL == []

@t
def connect_takes_only_a_clean_https_address():
    com, tok = client(dict(role="committee")), "made-up-" + secrets.token_hex(10)
    cookie = com.get_cookie("session").value
    def connect(headers, practice=False):
        f, seen = fake_bot(dict(getMe=ME_OK))
        c = A.app.test_client(use_cookies=False)
        r = with_send(never if practice else f, lambda: c.post("/api/relief/telegram/connect", headers=dict(headers, Cookie=f"session={cookie}")))
        return r.status_code, (r.get_json() or {}).get("error"), [d["url"] for m, d in seen if m == "setWebhook"], (tgdb.get_state("bot") or {}).get("base")
    S = {"X-Forwarded-Proto": "https"}
    with telegram(token=tok, connected=False):
        for host, want in (("ctss.example", None), ("ctss.example:8443", None), ("CTSS.example", None), ("a-b.c-d.example", None)):
            for headers in (dict(S, **{"X-Forwarded-Host": host}), dict(S, Host=host)):
                got = connect(headers); assert got == (200, None, [f"https://{host.lower()}/telegram/hook"], f"https://{host.lower()}"), (headers, got)
                tgdb.set_state("bot", None)
        bad = [{"X-Forwarded-Proto": x} for x in ("https://evil.example/?", "https://evil.example/#", "https://evil.example/", "https://evil.example", "https://me:pw@evil.example/?",
                                                  "https://evil.example?", "https://evil.example\\", "https://evil.example:443/?a=", "https://evil.example:99999999", "https://evil.example:x", "https://[evil", "http", "javascript", "ftp", "https\t", "https ://x")]
        bad += [dict(S, **{"X-Forwarded-Host": x}) for x in ("evil.example/path", "me:pw@evil.example", "me@evil.example", "evil.example?x", "evil.example#x", "evil.example\\x",
                                                             "[::1]", "localhost", "evil.example.", "-evil.example", "evil_x.example", "a b.example",
                                                             "evil.example:", "evil.example:99999999", "evil.example:x", "evil.example:0", "é.example", "x." * 130 + "example")]
        bad += [dict(S, Host=x) for x in ("evil.example/path", "me:pw@evil.example", "evil.example?x", "evil.example#x", "localhost", "evil.example:x")]
        bad += [{"X-Forwarded-Host": "ctss.example"}, {}]                                             # plain http
        before = [{"X-Forwarded-Proto": "wss"}] + [dict(S, **{"X-Forwarded-Host": x}) for x in ("evil..example", ".evil.example", "a" * 250 + ".example")]   # werkzeug's own refusal
        for headers in bad + before:
            got = connect(headers)
            assert got == ((400, None, [], None) if headers in before else (409, tgweb.NOT_HTTPS, [], None)), (headers, got)
        os.environ["RAILWAY_PUBLIC_DOMAIN"] = "ctss-made-up.example"                                   # Railway's own name: none of it matters
        try:
            for headers in bad: assert connect(headers)[2:] == (["https://ctss-made-up.example/telegram/hook"], "https://ctss-made-up.example"), headers
        finally: os.environ.pop("RAILWAY_PUBLIC_DOMAIN")
    with telegram(connected=False):                                                                   # practice: a local address, by http
        for host in ("localhost", "localhost:8793", "127.0.0.1:5000", "ctss.example"):
            assert connect({"Host": host}, practice=True) == (200, None, [], f"http://{host}"), host
    assert REAL == []

@t
def connect_points_the_hook_at_railways_own_address():
    com, tok = client(dict(role="committee")), "made-up-" + secrets.token_hex(10)
    forged = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "elsewhere.example"}
    def connect(headers):
        f, seen = fake_bot(dict(getMe=ME_OK))
        r = with_send(f, lambda: com.post("/api/relief/telegram/connect", headers=headers))
        return r.status_code, [d["url"] for m, d in seen if m == "setWebhook"], (tgdb.get_state("bot") or {}).get("base")
    try:
        with telegram(token=tok, connected=False):
            for var in ("ctss-made-up.example", "  ctss-made-up.example\n", "CTSS-Made-Up.example"):
                os.environ["RAILWAY_PUBLIC_DOMAIN"] = var; want = "https://" + var.strip()
                for headers in (forged, {"X-Forwarded-Host": "elsewhere.example"}, {}):
                    assert connect(headers) == (200, [want + "/telegram/hook"], want), (var, headers)
            for var in ("", "   ", "https://x.example", "x.example/path", "x.example:8080", "me@x.example", "x.example?y", "x example", "x.example\nelsewhere.example",
                        "x..example", ".x.example", "x.example.", "-x.example", "x-.example", "localhost", "é.example", "x_y.example", "[::1]", "a" * 250 + ".example"):
                os.environ["RAILWAY_PUBLIC_DOMAIN"] = var; tgdb.set_state("bot", None)           # malformed: as if it were not set
                assert connect({"X-Forwarded-Proto": "https", "X-Forwarded-Host": "ctss.example"}) == (200, ["https://ctss.example/telegram/hook"], "https://ctss.example"), var
                tgdb.set_state("bot", None); assert connect({}) == (409, [], None), (var, "http is still refused")
            os.environ.pop("RAILWAY_PUBLIC_DOMAIN")
            assert connect({"X-Forwarded-Proto": "https", "X-Forwarded-Host": "ctss.example"})[1] == ["https://ctss.example/telegram/hook"]
        with telegram(connected=False):                                                           # practice too
            os.environ["RAILWAY_PUBLIC_DOMAIN"] = "ctss-made-up.example"
            assert com.post("/api/relief/telegram/connect").get_json()["base"] == "https://ctss-made-up.example"
    finally: os.environ.pop("RAILWAY_PUBLIC_DOMAIN", None)
    assert REAL == []

@t
def connect_needs_the_secret_key():
    with telegram(connected=False):
        com, key = client(dict(role="committee")), os.environ.pop("SECRET_KEY")
        try: r = com.post("/api/relief/telegram/connect")
        finally: os.environ["SECRET_KEY"] = key
        assert r.status_code == 409 and "SECRET_KEY" in r.get_json()["error"] and tg.PRACTICE_LOG == [] and tgdb.get_state("bot") is None, (r.status_code, r.get_json())

@t
def admin_lists_who_is_not_linked():
    API = "/api/relief/telegram/"
    com = client(dict(role="committee"))
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    j = com.get(API + "admin").get_json()
    everyone = sorted([CORA, HUGO, ROSA, TEAM, TIA])                                             # by name; not the executive, not whoever is switched off
    assert j == dict(token_set=False, practice=False, connected=False, bot=None, base=None, at=None, linked=[], not_linked=everyone, people=5), j
    with telegram():
        links.link(TIA, 501, "tia_t"); links.link(GONE_, 502, None); links.link(EXE, 503, None)
        j = who(TEAM).get(API + "admin").get_json()
        assert (j["token_set"], j["practice"], j["connected"], j["bot"], j["base"], j["at"]) == (True, True, True, "practice_bot", CONNECTED["base"], CONNECTED["at"]), j
        assert [x["name"] for x in j["linked"]] == [EXE, GONE_, TIA] == sorted([EXE, GONE_, TIA]) and all(set(x) == {"name", "handle", "at"} for x in j["linked"]), j["linked"]
        assert j["linked"][2]["handle"] == "tia_t" and j["not_linked"] == sorted([CORA, HUGO, ROSA, TEAM]) and j["people"] == 5, j
        assert not re.search(r"\b50[123]\b", json.dumps(j)), "no chat id"
        with record(EXE, extras=dict(relief=True, exams=None, admin=False)): assert com.get(API + "admin").get_json()["people"] == 6
        with record(ROSA, off=True): assert ROSA not in com.get(API + "admin").get_json()["not_linked"]
        # unlink
        for body in (dict(name="Nobody Here"), dict(name=ROSA), dict(name=None), dict(name=[TIA]), dict(), [], "x"):
            r = com.post(API + "unlink", json=body); assert r.status_code == 404 and r.get_json()["error"], (body, r.status_code)
        for raw in (b'{"name": "\\ud800"}', b'{"name": "Ms \\udfff Teo"}', b'{"name": 3}', b'{"name": true}', b'{"name": {"a": 1}}', b'{"name": null}', b'{"name": ""}',
                    b"[" * 200_000, b'{"name": ' + b"[" * 200_000, b'{"a":' * 100_000, b"", b"not json", b"\xff\xfe", b'"\\ud800"', b'{"name": "\\u0000"}', b'{"name": "%s"}' % (b"x" * 100_000)):
            r = com.post(API + "unlink", data=raw, content_type="application/json"); assert r.status_code in (400, 404) and r.get_json()["error"], (raw[:30], r.status_code)
        assert len(links.linked()) == 3
        r = com.post(API + "unlink", json=dict(name=GONE_)); assert r.status_code == 200 and [x["name"] for x in r.get_json()["linked"]] == [EXE, TIA], r.get_json()
        assert who(TEAM).post(API + "unlink", json=dict(name=TIA)).status_code == 200 and links.chat_of(TIA) is None
        with no_pub(): assert com.get(API + "admin").status_code == 200

@t
def the_link_and_unlink_are_in_the_history():
    with telegram():
        n = len(entries())
        codes = []
        def use(name, chat):
            codes.append(links.new_code(name)["code"]); hook(msg(codes[-1], chat, user="some_handle_x"))
        def new():
            nonlocal n
            got = entries()[: len(entries()) - n]; n = len(entries())
            return [(e["who"], e["as"], e["via"], e["what"], e["text"]) for e in reversed(got)]
        use(TIA, 987654321)
        assert new() == [(TIA, TIA, "telegram", "telegram linked", "Telegram linked")]
        use(TIA, 987654322)
        assert new() == [(TIA, TIA, "telegram", "telegram linked", "Telegram linked (moved from another Telegram)")]
        use(HUGO, 987654322)
        assert new() == [(HUGO, HUGO, "telegram", "telegram linked", "Telegram linked"),
                         (HUGO, HUGO, "telegram", "telegram unlinked", f"Telegram unlinked for {TIA}: the same Telegram is now {HUGO}'s")]
        hook(msg("/stop", 987654322))
        assert new() == [(HUGO, HUGO, "telegram", "telegram unlinked", "Telegram unlinked")]
        hook(msg("/stop", 987654322)); hook(msg("ABCD-EFGH", 987654322)); hook(msg("hello", 987654322)); assert new() == []
        links.link(TIA, 987654321, None); who(TIA).delete("/api/relief/telegram/link"); who(TIA).delete("/api/relief/telegram/link")
        assert new() == [(TIA, TIA, "code", "telegram unlinked", "Telegram unlinked")]
        links.link(TIA, 987654321, None); client(dict(role="committee")).post("/api/relief/telegram/unlink", json=dict(name=TIA))
        assert new() == [(None, "Shared committee code", "shared", "telegram unlinked", f"Telegram unlinked for {TIA}")]
        who(TIA).post("/api/relief/telegram/code"); assert new() == [], "a code asked for is not a link"
        client(dict(role="committee")).post("/api/relief/telegram/connect"); who(TEAM).post("/api/relief/telegram/disconnect")
        assert [x[:1] + x[3:] for x in new()] == [(None, "telegram connected", "Telegram connected (@practice_bot)"), (TEAM, "telegram disconnected", "Telegram disconnected")]
        raw = "".join(open(os.path.join(history.DIR, f), encoding="utf-8").read() for f in os.listdir(history.DIR))
        for bad in codes + [access.norm(c) for c in codes] + ["987654321", "987654322", "some_handle_x"]: assert bad not in raw, "no chat id, handle or code"
        assert all(e["where"] == "Relief" and e["link"] == "/relief" and "absence" not in e for e in entries())

@t
def an_entry_says_who_and_by_what_way():
    with A.app.test_request_context():
        A.session.update(who=TIA, via="code", n=0)
        A._relief_entry("x", "By the session"); A._relief_entry("x", "By Hugo on Telegram", "abc123", who=HUGO, via="telegram")
        WB._noted("x", dict(id="def456", teacher=TIA, dates=["2026-10-13"]), "acknowledged")
        WB._noted("x", dict(id="def456", teacher=TIA, dates=["2026-10-13"]), lambda: "acknowledged there", by=(HUGO, "telegram"))
    d, c, b, a = entries(4)
    assert (a["who"], a["via"], a.get("absence")) == (TIA, "code", None) and (b["who"], b["as"], b["via"], b["absence"]) == (HUGO, HUGO, "telegram", "abc123"), (a, b)
    assert (c["who"], c["via"], c["absence"]) == (TIA, "code", "def456") and (d["who"], d["via"], d["text"]) == (HUGO, "telegram", f"Relief for {TIA} on Tue 13 Oct: acknowledged there")
    js = open(os.path.join(ROOT, "static", "history.js"), encoding="utf-8").read()
    assert re.search(r'const VIA = \{[^}]*\btelegram: "Telegram"', js)

@t
def nothing_private_is_logged_by_the_hook():
    h, root = Grab(), logging.getLogger()
    old = root.level; root.addHandler(h); KINDS.addHandler(h); root.setLevel(logging.DEBUG)
    try:
        with telegram():
            code = links.new_code(TIA)["code"]
            for text in (code, "ABCD-EFGH", "a private line", "/stop", "/help"): hook(msg(text, 987650001, user="some_handle_y"))
            real = links.name_of
            def boom(chat): raise ValueError(f"{chat} {code} a private line")
            links.name_of = boom
            try: assert hook(msg("a private line", 987650001)).status_code == 200
            finally: links.name_of = real
            real_note = bot._note
            def bad_note(*a, **k): raise ValueError(f"{code} 987650001")
            bot._note = bad_note
            try: hook(msg(links.new_code(TIA)["code"], 987650002))
            finally: bot._note = real_note
            assert links.chat_of(TIA) == 987650002 and sent(987650002) == [(987650002, HELLO.format(name=TIA))], "a history entry that cannot be made fails nothing"
        text = "\n".join(r.getMessage() + str(r.exc_info or "") + str(r.args or "") for r in h.records if r.name.startswith("relief"))
        assert "ValueError" in text, "a failure is logged by its kind"
        everything = "\n".join(r.getMessage() + str(r.exc_info or "") + str(r.args or "") for r in h.records)
        for bad in (code, access.norm(code), "ABCD", "a private line", "98765", "some_handle_y", tg.hook_secret() or "x" * 64): assert bad not in everything, "logged"
    finally: root.removeHandler(h); KINDS.removeHandler(h); root.setLevel(old)

# ---- Task 3: the message queue and its sender ----
import datetime, subprocess  # noqa: E402
from relief import absences, files as FI  # noqa: E402

assert OB.SPACING == 0.05 and OB.EVERY == 5
OB.SPACING = 0
NAPS = []                                             # every wait the sender asked for, never waited for here
OB._sleep = NAPS.append
OK_ = None
BLOCKED, REFUSED, DOWN, LATE = (403, dict(ok=False)), (400, dict(ok=False)), (502, dict(ok=False)), (504, dict(ok=False))
def SLOW(s): return 429, dict(ok=False, parameters=dict(retry_after=s))
NEVER_LEFT, MAY_HAVE = ConnectionRefusedError("made up"), TimeoutError("made up")
MAYBE_SENT = (OK_, MAY_HAVE, LATE)                          # the answers after which the message is, or may be, with the person

def made_up(): return telegram(token="made-up-" + secrets.token_hex(10))

def parts(data, headers):
    """(params, file) of one call: JSON, or multipart with its file as (field, name, bytes)"""
    ctype = {k.lower(): v for k, v in headers.items()}["content-type"]
    if not ctype.startswith("multipart/"): return json.loads(data), None
    params, up = {}, None
    for x in data.split(b"--" + ctype.split("boundary=")[1].encode())[1:-1]:
        head, body = x[2:-2].split(b"\r\n\r\n", 1)
        field = re.search(rb' name="([^"]*)"', head).group(1).decode(); fname = re.search(rb'filename="([^"]*)"', head)
        if fname: up = (field, fname.group(1).decode(), body)
        else: params[field] = json.loads(body)
    return params, up

def tele(*answers, rest=OK_, before=None, me=OK_):
    """a _send answering one call after another from answers, then rest: (status, body), an exception, or OK_ (getMe: always
    me); seen: every call as (method, params, file)"""
    seen, left = [], list(answers)
    def f(url, data, headers, timeout):
        seen.append((url.rsplit("/", 1)[1], *parts(data, headers)))
        if before: before(*seen[-1])
        got = me if seen[-1][0] == "getMe" else left.pop(0) if left else rest
        if isinstance(got, BaseException): raise got
        status, body = got or (200, dict(ok=True, result=dict(message_id=1000 + len(seen))))
        return status, json.dumps(body).encode()
    return f, seen

def texts(seen): return [p["text"] for m, p, up in seen if m == "sendMessage"]
def item(key): return next((r for r in rows("outbox") if r["key"] == key), None)
def state(key): return (item(key) or {}).get("state")
def put(key, **changes):
    with tgdb.db() as c:
        for k, v in changes.items(): assert c.execute(f"UPDATE outbox SET {k}=? WHERE key=?", (v, key)).rowcount == 1
def q(key="k", name=TIA, text="A made-up message", **more): return OB.queue(key, name, text, kind=more.pop("kind", "made-up"), **more)

@contextlib.contextmanager
def valid(f):
    old = OB.VALID; OB.VALID = f
    try: yield
    finally: OB.VALID = old

@contextlib.contextmanager
def now_is(text):
    old = absences._now; absences._now = lambda: text
    try: yield
    finally: absences._now = old

@contextlib.contextmanager
def work(*names):
    """made-up work files -> their rows for queue"""
    got = [FI.save("abc123", n, f"made-up {n}".encode()) for n in names]
    try: yield [dict(id="abc123", file=x["id"], name=n) for x, n in zip(got, names)]
    finally:
        for x in got: FI.delete("abc123", x["id"])

@t
def a_key_queues_once_and_only_for_a_linked_person():
    with telegram():
        assert q() is False and rows("outbox") == [], "not linked"
        links.link(TIA, 501, None); links.link(OFFIE, 502, None); links.link(GONE_, 503, None)
        assert q("off", OFFIE) is False and q("gone", GONE_) is False and rows("outbox") == []
        with broken_accounts(): assert q() is False and rows("outbox") == []
        ref, files = dict(id="abc", who=TIA, n=[1, 2]), [dict(id="abc", file="f1", name="work é.pdf")]
        buttons = [[dict(text="✅ Acknowledge", what="ack", id="abc", ckey="c", who=TIA, extra=dict(a=1))], [dict(text="Open in the app", url="https://example.org/relief")]]
        with now_is("2026-10-13T07:20:00+08:00"): assert q(text="Line é 1\nLine 2 ", buttons=buttons, files=files, ref=ref) is True
        r = item("k")
        assert (r["name"], r["chat"], r["kind"], r["text"], r["state"], r["at"], r["sent_at"], r["message_id"], r["tries"]) == \
            (TIA, 501, "made-up", "Line é 1\nLine 2 ", "queued", "2026-10-13T07:20:00+08:00", None, None, 0), r
        assert json.loads(r["ref"]) == ref and json.loads(r["files"]) == files and json.loads(r["buttons"]) == buttons
        assert tg.PRACTICE_LOG == [] and rows("buttons") == [], "queueing sends nothing"
        for s in ("queued", "sending", "sent", "failed", "unsure"):
            put("k", state=s); assert q(text="Another") is False and item("k")["text"] == "Line é 1\nLine 2 ", s
        put("k", state="dropped", tries=4, next_at=9e9, files_failed=1)
        assert q(text="Again") is True, "a dropped key is as if it were not there"
        r = item("k"); assert (r["text"], r["state"], r["tries"], r["files_failed"], r["buttons"]) == ("Again", "queued", 0, 0, "[]") and "slows" not in r and len(rows("outbox")) == 1, r
        assert q() is False
        assert q("flat", buttons=[dict(text="One", what="ack")]) is True and json.loads(item("flat")["buttons"]) == [[dict(text="One", what="ack")]], "a button alone is its own row"

@t
def what_cannot_be_kept_is_refused_when_it_is_queued():
    with telegram():
        links.link(TIA, 501, None); ok = dict(text="A", what="ack", id="abc", ckey="c", who=TIA, extra=dict(a=[1, None]))
        loop = []; loop.append(loop)
        bad = [[["x"]], [5], [[dict(what="ack")]], [[dict(ok, text=None)]], [[dict(ok, text=" ")]], [[dict(text="x", url=None)]], [[dict(text="x", url=5)]], [[dict(text="x", url=["https://x"])]]]
        bad += [[[dict(ok, **{k: v})]] for k in ("text", "what", "id", "ckey", "who") for v in (["x"], dict(a=1), 5, 2 ** 70, True, b"x", "\ud800")]
        bad += [[[dict(ok, extra=v)]] for v in (object(), {1, 2}, b"x", loop)] + [[[ok], [dict(ok, who=["x"])]]]
        for b in bad:
            try: q("bad", buttons=b)
            except ValueError: pass
            else: raise AssertionError(b)
        for text in (None, 5, ["x"], b"x", "\ud800"):
            try: q("bad", text=text)
            except ValueError: pass
            else: raise AssertionError(text)
        for more in (dict(ref=object()), dict(files=[object()]), dict(files=["x"]), dict(files=[5]), dict(files=[dict(id={1})])):
            try: q("bad", **more)
            except ValueError: pass
            else: raise AssertionError(more)
        assert rows("outbox") == [], "nothing of it is kept"
        assert q("good", buttons=[[ok, dict(text="B", what=None, id=None, ckey=None, who=None)], [dict(text="C", url="https://x.org")]]) and q("plain", text="")
        assert q("one", files=(x for x in [dict(id="a", file="b", name="c")]), buttons=(r for r in [[ok]])) and len(json.loads(item("one")["files"])) == 1
        assert OB.send_due()["sent"] == 3

@t
def a_bad_item_never_stops_the_rest():
    """rows that should not be there (kept by an earlier version, or by hand)"""
    button = lambda **more: json.dumps([[dict(dict(text="A", what="ack", id="abc"), **more)]])
    bads = [dict(buttons=button(who=["x"])), dict(text=None), dict(buttons=button(id=2 ** 70)), dict(buttons=button(what=dict(a=1))), dict(buttons="{ not json"), dict(buttons=None),
            dict(buttons='[["x"]]'), dict(buttons='[[{"what": "ack"}]]'), dict(ref="not json"), dict(files=None), dict(at="not a time", buttons=button()), dict(buttons=button(ckey="\ud800"))]
    with made_up():
        links.link(TIA, 501, None)
        for i, b in enumerate(bads):                                                         # each alone, with one after it
            q(f"bad{i}"); put(f"bad{i}", **b); q(f"good{i}", text=f"good {i}"); f, seen = tele()
            assert with_send(f, OB.send_due) == dict(sent=1, waiting=0) and texts(seen) == [f"good {i}"], (b, seen)
            assert state(f"bad{i}") == "failed" and item(f"bad{i}")["tries"] == 1 and q(f"bad{i}") is False, b
        f, seen = tele(); assert with_send(f, lambda: OB.send_due(now=9e12)) == dict(sent=0, waiting=0) and seen == [], "failed for good"
        assert OB.told("bad0")["state"] == "failed" == OB.told_for("bad0")["bad0"]["state"]
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None)                      # more bad ones than a run takes, among good ones
        for i in range(50):
            q(f"bad{i}"); put(f"bad{i}", **bads[i % 2])
            if i % 5 == 0: q(f"good{i}", text=f"good {i}")
        f, seen = tele(); runs = [with_send(f, OB.send_due) for _ in range(2)]
        assert sum(r["sent"] for r in runs) == 10 and runs[-1]["waiting"] == 0 and texts(seen) == [f"good {i}" for i in range(0, 50, 5)], runs
        assert {state(f"bad{i}") for i in range(50)} == {"failed"}
        # a store that is locked, or a disk that is full, is nobody's fault: the run ends and nothing is failed by it
        real = tgdb.db; q("a", text="a"); q("b", text="b"); writes = []
        def locked(read=False):
            if not read: writes.append(1); raise sqlite3.OperationalError("database is locked")
            return real(read)
        tgdb.db = locked; f, seen = tele()
        try: assert with_send(f, OB.send_due) == dict(sent=0, waiting=2) and writes == [1] and seen == []
        finally: tgdb.db = real
        assert item("a")["state"] == item("b")["state"] == "queued" and item("a")["tries"] == 0
        real_chat = links.chat_of                                                            # locked as the chat is looked up
        def no_chat(name): writes.append(2); raise sqlite3.OperationalError("database is locked")
        links.chat_of = no_chat
        try: assert with_send(f, OB.send_due) == dict(sent=0, waiting=2) and writes == [1, 2] and item("a")["tries"] == 0 == item("a")["next_at"]
        finally: links.chat_of = real_chat
        assert with_send(f, OB.send_due)["sent"] == 2
        real_settle = OB._settle; q("c", text="c"); q("d", text="d")                         # any other trouble with one answer: the next one goes
        def settle(it, *a):
            if it["key"] == "c": raise sqlite3.IntegrityError("made up")
            return real_settle(it, *a)
        OB._settle = settle; f, seen = tele()
        try: assert with_send(f, OB.send_due) == dict(sent=1, waiting=0) and (state("c"), state("d")) == ("sending", "sent") and texts(seen) == ["c", "d"]
        finally: OB._settle = real_settle

@t
def two_sweeps_queue_one():
    with telegram():
        links.link(TIA, 501, None)
        for old in (None, "dropped"):
            if old: put("k", state=old)
            out, go = [], threading.Barrier(8)
            def sweep(): go.wait(); out.append(q())
            ths = [threading.Thread(target=sweep) for _ in range(8)]
            [x.start() for x in ths]; [x.join() for x in ths]
            assert sorted(out) == [False] * 7 + [True] and len(rows("outbox")) == 1, (old, out)

@t
def a_sent_message_is_not_sent_again():
    with telegram():
        links.link(TIA, 501, None); links.link(HUGO, 502, None)
        assert OB.send_due() == dict(sent=0, waiting=0)
        q("a", text="First"); q("b", HUGO, "Second")
        with now_is("2026-10-13T07:21:00+08:00"): assert OB.send_due() == dict(sent=2, waiting=0)
        assert tg.PRACTICE_LOG == [("sendMessage", dict(chat_id=501, text="First", disable_web_page_preview=True)),
                                   ("sendMessage", dict(chat_id=502, text="Second", disable_web_page_preview=True))], tg.PRACTICE_LOG
        a = item("a"); assert a["state"] == "sent" and a["sent_at"] == "2026-10-13T07:21:00+08:00" and item("b")["message_id"] == a["message_id"] + 1, a
        for _ in range(3): assert OB.send_due(now=9e12) == dict(sent=0, waiting=0)
        assert q("a") is False and OB.send_due() == dict(sent=0, waiting=0) and len(tg.PRACTICE_LOG) == 2
        tg.PRACTICE_LOG.clear()                                   # oldest first, at most limit of them
        for i in range(7): q(f"n{i}", text=str(i))
        assert OB.send_due(limit=3) == dict(sent=3, waiting=4) and [x for c, x in sent()] == ["0", "1", "2"]
        assert OB.send_due() == dict(sent=4, waiting=0) and [x for c, x in sent()] == list("0123456")

@t
def what_goes_out_is_plain_text():
    with made_up():
        links.link(TIA, 501, None); f, seen = tele()
        q(text="<b>Not bold</b> *_x_* & \"é\" 🔔 · –"); with_send(f, OB.send_due)
        assert seen == [("sendMessage", dict(chat_id=501, text="<b>Not bold</b> *_x_* & \"é\" 🔔 · –", disable_web_page_preview=True), None)], seen
        assert item("k")["message_id"] == 1001 and item("k")["chat"] == 501
        for i, odd in enumerate((True, [], dict(message_id="x"), dict(message_id=2 ** 70), dict(message_id=True), None)):       # an answer with no id: still sent
            f, seen = tele((200, dict(ok=True, result=odd))); q(f"o{i}"); with_send(f, OB.send_due)
            assert state(f"o{i}") == "sent" and item(f"o{i}")["message_id"] is None, odd

@t
def it_is_marked_and_committed_before_it_goes_and_nothing_is_locked():
    with made_up():
        links.link(TIA, 501, None); at = []
        def look(method, params, up):
            at.append((state("k"), len(rows("buttons"))))         # another connection sees it
            assert OB.told("k")["at"] == "2026-10-13T07:20:00+08:00" and item("k")["sent_at"] == "2026-10-13T07:25:00+08:00"
            began = time.monotonic(); tgdb.set_state("free", len(at)); assert time.monotonic() - began < 2, "the store is locked during the call"
            assert absences._LOCK.acquire(timeout=1); absences._LOCK.release()
            assert q("while", text="Queued meanwhile") is (len(at) == 1) and OB.send_due() == dict(sent=0, waiting=1, busy=True)
        f, seen = tele(before=look)
        with now_is("2026-10-13T07:20:00+08:00"): q(buttons=[[dict(text="A", what="ack")]])
        with now_is("2026-10-13T07:25:00+08:00"): assert with_send(f, OB.send_due) == dict(sent=1, waiting=1)
        assert at == [("sending", 1)] and texts(seen) == ["A made-up message"]
        assert OB.told("k")["state"] == "sent"

@t
def a_restart_mid_send_is_unsure_not_resent():
    with telegram():
        links.link(TIA, 501, None)
        with now_is("2026-10-13T07:20:00+08:00"): q(); q("other"); q("done")
        with now_is("2026-10-13T07:22:00+08:00"):
            put("k", state="sending", sent_at="2026-10-13T07:21:00+08:00"); put("done", state="sent", sent_at="2026-10-13T07:21:30+08:00")
            assert OB.recover() == 1 and OB.recover() == 0
        assert OB.told("k") == dict(state="unsure", at="2026-10-13T07:21:00+08:00", name=TIA, ref=None, files_failed=0), OB.told("k")
        assert OB.send_due(now=9e12) == dict(sent=1, waiting=0) and len(tg.PRACTICE_LOG) == 1, "only the other one"
        assert state("k") == "unsure" and state("done") == "sent" and q() is False, "never queued again by itself"
        put("k", state="sending", sent_at=None); OB.recover(); assert OB.told("k")["at"] == "2026-10-13T07:20:00+08:00"

class Killed(BaseException): pass

def killed_at(n, f, *answers):
    """f run with the process killed at its nth step (a block on the store opened, about to be committed, committed; a call
    about to go out, answered) and never anything after it -> (was it killed, how many messages the person has or may
    have by it, the files they have)"""
    steps, real, left = [0], tgdb.db, list(answers)
    got, docs = [], []
    def step():
        steps[0] += 1
        if steps[0] >= n: raise Killed()
    @contextlib.contextmanager
    def db(read=False):
        step()
        with real(read) as c:
            yield c
            step()
        step()
    def out(url, data, headers, timeout):
        step()
        answer_ = left.pop(0) if left and not url.endswith("/getMe") else OK_
        if any(answer_ is x for x in MAYBE_SENT) and not url.endswith("/getMe"):
            (got if url.endswith("/sendMessage") else docs).append(parts(data, headers))
        step()
        if isinstance(answer_, BaseException): raise answer_
        status, body = answer_ or (200, dict(ok=True, result=dict(message_id=1)))
        return status, json.dumps(body).encode()
    tgdb.db = db
    try: with_send(out, f)
    except Killed: return True, got, docs
    finally: tgdb.db = real
    return False, got, docs

@t
def killed_at_any_step_a_message_never_goes_twice():
    saved = FI.save("abc123", "work.pdf", b"made-up work"); ends = collections.Counter()
    keep = sqlite3.connect(tgdb.PATH); keep.execute("SELECT count(*) FROM state").fetchone()      # one connection kept open: the others close much faster
    with made_up():
        for first in ((), (DOWN, NEVER_LEFT), (SLOW(9),), (MAY_HAVE,), (LATE,), (REFUSED,), (BLOCKED,)):
            n = 0
            while True:
                n += 1; wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None)
                q(buttons=[[dict(text="A", what="ack")]], files=[dict(id="abc123", file=saved["id"], name="work.pdf")])
                dead, got, docs = killed_at(n, lambda: [OB.send_due(now=1000 * i) for i in (1, 2, 3)[:len(first) + 1]], *first)
                assert not OB._busy.locked()
                mid = state("k"); OB.recover(); OB._doubt.clear(); OB._hold[0] = 0.0       # the app starts again, and everything works
                f, seen = tele(); with_send(f, lambda: [OB.send_due(now=10_000 * i) for i in (1, 2, 3)])
                assert len(got) + len(texts(seen)) <= 1, (first, n, mid, "went twice")
                assert len(docs) + len([1 for m, p, up in seen if m == "sendDocument"]) <= 1, (first, n, mid, "a file went twice")
                end = state("k"); ends[end] += 1
                if len(got) + len(texts(seen)) == 0: assert end in ("unsure", "failed", "dropped", None), (first, n, mid, end)
                if end == "sent" and not docs and not [1 for m, p, up in seen if m == "sendDocument"]: assert OB.told("k")["files_failed"] == 1, (first, n, "a file that never went is noted")
                if end is None or end == "dropped": assert first == (BLOCKED,), (first, n)
                assert len(rows("buttons")) <= 1, "the same token over every try"
                if not dead: break
            assert n > 8, (first, n)
        assert ends["sent"] > 20 and ends["unsure"] > 10, ends
    keep.close(); FI.delete("abc123", saved["id"])

@t
def a_store_that_fails_after_the_call_never_sends_again():
    with made_up():
        links.link(TIA, 501, None); real = tgdb.db; broken, failed = [], []
        def db(read=False):
            if broken and not read: failed.append(1); raise sqlite3.OperationalError("database is locked: made-up private line")
            return real(read)
        f, seen = tele(before=lambda *a: broken.append(1)); q("a"); q("b")
        tgdb.db = db
        try: assert with_send(f, OB.send_due)["sent"] == 0
        finally: tgdb.db = real
        assert len(seen) == 1 == len(failed) and state("a") == "sending" and state("b") == "queued", "the run stops when the store does"
        f, seen = tele(); assert with_send(f, OB.send_due) == dict(sent=1, waiting=0) and state("a") == "sending"
        OB.recover(); assert state("a") == "unsure" and with_send(f, OB.send_due) == dict(sent=0, waiting=0) and len(seen) == 1
        broken.clear(); failed.clear(); f, seen = tele(MAY_HAVE, before=lambda *a: broken.append(1)); q("c"); q("d"); tgdb.db = db
        try: with_send(f, OB.send_due)
        finally: tgdb.db = real
        assert state("c") == "sending" and OB._doubt.is_set(), "held, though the answer could not be written"

@t
def slow_and_network_wait_and_retry():
    with made_up():
        links.link(TIA, 501, None); f, seen = tele(rest=NEVER_LEFT); now = 1_000_000
        go = lambda at: with_send(f, lambda: OB.send_due(now=at))
        q()
        for i, wait in enumerate((5, 30, 120, 600, 1800)):
            assert go(now) == dict(sent=0, waiting=1) and len(seen) == i + 1
            r = item("k"); assert (r["state"], r["tries"], r["next_at"], r["sent_at"]) == ("queued", i + 1, now + wait, None), r
            assert OB.told("k")["state"] == "queued" and OB.told("k")["at"] == r["at"]
            go(now + wait - 1); assert len(seen) == i + 1, "it waits"
            now += wait
        assert go(now) == dict(sent=0, waiting=0) and state("k") == "failed" and len(seen) == 6
        go(9e12); assert len(seen) == 6 and q() is False
        # slow: until Telegram's pause ends, an hour at most, and no try is counted
        f, seen = tele(SLOW(12), NEVER_LEFT, SLOW(7200), SLOW(0)); q("s", text="Slow one"); now = 2_000_000
        go(now); r = item("s"); assert (r["state"], r["tries"], r["next_at"], r["sent_at"]) == ("queued", 0, now + 12, None), r
        go(now + 11); assert len(seen) == 1
        go(now + 12); r = item("s"); assert (r["tries"], r["next_at"]) == (1, now + 12 + 5), r
        go(now + 17); r = item("s"); assert (r["tries"], r["next_at"]) == (1, now + 17 + 3600), r
        go(now + 17 + 3600); r = item("s"); assert (r["tries"], r["next_at"]) == (1, now + 17 + 3601), r
        assert go(now + 17 + 3601)["sent"] == 1 and texts(seen) == ["Slow one"] * 5 and state("s") == "sent"
        f, seen = tele(rest=SLOW(1)); q("t")                                        # however often it says so
        for i in range(1, 41): go(10_000_000 + 1000 * i); assert (state("t"), item("t")["tries"], len(seen)) == ("queued", 0, i)
        f, seen = tele(); assert go(11_000_000)["sent"] == 1
        f, seen = tele(SLOW(5), NEVER_LEFT); real = OB._clock                       # the real clock, when none is given
        OB._clock = lambda: 15_000_000.5
        try: q("u"); with_send(f, OB.send_due); assert item("u")["next_at"] == 15_000_005.5 == OB._hold[0]
        finally: OB._clock = real

@t
def a_pause_telegram_asks_for_holds_everything():
    with made_up():
        links.link(TIA, 501, None); links.link(HUGO, 502, None); f, seen = tele(SLOW(30)); go = lambda at, **k: with_send(f, lambda: OB.send_due(now=at, **k))
        for i in range(3): q(f"k{i}", text=f"old {i}")
        assert go(1000) == dict(sent=0, waiting=3) and texts(seen) == ["old 0"]
        was = rows("outbox"); q("new", HUGO, "new")                                  # queued during the pause: it waits its turn behind the older ones
        for at in (1000, 1001, 1015, 1029.9):
            with valid(lambda it: (_ for _ in ()).throw(ValueError())): assert go(at) == dict(sent=0, waiting=4) and len(seen) == 1, at
            with record(TIA, off=True): assert go(at) == dict(sent=0, waiting=4) and rows("outbox")[:3] == was, "nothing is dropped or counted"
        assert go(1030) == dict(sent=4, waiting=0) and texts(seen)[1:] == ["old 0", "old 1", "old 2", "new"], texts(seen)
        # a storm of new ones during one pause: nothing until it ends, then oldest first
        f, seen = tele(SLOW(600)); q("a0", text="a0"); go(2000)
        for i in range(1, 40): q(f"a{i}", HUGO if i % 2 else TIA, f"a{i}"); assert go(2000 + 15 * i)["sent"] == 0 and len(seen) == 1, i
        assert go(2599.9)["sent"] == 0 and len(seen) == 1 and go(2600, limit=30) == dict(sent=30, waiting=10) and go(2600) == dict(sent=10, waiting=0)
        assert texts(seen)[1:] == [f"a{i}" for i in range(40)], "oldest first, each once"
        # one pause after another: nobody is pushed back behind a newer one
        f, seen = tele(SLOW(10), SLOW(10), SLOW(10)); q("b0", text="b0"); got = []
        for i in range(1, 4): go(3000 + 10 * i); q(f"b{i}", text=f"b{i}")
        assert texts(seen) == ["b0"] * 3 and go(3040)["sent"] == 4 and texts(seen)[3:] == ["b0", "b1", "b2", "b3"]
        # never longer than an hour, and a clock put back does not make it longer
        f, seen = tele(SLOW(99_999)); q("c", text="c"); q("c2", text="c2"); go(5000)
        assert OB.HOLD_MOST == 3600 and len(seen) == 1 and go(8599)["sent"] == 0 and len(seen) == 1 and go(8600)["sent"] == 2
        f, seen = tele(SLOW(3600)); q("d"); go(9e9); put("d", next_at=0); f, seen = tele(); assert go(5000)["sent"] == 1
        for at, odd in ((20_000, -5), (21_000, 0), (22_000, float("nan"))):
            f, seen = tele(SLOW(odd)); q(f"o{odd}"); go(at); assert OB._hold[0] == at + 1 and len(seen) == 1, odd; assert go(at + 1)["sent"] == 1
        # the bot's own question (after an unsure one) can be told to wait too
        f, seen = tele(MAY_HAVE, me=SLOW(40)); q("e", text="e"); q("g", text="g"); go(30_000); go(30_001); n = len(seen); assert [m for m, p, up in seen] == ["sendMessage", "getMe"]
        for at in (30_002, 30_040): assert go(at) == dict(sent=0, waiting=1) and len(seen) == n, at
        f, seen = tele(); assert go(30_041)["sent"] == 1 and [m for m, p, up in seen] == ["getMe", "sendMessage"]

@t
def a_pause_asked_for_by_a_file_holds_everything():
    with made_up(), work("a.pdf", "b.docx", "c.png") as fs:
        links.link(TIA, 501, None); q("k", files=fs); q("next", text="next"); f, seen = tele(OK_, OK_, SLOW(600)); NAPS.clear()
        go = lambda at: with_send(f, lambda: OB.send_due(now=at)); said = lambda: [up[1] if up else p["text"] for m, p, up in seen]
        assert go(1000) == dict(sent=1, waiting=1) and said() == ["A made-up message", "a.pdf", "b.docx"] and NAPS == [], "one call, and nothing after it"
        assert OB.told("k")["state"] == "sent" and OB.told("k")["files_failed"] == 2, "the file and those after it"
        for at in (1001, 1599): assert go(at) == dict(sent=0, waiting=1) and len(seen) == 3
        assert go(1600) == dict(sent=1, waiting=0) and said()[3:] == ["next"], "the files are not tried again"
        for s, waits in ((20, True), (21, False)):                                  # waited for at once up to FILE_SLOW seconds
            wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None); q("k", files=fs); NAPS.clear(); f, seen = tele(OK_, SLOW(s)); go(1000)
            assert (NAPS == [20] and said()[1:] == ["a.pdf", "a.pdf", "b.docx", "c.png"] and OB.told("k")["files_failed"] == 0) if waits else \
                (NAPS == [] and said()[1:] == ["a.pdf"] and OB.told("k")["files_failed"] == 3), (s, NAPS, said())
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None); q("k", files=fs[:2]); q("z", text="z"); NAPS.clear(); f, seen = tele(OK_, SLOW(2), SLOW(3), SLOW(4))
        assert go(1000)["sent"] == 2 and NAPS == [2, 3, 4] and said()[1:] == ["a.pdf"] * 3 + ["b.docx", "z"] and OB.told("k")["files_failed"] == 1, "the last pause is kept to as well"

@t
def refused_is_failed_and_unsure_is_unsure():
    with made_up():
        links.link(TIA, 501, None)
        for i, (answer_, want) in enumerate(((REFUSED, "failed"), ((200, dict(ok=False)), "failed"), (MAY_HAVE, "unsure"), (ConnectionResetError(), "unsure"), (LATE, "unsure"), ((500, dict(ok=False)), "unsure"))):
            f, seen = tele(answer_)
            with now_is("2026-10-13T07:20:00+08:00"): q(f"k{i}")
            with now_is("2026-10-13T07:25:00+08:00"): assert with_send(f, OB.send_due) == dict(sent=0, waiting=0)
            assert OB.told(f"k{i}")["state"] == want and (item(f"k{i}")["sent_at"] is None) is (want == "failed") and OB.told(f"k{i}")["at"] == ("2026-10-13T07:25:00+08:00" if want == "unsure" else "2026-10-13T07:20:00+08:00")
            assert with_send(f, lambda: OB.send_due(now=9e12)) == dict(sent=0, waiting=0) and len(texts(seen)) == 1 and q(f"k{i}") is False, want
        assert links.chat_of(TIA) == 501

@t
def an_unsure_send_holds_the_rest():
    with made_up():
        links.link(TIA, 501, None); times = []
        def go(f):
            def timed(url, data, headers, timeout): times.append((url.rsplit("/", 1)[1], timeout)); return f(url, data, headers, timeout)
            return with_send(timed, OB.send_due)
        said = lambda seen: [m for m, p, up in seen]
        for k in "abc": q(k, text=k)
        f, seen = tele(MAY_HAVE)
        assert go(f) == dict(sent=0, waiting=2) and said(seen) == ["sendMessage"] and texts(seen) == ["a"] and state("a") == "unsure", "the run ends"
        was = rows("outbox")
        for me in (MAY_HAVE, NEVER_LEFT, DOWN, LATE, REFUSED, BLOCKED, (200, dict(ok=False))):
            f, seen = tele(me=me); times.clear()
            assert go(f) == dict(sent=0, waiting=2) and seen == [("getMe", {}, None)] and rows("outbox") == was, me
            assert times == [("getMe", 5)] and links.chat_of(TIA) == 501, me
        q("d", text="d"); f, seen = tele(me=DOWN); assert go(f) == dict(sent=0, waiting=3) and said(seen) == ["getMe"], "what comes meanwhile waits too"
        with broken_accounts(): f, seen = tele(); assert go(f) == dict(sent=0, waiting=3) and seen == []
        b = tgdb.get_state("bot"); tgdb.set_state("bot", None); assert go(f) == dict(sent=0, waiting=3) and seen == []; tgdb.set_state("bot", b)
        f, seen = tele(); assert go(f) == dict(sent=3, waiting=0) and said(seen) == ["getMe"] + ["sendMessage"] * 3 and texts(seen) == ["b", "c", "d"]
        assert state("a") == "unsure"
        q("e"); f, seen = tele(); assert go(f)["sent"] == 1 and said(seen) == ["sendMessage"], "asked once"
        # it comes back and goes again: one more message, not all of them
        for k in "wxyz": q(k, text=k)
        for k in "wx": f, seen = tele(MAY_HAVE); go(f); assert texts(seen) == [k] and state(k) == "unsure"
        f, seen = tele(); assert go(f) == dict(sent=2, waiting=0) and texts(seen) == ["y", "z"]
        # a refusal, a failure to connect or a flood answer is no such doubt
        for answer_ in (REFUSED, NEVER_LEFT, DOWN, SLOW(1)):
            f, seen = tele(answer_); q("h" + str(len(rows("outbox")))); go(f); assert not OB._doubt.is_set(), answer_

@t
def a_hold_survives_a_run_asked_for_at_the_same_time():
    with made_up():
        links.link(TIA, 501, None)
        for k in "abc": q(k, text=k)
        busy, inside, go = dict(sent=0, waiting=2, busy=True), threading.Event(), threading.Event()
        other = lambda: [OB.send_due(), OB.send_due(now=9e12)]
        out = []; f, seen = tele(MAY_HAVE, before=lambda *a: out.extend(other()))          # while the message is timing out
        assert with_send(f, OB.send_due) == dict(sent=0, waiting=2) and out == [busy, busy] and OB._doubt.is_set()
        def wait(*a): inside.set(); assert go.wait(10)
        f, seen = tele(me=MAY_HAVE, before=wait); got = []                                  # while getMe is
        def both():
            th = threading.Thread(target=lambda: got.append(OB.send_due())); th.start(); assert inside.wait(10)
            assert other() == [busy, busy]; go.set(); th.join(10)
        with_send(f, both); assert got == [dict(sent=0, waiting=2)] and [m for m, p, up in seen] == ["getMe"] and OB._doubt.is_set()
        ths = [threading.Thread(target=OB.send_due) for _ in range(6)]; f, seen = tele(me=NEVER_LEFT)
        with_send(f, lambda: ([x.start() for x in ths], [x.join() for x in ths])); assert {m for m, p, up in seen} == {"getMe"} and OB._doubt.is_set()
        f, seen = tele(); assert with_send(f, OB.send_due) == dict(sent=2, waiting=0) and texts(seen) == ["b", "c"]

@t
def nothing_is_dropped_while_the_accounts_cannot_be_read():
    with made_up():
        links.link(TIA, 501, None); links.link(HUGO, 502, None); q("a", text="a"); q("b", HUGO, "b"); was = rows("outbox"); f, seen = tele()
        asked = []
        with broken_accounts(), valid(lambda it: asked.append(it)): assert with_send(f, OB.send_due) == dict(sent=0, waiting=2) and seen == [] == asked and rows("outbox") == was
        # ... from the moment it is looked at: the run stops there
        real, left = AP.readable, [True, True]
        AP.readable = lambda: left.pop(0) if left else real()
        try:
            with broken_accounts(): assert with_send(f, OB.send_due) == dict(sent=0, waiting=2) and seen == [] and rows("outbox") == was and left == []
        finally: AP.readable = real
        good = open(AP.PATH, encoding="utf-8").read()                                       # between two messages
        f, seen = tele(before=lambda *a: open(AP.PATH, "w", encoding="utf-8").write("{ not json"))
        try: assert with_send(f, OB.send_due) == dict(sent=1, waiting=1) and texts(seen) == ["a"] and state("b") == "queued"
        finally: open(AP.PATH, "w", encoding="utf-8").write(good)
        f, seen = tele(); assert with_send(f, OB.send_due) == dict(sent=1, waiting=0) and texts(seen) == ["b"]

@t
def a_blocked_chat_is_unlinked():
    with made_up():
        links.link(TIA, 501, None); links.link(HUGO, 502, None); f, seen = tele(BLOCKED)
        q("a"); q("b"); q("h", HUGO)
        assert with_send(f, OB.send_due) == dict(sent=1, waiting=0) and [p["chat_id"] for m, p, up in seen] == [501, 502]
        assert TIA not in links.linked() and links.chat_of(HUGO) == 502
        assert item("a") is None and state("b") == "dropped" and OB.told("a") is None and q("a") is False
        links.link(TIA, 601, None)                                                       # linked again: what is still to come goes
        assert q("a") is True and q("b") is True and with_send(f, OB.send_due)["sent"] == 2 and [p["chat_id"] for m, p, up in seen[2:]] == [601, 601]
        # linked again, on another phone, while the message was on its way to the old chat: the new link stays
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None)
        f, seen = tele(BLOCKED, before=lambda *a: links.link(TIA, 601, None)); q("a"); with_send(f, OB.send_due)
        assert links.chat_of(TIA) == 601 and item("a") is None and q("a") is True
        # ... between the look and the unlinking too
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None); real = links.unlink
        def late(name, *a): links.link(TIA, 601, None); return real(name, *a)
        links.unlink = late
        try: f, seen = tele(BLOCKED); q("a"); with_send(f, OB.send_due)
        finally: links.unlink = real
        assert links.linked()[TIA] and links.chat_of(TIA) == 601 and item("a") is None
        # the chat taken by somebody else meanwhile: theirs is not touched
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None)
        f, seen = tele(BLOCKED, before=lambda *a: links.link(HUGO, 501, None)); q("a"); with_send(f, OB.send_due)
        assert links.linked() and links.chat_of(HUGO) == 501 and links.chat_of(TIA) is None and item("a") is None
        # the bot disconnected meanwhile (somebody else's token says 403 to everybody): nobody is unlinked, and it waits
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None); b = tgdb.get_state("bot")
        f, seen = tele(BLOCKED, before=lambda *a: tgdb.set_state("bot", None)); q("a"); q("b")
        assert with_send(f, OB.send_due) == dict(sent=0, waiting=2) and links.chat_of(TIA) == 501 and len(seen) == 1
        assert (state("a"), item("a")["tries"], item("a")["sent_at"]) == ("queued", 0, None)
        tgdb.set_state("bot", b); f, seen = tele(); assert with_send(f, OB.send_due)["sent"] == 2
        # switched off meanwhile: the chat is still theirs, and blocked
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None)
        with record(TIA): f, seen = tele(BLOCKED, before=lambda *a: AP.update(lambda d: d["people"].__setitem__(TIA, dict(off=True)))); q("a"); with_send(f, OB.send_due)
        assert TIA not in links.linked() and item("a") is None
        # whatever goes wrong there, the message is not left as being sent
        def boom(*a, **k): raise RuntimeError("made up")
        for what, want in (("unlink", None), ("connected", "queued"), ("chat_of", None)):
            wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None); q("a"); real = getattr(links, what)
            f, seen = tele(BLOCKED, before=lambda *a: setattr(links, what, boom))
            try: with_send(f, OB.send_due)
            finally: setattr(links, what, real)
            assert state("a") == want, (what, state("a"))

@t
def an_item_sending_for_too_long_is_unsure():
    with made_up():
        links.link(TIA, 501, None); assert OB.STUCK == 120; f, seen = tele(); go = lambda at: with_send(f, lambda: OB.send_due(now=at))
        for k, at in (("old", 879.9), ("edge", 880), ("fresh", 999), ("none", None)): q(k); put(k, state="sending", claimed=at, sent_at="2026-10-13T07:21:00+08:00")
        q("go"); assert go(1000) == dict(sent=1, waiting=0)
        assert [state(k) for k in ("old", "edge", "fresh", "none", "go")] == ["unsure", "sending", "sending", "sending", "sent"]
        assert OB.told("old")["at"] == "2026-10-13T07:21:00+08:00" and q("old") is False
        go(1200); assert [state(k) for k in ("old", "edge", "fresh", "none")] == ["unsure", "unsure", "unsure", "sending"] and len(seen) == 1, "never sent again"
        q("k"); go(2000); assert item("k")["claimed"] == 2000 and state("k") == "sent"
        put("k", state="sending"); b = tgdb.get_state("bot"); tgdb.set_state("bot", None); go(9000); assert state("k") == "sending", "nothing changes while it is off"
        tgdb.set_state("bot", b); OB._hold[0] = 9999.0; go(9000); assert state("k") == "unsure", "a pause does not hide it"
        # an answer that could not be written, in the app as it runs
        real = tgdb.db; broken = []
        def db(read=False):
            if broken and not read: raise sqlite3.OperationalError("database is locked")
            return real(read)
        OB._hold[0] = 0.0; f, seen = tele(before=lambda *a: broken.append(1)); q("w"); tgdb.db = db
        try: go(10_000)
        finally: tgdb.db = real
        f, seen = tele(); go(10_100); assert state("w") == "sending"; go(10_121); assert state("w") == "unsure" and seen == []

@t
def unlink_may_name_the_chat():
    with telegram():
        links.link(TIA, 501, None)
        assert links.unlink(TIA, 999) is None and links.chat_of(TIA) == 501 and links.unlink(TIA, 501) == 501 and links.chat_of(TIA) is None
        links.link(TIA, 501, None); assert links.unlink(TIA) == 501 and links.unlink(TIA) is None and links.unlink(TIA, 501) is None

@t
def an_item_no_longer_true_is_dropped():
    with telegram():
        links.link(TIA, 501, None); got = []
        assert OB.VALID(dict(key="any")) is True
        q("a", ref=dict(id="abc", n=1), kind="relief"); q("b")
        with valid(lambda it: got.append(it) or it["key"] != "a"): assert OB.send_due() == dict(sent=1, waiting=0)
        assert state("a") == "dropped" and state("b") == "sent" and [x["key"] for x in got] == ["a", "b"] and len(sent()) == 1
        assert (got[0]["name"], got[0]["kind"], got[0]["ref"], got[0]["state"], got[0]["text"]) == (TIA, "relief", dict(id="abc", n=1), "queued", "A made-up message"), got[0]
        assert got[1]["ref"] is None and OB.told("a")["state"] == "dropped"
        assert OB.send_due(now=9e12) == dict(sent=0, waiting=0) and q("a") is True and OB.send_due()["sent"] == 1 and state("a") == "sent"
        for i, f in enumerate((lambda it: None, lambda it: 0)):                           # only False drops it
            q(f"v{i}")
            with valid(f): assert OB.send_due()["sent"] == 1 and state(f"v{i}") == "sent", i
    with made_up():
        links.link(TIA, 501, None); f, seen = tele(NEVER_LEFT); q("r"); with_send(f, lambda: OB.send_due(now=1000))
        with valid(lambda it: False): with_send(f, lambda: OB.send_due(now=2000))
        assert state("r") == "dropped" and len(seen) == 1, "asked again before another try"

@t
def what_cannot_be_checked_waits_and_is_not_sent():
    class Odd(Exception): pass
    def check(raises):
        """VALID, or the look for the person's chat, raising for the first n tries"""
        left = [raises]
        def f(*a):
            if left[0] > 0: left[0] -= 1; raise kinds[left[0] % len(kinds)](f"{TIA} made up")
            return True
        return f
    kinds = (Odd, ValueError, sqlite3.OperationalError); ladder = (5, 30, 120, 600, 1800)
    with made_up():
        links.link(TIA, 501, None); f, seen = tele(); h = Grab(); KINDS.addHandler(h)
        go = lambda at: with_send(f, lambda: OB.send_due(now=at))
        q("a"); now = 1000
        with valid(check(4)):
            for i in range(4):
                assert go(now) == dict(sent=0, waiting=1) and (state("a"), item("a")["tries"], item("a")["next_at"]) == ("queued", i + 1, now + ladder[i]), i
                go(now + ladder[i] - 1); assert item("a")["tries"] == i + 1; now += ladder[i]
            assert seen == [] and go(now) == dict(sent=1, waiting=0) and len(seen) == 1 and go(9e12)["sent"] == 0 and len(seen) == 1
        q("b"); q("other", text="other"); now = 100_000
        with valid(lambda it: it["key"] != "b" or check(1)()):
            for i in range(5): go(now); assert (state("b"), item("b")["tries"]) == ("queued", i + 1); now += ladder[i]
            assert texts(seen)[1:] == ["other"], "only that one waits"
            go(now); assert state("b") == "failed" and go(9e12) == dict(sent=0, waiting=0) and len(seen) == 2 and q("b") is False
        # the person's chat could not be looked up (the timetable being published): the same
        q("c"); real = links.chat_of; n = [2]
        def chat_of(name):
            if n[0]: n[0] -= 1; raise FileNotFoundError("made up")
            return real(name)
        links.chat_of = chat_of
        try:
            go(1000); assert (state("c"), item("c")["tries"], item("c")["next_at"]) == ("queued", 1, 1005)
            go(1005); assert (state("c"), item("c")["tries"]) == ("queued", 2)
            assert go(1035)["sent"] == 1 and len(seen) == 3
        finally: links.chat_of = real
        KINDS.removeHandler(h); said = [r.getMessage() for r in h.records]
        assert any("Odd" in x for x in said) and any("FileNotFoundError" in x for x in said) and not any("made up" in x or "Tia" in x for x in said), said

@t
def the_chat_is_read_when_it_goes():
    with telegram():
        links.link(TIA, 501, None); q("a"); q("b"); q("c")
        links.link(TIA, 601, None)                                                       # moved to another Telegram
        links.link(HUGO, 501, None)                                                      # whose chat is somebody else's now
        assert OB.send_due(limit=1)["sent"] == 1 and sent() == [(601, "A made-up message")] and item("a")["chat"] == 601
        with record(TIA, off=True): assert OB.send_due() == dict(sent=0, waiting=0) and q("z") is False        # switched off
        assert (state("b"), state("c")) == ("dropped", "dropped") and len(sent()) == 1
        assert q("b") is True and OB.send_due()["sent"] == 1 and sent()[-1][0] == 601, "back: what is still to come goes"
        q("d"); links.unlink(TIA); assert OB.send_due() == dict(sent=0, waiting=0) and state("d") == "dropped" and q("d") is False
        links.link(TIA, 701, None); assert q("d") is True and OB.send_due()["sent"] == 1 and sent()[-1][0] == 701
        q("e")
        with no_pub(RP.fake_pub([dict(name=HUGO, dept="Science")])): assert OB.send_due()["sent"] == 0 and state("e") == "dropped", "not on the timetable any more"
        assert [c for c, x in sent()] == [601, 601, 701]

@t
def nothing_goes_while_the_bot_is_off():
    with made_up():
        links.link(TIA, 501, None); q(); tok = os.environ["TELEGRAM_BOT_TOKEN"]; waits = dict(sent=0, waiting=1); f, seen = tele()
        go = lambda: with_send(f, OB.send_due)
        os.environ.pop("TELEGRAM_BOT_TOKEN"); assert go() == waits
        os.environ["TELEGRAM_BOT_TOKEN"] = "made-up-" + secrets.token_hex(10); assert go() == waits, "another bot's token, not connected"
        os.environ["TELEGRAM_BOT_TOKEN"] = tok; old = os.environ["SECRET_KEY"]
        os.environ["SECRET_KEY"] = secrets.token_hex(16); assert go() == waits
        os.environ["SECRET_KEY"] = old; bot = tgdb.get_state("bot")
        with tgdb.db() as c: c.execute("DELETE FROM state WHERE k='bot'")
        assert go() == waits and seen == [] and state("k") == "queued" and item("k")["tries"] == 0
        tgdb.set_state("bot", bot); q("second")                                           # disconnected between two messages
        def off(*a):
            with tgdb.db() as c: c.execute("DELETE FROM state WHERE k='bot'")
        f, seen = tele(before=off); assert go() == dict(sent=1, waiting=1) and len(seen) == 1 and state("second") == "queued"
        tgdb.set_state("bot", bot); f, seen = tele(); assert go() == dict(sent=1, waiting=0)

@t
def buttons_carry_a_token_under_64_bytes():
    with made_up():
        links.link(TIA, 501, None); f, seen = tele(); extra = dict(absent="Mdm Very Long Name " * 9, n=[1]); SENT_AT = datetime.datetime(2026, 10, 12, 23, 20, tzinfo=datetime.timezone.utc).timestamp()
        with now_is("2026-10-13T07:20:00+08:00"): q(buttons=[[dict(text="✅ Acknowledge", what="ack", id="abc", ckey="Mon|3|S1|" + "x" * 90, who=TIA, extra=extra), dict(text="↩ Request to change", what="change", id="abc", ckey="c")],
                   [dict(text="Open in the app", url="https://ct.example.org/relief"), dict(text="Open here", url="http://localhost:8000/relief")],
                   [dict(text="Not secure", url="http://example.org"), dict(text="Odd", url="javascript:alert(1)")]])
        with_send(f, lambda: OB.send_due(now=5000))
        kb = seen[0][1]["reply_markup"]["inline_keyboard"]
        assert [[b["text"] for b in row] for row in kb] == [["✅ Acknowledge", "↩ Request to change"], ["Open in the app"]], kb
        assert kb[1][0] == dict(text="Open in the app", url="https://ct.example.org/relief") and [sorted(b) for b in kb[0]] == [["callback_data", "text"]] * 2
        data = [b["callback_data"] for b in kb[0]]
        assert all(re.fullmatch(r"b:[A-Za-z0-9_-]{16}", d) and len(d.encode()) < 64 for d in data) and data[0] != data[1], data
        got = {r["token"]: r for r in rows("buttons")}
        assert set(got) == {d[2:] for d in data}
        a, b = got[data[0][2:]], got[data[1][2:]]
        assert (a["name"], a["what"], a["id"], a["ckey"], a["who"], json.loads(a["extra"]), a["until"]) == (TIA, "ack", "abc", "Mon|3|S1|" + "x" * 90, TIA, extra, SENT_AT + 30 * 86400), "30 days from when it was queued"
        assert (b["name"], b["what"], b["id"], b["ckey"], b["who"], json.loads(b["extra"])) == (TIA, "change", "abc", "c", None, None), b
        f, seen = tele(); q("none", buttons=[[dict(text="x", url="http://localhost/relief")]]); q("no"); with_send(f, OB.send_due)
        assert all("reply_markup" not in p for m, p, up in seen) and len(seen) == 2 and len(rows("buttons")) == 2
    with telegram():                                                                       # practice: the same keyboard
        links.link(TIA, 501, None); q(buttons=[[dict(text="Here", url="http://localhost/relief"), dict(text="A", what="ack")]]); OB.send_due()
        assert [b["text"] for b in tg.PRACTICE_LOG[0][1]["reply_markup"]["inline_keyboard"][0]] == ["A"]

@t
def a_retry_keeps_its_tokens():
    with made_up():
        links.link(TIA, 501, None); f, seen = tele(NEVER_LEFT, SLOW(3), DOWN); SENT_AT = datetime.datetime(2026, 10, 12, 23, 20, tzinfo=datetime.timezone.utc).timestamp()
        with now_is("2026-10-13T07:20:00+08:00"): q(buttons=[[dict(text="A", what="ack"), dict(text="B", what="change")]])
        for at in (1000, 2000, 3000, 4000): with_send(f, lambda: OB.send_due(now=at))
        kbs = [p["reply_markup"]["inline_keyboard"] for m, p, up in seen]
        assert len(kbs) == 4 and all(k == kbs[0] for k in kbs) and state("k") == "sent", kbs
        got = rows("buttons"); assert len(got) == 2 and {r["until"] for r in got} == {SENT_AT + 30 * 86400}, "30 days from when it was queued, over every try"
        # buttons taken from another message (a reminder's) get tokens of their own
        q("again", buttons=json.loads(item("k")["buttons"])); f, seen = tele(); with_send(f, OB.send_due)
        assert not {b["callback_data"] for b in seen[0][1]["reply_markup"]["inline_keyboard"][0]} & {b["callback_data"] for b in kbs[0][0]} and len(rows("buttons")) == 4
        # a row pruned while the message waited is there again when it goes
        f, seen = tele(NEVER_LEFT); q("late", buttons=[[dict(text="A", what="ack")]]); with_send(f, lambda: OB.send_due(now=1000))
        with tgdb.db() as c: c.execute("DELETE FROM buttons")
        with_send(f, lambda: OB.send_due(now=9e9)); assert "b:" + rows("buttons")[0]["token"] == seen[-1][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]

@t
def a_long_text_is_cut_at_a_line_end():
    more = "…and more in the app."
    assert OB.MORE == more and OB.LIMIT == 4000
    with made_up():
        links.link(TIA, 501, None)
        def goes(text):
            f, seen = tele(); q("k", text=text); with_send(f, OB.send_due); assert item("k")["text"] == text, "kept as given"
            with tgdb.db() as c: c.execute("DELETE FROM outbox")
            return texts(seen)[0]
        line = "• 🔔 a line of made-up words\n"
        for n in (3999, 4000): assert goes("é" * n) == "é" * n
        long = line * 400; got = goes(long)
        assert len(got) <= 4000 and got.endswith("\n" + more) and long.startswith(got[:-len(more)]) and 4000 - len(got) < len(line), len(got)
        assert goes(long[:4000]) == long[:4000] and goes(long[:4001]) == got
        assert goes("x" * 5000) == "x" * (4000 - len(more)) + more, "no line end: cut where it must"
        assert goes("\n" + "x" * 5000) == ("\n" + "x" * 5000)[:4000 - len(more)] + more
        room = 4000 - len(more)                                   # a line end at the very last place, and one past it
        assert goes("a" * (room - 1) + "\n" + "b" * 100) == "a" * (room - 1) + "\n" + more
        assert goes("a\n" + "a" * (room - 2) + "\n" + "b" * 100) == "a\n" + more

@t
def files_follow_the_message_and_a_failed_file_is_noted():
    with made_up(), work("a.pdf", "b.docx", "c.png") as fs:
        links.link(TIA, 501, None); f, seen = tele(OK_, OK_, REFUSED); q(files=fs)
        assert with_send(f, OB.send_due) == dict(sent=1, waiting=0)
        assert [m for m, p, up in seen] == ["sendMessage"] + ["sendDocument"] * 3 and [p["chat_id"] for m, p, up in seen] == [501] * 4
        assert [up for m, p, up in seen[1:]] == [("document", n, f"made-up {n}".encode()) for n in ("a.pdf", "b.docx", "c.png")], seen
        assert state("k") == "sent" and OB.told("k")["files_failed"] == 1 == OB.told_for("k")["k"]["files_failed"] and item("k")["message_id"] == 1001
        assert with_send(f, OB.send_due)["sent"] == 0 and len(seen) == 4, "never again"
        # slow and network: twice more, with a short wait; unsure, blocked and refused: not again
        for answers, calls, failed, naps in (((SLOW(3),), 2, 0, 1), ((SLOW(3), NEVER_LEFT), 3, 0, 2), ((DOWN, DOWN, DOWN), 3, 1, 2), ((SLOW(9999), SLOW(1)), 1, 1, 0), ((SLOW(20), SLOW(1)), 3, 0, 2),
                                             ((MAY_HAVE,), 1, 1, 0), ((LATE,), 1, 1, 0), ((BLOCKED,), 1, 1, 0), ((REFUSED,), 1, 1, 0), ((NEVER_LEFT, MAY_HAVE), 2, 1, 1)):
            NAPS.clear(); OB._hold[0] = 0.0; f, seen = tele(OK_, *answers); key = f"f{len(rows('outbox'))}"; q(key, files=fs[:1]); with_send(f, OB.send_due)
            assert (len(seen) - 1, OB.told(key)["files_failed"], len(NAPS), state(key)) == (calls, failed, naps, "sent"), (answers, seen, NAPS)
            assert all(0 < n <= 20 for n in NAPS), NAPS
        assert links.chat_of(TIA) == 501, "a file refused unlinks nobody"
        # after one that may or may not have gone the rest are not tried: counted as not gone
        for answers, names, failed in (((MAY_HAVE,), ["a.pdf"], 3), ((OK_, LATE), ["a.pdf", "b.docx"], 2), ((REFUSED,), ["a.pdf", "b.docx", "c.png"], 1), ((OK_, DOWN, MAY_HAVE), ["a.pdf", "b.docx", "b.docx"], 2)):
            f, seen = tele(OK_, *answers); key = f"f{len(rows('outbox'))}"; q(key, files=fs); q(key + "z", text="z"); with_send(f, OB.send_due)
            assert [up[1] if up else p["text"] for m, p, up in seen[1:]] == names + ["z"] and OB.told(key)["files_failed"] == failed, (answers, seen)
        # missing, odd or unreadable: noted, the others go
        for bad in (dict(id="abc123", file="0" * 12, name="x.pdf"), dict(id="../x", file="y", name="z"), dict(name="x.pdf"), dict(id="abc123", file=fs[0]["file"])):
            f, seen = tele(); key = f"f{len(rows('outbox'))}"; q(key, files=[bad, fs[1]]); with_send(f, OB.send_due)
            assert len(seen) == 2 and seen[1][2][1] == "b.docx" and OB.told(key)["files_failed"] == 1 and state(key) == "sent", (bad, seen)
        # a message that did not go takes no file with it
        for answer_ in (REFUSED, MAY_HAVE, LATE, NEVER_LEFT, SLOW(4), BLOCKED):
            OB._doubt.clear(); OB._hold[0] = 0.0; f, seen = tele(answer_); key = f"f{len(rows('outbox'))}"; q(key, files=fs); with_send(f, lambda: OB.send_due(now=1000)); assert len(seen) == 1, answer_
        # the person's Telegram moved while the files were going: the rest do not go to a chat that is another's
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None)
        f, seen = tele(before=lambda m, p, up: up and up[1] == "a.pdf" and links.link(HUGO, 501, None)); q("m", files=fs); with_send(f, OB.send_due)
        assert [up[1] for m, p, up in seen[1:]] == ["a.pdf"] and OB.told("m")["files_failed"] == 2
        # ... or the bot was disconnected, or they were switched off
        for stop in (lambda: tgdb.set_state("bot", None), lambda: AP.update(lambda d: d["people"].__setitem__(TIA, dict(off=True)))):
            wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None)
            with record(TIA): f, seen = tele(before=lambda m, p, up: up and up[1] == "b.docx" and stop()); q("m", files=fs); with_send(f, OB.send_due)
            assert [up[1] for m, p, up in seen[1:]] == ["a.pdf", "b.docx"] and OB.told("m")["files_failed"] == 1
    with telegram(), work("a.pdf") as fs:
        links.link(TIA, 501, None); q(files=fs); OB.send_due()
        assert tg.PRACTICE_LOG[1] == ("sendDocument", dict(chat_id=501)) and OB.told("k")["files_failed"] == 0

@t
def two_runs_never_send_the_same_item():
    with made_up():
        links.link(TIA, 501, None); inside, go = threading.Event(), threading.Event()
        def slow_call(*a): inside.set(); assert go.wait(10)
        f, seen = tele(before=slow_call); q(); out = []
        def both():
            th = threading.Thread(target=lambda: out.append(OB.send_due())); th.start(); assert inside.wait(10)
            assert OB.send_due() == dict(sent=0, waiting=0, busy=True) and OB.send_due(now=9e12)["busy"], "at once, not after it"
            real = OB._busy; OB._busy = threading.Lock()                                  # the other copy of the app: another lock, the same store
            try: assert OB.send_due(now=9e12) == dict(sent=0, waiting=0)
            finally: OB._busy = real
            go.set(); th.join(10)
        with_send(f, both)
        assert out == [dict(sent=1, waiting=0)] and len(seen) == 1 and state("k") == "sent"
        # two threads over many: each goes once
        f, seen = tele(before=lambda *a: time.sleep(0.005))
        for i in range(12): q(f"m{i}", text=str(i))
        ths = [threading.Thread(target=OB.send_due) for _ in range(4)]
        with_send(f, lambda: ([x.start() for x in ths], [x.join() for x in ths]))
        assert sorted(texts(seen), key=int) == [str(i) for i in range(12)]
        # ... and with a lock each, as two copies of the app would have
        f, seen = tele(before=lambda *a: time.sleep(0.005))
        for i in range(12): q(f"o{i}", text=str(i))
        ths = [threading.Thread(target=lambda: OB._run(None, 50)) for _ in range(3)]
        with_send(f, lambda: ([x.start() for x in ths], [x.join() for x in ths]))
        assert sorted(texts(seen), key=int) == [str(i) for i in range(12)], texts(seen)

@t
def another_copy_starting_never_makes_it_go_again():
    """the copies overlap: the new one marks what the old one is sending unsure; the old one's answer then says what it was"""
    for answer_, want in ((OK_, "sent"), (NEVER_LEFT, "unsure"), (SLOW(2), "unsure"), (MAY_HAVE, "unsure"), (REFUSED, "failed"), (BLOCKED, None)):
        with made_up():
            links.link(TIA, 501, None); f, seen = tele(answer_, before=lambda *a: [OB._mark_unsure() for _ in range(2)]); q()
            with_send(f, lambda: OB.send_due(now=1000)); assert state("k") == want, (answer_, state("k"))
            with_send(f, lambda: OB.send_due(now=9e12)); assert len(texts(seen)) == 1

@t
def recover_waits_for_a_run_that_is_going():
    with made_up():
        links.link(TIA, 501, None); inside, go = threading.Event(), threading.Event()
        f, seen = tele(before=lambda *a: (inside.set(), go.wait(10))); q(); out = []
        def both():
            a = threading.Thread(target=OB.send_due); a.start(); assert inside.wait(10)
            b = threading.Thread(target=lambda: out.append(OB.recover())); b.start(); b.join(0.1); assert b.is_alive() and state("k") == "sending"
            go.set(); a.join(10); b.join(10)
        with_send(f, both); assert out == [0] and state("k") == "sent"

@t
def told_for_takes_keys_as_they_are():
    with telegram():
        links.link(TIA, 501, None)
        keys = ["relief:Ms 100%_Tan:c:1", "relief:Ms 100%_Tan:c:1:r2", "relief:Ms 100xyTan:c:1", "Relief:Ms 100%_Tan:c:1", "relief:é'\"\\:1", "report:2026-10-13"]
        with now_is("2026-10-13T07:20:00+08:00"): [q(k, ref=dict(k=k)) for k in keys]
        got = OB.told_for("relief:Ms 100%_")
        assert set(got) == set(keys[:2]) and got[keys[0]] == dict(state="queued", at="2026-10-13T07:20:00+08:00", name=TIA, ref=dict(k=keys[0]), files_failed=0), got
        assert set(OB.told_for("relief:")) == {k for k in keys if k.startswith("relief:")} and set(OB.told_for("")) == set(keys) and OB.told_for("%") == {} == OB.told_for("nothing")
        assert set(OB.told_for("relief:é'\"\\")) == {keys[4]}
        assert OB.told("relief:") is None and OB.told(keys[1]) == got[keys[1]]
        with now_is("2026-10-13T07:31:00+08:00"): OB.send_due()
        assert OB.told_for("relief:")[keys[0]]["at"] == "2026-10-13T07:31:00+08:00" and OB.told(keys[0])["state"] == "sent"

@t
def messages_are_spaced():
    with made_up():
        links.link(TIA, 501, None); at = []; f, seen = tele(before=lambda *a: at.append(time.monotonic()))
        for i in range(4): q(f"k{i}")
        q("gone", HUGO); OB.SPACING, OB._sleep = 0.05, time.sleep
        try: with_send(f, OB.send_due)
        finally: OB.SPACING, OB._sleep = 0, NAPS.append
        assert len(at) == 4 and all(b - a >= 0.049 for a, b in zip(at, at[1:])), at

@t
def old_items_and_buttons_are_pruned_only_when_asked():
    with telegram():
        links.link(TIA, 501, None); now = datetime.datetime(2026, 11, 22, 9, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        ago = lambda days: (now - datetime.timedelta(days=days)).isoformat(timespec="seconds")
        for s in ("queued", "sending", "sent", "failed", "unsure", "dropped"):
            for days in (401, 399): q(f"{s}{days}"); put(f"{s}{days}", state=s, at=ago(days), next_at=9e12)
        with tgdb.db() as c: [c.execute("INSERT INTO buttons(token, name, until) VALUES (?, ?, ?)", (f"t{d}", TIA, now.timestamp() + d)) for d in (-1, 1)]
        OB.send_due(); q("more"); OB.recover(); put("sending401", state="sending"); put("sending399", state="sending")
        assert len(rows("outbox")) == 13 and len(rows("buttons")) == 2, "nothing else prunes"
        OB.prune(now=now.timestamp())
        left = {r["key"] for r in rows("outbox")}
        assert left == {"queued401", "sending401", "more"} | {s + "399" for s in ("queued", "sending", "sent", "failed", "unsure", "dropped")}, left
        assert [r["token"] for r in rows("buttons")] == ["t1"]

@t
def the_sender_recovers_first_then_sends_and_never_dies():
    h, lg = Grab(), logging.getLogger("relief.telegram"); lg.addHandler(h)
    real, order = (OB.send_due, OB.recover, OB.prune), []
    with telegram():
        links.link(TIA, 501, None); q("half"); put("half", state="sending"); q("a", text="To go")
        def wait_for(f):
            for _ in range(500):
                if f(): return True
                time.sleep(0.01)
        def boom(*a, **k): order.append("boom"); raise ValueError(f"{TIA} 501 made-up private line")
        def recover(): order.append("recover"); return real[1]()
        def send_due(*a, **k): order.append("send"); return real[0](*a, **k)
        OB.recover, OB.send_due = boom, send_due
        th = None
        try:
            th = OB.start(every=0.02)
            assert th.name == "relief-telegram" and th.daemon and OB.start(every=0.02) is th, "started once"
            assert wait_for(lambda: len(order) > 2) and set(order) == {"boom"} and tg.PRACTICE_LOG == [], "nothing goes before it has recovered"
            OB.recover = recover; OB.prune = boom
            assert wait_for(lambda: state("a") == "sent") and state("half") == "unsure" and order.count("recover") == 1 and order.index("recover") < order.index("send")
            OB.send_due = boom; n = len(order); assert wait_for(lambda: len(order) > n + 2) and th.is_alive()
            OB.send_due = send_due; q("b"); OB.wake(); assert wait_for(lambda: state("b") == "sent")
        finally:
            OB._stop.set(); OB.wake(); th and th.join(5); OB.send_due, OB.recover, OB.prune = real; lg.removeHandler(h)
        assert not th.is_alive() and OB._busy.acquire(blocking=False); OB._busy.release()
        # woken: at once, long before its time
        tg.PRACTICE_LOG.clear(); th = OB.start(every=60)
        try:
            assert wait_for(lambda: not OB._busy.locked()); time.sleep(0.05); q("c"); began = time.monotonic(); OB.wake()
            assert wait_for(lambda: state("c") == "sent") and time.monotonic() - began < 4
        finally: OB._stop.set(); OB.wake(); th.join(5)
        assert not th.is_alive() and [x for c, x in sent()] == ["A made-up message"]
    said = " ".join(r.getMessage() for r in h.records)
    assert "ValueError" in said and all(r.exc_info is None for r in h.records)
    for bad in (TIA, "501", "private"): assert bad not in said, said

@t
def the_sender_starts_only_with_the_jobs_and_a_token():
    assert not any(x.name == "relief-telegram" for x in threading.enumerate())
    code = "import threading, app; print(sorted(x.name for x in threading.enumerate() if x.name.startswith('relief')))"
    def go(jobs, token):
        env = dict(os.environ, DATA_DIR=tempfile.mkdtemp(), RELIEF_JOBS=jobs, TELEGRAM_BOT_TOKEN=token)
        return subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    cases = [("on", "practice", ["relief-telegram", "relief-ticker"]), ("on", "", ["relief-ticker"]), ("", "practice", [])]
    for p, (jobs, token, want) in zip([go(j, k) for j, k, w in cases], cases):
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0 and out.strip().splitlines()[-1] == str(want), (jobs, token, out[-300:], err[-300:])

@t
def nothing_private_is_logged_by_the_sender():
    h, root = Grab(), logging.getLogger(); old = root.level; root.addHandler(h); KINDS.addHandler(h); root.setLevel(logging.DEBUG)
    try:
        with made_up(), work("secret-name.pdf") as fs:
            tok = os.environ["TELEGRAM_BOT_TOKEN"]; links.link(TIA, 987650077, None); real = tgdb.db
            for i, a in enumerate((OK_, BLOCKED, REFUSED, DOWN, SLOW(3), NEVER_LEFT, MAY_HAVE, ValueError(f"{TIA} {tok}"))):
                links.link(TIA, 987650077, None); OB._hold[0] = 0.0; f, seen = tele(a, MAY_HAVE)
                q(f"relief:{TIA}:{i}", text="a private line", files=[dict(name="secret-name.pdf")] + fs, buttons=[[dict(text="private label", what="ack", extra=dict(p="private extra"))]])
                with_send(f, lambda: OB.send_due(now=1000)); assert "a private line" in texts(seen), a
            def boom(it): raise RuntimeError(f"{TIA} a private line {tok}")
            q(f"relief:{TIA}:y")
            with valid(boom): with_send(tele()[0], lambda: OB.send_due(now=1000))
            q(f"relief:{TIA}:z"); put(f"relief:{TIA}:z", buttons='[[{"what": "a private line"}]]'); with_send(tele()[0], lambda: OB.send_due(now=1000)); assert state(f"relief:{TIA}:z") == "failed"
            real_unlink = links.unlink
            def no_unlink(name, chat=None): raise LookupError(f"{name} {chat} {tok}")
            links.unlink = no_unlink; q(f"relief:{TIA}:w")
            try: with_send(tele(BLOCKED)[0], lambda: OB.send_due(now=1000))
            finally: links.unlink = real_unlink
            q(f"relief:{TIA}:x")
            def no_store(read=False): raise sqlite3.OperationalError(f"{TIA} a private line") if read is False else None
            tgdb.db = lambda read=False: real(read) if read else no_store()
            try: with_send(tele()[0], lambda: OB.send_due(now=9e12))
            finally: tgdb.db = real
        mine = "\n".join(r.getMessage() for r in h.records if r.name.startswith("relief"))
        for want in ("RuntimeError", "OperationalError", "KeyError", "LookupError", "network", "unsure", "blocked", "slow", "refused"): assert want in mine, (want, mine)
        everything = "\n".join(r.getMessage() + str(r.exc_info or "") + str(r.args or "") for r in h.records)
        for bad in ("private", TIA, "Tia", "98765", tok, "secret-name", "relief:", tg.hook_secret() or "x" * 64): assert bad not in everything, bad
    finally: root.removeHandler(h); KINDS.removeHandler(h); root.setLevel(old)

# ---- Task 4: what to tell, and telling it ----
import shutil, types, urllib.parse  # noqa: E402
from relief import cover as CV, fill as FL, free as FR, lessons as LS, pick as PK, settings as RS, words as WO  # noqa: E402
from ttgen.spec import day_names  # noqa: E402

EVE, SAM, RUTH, MAYA, BUSY, LEE = "Ms Evelyn Koh", "Mr Sam Tan", "Ms Ruth Goh", "Ms Maya Lee", "Mr Busy Chan", "Mr Team Lee"
DAYS = day_names(2)
TUE, WED, FRI = [next(d for d in DAYS if d.startswith("Even") and d.split()[-1].startswith(x)) for x in ("Tue", "Wed", "Fri")]
TERM = dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[])
BASE = "https://relief.example.org"

def lesson(day, p, n, classes, subject, teachers, group="", room="2-05"):
    return dict(d=DAYS.index(day), p=p, n=n, classes=classes, subject=subject, group=group, teachers=teachers, room=room, level="Sec 1")

# periods of 30 minutes from 08:00: P3-P5 is 09:00-10:30, P6-P7 10:30-11:30. Today is Mon 12 Oct 2026 unless a test says not
SCHOOL = RP.fake_pub([dict(name=EVE, dept="Science"), dict(name=SAM, dept="Science", short="Mr Tan"), dict(name=RUTH, dept="Science"), dict(name=MAYA, dept="Mathematics", short="Ms Lee"),
                      dict(name=BUSY, dept="Mathematics"), dict(name=HUGO, dept="Science", role="HOD"), dict(name=TEAM, dept="Mathematics"), dict(name=LEE, dept="Mathematics"),
                      dict(name=ROSA, dept="English"), dict(name=OFFIE, dept="English")],
                     [lesson(TUE, 2, 3, ["1C"], "Science", [EVE], room=""), lesson(TUE, 5, 2, ["1A", "1B"], "Science", [EVE], group="G2"), lesson(TUE, 8, 1, ["5A"], "Art", [EVE, BUSY]),
                      lesson(WED, 1, 1, ["2A"], "Science", [EVE]), lesson(FRI, 0, 2, ["1A"], "Art", [EVE]), lesson(TUE, 0, 1, ["2A"], "Science", [SAM]),
                      lesson(TUE, 6, 1, ["3B"], "Physics", [RUTH]), lesson(TUE, 6, 1, ["4A"], "Maths", [BUSY])])
SCHOOL["model"]["school"].update(start_time="08:00", period_minutes=30)
SCHOOL["model"]["NP"] = 12
SCHOOL["model"]["setup"]["rules"] = []
AP.update(lambda d: d["people"].update({LEE: dict(extras=dict(relief=True, exams=None, admin=False))}))
os.makedirs(os.path.dirname(RS.PATH), exist_ok=True)
clock = types.SimpleNamespace(now=None)
CHATS = {n: 811 + i for i, n in enumerate((EVE, SAM, RUTH, MAYA, BUSY, HUGO, TEAM, LEE, ROSA))}
def at(hm, day=12): clock.now = f"2026-10-{day:02d}T{hm if len(hm) > 5 else hm + ':00'}+08:00"
def day_key(p, date): return next(x["key"] for x in LS.on_date(SCHOOL, TERM, EVE, date) if x["p"] == p)
K2, K5, K8 = [day_key(p, datetime.date(2026, 10, 13)) for p in (2, 5, 8)]
KW, KF = day_key(1, datetime.date(2026, 10, 14)), day_key(0, datetime.date(2026, 10, 16))

@contextlib.contextmanager
def school(*linked, since="2026-10-12T08:00:00+08:00", base=BASE, **settings):
    """the made-up school at 09:00 on Mon 12 Oct 2026 with no absences, its bot connected at `since` and these people linked"""
    old = LS.today, absences._now, FL.SYNC, FL.ON, PK.CALL
    shutil.rmtree(absences.DIR, ignore_errors=True)
    store.write_json(RS.PATH, dict(dict(calendar=TERM), **settings))
    LS.today, absences._now = lambda: datetime.date.fromisoformat(clock.now[:10]), lambda: clock.now
    FL.SYNC, FL.ON, PK.CALL = True, False, lambda data: dict(label="Teacher 1", reason="Teacher 1 is free then.")
    at("09:00")
    try:
        with telegram(), no_pub(SCHOOL):
            tgdb.set_state("bot", dict(username="practice_bot", base=base, at=since, key=digest(tg.hook_secret())))
            for n in linked: links.link(n, CHATS[n], None)
            yield
    finally:
        LS.today, absences._now, FL.SYNC, FL.ON, PK.CALL = old
        shutil.rmtree(absences.DIR, ignore_errors=True)
        os.remove(RS.PATH)

def absent(teacher=EVE, by=None, lessons=(), dates=("2026-10-13",), **kw):
    """an absence asked by the teacher (by None), or planned by by with the relief teachers in lessons -> its id"""
    d = dict(dict(teacher=teacher, dates=list(dates), periods=None, reason="Medical", reason_text="", remarks="", reporting_officer=ROSA, lessons=list(lessons)), **kw)
    return absences.new(d, SCHOOL, by or teacher, "planned" if by else "asked", may_choose=bool(by))["id"]

def rs(): return RS.load(SCHOOL)
def give(i, ckey, who_, by=TEAM): return CV.change(i, ckey, who_, by, SCHOOL, rs())          # chosen and approved in one
def covered(i, ckey): r = absences.load(i); return (r, *CV.find(r, ckey))
def approved_at(i, ckey): return covered(i, ckey)[2]["approved"]["at"]
def new_pick(i, ckey, who_, reason="Teaches Science and is free then."):
    return CV.set_pick(i, ckey, dict(who=who_, by="ai", reason=reason, at=clock.now), SCHOOL, rs(), into="change")
def outs(kind=None, name=None): return [r for r in rows("outbox") if kind in (None, r["kind"]) and name in (None, r["name"])]
def buttons_of(r): return [[{k: v for k, v in b.items() if k != "token"} for b in row] for row in json.loads(r["buttons"])]
def told_of(kind=None, name=None): return [(r["kind"], r["name"]) for r in outs(kind, name)]
def send(): return OB.send_due()["sent"]
def swept(): n = TE.sweep(); send(); return n                                              # a sweep, and what it queued sent
def said(name): return [x for c, x in sent(CHATS[name])]
def change_record(i, f):
    r = absences.load(i); f(r); absences._save(r)
def quoted(x): return urllib.parse.quote(x, safe="")
def call(name, method, url, body=None, code=200):
    r = getattr(who(name), method)(url, json=body or {})
    assert r.status_code == code, (r.status_code, r.get_data(as_text=True)[:300])
    return r.get_json()
def on_cover(name, i, ckey, what, body=None, code=200): return call(name, "put" if what == "relief" else "post", f"/api/relief/absences/{i}/covers/{quoted(ckey)}/{what}", body, code)
def on_lesson(name, i, key, what, body=None, code=200): return call(name, "put" if what in ("relief", "work") else "post", f"/api/relief/absences/{i}/lessons/{quoted(key)}/{what}", body, code)
def dues(records=None, told=None, reach=None, **kw):
    """due, with what a sweep would pass it"""
    now = kw.pop("now", clock.now)
    return TE.due(SCHOOL, rs(), absences.all_records() if records is None else records, now, links.reachable() if reach is None else reach,
                  OB.told_for("") if told is None else told, kw.pop("since", "2026-10-12T08:00:00+08:00"), **dict(dict(team=(TEAM, LEE), base=BASE), **kw))

RELIEF_K5 = "🔔 Relief for you · Tue 13 Oct\n1A, 1B Science (G2) · P6–P7 · 10:30–11:30\nRoom 2-05\nFor Ms Evelyn Koh\nNo work set yet: look in Reliefs I'm covering."
MOVED_K5 = "✔ The relief team has moved 1A, 1B Science (G2) P6–P7 on Tue 13 Oct to someone else. You're free then."
GONE_K5 = "❌ No longer needed: 1A, 1B Science (G2) P6–P7 (10:30) on Tue 13 Oct. You're free then."
KEPT_K5 = "The relief team has kept 1A, 1B Science (G2) P6–P7 on Tue 13 Oct with you."
ASK_K5 = "↩ Request to change\nMr Sam Tan · 1A, 1B Science (G2) · P6–P7 (10:30) on Tue 13 Oct\n“A parent meeting”\n"
PLANNED_EVE = "📋 Relief planned for you\nTue 13 Oct · whole day\nPlanned by Mr Hugo Ong\n2 lessons will be covered.\nPlease acknowledge and set work for the relief teachers."
REMIND_EVE = "⏰ Reminder: please acknowledge your relief for Tue 13 Oct and set work."
OFFICER_EVE = "Ms Evelyn Koh is away on Tue 13 Oct (whole day): Medical.\nRelief is being arranged."
CANCELLED_EVE = "❌ Cancelled by {}: Ms Evelyn Koh's absence on Tue 13 Oct. Its reliefs are no longer needed."

@t
def every_text_is_the_plans():
    plan = open(os.path.join(ROOT, "docs", "superpowers", "plans", "2026-11-22-relief-stage-4-telegram.md"), encoding="utf-8").read()
    pick = dict(who="{name}", reason="{pick reason}")
    got = TE.relief_text("{day}", "{lesson}", "{periods}", "{time}", "{room}", "{absent}", dict(text="{text}", link="{link}", files=[1, 2])).replace("Files: 2", "Files: {n}")
    got += "\n" + TE.planned_text("{days}", "{whole day or periods}", "{by}", 4).replace("4 lessons", "{n} lessons") + "\n" + TE.remind_text("{days}")
    got += "\n" + TE.officer_text("{absent}", "{days}", "{whole day or periods}", "{kind}") + "\n" + TE.cancelled_text("{by}", "{absent}", "{days}")
    got += "\n" + TE.gone_text("{lesson}", "{periods}", "{start}", "{day}") + "\n" + TE.moved_text("{lesson}", "{periods}", "{day}") + "\n" + TE.kept_text("{lesson}", "{periods}", "{day}")
    got += "\n" + TE.ask_text("{who}", "{lesson}", "{periods}", "{start}", "{day}", "{why}", pick=pick)
    got += "\n" + TE.ask_text("", "", "", "x", "", "", nobody=True).splitlines()[-1] + "\n" + TE.ask_text("", "", "", "x", "", "").splitlines()[-1]
    got += "\n" + TE.relief_text("", "x", "", "", "", "", {}).splitlines()[-1]
    for line in got.splitlines(): assert f"`{line}`" in plan, line
    assert len(got.splitlines()) == 7 + 5 + 1 + 2 + 1 + 1 + 1 + 1 + 5 + 3, got
    for label in ("✅ Acknowledge", "↩ Request to change", "✅ Acknowledge and set work", "❌ Not needed: cancel", "Open in the app"): assert f"`{label}`" in plan
    # whole, in order, with made-up words
    assert TE.relief_text("Tue 13 Oct", "2B Science", "P9–P11", "10:40–11:40", "2-06", EVE, dict(text="Notes, chapter 6.", link="https://x.org/a", files=[dict(id="a"), dict(id="b")])) == \
        "🔔 Relief for you · Tue 13 Oct\n2B Science · P9–P11 · 10:40–11:40\nRoom 2-06\nFor Ms Evelyn Koh\nWork from Ms Evelyn Koh: Notes, chapter 6.\nLink: https://x.org/a\nFiles: 2, sent after this message."
    assert TE.relief_text("Tue 13 Oct", "2B Science", "P9", "", "", EVE, {}) == "🔔 Relief for you · Tue 13 Oct\n2B Science · P9\nFor Ms Evelyn Koh\nNo work set yet: look in Reliefs I'm covering."
    for work, last in ((dict(text="", link="https://x.org/a", files=[]), ["Link: https://x.org/a"]), (dict(files=[1]), ["Files: 1, sent after this message."])):   # work, with nothing typed: it is not said that none is set
        assert TE.relief_text("d", "l", "P1", "", "", EVE, work).splitlines()[2:] == ["For Ms Evelyn Koh"] + last
    assert TE.planned_text("Tue 13 Oct", "whole day", HUGO, 2) == PLANNED_EVE and "\n1 lesson will be covered.\n" in TE.planned_text("d", "whole day", HUGO, 1)
    assert TE.remind_text("Tue 13 Oct") == REMIND_EVE and TE.officer_text(EVE, "Tue 13 Oct", "whole day", "Medical") == OFFICER_EVE
    assert TE.cancelled_text(HUGO, EVE, "Tue 13 Oct") == CANCELLED_EVE.format(HUGO)
    assert TE.gone_text("1A, 1B Science (G2)", "P6–P7", "10:30", "Tue 13 Oct") == GONE_K5 and "Art P1 on Tue" in TE.gone_text("Art", "P1", "", "Tue")
    assert TE.moved_text("1A, 1B Science (G2)", "P6–P7", "Tue 13 Oct") == MOVED_K5 and TE.kept_text("1A, 1B Science (G2)", "P6–P7", "Tue 13 Oct") == KEPT_K5
    ask = lambda **k: TE.ask_text(SAM, "1A, 1B Science (G2)", "P6–P7", "10:30", "Tue 13 Oct", "A parent meeting", **k)
    assert ask(pick=dict(who=MAYA, reason="Is free then.")) == ASK_K5 + "New pick: Ms Maya Lee\nIs free then." and ask(pick=dict(who=MAYA, reason="")) == ASK_K5 + "New pick: Ms Maya Lee"
    assert ask(nobody=True) == ASK_K5 + "Nobody else is free then: choose someone in the app." and ask() == ASK_K5 + "No new pick yet: open the app."

@t
def the_words_are_the_pages_own():
    assert (WB._class_group, WB._periods_text, WB._times, WB._nudge, WB.ENTIRE) == (WO.class_group, WO.periods_text, WO.times, FL.nudge, "Entire Class"), "web's names are the same functions"
    x = dict(key="k", date="2026-10-13", p=8, n=3, start="12:00", end="13:30", classes=["1B", "1A"], subject="Maths", group="G1")
    assert WO.class_group(x) == "1B, 1A Maths (G1)" and WO.class_group(dict(x, group="Entire Class")) == "1B, 1A Maths" and WO.class_group(dict(subject="Art")) == "Art" and WO.class_group({}) == ""
    assert WO.periods_text(x) == "P9–P11" and WO.periods_text(dict(p=0, n=1)) == "P1" and WO.periods_text(dict(p=2)) == "P3"
    assert WO.times(SCHOOL, x, x) == ("12:00", "13:30") and WO.times(None, dict(p=1), {}) == ("", "")
    part = dict(p=9, n=2); assert WO.times(SCHOOL, dict(x, parts=[part]), part) == ("12:30", "13:30") and WO.times(None, dict(x, parts=[part]), part) == ("", "")
    assert WO.day("2026-10-13") == "Tue 13 Oct" and WO.day("2026-10-03T09:00:00+08:00") == "Sat 3 Oct"
    assert WO.days(dict(dates=["2026-10-13", "2026-10-14"])) == "Tue 13 Oct, Wed 14 Oct" and WO.days({}) == ""
    assert [WO.away(dict(periods=v)) for v in (None, [0, 2], [3, 3], [0, 8])] == ["whole day", "P1–P3", "P4", "P1–P9"] and WO.away({}) == "whole day"

@t
def the_module_stands_alone():
    """tell imports neither web nor bot nor tgweb (they import it), and sets the queue's check at import"""
    code = "import sys; import relief.tell, relief.outbox as o; print([m for m in ('relief.web', 'relief.bot', 'relief.tgweb', 'flask') if m in sys.modules], o.VALID is relief.tell.still_true, relief.tell.SYNC)"
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=dict(os.environ, DATA_DIR=tempfile.mkdtemp()), capture_output=True, text=True)
    assert p.stdout.strip() == "[] True False", (p.stdout, p.stderr[-400:])
    assert OB.VALID is TE.still_true and TE.still_true(dict(key="any")) is True and TE.still_true(dict(key="x", kind="exam-duty", ref=None)) is True
    assert {"relief", "planned", "remind", "officer", "ask", "askpick"} == set(TE.CHECKS), "report, clear and weekly (Tasks 6 and 7) are added here"

# ---- the hooks: fill.AFTER, tell.soon, and who asks for a sweep
@t
def what_runs_after_a_tick_and_a_run_asked_for():
    log, h = logging.getLogger("relief.fill"), Grab(); log.addHandler(h); prop, log.propagate = log.propagate, False
    real_run, seen = FL._run, []
    def hook_(): seen.append((FL._busy.locked(), FL._going[0]))
    def boom(): raise RuntimeError(f"{SAM} made up")
    try:
        with school():
            assert FL.AFTER == [], "nothing is hooked in a test"
            FL.AFTER.extend([hook_, boom, hook_])
            FL.run(); assert seen == [], "never in run itself"
            assert FL.tick() == dict(picked=0, nobody=0) and seen == [(False, 0)] * 2, "both, whatever the one between them did, with nothing held"
            FL.soon(force=True); assert seen == [(False, 0)] * 4 and len(h.records) == 2
            FL.SYNC = False; FL.soon(force=True); ths = [x for x in threading.enumerate() if x.name == "relief-fill"]; [x.join(10) for x in ths]; assert len(seen) == 6
            def bad(*a): raise ValueError(f"{SAM} made up")
            FL._run = bad; h.records.clear()
            assert FL.tick() is None and len(seen) == 8, "a run that failed too"
            FL.SYNC = True
            try: FL.soon(force=True); raise AssertionError("inline, a failed run raises as it did")
            except ValueError: pass
            assert len(seen) == 10 and not FL._busy.locked() and FL._going[0] == 0
            FL._run = real_run
            with FL._busy: assert FL.tick()["busy"] is True
            assert len(seen) == 12, "a tick that found another run going: the messages do not wait for the model"
    finally: FL._run = real_run; FL.AFTER.clear(); log.removeHandler(h); log.propagate = prop
    lines = [r.getMessage() for r in h.records]
    assert any("RuntimeError" in x for x in lines) and not any(SAM in x or "made up" in x for x in lines) and all(r.exc_info is None for r in h.records), lines

@t
def the_sweep_is_hooked_only_with_the_jobs_on():
    code = "import app; from relief import fill, tell; print([f is tell.sweep for f in fill.AFTER])"
    def go(jobs):
        env = dict(os.environ, DATA_DIR=tempfile.mkdtemp(), RELIEF_JOBS=jobs, TELEGRAM_BOT_TOKEN="")
        return subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for p, want in zip([go("on"), go(""), go("off")], ["[True]", "[]", "[]"]):
        out, err = p.communicate(timeout=120); assert p.returncode == 0 and out.strip().splitlines()[-1] == want, (want, out[-200:], err[-300:])

@contextlib.contextmanager
def stand_in(module, name, f):
    old = getattr(module, name); setattr(module, name, f)
    try: yield
    finally: setattr(module, name, old)

@t
def a_sweep_asked_for_while_one_runs_runs_once_more_after():
    def ended():
        for x in [x for x in threading.enumerate() if x.name == "relief-tell"]: x.join(10)
        assert not any(x.name == "relief-tell" for x in threading.enumerate())
    with school(SAM):
        TE.SYNC = False
        try:
            inside, let, ran, now_ = threading.Event(), threading.Event(), [], []
            def slow(*a, **k):
                now_.append(1); ran.append((threading.current_thread().name, threading.current_thread().daemon, len(now_))); inside.set(); assert let.wait(10); now_.pop()
                return []
            with stand_in(TE, "due", slow):
                assert TE.soon() is True and inside.wait(10)
                for _ in range(8): assert TE.soon() is True
                direct = threading.Thread(target=TE.sweep); direct.start(); time.sleep(0.05)      # the ticker's, meanwhile: it waits
                assert len(ran) == 1 and direct.is_alive()
                let.set(); ended(); direct.join(10)
                assert len(ran) == 3 and [x[0] for x in ran].count("relief-tell") == 2, ran
                assert all(x[2] == 1 for x in ran), "never two at once"
                assert [x[1] for x in ran if x[0] == "relief-tell"] == [True, True]
                TE.soon(); ended(); assert len(ran) == 4, "and again later"
            # a thread that cannot be had never fails the save that asked, and the next one asked for runs
            def refuse(self): raise RuntimeError("can't start new thread")
            real = threading.Thread.start; threading.Thread.start = refuse
            try: assert TE.soon() is False
            finally: threading.Thread.start = real
            with stand_in(TE, "due", lambda *a, **k: ran.append(1) or []): assert TE.soon() is True; ended()
            assert len(ran) == 5
        finally: TE.SYNC = True

@t
def soon_and_sweep_do_nothing_while_the_bot_is_off():
    n = []
    with school(SAM), stand_in(TE, "due", lambda *a, **k: n.append(1) or []):
        assert TE.soon() is True and TE.sweep() == 0 and len(n) == 2
        b = tgdb.get_state("bot"); tgdb.set_state("bot", None); assert TE.soon() is False and TE.sweep() == 0 and len(n) == 2, "not connected"
        tgdb.set_state("bot", b); os.environ.pop("TELEGRAM_BOT_TOKEN")
        opened = []
        with stand_in(tgdb, "db", lambda read=False: opened.append(1)): assert TE.soon() is False and TE.sweep() == 0 and opened == [], "no token: not even the store is opened"
        os.environ["TELEGRAM_BOT_TOKEN"] = "practice"
        with no_pub(): assert TE.sweep() == 0 and len(n) == 2, "nothing published (a publish swaps folders): the next one"
        with broken_accounts(): assert TE.sweep() == 0 and len(n) == 2, "nobody can be reached"
        links.unlink(SAM); assert TE.sweep() == 0 and len(n) == 2, "nobody linked"

@t
def the_sweep_never_raises_and_logs_its_kind_alone():
    h = Grab(); KINDS.addHandler(h)
    def boom(*a, **k): raise LookupError(f"{SAM} a private line")
    try:
        with school(SAM):
            i = absent(by=HUGO); give(i, K5, SAM)
            for module, name in ((TE, "due"), (store, "published"), (links, "reachable"), (absences, "all_records"), (RS, "load"), (links, "connected"), (OB, "told_for"), (AP, "staff")):
                h.records.clear()
                with stand_in(module, name, boom): assert TE.sweep() == 0 and TE.soon() in (True, False), name
                assert [r.getMessage() for r in h.records] and all("LookupError" in r.getMessage() and "private" not in r.getMessage() and SAM not in r.getMessage() and r.exc_info is None for r in h.records), name
            assert outs() == [] and not absences._LOCK.locked()
            # one message that cannot be queued never stops the rest; the store failing ends the sweep, and the next one queues them
            give(i, K2, SAM); real = OB.queue
            with stand_in(OB, "queue", lambda key, *a, **k: boom() if K2 in key else real(key, *a, **k)): assert TE.sweep() == 1
            assert [r["ref"] and json.loads(r["ref"])["ckey"] for r in outs()] == [K5] and h.records and not any("private" in r.getMessage() for r in h.records)
            def locked(*a, **k): tries.append(1); raise sqlite3.OperationalError("database is locked")
            tries = []; links.link(ROSA, CHATS[ROSA], None)
            with stand_in(OB, "queue", locked): assert TE.sweep() == 0 and len(tries) == 1
            assert TE.sweep() == 2 and len(outs()) == 3; links.unlink(ROSA)
            # an absence that cannot be read as one (changed by hand) is passed over: the others' messages go
            j = absent(dates=["2026-10-16"]); give(j, KF, RUTH); links.link(RUTH, CHATS[RUTH], None)
            for n, odd in enumerate((dict(id="odd1", teacher=EVE, dates="x", lessons=[5]), dict(id="odd2", dates=[5, None]), dict(id="odd3", teacher=["x"], how="planned", by=[], at="x", dates=["2026-10-13"], lessons=[dict(date="2026-10-13")]),
                                     dict(id="odd4", teacher=SAM, dates=["2026-10-13"], cancelled=5, lessons=None), dict(id="odd5", teacher=SAM, dates=["2026-10-13"], reporting_officer=["x"], lessons=[dict(date="2026-10-13", key="k", p="a private word", needed=True)]))):
                absences._save(odd)
            h.records.clear(); assert TE.sweep() == 1 and told_of(name=RUTH) == [("relief", RUTH)] and h.records
            assert not any("private" in r.getMessage() or "odd" in r.getMessage() for r in h.records)
    finally: KINDS.removeHandler(h)

@t
def every_save_asks_for_a_sweep_once_after_its_history_entry():
    asked, fails = [], []
    def spy():
        asked.append((len(entries()), absences._LOCK.locked()))
        if fails: raise RuntimeError("made up")
    with school(), stand_in(TE, "soon", spy):
        def after(f, n=1):
            del asked[:]; before = len(entries()); got = f()
            assert len(asked) == n and all(x == (before + n, False) for x in asked), (asked, before)
            return got
        body = dict(teacher=EVE, dates=["2026-10-13"], periods=None, reason="Medical", reporting_officer=ROSA, lessons=[])
        i = after(lambda: call(HUGO, "post", "/api/relief/absences", body))["id"]
        after(lambda: call(EVE, "post", f"/api/relief/absences/{i}/acknowledge"))
        after(lambda: call(EVE, "post", f"/api/relief/absences/{i}/acknowledge", code=400), 0)                  # refused: nothing saved
        after(lambda: on_lesson(EVE, i, K5, "work", dict(text="Read", link="", files=[], known=[])))
        after(lambda: on_lesson(HUGO, i, K5, "relief", dict(relief=SAM)))
        after(lambda: on_lesson(EVE, i, K8, "needed")); after(lambda: on_lesson(EVE, i, K8, "not-needed", dict(why="No")))
        after(lambda: on_cover(TEAM, i, K5, "approve", dict(who=MAYA), code=400), 0); after(lambda: on_cover(EVE, i, K5, "approve", dict(who=SAM), code=403), 0)
        after(lambda: on_cover(TEAM, i, K5, "approve", dict(who=SAM)))
        after(lambda: on_cover(SAM, i, K5, "acknowledge")); after(lambda: on_cover(SAM, i, K5, "acknowledge"), 0)   # the second saves nothing
        after(lambda: on_cover(MAYA, i, K5, "acknowledge", code=403), 0)
        after(lambda: on_cover(SAM, i, K5, "ask-change", dict(why="A meeting"))); after(lambda: on_cover(TEAM, i, K5, "keep"))
        after(lambda: on_cover(TEAM, i, K5, "relief", dict(relief=MAYA)))
        after(lambda: on_lesson(TEAM, i, K2, "split", dict(at=3))); after(lambda: on_lesson(TEAM, i, K2, "join"))
        on_lesson(HUGO, i, K2, "relief", dict(relief=SAM)); rows_ = [dict(id=i, ckey=K2, who=SAM)]
        after(lambda: call(TEAM, "post", "/api/relief/today/approve-all", dict(date="2026-10-13", covers=rows_)))
        after(lambda: call(TEAM, "post", "/api/relief/today/approve-all", dict(date="2026-10-13", covers=rows_)), 0)   # skipped: nothing saved
        fails.append(1); errs = []                                                          # asking never fails the save
        with stand_in(A.app.logger, "error", lambda *a: errs.append(a)): after(lambda: call(HUGO, "post", f"/api/relief/absences/{i}/cancel", dict(why="Better")))
        assert absences.load(i)["cancelled"] and [x[1:] for x in errs] == [("RuntimeError",)], errs

@t
def linking_asks_for_a_sweep_once():
    n = []
    with school(), stand_in(TE, "soon", lambda: n.append(list(sent()))):
        c = links.new_code(SAM)["code"]
        hook(msg(f"/start {c}", 812)); assert n == [[(812, HELLO.format(name=SAM))]], "after the answer"
        hook(msg(f"/start {c}", 812)); hook(msg("/help", 812)); hook(msg("ABCD-EFGH", 999)); hook(msg("/stop", 812)); assert len(n) == 1, "only a link that was made"
    with school():
        i = absent(by=HUGO); give(i, K5, SAM); assert TE.sweep() == 0
        hook(msg(links.new_code(SAM)["code"], 812)); assert told_of() == [("relief", SAM)]
        send(); assert said(SAM) == [HELLO.format(name=SAM), RELIEF_K5]

# ---- the relief teacher
@t
def approve_queues_the_relief_once():
    with school(SAM, TEAM):
        i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)])
        assert TE.sweep() == 0 and outs() == []
        on_cover(TEAM, i, K5, "approve", dict(who=SAM))                                    # in the app: the save asked for the sweep
        r, = outs(); ref = json.loads(r["ref"])
        assert r["key"] == f"relief:{EVE}:{K5}:2026-10-12T09:00:00+08:00" and (r["name"], r["kind"], r["text"], r["state"]) == (SAM, "relief", RELIEF_K5, "queued"), r
        assert json.loads(r["buttons"]) == [[dict(text="✅ Acknowledge", what="ack", id=i, ckey=K5, who=SAM, extra=dict(absent=EVE, date="2026-10-13")),
                                            dict(text="↩ Request to change", what="change", id=i, ckey=K5, who=SAM, extra=dict(absent=EVE, date="2026-10-13"))]]
        assert ref == dict(id=i, absent=EVE, ckey=K5, approved_at="2026-10-12T09:00:00+08:00", who=SAM, lesson="1A, 1B Science (G2)", periods="P6–P7", start="10:30",
                           day="Tue 13 Oct", date="2026-10-13", ends="2026-10-13T11:30:00+08:00"), ref
        assert OB._wake.is_set() and json.loads(r["files"]) == []
        OB._wake.clear(); assert TE.sweep() == 0 and TE.soon() is True and len(outs()) == 1 and not OB._wake.is_set(), "a second sweep queues nothing"
        assert send() == 1 and said(SAM) == [RELIEF_K5] and TE.sweep() == 0
        links.link(ROSA, CHATS[ROSA], None); assert TE.sweep() == 1
        offered = []
        with stand_in(OB, "queue", lambda *a, **k: offered.append(a) or False): assert TE.sweep() == 0 and offered == [], "what is in the queue is not even offered to it"
        for s in ("sending", "sent", "failed", "unsure", "queued"): put(r["key"], state=s); assert TE.sweep() == 0, s
        on_cover(SAM, i, K5, "acknowledge"); at("09:30"); assert TE.sweep() == 0 and len(outs("relief")) == 1

@t
def two_copies_sweeping_at_once_queue_one():
    """two copies of the app (a deploy swaps them): another lock, the same store"""
    with school(SAM, MAYA, EVE, ROSA):
        i = absent(by=HUGO); give(i, K5, SAM); give(i, K2, MAYA); got, go = [], threading.Barrier(6)
        def copy(): go.wait(); got.append(TE._swept(None))
        ths = [threading.Thread(target=copy) for _ in range(6)]; [x.start() for x in ths]; [x.join() for x in ths]
        assert sum(got) == 4 and sorted(told_of()) == sorted([("officer", ROSA), ("planned", EVE), ("relief", SAM), ("relief", MAYA)]) and send() == 4, (got, told_of())

@t
def the_work_and_its_files_go_with_the_relief():
    with school(SAM):
        i = absent(by=HUGO); f = FI.save(i, "Sheet 4.pdf", b"made-up")
        absences.set_work(i, K2, dict(text="Notes, chapter 6.", link="https://example.org/a", files=[dict(id=f["id"], name="Sheet 4.pdf")], known=[]), EVE)
        give(i, K2, SAM); assert swept() == 1
        r, = outs()
        assert r["text"] == "🔔 Relief for you · Tue 13 Oct\n1C Science · P3–P5 · 09:00–10:30\nFor Ms Evelyn Koh\nWork from Ms Evelyn Koh: Notes, chapter 6.\nLink: https://example.org/a\nFiles: 1, sent after this message."
        assert json.loads(r["files"]) == [dict(id=i, file=f["id"], name="Sheet 4.pdf")] and r["state"] == "sent" and r["files_failed"] == 0
        assert [m for m, p in tg.PRACTICE_LOG if m.startswith("send")] == ["sendMessage", "sendDocument"]
        FI.delete(i, f["id"])
        # a part of a split lesson: its own periods and times
        j = absent(dates=["2026-10-16"]); CV.split(j, KF, 1, TEAM); give(j, KF + "#0", SAM); swept()
        assert "\n1A Art · P1 · 08:00–08:30\n" in said(SAM)[-1] and json.loads(outs()[-1]["ref"])["ends"] == "2026-10-16T08:30:00+08:00"
        give(j, KF + "#1", SAM); swept()
        assert "🔔 Relief for you · Fri 16 Oct\n1A Art · P2 · 08:30–09:00\nRoom 2-05\n" in said(SAM)[-1] and json.loads(outs()[-1]["ref"])["ends"] == "2026-10-16T09:00:00+08:00"

@t
def nothing_goes_before_approval():
    with school(SAM, RUTH, MAYA, TEAM, LEE, HUGO):
        i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)])
        for hm in ("09:00", "09:05", "15:00", "23:00"): at(hm); assert TE.sweep() == 0 and outs() == [], hm
        give(i, K2, SAM); swept(); CV.ask_change(i, K2, "A meeting", SAM); new_pick(i, K2, MAYA); swept()
        assert set(told_of()) == {("relief", SAM), ("ask", TEAM), ("ask", LEE)}, "the new pick of a request to change is told to the team alone"

@t
def only_people_reached_are_told():
    with school(TEAM):
        i = absent(by=HUGO); give(i, K5, SAM)
        assert TE.sweep() == 0 and outs() == [], "Sam is not linked: the app shows it"
        links.link(SAM, CHATS[SAM], None)
        with record(SAM, off=True): assert TE.sweep() == 0
        assert TE.sweep() == 1 and told_of() == [("relief", SAM)]
        assert dues(reach={}) == []; send(); absences.not_needed(i, K5, "x", HUGO); assert [x["name"] for x in dues()] == [SAM] and dues(reach={TEAM: 1}) == []
        absences.needed_again(i, K5, HUGO)
        got = dues(reach={EVE: 1, ROSA: 2}, told={}); assert {(x["kind"], x["name"]) for x in got} == {("planned", EVE), ("officer", ROSA)}

@t
def a_moved_relief_tells_the_first_teacher_once():
    with school(SAM, MAYA, RUTH):
        i = absent(by=HUGO); give(i, K5, SAM); assert swept() == 1
        key = f"relief:{EVE}:{K5}:{approved_at(i, K5)}"
        at("09:10"); give(i, K5, MAYA); assert swept() == 2
        assert [(r["key"], r["name"], r["text"]) for r in outs()][1:] == [(f"moved:{key}", SAM, MOVED_K5), (f"relief:{EVE}:{K5}:{approved_at(i, K5)}", MAYA, RELIEF_K5)]
        assert swept() == 0
        at("09:20"); CV.ask_change(i, K5, "A meeting", MAYA); new_pick(i, K5, TEAM); CV.approve(i, K5, TEAM, LEE, SCHOOL, rs()); swept()      # a request to change approved
        assert said(SAM) == [RELIEF_K5, MOVED_K5] and said(MAYA) == [RELIEF_K5, MOVED_K5]
        at("09:30"); absences.cancel(i, "Better", HUGO); swept(); swept()
        assert said(SAM) == [RELIEF_K5, MOVED_K5] and said(MAYA) == [RELIEF_K5, MOVED_K5], "who was told it moved is not told again that it ended"
        # moved before its message went: the first teacher gets nothing at all
        j = absent(dates=["2026-10-16"]); give(j, KF, SAM); TE.sweep(); at("09:40"); give(j, KF, RUTH); n = len(said(SAM)); swept(); swept()
        assert len(said(SAM)) == n and state(f"relief:{EVE}:{KF}:2026-10-12T09:30:00+08:00") == "dropped" and len(said(RUTH)) == 1

@t
def a_relief_no_longer_needed_is_told_once():
    for how in ("cancel", "not needed", "split", "lost"):
        with school(SAM, MAYA):
            i = absent(by=HUGO); give(i, K5, SAM); swept(); key = f"relief:{EVE}:{K5}:{approved_at(i, K5)}"; at("09:10")
            if how == "cancel": absences.cancel(i, "Better", HUGO)
            if how == "not needed": absences.not_needed(i, K5, "A test", HUGO)
            if how == "split": absences.not_needed(i, K5, "A test", HUGO); absences.needed_again(i, K5, HUGO); CV.split(i, K5, 6, TEAM)       # the cover key is no longer there
            if how == "lost": change_record(i, lambda r: r.update(lessons=[x for x in r["lessons"] if x["key"] != K5]))                        # taken off outside our routes
            assert swept() == 1 and [(r["key"], r["kind"], r["name"], r["text"]) for r in outs()][1:] == [(f"gone:{key}", "gone", SAM, GONE_K5)], how
            assert swept() == 0 and said(SAM) == [RELIEF_K5, GONE_K5]
            if how == "not needed":                                                        # needed again, and given to another: Sam has been told already
                absences.needed_again(i, K5, HUGO); at("09:20"); give(i, K5, MAYA); swept(); assert said(SAM) == [RELIEF_K5, GONE_K5] and said(MAYA) == [RELIEF_K5]
                at("09:30"); give(i, K5, SAM); swept(); assert said(SAM) == [RELIEF_K5, GONE_K5, RELIEF_K5]                        # and theirs again: a relief anew
                at("09:40"); absences.not_needed(i, K5, "A test", HUGO); swept(); assert said(SAM)[3:] == [GONE_K5] and swept() == 0 and said(MAYA) == [RELIEF_K5, MOVED_K5]

@t
def the_same_person_again_is_neither_moved_nor_gone():
    with school(SAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); at("09:10"); give(i, K5, SAM); swept(); swept()
        assert said(SAM) == [RELIEF_K5] * 2 and set(told_of()) == {("relief", SAM)}, "approved again: told again, with what it is now"
        at("09:20"); give(i, K5, MAYA); told = OB.told_for("relief:"); want = [f"moved:{outs()[1]['key']}"]
        for order in (told, dict(reversed(list(told.items())))): assert [x["key"] for x in dues(told=order) if x["kind"] == "moved"] == want, "for the last of them"
        swept(); swept(); assert said(SAM)[2:] == [MOVED_K5], "once, for both"
        at("09:30"); give(i, K5, SAM); swept(); at("09:40"); give(i, K5, MAYA); swept(); swept()
        assert said(SAM)[3:] == [RELIEF_K5, MOVED_K5], "given back and moved again: once more"
        # cancelled and planned again for the same lessons, the same person approved: told of it, and not that it ended
        at("10:00"); j = absent(dates=["2026-10-16"], by=HUGO); give(j, KF, SAM); swept(); n = len(said(SAM))
        absences.cancel(j, "Better", HUGO); at("10:05"); k = absent(dates=["2026-10-16"], by=HUGO); give(k, KF, SAM); swept(); swept()
        assert len(said(SAM)) == n + 1 and said(SAM)[-1].startswith("🔔 Relief for you · Fri 16 Oct")
        absences.cancel(k, "Better", HUGO); at("10:10"); swept(); swept(); assert len(said(SAM)) == n + 2 and said(SAM)[-1].startswith("❌ No longer needed: 1A Art P1–P2 (08:00) on Fri 16 Oct")

@t
def two_approvals_in_one_second_tell_both():
    """the same cover approved to Sam, then given to Maya, in the same second: the same approved.at"""
    with school(SAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); give(i, K5, MAYA); assert TE.sweep() == 1
        base = f"relief:{EVE}:{K5}:2026-10-12T09:00:00+08:00"
        assert [(r["key"], r["name"]) for r in outs()] == [(base, SAM), (f"{base}:{MAYA}", MAYA)]
        assert send() == 1 and state(base) == "dropped" and swept() == 0 and said(MAYA) == [RELIEF_K5] and said(SAM) == [], "Sam's had not gone: it never does, and Maya is told once"
        at("09:05"); give(i, K5, SAM); swept(); assert said(MAYA) == [RELIEF_K5, MOVED_K5] and said(SAM) == [RELIEF_K5]
    with school(SAM, MAYA):                                                                # Sam's had gone
        i = absent(by=HUGO); give(i, K5, SAM); swept(); give(i, K5, MAYA); swept(); swept()
        assert said(SAM) == [RELIEF_K5, MOVED_K5] and said(MAYA) == [RELIEF_K5]

@t
def a_cover_taken_over_by_another_absence_is_not_told_again():
    """an exam's takeover moves an approved cover to another record of the same teacher: the same key, approved.at and person"""
    def take_over(i, j):
        r = absences.load(i); x = next(x for x in r["lessons"] if x["key"] == K5)
        r["lessons"].remove(x); absences._save(r); absences._save(dict(r, id=j, how="asked", by=EVE, lessons=[x], at=clock.now))
    with school(SAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); take_over(i, "dead00beef")
        assert send() == 1 and swept() == 0 and said(SAM) == [RELIEF_K5], "still true, neither gone nor moved, and not sent again"
        at("09:10"); give("dead00beef", K5, MAYA); swept(); swept(); assert said(SAM) == [RELIEF_K5, MOVED_K5] and said(MAYA) == [RELIEF_K5]
    with school(SAM):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); take_over(i, "dead00beef"); at("09:10"); swept(); assert said(SAM) == [RELIEF_K5]
        absences.cancel("dead00beef", "Better", EVE); swept(); assert said(SAM) == [RELIEF_K5, GONE_K5]
    with school(SAM, MAYA):                                                                # the absence the message was about is looked at first, wherever else the cover is
        for mine, other in (("1" * 12, "2" * 12), ("3" * 12, "0" * 12)):
            i = absent(by=HUGO); give(i, K5, SAM); r = absences.load(i); os.remove(absences._path(i)); absences._save(dict(r, id=mine)); TE.sweep()
            x = json.loads(json.dumps(next(x for x in r["lessons"] if x["key"] == K5))); x["relief"] = MAYA; absences._save(dict(r, id=other, lessons=[x])); ref = json.loads(outs(name=SAM)[0]["ref"])
            assert TE._holder(absences.all_records(), dict(ref, id=mine))[1]["relief"] == SAM and TE._holder(absences.all_records(), dict(ref, id=other))[1]["relief"] == MAYA
            shutil.rmtree(absences.DIR)

@t
def a_lesson_two_absent_teachers_share_is_each_ones_own_relief():
    """the lesson's key is the same in both absences: what is told is kept apart by the absent teacher"""
    with school(SAM, MAYA):
        i = absent(by=HUGO, lessons=[dict(key=K8, needed=True)]); j = absent(teacher=BUSY, lessons=[dict(key=K8, needed=True)])
        give(i, K8, SAM); give(j, K8, MAYA); assert swept() == 2 and {json.loads(r["ref"])["absent"] for r in outs()} == {EVE, BUSY}
        assert swept() == 0; at("09:10"); absences.not_needed(i, K8, "x", HUGO); swept(); swept()
        assert [x[:19] for x in said(SAM)] == ["🔔 Relief for you · ", "❌ No longer needed:"] and len(said(MAYA)) == 1, "gone, not moved to who relieves the other teacher"

@t
def an_absence_that_cannot_be_read_never_says_its_reliefs_are_gone():
    with school(SAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); j = absent(dates=["2026-10-16"]); p = absences._path(i); good = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write("{ not json"); assert swept() == 0 and said(SAM) == [RELIEF_K5]
        give(j, KF, MAYA); assert swept() == 1 and len(said(MAYA)) == 1, "the other messages go"
        open(p, "w", encoding="utf-8").write(good); assert swept() == 0
        os.rename(absences.DIR, absences.DIR + ".away")
        try: assert swept() == 0 and said(SAM) == [RELIEF_K5], "the folder itself not there"
        finally: os.rename(absences.DIR + ".away", absences.DIR)
        os.remove(p); assert swept() == 1 and said(SAM) == [RELIEF_K5, GONE_K5], "really gone"
    # a change of two records (an exam's takeover) read half way: the cover is in neither, until it is read again in one go
    with school(SAM):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); held, real = [], absences.all_records
        def half():
            held.append(absences._LOCK.locked()); got = real()
            return got if absences._LOCK.locked() else [dict(v, lessons=[y for y in v["lessons"] if y["key"] != K5]) for v in got]
        with stand_in(absences, "all_records", half): assert swept() == 0 and held == [False, True] and said(SAM) == [RELIEF_K5] and not absences._LOCK.locked()
        with stand_in(absences, "all_records", lambda: held.append(absences._LOCK.locked()) or real()): del held[:]; assert swept() == 0 and held == [False], "read once when nothing is gone"

@t
def a_lesson_that_is_over_is_not_told():
    with school(SAM, MAYA, TEAM):
        i = absent(by=HUGO); at("11:29", 13); give(i, K5, SAM); assert [x["kind"] for x in dues()] == ["relief"]
        at("11:30", 13); assert dues() == [] and TE.sweep() == 0, "its end: nothing more"
        at("11:29", 13); swept(); assert said(SAM) == [RELIEF_K5]
        give(i, K5, MAYA); at("11:30", 13); assert swept() == 0 and len(said(SAM)) == 1, "nor that it moved"
        at("09:00", 14); assert dues() == []
        # queued, and over before it could go
        at("11:29", 13); TE.sweep(); at("11:30", 13); send(); assert said(MAYA) == [] and state(f"relief:{EVE}:{K5}:2026-10-13T11:29:00+08:00:{MAYA}") == "dropped"
    with school(SAM):                                                                      # a period with no times: over when its day is
        i = absent(by=HUGO); give(i, K5, SAM); change_record(i, lambda r: [x.update(p=20) for x in r["lessons"] if x["key"] == K5])
        at("23:59", 13); x, = dues(); assert x["ref"]["ends"] == "2026-10-14T00:00:00+08:00"; swept(); absences.cancel(i, "x", HUGO); assert [x["kind"] for x in dues()] == ["gone"]; at("00:00", 14); assert dues() == []
    with school(SAM, TEAM):
        i = absent(by=HUGO); give(i, K5, SAM); CV.ask_change(i, K5, "A meeting", SAM)
        at("11:29", 13); assert {x["kind"] for x in dues()} == {"ask"}; at("11:30", 13); assert dues() == []
        at("11:29", 13); CV.keep(i, K5, TEAM); assert {x["kind"] for x in dues()} == {"relief", "kept"}; at("11:30", 13); assert dues() == []

@t
def remind_copies_are_not_reliefs_of_their_own():
    """Task 6 sends a relief again under its key with :r1 after it: it never makes a second moved or gone"""
    with school(SAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); r, = outs()
        assert OB.queue(r["key"] + ":r1", SAM, "again", kind="relief", ref=json.loads(r["ref"])) and send() == 1
        at("09:10"); give(i, K5, MAYA); swept(); swept(); assert told_of("moved") == [("moved", SAM)]
    with school(SAM, MAYA):                                                                # the first never went: the copy alone counts for nothing
        i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); r, = outs(); put(r["key"], state="failed")
        OB.queue(r["key"] + ":r1", SAM, "again", kind="relief", ref=json.loads(r["ref"])); send(); at("09:10"); give(i, K5, MAYA); swept(); assert told_of("moved") == []
    for s, n in (("sent", 1), ("unsure", 1), ("queued", 0), ("sending", 0), ("failed", 0), ("dropped", 0)):
        with school(SAM):
            i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); put(outs()[0]["key"], state=s); at("09:10"); absences.cancel(i, "Better", HUGO)
            assert len([x for x in dues() if x["kind"] == "gone"]) == n, s

# ---- the absent teacher, the reporting officer, the team
@t
def planned_tells_the_absent_teacher():
    with school(EVE, HUGO, TEAM):
        i = absent(by=HUGO); assert TE.sweep() == 1
        r, = outs(); assert (r["key"], r["name"], r["kind"], r["text"]) == (f"planned:{i}", EVE, "planned", PLANNED_EVE), r
        assert json.loads(r["buttons"]) == [[dict(text="✅ Acknowledge and set work", url=BASE + "/relief#mine")], [dict(text="❌ Not needed: cancel", what="cancel", id=i)]]
        assert swept() == 0 and said(EVE) == [PLANNED_EVE], "once; the planner is not told"
    with school(EVE):
        i = absent(by=HUGO, dates=["2026-10-13", "2026-10-14"], periods=[0, 2]); TE.sweep(); assert outs()[0]["text"].splitlines()[1:4] == ["Tue 13 Oct, Wed 14 Oct · P1–P3", "Planned by Mr Hugo Ong", "2 lessons will be covered."]
    with school(EVE):
        absent(by=HUGO, periods=[2, 4]); TE.sweep(); assert "\n1 lesson will be covered.\n" in outs()[0]["text"]
    for what in ("asked", "acknowledged", "cancelled", "past", "by themselves", "not planned"):
        with school(EVE):
            i = absent(by=None if what == "asked" else HUGO)
            if what == "by themselves": change_record(i, lambda r: r.update(by=EVE))
            if what == "not planned": change_record(i, lambda r: r.update(how="asked"))
            if what == "acknowledged": absences.acknowledge(i, EVE)
            if what == "cancelled": absences.cancel(i, "Better", HUGO)
            if what == "past": at("09:00", 14)
            assert [x for x in dues() if x["kind"] in ("planned", "remind")] == [] and [x for x in outs() if x["name"] == EVE] == [], what
    with school(EVE):                                                                      # acknowledged before it could go
        i = absent(by=HUGO); TE.sweep(); absences.acknowledge(i, EVE); assert send() == 0 and said(EVE) == []

@t
def the_reminder_goes_once_after_its_time():
    with school(EVE):
        i = absent(by=HUGO); swept(); at("14:59"); assert swept() == 0
        at("15:00"); assert swept() == 1 and [(r["key"], r["kind"], r["text"], json.loads(r["buttons"])) for r in outs()][1:] == [(f"remind:{i}", "remind", REMIND_EVE, [])]
        for hm, d in (("15:01", 12), ("23:00", 12), ("00:00", 13), ("09:00", 13)): at(hm, d); assert swept() == 0, (hm, d)
        assert said(EVE) == [PLANNED_EVE, REMIND_EVE]
    for sent_, day in (("15:00", 12), ("16:00", 12), ("07:00", 13)):                       # sent at or after that time: never, the next day neither
        with school(EVE):
            at(sent_, day); i = absent(by=HUGO); swept()
            for hm, d in (("16:30", 12), ("23:59", 12), ("00:00", 13), ("07:30", 13), ("12:00", 13)):
                if (d, hm) >= (day, sent_): at(hm, d); assert swept() == 0, (sent_, hm, d)
            assert told_of() == [("planned", EVE)]
    with school(EVE):                                                                      # the first day's, when there are several
        at("16:00"); i = absent(by=HUGO, dates=["2026-10-13", "2026-10-16"]); assert swept() == 1
        for hm, d in (("16:30", 12), ("00:00", 13), ("15:30", 15), ("09:00", 16)): at(hm, d); assert swept() == 0, (hm, d)
    with school(EVE, times=dict(remind_at="16:30")):                                       # the setting, and the school day before
        i = absent(by=HUGO, dates=["2026-10-16"]); swept(); at("16:29", 15); assert swept() == 0; at("16:30", 15); assert swept() == 1
    for what in ("acknowledged", "cancelled", "asked"):
        with school(EVE):
            i = absent(by=None if what == "asked" else HUGO); swept()
            if what == "acknowledged": absences.acknowledge(i, EVE)
            if what == "cancelled": absences.cancel(i, "Better", HUGO)
            at("15:00"); swept(); assert "remind" not in [k for k, n in told_of()], what
    with school(EVE):                                                                      # acknowledged between the two
        i = absent(by=HUGO); swept(); at("15:00"); TE.sweep(); absences.acknowledge(i, EVE); assert send() == 0

@t
def the_officer_message_has_only_the_kind_of_reason():
    with school(ROSA, EVE, HUGO, TEAM):
        i = absent(reason="Other", reason_text="a made-up private matter", remarks="a made-up remark"); TE.sweep()
        r, = outs(); assert (r["key"], r["name"], r["kind"], r["text"], json.loads(r["buttons"])) == \
            (f"officer:{i}", ROSA, "officer", "Ms Evelyn Koh is away on Tue 13 Oct (whole day): Other.\nRelief is being arranged.", [])
        assert "made-up" not in str(r) and swept() == 0 and told_of() == [("officer", ROSA)]
        absent(teacher=EVE, dates=["2026-10-16"], periods=[0, 1], reason="Course", by=HUGO); TE.sweep()
        assert [r["text"] for r in outs("officer")][1:] == ["Ms Evelyn Koh is away on Fri 16 Oct (P1–P2): Course.\nRelief is being arranged."]
        change_record(i, lambda r: r.update(reason="something typed by hand", id="f" * 12)); TE.sweep(); assert "hand" not in str(outs())
    for officer, by in ((EVE, None), (EVE, HUGO), (HUGO, HUGO), ("Mr Nobody Known", None), ("", None), (None, None)):
        with school(ROSA, EVE, HUGO):
            i = absent(by=by or (None if officer else HUGO)); change_record(i, lambda r: r.update(reporting_officer=officer) if officer is not None else r.pop("reporting_officer"))
            assert [x for x in dues() if x["kind"] == "officer"] == [], officer
    for what in ("cancelled", "past"):
        with school(ROSA):
            i = absent(); absences.cancel(i, "Better", EVE) if what == "cancelled" else at("09:00", 14); assert dues() == [], what

@t
def cancel_tells_the_team_the_planner_and_the_told():
    with school(EVE, SAM, MAYA, HUGO, TEAM, LEE, ROSA):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); at("09:10"); absences.cancel(i, "a made-up why", EVE); swept(); swept()
        assert sorted((r["kind"], r["name"], r["key"]) for r in outs()[3:]) == sorted([("gone", SAM, f"gone:relief:{EVE}:{K5}:2026-10-12T09:00:00+08:00")] + [("cancelled", n, f"cancelled:{i}:{n}") for n in (HUGO, TEAM, LEE)]), outs()[3:]
        assert said(HUGO) == said(TEAM) == said(LEE) == [CANCELLED_EVE.format(EVE)] and said(SAM) == [RELIEF_K5, GONE_K5] and "made-up why" not in str(rows("outbox"))
        assert {x["name"] for x in dues(reach={TEAM: 1}, told={})} == {TEAM}, "nobody who cannot be reached"
    for by, want in ((HUGO, {TEAM, LEE}), (TEAM, {HUGO, LEE})):                            # never the canceller; the absent teacher is not told either
        with school(EVE, HUGO, TEAM, LEE, ROSA):
            i = absent(by=HUGO); swept(); absences.cancel(i, "Better", by, team=True); swept(); assert {n for k, n in told_of("cancelled")} == want
    with school(EVE, TEAM, LEE):                                                           # asked by the teacher: there is no planner
        i = absent(); swept(); absences.cancel(i, "Better", TEAM, team=True); swept(); assert told_of("cancelled") == [("cancelled", LEE)]
    with school(TEAM, LEE):                                                                # a team member who is the absent teacher and cancels
        i = absent(teacher=SAM, lessons=[]); absences.cancel(i, "Better", SAM); swept(); assert {n for k, n in told_of("cancelled")} == {TEAM, LEE}
    with school(TEAM):                                                                     # long after, to somebody on the team now: nothing about what is past
        i = absent(); absences.cancel(i, "Better", EVE); at("09:00", 14); assert dues() == []

@t
def a_team_member_is_told_by_their_rights_at_that_moment():
    with school(TEAM, LEE, HUGO, SAM):
        i = absent(); absences.cancel(i, "Better", EVE)
        with record(LEE, extras=dict(relief=False, exams=None, admin=False)), record(SAM, extras=dict(relief=True, exams=None, admin=False)): TE.sweep()
        assert {n for k, n in told_of("cancelled")} == {TEAM, SAM}
        TE.sweep(); assert {n for k, n in told_of("cancelled")} == {TEAM, SAM, LEE}

@t
def both_roles_get_both_messages():
    """a person who is both the relief teacher and on the team; a team member who is the absent teacher"""
    with school(TEAM, LEE, EVE):
        i = absent(by=HUGO); give(i, K2, TEAM, by=TEAM); swept(); assert ("relief", TEAM) in told_of(), "approved by themselves"
        CV.ask_change(i, K2, "A meeting", TEAM); new_pick(i, K2, MAYA); swept(); assert {n for k, n in told_of("ask")} == {TEAM, LEE}
        CV.keep(i, K2, TEAM); swept(); assert told_of("kept") == [("kept", TEAM)]
        at("09:10"); give(i, K2, MAYA, by=TEAM); swept(); assert told_of("moved") == [("moved", TEAM)]
    with record(EVE, extras=dict(relief=True, exams=None, admin=False)), school(TEAM, EVE, SAM):
        i = absent(by=HUGO); give(i, K2, SAM); CV.ask_change(i, K2, "A meeting", SAM); new_pick(i, K2, MAYA); swept()
        assert sorted(told_of(name=EVE)) == [("ask", EVE), ("planned", EVE)]

# ---- the request to change
def ask_buttons(i, name=MAYA, short="Ms Lee"): return [[dict(text=f"Approve {short}", what="approve", id=i, ckey=K5, who=name)], [dict(text="Open in the app", url=BASE + "/relief#today")]]

def asked(*, pick=True):
    """Sam's relief, told, then asked to change at 09:10 -> the absence's id"""
    i = absent(by=HUGO); give(i, K5, SAM); swept(); at("09:10")
    if pick: on_cover(SAM, i, K5, "ask-change", dict(why="A parent meeting"))              # in the app: the pick is made at once
    else: CV.ask_change(i, K5, "A parent meeting", SAM)
    return i

@t
def an_ask_waits_for_the_pick_then_goes():
    with school(SAM, MAYA, TEAM, LEE, HUGO, EVE):
        i = asked(pick=False); n = len(outs())
        for hm in ("09:10", "09:11:59"): at(hm); assert TE.sweep() == 0, "two minutes for the pick"
        new_pick(i, K5, MAYA); assert TE.sweep() == 2
        a, b = outs()[n:]; ask_at = "2026-10-12T09:10:00+08:00"
        assert [(r["key"], r["name"], r["kind"], r["text"]) for r in (a, b)] == [(f"ask:{i}:{K5}:{ask_at}:{x}", x, "ask", ASK_K5 + "New pick: Ms Maya Lee\nTeaches Science and is free then.") for x in (LEE, TEAM)]
        assert json.loads(a["buttons"]) == json.loads(b["buttons"]) == ask_buttons(i)
        at("09:30"); assert swept() == 0 and len(said(TEAM)) == 1 and said(MAYA) == [] and said(SAM) == [RELIEF_K5], "only the team, once, with that pick"
        on_cover(TEAM, i, K5, "approve", dict(who=MAYA)); send(); assert said(SAM) == [RELIEF_K5, MOVED_K5] and said(MAYA) == [RELIEF_K5] and len(said(TEAM)) == 1
    with school(SAM, TEAM):                                                                # asked in the app: the pick is in with the answer
        with stand_in(FL, "AFTER", [TE.sweep]): i = asked()
        new = covered(i, K5)[2]["change"]["pick"]; r, = outs("ask")
        assert r["text"] == ASK_K5 + f"New pick: {new['who']}\n{new['reason']}" and json.loads(r["buttons"])[0][0]["who"] == new["who"]

@t
def an_ask_without_a_pick_goes_after_two_minutes_and_the_pick_once_more():
    with school(SAM, MAYA, TEAM, LEE):
        i = asked(pick=False); ask_at = "2026-10-12T09:10:00+08:00"; calls, real = [], FR.free_then
        def free_then(*a): calls.append(a[3]["key"]); return real(*a)
        with stand_in(FR, "free_then", free_then):
            at("09:11:59"); assert TE.sweep() == 0 and calls == []
            at("09:12"); assert swept() == 2 and calls == [K5], calls
            r = outs("ask")[0]; assert r["text"] == ASK_K5 + "No new pick yet: open the app." and json.loads(r["buttons"]) == [[dict(text="Open in the app", url=BASE + "/relief#today")]]
            for hm in ("09:13", "10:00"): at(hm); assert swept() == 0
            assert calls == [K5], "asked who is free only for the message that says it"
            new_pick(i, K5, MAYA); del calls[:]; assert swept() == 2 and calls == []
        r = outs("askpick", TEAM)[0]; assert (r["key"], r["name"], r["text"]) == (f"askpick:{i}:{K5}:{ask_at}:{TEAM}", TEAM, ASK_K5 + "New pick: Ms Maya Lee\nTeaches Science and is free then.")
        assert buttons_of(r) == ask_buttons(i) and swept() == 0 and len(said(TEAM)) == 2
    with school(SAM, TEAM, limits=dict(fat_per_day=3, other_per_day=None, never=[MAYA, RUTH, BUSY, HUGO, LEE, TEAM, ROSA, OFFIE])):
        i = asked(pick=False); at("09:12"); swept(); assert outs("ask")[0]["text"] == ASK_K5 + "Nobody else is free then: choose someone in the app.", "Sam, who asked, does not count"
    with school(SAM, TEAM, limits=dict(fat_per_day=3, other_per_day=None, never=[MAYA, BUSY, HUGO, LEE, TEAM, ROSA, OFFIE])):
        i = absent(by=HUGO); CV.split(i, K5, 6, TEAM); give(i, K5 + "#0", SAM); CV.ask_change(i, K5 + "#0", "x", SAM); at("09:12"); swept()
        assert outs("ask")[0]["text"].endswith("No new pick yet: open the app."), "a part of a split lesson: Ruth is free for that part"
    with school(SAM, TEAM):                                                                # a date that is no longer a school day: said as plainly
        i = asked(pick=False); at("09:12")
        def odd(*a): raise ValueError("made up")
        with stand_in(FR, "free_then", odd): swept()
        assert outs("ask")[0]["text"].endswith("No new pick yet: open the app.")
    with school(SAM):                                                                      # nobody on the team to tell: nothing is worked out
        i = asked(pick=False); at("09:12")
        with stand_in(FR, "free_then", lambda *a: 1 / 0): assert TE.sweep() == 0

@t
def a_pick_the_ask_carried_is_not_sent_twice():
    with school(SAM, MAYA, TEAM):
        i = asked(pick=False); new_pick(i, K5, MAYA); swept(); assert swept() == 0 and told_of("askpick") == []
        CV.drop(i, K5, "x", who=MAYA, into="change"); at("09:20"); assert swept() == 0, "dropped: nothing to say yet"
        new_pick(i, K5, MAYA); assert swept() == 0, "the same name again"
        CV.drop(i, K5, "x", who=MAYA, into="change"); new_pick(i, K5, HUGO); assert swept() == 1 and "New pick: Mr Hugo Ong\n" in outs("askpick")[0]["text"], "another name: once more"
        assert swept() == 0
    for s, n in (("queued", 0), ("sent", 0), ("failed", 0), ("dropped", 1)):
        with school(SAM, TEAM):
            i = asked(pick=False); new_pick(i, K5, MAYA); TE.sweep(); put(outs("ask")[0]["key"], state=s); assert TE.sweep() == n and told_of("askpick") == [], s

@t
def a_request_that_is_over_is_not_told():
    for how in ("kept", "acknowledged", "changed", "cancelled"):
        with school(SAM, MAYA, TEAM):
            i = asked(pick=False); new_pick(i, K5, MAYA); TE.sweep()
            if how == "kept": CV.keep(i, K5, LEE)
            if how == "acknowledged": CV.acknowledge(i, K5, SAM)
            if how == "changed": give(i, K5, HUGO)
            if how == "cancelled": absences.cancel(i, "Better", HUGO)
            send(); assert not any(x.startswith("↩") for x in said(TEAM)) and [x for x in dues(told={}) if x["kind"] in ("ask", "askpick")] == [], how
    with school(SAM, MAYA, TEAM):                                                          # asked again: another request
        i = asked(pick=False); new_pick(i, K5, MAYA); swept(); at("09:20"); CV.keep(i, K5, LEE); swept(); at("09:30"); CV.ask_change(i, K5, "A parent meeting", SAM); new_pick(i, K5, MAYA); swept()
        assert [r["key"][-26 - len(TEAM):] for r in outs("ask")] == [f"2026-10-12T{hm}:00+08:00:{TEAM}" for hm in ("09:10", "09:30")] and len(said(TEAM)) == 2

@t
def kept_tells_the_asker():
    with school(SAM, MAYA, TEAM, LEE, EVE):
        i = asked(pick=False); new_pick(i, K5, MAYA); swept(); at("09:20"); on_cover(TEAM, i, K5, "keep"); send()
        r, = outs("kept"); assert (r["key"], r["name"], r["text"], json.loads(r["buttons"])) == (f"kept:{i}:{K5}:2026-10-12T09:20:00+08:00", SAM, KEPT_K5, [])
        assert swept() == 0 and said(SAM) == [RELIEF_K5, KEPT_K5] and said(MAYA) == []
        at("09:30"); on_cover(SAM, i, K5, "ask-change", dict(why="Again")); at("09:40"); on_cover(LEE, i, K5, "keep"); send(); assert said(SAM)[2:] == [KEPT_K5], "kept a second time"
    for later in ("asked again", "moved", "moved and back", "cancelled"):                  # no longer so when it could first be told
        with school(TEAM):
            i = asked(pick=False); at("09:20"); CV.keep(i, K5, TEAM); at("09:30")
            if later == "asked again": CV.ask_change(i, K5, "Again", SAM)
            if later.startswith("moved"): give(i, K5, MAYA)
            if later == "moved and back": at("09:40"); give(i, K5, SAM)
            if later == "cancelled": absences.cancel(i, "Better", HUGO)
            links.link(SAM, CHATS[SAM], None); links.link(MAYA, CHATS[MAYA], None); assert [x for x in dues() if x["kind"] == "kept"] == [], later
    with school(TEAM):                                                                     # acknowledged since: told
        i = asked(pick=False); at("09:20"); CV.keep(i, K5, TEAM); CV.acknowledge(i, K5, SAM); links.link(SAM, CHATS[SAM], None); assert [x["kind"] for x in dues()] == ["kept"]
    with school(MAYA):                                                                     # kept, and moved in the same second: not said to the other
        i = asked(pick=False); CV.keep(i, K5, TEAM); give(i, K5, MAYA); assert [x["kind"] for x in dues()] == ["relief"]

# ---- what is old, and what is still to come
@t
def a_person_who_links_later_gets_what_is_still_to_come():
    with school(TEAM):
        i = absent(by=HUGO); give(i, K5, SAM); give(i, K2, SAM); j = absent(dates=["2026-10-16"]); give(j, KF, SAM); CV.acknowledge(i, K2, SAM)
        at("15:00"); assert swept() == 0
        links.link(SAM, CHATS[SAM], None); swept(); assert [x.splitlines()[0][-6:] for x in said(SAM)] == ["13 Oct", "16 Oct"] and said(SAM)[0] == RELIEF_K5, "in time order; one acknowledged in the app is not asked again"
        links.link(EVE, CHATS[EVE], None); links.link(ROSA, CHATS[ROSA], None); swept()
        assert said(EVE) == [PLANNED_EVE, REMIND_EVE] and said(ROSA) == [OFFICER_EVE, "Ms Evelyn Koh is away on Fri 16 Oct (whole day): Medical.\nRelief is being arranged."], (said(EVE), said(ROSA))
        links.link(SAM, 900, None); assert swept() == 0, "another phone: nothing is sent twice"
        # moved while they had no Telegram: told when they have one again
        links.unlink(SAM); at("15:10"); give(i, K5, MAYA); assert swept() == 0; links.link(SAM, CHATS[SAM], None); swept(); assert said(SAM)[-1] == MOVED_K5

@t
def nothing_old_is_sent_when_the_bot_first_connects():
    with school(EVE, SAM, ROSA, TEAM, HUGO, since="2026-10-12T12:00:00+08:00"):
        i = absent(by=HUGO); give(i, K5, SAM); CV.ask_change(i, K5, "x", SAM); CV.keep(i, K5, TEAM); j = absent(by=HUGO, dates=["2026-10-16"]); absences.cancel(j, "Better", EVE)
        at("12:30"); assert TE.sweep() == 1 and told_of() == [("relief", SAM)], "the relief is still to be done, whenever it was approved"
        at("15:00"); assert TE.sweep() == 1 and told_of()[1:] == [("remind", EVE)], "and still to be acknowledged"
        k = absent(by=HUGO, dates=["2026-10-16"]); CV.ask_change(i, K5, "x", SAM); CV.keep(i, K5, TEAM); TE.sweep()
        assert set(told_of()[2:]) == {("planned", EVE), ("officer", ROSA), ("kept", SAM)}, told_of()
        absences.cancel(k, "Better", EVE); TE.sweep(); assert {(a, b) for a, b in told_of("cancelled")} == {("cancelled", TEAM), ("cancelled", HUGO)}
    with school(EVE, ROSA, since="2026-10-12T09:00:00+08:00"): absent(by=HUGO); assert TE.sweep() == 2, "in the very second it was connected: told"
    with school(EVE, ROSA, TEAM, since=None): absent(by=HUGO); assert TE.sweep() == 2; at("09:01"); assert dues(since=None, told={}) == [], "no time of connecting: nothing before now"

# ---- still true when it goes
@t
def still_true_says_what_may_still_go():
    def it(kind, name=None): r = outs(kind, name)[0]; return dict(r, ref=json.loads(r["ref"]))
    with school(EVE, SAM, ROSA, TEAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); relief, planned, officer = it("relief"), it("planned"), it("officer")
        assert all(TE.still_true(x) is True for x in (relief, planned, officer))
        CV.acknowledge(i, K5, SAM); assert TE.still_true(relief) is True; CV.ask_change(i, K5, "x", SAM); assert TE.still_true(relief) is True, "theirs, whatever they answered in the app"
        new_pick(i, K5, MAYA); TE.sweep(); ask = it("ask"); assert TE.still_true(ask) is True
        absences.acknowledge(i, EVE); assert TE.still_true(planned) is False and TE.still_true(dict(planned, kind="remind")) is False and TE.still_true(officer) is True
        at("11:30", 13); assert TE.still_true(relief) is False, "over"; at("11:29", 13); assert TE.still_true(relief) is True
        at("09:00", 14); assert TE.still_true(officer) is False, "past"; at("09:10")
        CV.keep(i, K5, TEAM); assert TE.still_true(ask) is False and TE.still_true(dict(ask, kind="askpick")) is False
        CV.ask_change(i, K5, "x", SAM); assert TE.still_true(ask) is False, "another request"; CV.keep(i, K5, TEAM)
        give(i, K5, SAM); assert TE.still_true(relief) is False, "approved anew: that message is the one to go"
        absences.cancel(i, "Better", HUGO); assert TE.still_true(officer) is False and TE.still_true(relief) is False
        for kind in ("gone", "moved", "kept", "cancelled", "report", "clear", "weekly", "anything"): assert TE.still_true(dict(kind=kind, ref=None)) is True, kind
    with school(EVE, SAM, ROSA, TEAM):
        i = absent(by=HUGO); give(i, K5, SAM); j = absent(dates=["2026-10-16"]); TE.sweep(); CV.ask_change(i, K5, "x", SAM); new_pick(i, K5, MAYA); TE.sweep()
        items = [next(dict(r, ref=json.loads(r["ref"])) for r in outs(k) if json.loads(r["ref"])["id"] == i) for k in ("relief", "planned", "officer", "ask")]; p = absences._path(i); good = open(p, encoding="utf-8").read()
        def raises(x):
            try: TE.still_true(x)
            except Exception: return True
            return False
        for bad in ("{ not json", "[]", "{}", ""): open(p, "w", encoding="utf-8").write(bad); assert all(raises(x) for x in items), bad
        assert send() == 1 and [state(x["key"]) for x in items] == ["queued"] * 4, "what cannot be read waits (the other officer message went)"
        open(p, "w", encoding="utf-8").write(good); assert all(TE.still_true(x) is True for x in items)
        os.rename(p, p + ".away"); assert all(TE.still_true(x) is False for x in items), "the file really gone"
        q_ = absences._path(j); other = open(q_, encoding="utf-8").read(); open(q_, "w", encoding="utf-8").write("{ not json")
        assert raises(items[0]) and all(TE.still_true(x) is False for x in items[1:]), "the cover may be in the one that cannot be read"
        open(q_, "w", encoding="utf-8").write(other); os.rename(p + ".away", p)
        with stand_in(absences, "all_records", lambda: 1 / 0): assert TE.still_true(items[0]) is True, "every record is read only when its own does not answer"

# ---- what a message never carries
@t
def no_message_carries_remarks_or_the_typed_reason():
    with school(EVE, SAM, ROSA, TEAM, LEE, HUGO, MAYA):
        i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)], reason="Other", reason_text="zebra-reason", remarks="quokka-remark")
        change_record(i, lambda r: [x.update(pick=dict(who=SAM, by="ai", reason="lemur-first-pick", at=clock.now)) for x in r["lessons"] if x["key"] == K5])
        on_cover(TEAM, i, K5, "approve", dict(who=SAM)); send()
        at("09:10"); CV.ask_change(i, K5, "walrus-why", SAM); new_pick(i, K5, MAYA, reason="okapi-new-pick"); swept()
        at("09:15"); CV.keep(i, K5, LEE); swept(); at("09:20"); CV.ask_change(i, K5, "walrus-why", SAM); swept(); at("09:25"); swept(); new_pick(i, K5, MAYA, reason="okapi-new-pick"); swept()
        at("09:30"); on_cover(TEAM, i, K5, "approve", dict(who=MAYA)); swept(); at("15:00"); swept()
        absences.not_needed(i, K2, "gecko-not-needed", HUGO); absences.cancel(i, "bison-cancel", EVE); swept()
        j = absent(dates=["2026-10-16"], reason="Course", remarks="quokka-remark"); swept()
        kinds = {k for k, n in told_of()}; assert kinds == {"planned", "officer", "relief", "ask", "askpick", "kept", "moved", "remind", "gone", "cancelled"}, kinds
        for r in outs():
            all_ = json.dumps(r, ensure_ascii=False) + r["text"]
            for word in ("zebra", "quokka", "lemur", "gecko", "bison"): assert word not in all_, (word, r["kind"])
            for word in ("walrus", "okapi"): assert (word in all_) <= (r["kind"] in ("ask", "askpick") and r["name"] in (TEAM, LEE)), (word, r["kind"], r["name"])
            for word in absences.REASONS: assert (word in r["text"]) <= (r["kind"] == "officer" and r["name"] == ROSA), (word, r["kind"])
        assert set(CHATS[n] for n in (TEAM, LEE)) >= {c for c, x in sent() if "walrus" in x} and any("okapi" in x for x in said(TEAM))

@t
def due_is_worked_out_from_what_it_is_given():
    with school(EVE, SAM, ROSA, TEAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); give(i, K2, SAM); CV.ask_change(i, K2, "x", SAM); at("09:10"); absences.not_needed(i, K5, "x", HUGO)
        records, told, reach, st = absences.all_records(), OB.told_for(""), links.reachable(), rs(); before = json.dumps(records)
        def no(*a, **k): raise AssertionError("due read something")
        with stand_in(store, "read_json", no), stand_in(store, "published", no), stand_in(tgdb, "db", no), stand_in(absences, "all_records", no), stand_in(absences, "_now", no), stand_in(LS, "today", no), stand_in(os, "listdir", no):
            args = (SCHOOL, st, records, clock.now, reach, told, "2026-10-12T08:00:00+08:00")
            a, b = [TE.due(*args, team=(TEAM, LEE), base=BASE, shorts={}) for _ in range(2)]
            none = TE.due(*args)
        assert a == b and json.dumps(records) == before and [(x["kind"], x["name"]) for x in a] == [("gone", SAM), ("ask", TEAM)], a
        assert all(set(x) == {"key", "name", "kind", "text", "buttons", "files", "ref"} for x in a) and [x["kind"] for x in none] == ["gone"], "no team: nothing for it"
        assert [x["kind"] for x in TE.due(*args, team=(TEAM,), whole=False)] == ["ask"], "some records could not be read: nothing is said to have ended"
        assert json.dumps(a) and TE.due(SCHOOL, st, [], datetime.datetime(2026, 10, 12, 1, 10, tzinfo=datetime.timezone.utc), reach, {}, None) == []
        # no short name known: the name
        new_pick(i, K2, MAYA); got = dues(told={}); assert [x["buttons"][0][0]["text"] for x in got if x["kind"] == "ask"] == ["Approve Ms Maya Lee"]
        assert [x["buttons"][0][0]["text"] for x in dues(told={}, shorts={MAYA: "Ms Lee"}) if x["kind"] == "ask"] == ["Approve Ms Lee"]

@t
def the_sweep_is_quick():
    with school(EVE, SAM, ROSA, TEAM, LEE, HUGO):
        i = absent(by=HUGO, dates=["2026-10-13", "2026-10-14", "2026-10-16"]); give(i, K5, SAM); give(i, KF, SAM); whole_ = absences.load(i); os.remove(absences._path(i))
        for n in range(200):
            r = json.loads(json.dumps(whole_)); r.update(id=f"{n:012x}", teacher=f"Mx Made Up {n}")
            if n % 2: r.update(dates=["2026-10-01"], lessons=[dict(x, date="2026-10-01", key=x["key"].replace("2026-10-13", "2026-10-01")) for x in r["lessons"][:3]])
            absences._save(r)
        began = time.monotonic(); n = TE.sweep(); first = time.monotonic() - began
        assert n == 300, n                                                                 # 100 to come: two reliefs and the officer's, each
        began = time.monotonic(); assert TE.sweep() == 0; second = time.monotonic() - began
        assert first < 2 and second < 0.5, (first, second)

assert REAL == [], "a test reached the network"
print(f"{COUNT} relief telegram tests passed")

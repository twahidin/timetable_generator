"""Plain-assert tests for the Telegram client and its store (relief stage 4): .venv/bin/python tests/test_relief_telegram.py"""
import os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16))
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("RELIEF_JOBS", None)
os.environ.pop("RAILWAY_PUBLIC_DOMAIN", None)
for _k in ("ANTHROPIC_API_KEY", "AI_API_KEY", "TYPED_REQUEST_MODEL"): os.environ.pop(_k, None)   # no key and no practice picker: no test can reach a model
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
        for status in (400, 402, 405, 409, 418): assert kind(answer(status, dict(ok=False)))["kind"] == "refused", status
        for status in (401, 404): assert kind(answer(status, dict(ok=False)))["kind"] == "network", "a token that is revoked or wrong: nothing is the message's fault"
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
        c.execute("DELETE FROM state")
    tg.PRACTICE_LOG.clear(); links.tries.fails.clear(); OB._doubt.clear(); OB._hold[0] = 0.0; OB._failed[0] = None

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
NOT_READ = "I can't read messages here. To answer a relief, press a button under it. Send /relief to ask for relief."
NOT_LINKED = "This Telegram is not linked. Open Relief in the school's app, press Link Telegram and follow the link there."
BAD_CODE = "That code is not right or has run out. Get a new one in the app. If it was your personal code, do not send it here: it opens the app. I have deleted your message."
MOVED_LINK = "Your relief messages now go to another Telegram. If this was not you, tell the relief team."
TAKEN = "This Telegram was linked to someone else before. Their relief messages no longer come here."
STOPPED = "Unlinked. Your relief messages stop here. To link again, open Relief in the school's app and press Link Telegram."
BAD_CODE_KEPT = "That code is not right or has run out. Get a new one in the app. If it was your personal code, do not send it here: it opens the app. Please delete your message now."

@t
def the_bots_sentences_are_the_plans():
    assert (bot.HELLO, bot.NOT_LINKED, bot.BAD_CODE, bot.MOVED_LINK, bot.TAKEN, bot.STOPPED) == (HELLO, NOT_LINKED, BAD_CODE, MOVED_LINK, TAKEN, STOPPED)
    assert bot.BAD_CODE_KEPT == BAD_CODE_KEPT and bot.NOT_READ == NOT_READ
    plan = open(os.path.join(ROOT, "docs", "superpowers", "plans", "2026-11-22-relief-stage-4-telegram.md"), encoding="utf-8").read()
    for text in (HELLO, NOT_LINKED, BAD_CODE, BAD_CODE_KEPT, MOVED_LINK, TAKEN, STOPPED, NOT_READ): assert f"`{text}`" in plan, text

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
        with tgdb.db() as c: c.execute("INSERT INTO talks(chat, kind, data, until) VALUES (501, 'x', '{}', ?)", (time.time() + 600,))      # (in a talk that waits for a line a code is the answer)
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
        for text in ("/start", "/help", "/help@practice_bot", "/HELP", "hello there", "/start something long that is not a code", "/cancel", "/settings please"):
            want = NOT_READ if text in ("hello there", "/cancel", "/settings please") else HELLO.format(name=TIA)
            tg.PRACTICE_LOG.clear(); hook(msg(text, 501)); assert sent() == [(501, want)], (text, sent())
        assert not links.tries.fails.get("tg:501") and links.name_of(501) == TIA

@t
def what_is_not_read_is_said():
    """a linked person's line that is no command, no code and no answer: NOT_READ, as often as it comes; an unlinked chat and a group as before"""
    with telegram():
        links.link(TIA, 501, None)
        for text in ("Noted", "Sorry, I can't", "ok", " ", "/cancel", "/stopp"):
            tg.PRACTICE_LOG.clear(); hook(msg(text, 501)); assert sent() == [(501, NOT_READ)], (text, sent())
        for k in range(8): tg.PRACTICE_LOG.clear(); hook(msg(f"Thanks {k}", 501)); assert sent() == [(501, NOT_READ)], k
        assert not links.tries.fails.get("tg:501") and links.name_of(501) == TIA, "counted against nothing"
        tg.PRACTICE_LOG.clear(); hook(msg("Noted", 777)); assert sent() == [(777, NOT_LINKED)], sent()
        tg.PRACTICE_LOG.clear(); hook(msg("Noted", 501, kind="group")); assert tg.PRACTICE_LOG == [], "a group stays silent"

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
            bot.handle(dict(message={"chat": dict(id=501, type="private"), "from": dict(id=501, is_bot=False), "text": text}))
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
def without_the_relief_right_nobody_is_reached():
    ON = dict(relief=True, exams=None, admin=False)
    with telegram():
        links.link(EXE, 505, None); links.link(TIA, 501, None)
        assert links.chat_of(EXE) is None and links.name_of(505) is None and links.reachable() == links.reachable(PUB) == {TIA: 501}
        assert links.person(505)["name"] == EXE and "relief" not in links.rights_of(505) and EXE in links.linked(), "there, and linked, all the same"
        assert OB.queue("k", EXE, "x", kind="made-up") is False
        hook(msg("/help", 505)); assert sent() == [(505, NOT_LINKED)] and len(links.tries.fails["tg:505"]) == 1
        with record(EXE, extras=ON):                                                       # the extra given: at once
            assert links.chat_of(EXE) == 505 and links.name_of(505) == EXE and links.reachable() == {TIA: 501, EXE: 505}
            tg.PRACTICE_LOG.clear(); hook(msg("/help", 505)); assert sent() == [(505, HELLO.format(name=EXE))] and OB.queue("k", EXE, "x", kind="made-up") is True
        assert OB.send_due()["sent"] == 0 and OB.told("k")["state"] == "dropped", "taken away before it went"
        with record(TIA, group="executive"): assert links.chat_of(TIA) is None and links.name_of(501) is None and links.reachable() == {}
        assert links.chat_of(TIA) == 501
        with no_pub():                                                                     # nothing published: from the record alone
            assert links.chat_of(EXE) is None and links.name_of(505) is None and links.chat_of(TIA) == 501 and links.reachable() == {TIA: 501}
            with record(EXE, extras=ON): assert links.reachable() == {TIA: 501, EXE: 505}
        c = links.new_code(TIA)["code"]; hook(msg(c, 501)); tg.PRACTICE_LOG.clear()
        with record(TIA, group="executive"): assert links.again(c, 501) is None; hook(msg(c, 501, message_id=9)); assert sent() == [(501, BAD_CODE)], "the link pressed again"
        assert links.again(c, 501) == TIA
        n = len(entries()); tg.PRACTICE_LOG.clear(); hook(msg("/stop", 505))                # /stop still unlinks
        assert EXE not in links.linked() and sent() == [(505, NOT_LINKED)] and [e["who"] for e in entries()[:len(entries()) - n]] == [EXE]

@t
def the_code_route_needs_a_person_and_a_connection():
    API = "/api/relief/telegram"
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    tia = who(TIA)
    off = dict(on=False, connected=False, bot=None, linked=False, handle=None, since=None, blocked=None)
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
        assert j["url"] == "practice" and "practice_bot" not in json.dumps(j), "no bot to open: that name may be a stranger's"
        assert [r["name"] for r in rows("codes")] == [TIA]
        assert hook(msg(f"/start {j['code']}", 501, user="tia_t")).status_code == 200
        j = tia.get(API).get_json()
        assert (j["on"], j["connected"], j["bot"], j["linked"], j["handle"]) == (True, True, "practice_bot", True, "tia_t") and j["since"][:4] >= "2026", j
        assert set(j) == {"on", "connected", "bot", "linked", "handle", "since", "blocked"} and "501" not in json.dumps(j)
        assert who(HUGO).get(API).get_json()["linked"] is False, "each person sees their own link only"
        r = tia.delete(API + "/link"); assert r.status_code == 200 and r.get_json()["linked"] is False and links.linked() == {}
        assert tia.delete(API + "/link").status_code == 200                             # nothing to take away: the same answer
        links.link(TIA, 501, None)
        with record(TIA, off=True): assert who(TIA).get(API).status_code == 401
    with telegram(token="made-up-" + secrets.token_hex(10)):
        j = tia.post(API + "/code").get_json(); assert set(j) == {"code", "url", "until"} and CODE_SHAPE.match(j["code"]) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", j["code"])
        assert j["url"] == f"https://t.me/ctss_made_up_bot?start={j['code']}"
    assert REAL == []

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
        assert tg.PRACTICE_LOG[1][1] == dict(url="http://localhost/telegram/hook", secret_token=tg.hook_secret(), allowed_updates=["message", "edited_message", "callback_query"],
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
            assert go(now) == dict(sent=0, waiting=1) and len(texts(seen)) == i + 1
            r = item("k"); assert (r["state"], r["tries"], r["next_at"], r["sent_at"]) == ("queued", i + 1, now + wait, None), r
            assert OB.told("k")["state"] == "queued" and OB.told("k")["at"] == r["at"]
            go(now + wait - 1); assert len(texts(seen)) == i + 1, "it waits"                # Telegram answers getMe then: it is the message itself
            now += wait
        assert go(now) == dict(sent=0, waiting=0) and state("k") == "failed" and len(texts(seen)) == 6
        go(9e12); assert len(texts(seen)) == 6 and q() is False
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
            f, seen = tele(me=me); times.clear(); OB._asked[0] = 0.0                        # twenty seconds later, each time
            assert go(f) == dict(sent=0, waiting=2) and seen == [("getMe", {}, None)] and rows("outbox") == was, me
            assert times == [("getMe", 5)] and links.chat_of(TIA) == 501, me
        q("d", text="d"); f, seen = tele(me=DOWN); OB._asked[0] = 0.0; assert go(f) == dict(sent=0, waiting=3) and said(seen) == ["getMe"], "what comes meanwhile waits too"
        OB._asked[0] = 0.0
        with broken_accounts(): f, seen = tele(); assert go(f) == dict(sent=0, waiting=3) and seen == []
        b = tgdb.get_state("bot"); tgdb.set_state("bot", None); assert go(f) == dict(sent=0, waiting=3) and seen == []; tgdb.set_state("bot", b)
        f, seen = tele(); assert go(f) == dict(sent=3, waiting=0) and said(seen) == ["getMe"] + ["sendMessage"] * 3 and texts(seen) == ["b", "c", "d"]
        assert state("a") == "unsure"
        q("e"); f, seen = tele(); assert go(f)["sent"] == 1 and said(seen) == ["sendMessage"], "asked once"
        # it comes back and goes again: one more message, not all of them
        for k in "wxyz": q(k, text=k)
        for k in "wx": f, seen = tele(MAY_HAVE); go(f); assert texts(seen) == [k] and state(k) == "unsure"
        f, seen = tele(); assert go(f) == dict(sent=2, waiting=0) and texts(seen) == ["y", "z"]
        # a refusal, a blocked chat or a flood answer is no such doubt; a failure to connect, or a token that is not taken, is
        for answer_, doubt in ((REFUSED, False), (NEVER_LEFT, True), (DOWN, True), ((401, dict(ok=False)), True), ((404, dict(ok=False)), True), (SLOW(1), False), (BLOCKED, False)):
            OB._doubt.clear(); OB._hold[0] = 0.0; f, seen = tele(answer_); q("h" + str(len(rows("outbox")))); go(f); assert OB._doubt.is_set() is doubt and len(seen) == 1, answer_

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
        f, seen = tele(me=MAY_HAVE, before=wait); got = []; OB._asked[0] = 0.0                                  # while getMe is
        def both():
            th = threading.Thread(target=lambda: got.append(OB.send_due())); th.start(); assert inside.wait(10)
            assert other() == [busy, busy]; go.set(); th.join(10)
        with_send(f, both); assert got == [dict(sent=0, waiting=2)] and [m for m, p, up in seen] == ["getMe"] and OB._doubt.is_set()
        ths = [threading.Thread(target=OB.send_due) for _ in range(6)]; f, seen = tele(me=NEVER_LEFT); OB._asked[0] = 0.0
        with_send(f, lambda: ([x.start() for x in ths], [x.join() for x in ths])); assert [m for m, p, up in seen] == ["getMe"] and OB._doubt.is_set()
        OB._asked[0] = 0.0; f, seen = tele(); assert with_send(f, OB.send_due) == dict(sent=2, waiting=0) and texts(seen) == ["b", "c"]

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
        assert state("r") == "dropped" and len(texts(seen)) == 1, "asked again before another try"

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
        kbs = [p["reply_markup"]["inline_keyboard"] for m, p, up in seen if m == "sendMessage"]
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
        with tgdb.db() as c: [c.execute("INSERT INTO talks(chat, kind, data, until) VALUES (?, 'change', '{}', ?)", (700 + d, now.timestamp() + d)) for d in (-1, 0, 1)]
        OB.send_due(); q("more"); OB.recover(); put("sending401", state="sending"); put("sending399", state="sending")
        assert len(rows("outbox")) == 13 and len(rows("buttons")) == 2 and len(rows("talks")) == 3, "nothing else prunes"
        OB.prune(now=now.timestamp())
        left = {r["key"] for r in rows("outbox")}
        assert left == {"queued401", "sending401", "more"} | {s + "399" for s in ("queued", "sending", "sent", "failed", "unsure", "dropped")}, left
        assert [r["token"] for r in rows("buttons")] == ["t1"]
        assert [r["chat"] for r in rows("talks")] == [700, 701], "a talk past its deadline, also one nobody ever wrote in again"

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
    code = "import threading, app; from relief import tell; print(sorted(x.name for x in threading.enumerate() if x.name.startswith('relief')), [f'{f.__module__}.{f.__name__}' for f in tell.MINUTE])"
    def go(jobs, token):
        env = dict(os.environ, DATA_DIR=tempfile.mkdtemp(), RELIEF_JOBS=jobs, TELEGRAM_BOT_TOKEN=token)
        return subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    cases = [("on", "practice", "['relief-telegram', 'relief-tell-ticker', 'relief-ticker'] ['relief.tell.sweep', 'relief.report.tick', 'relief.bot.forget']"), ("on", "", "['relief-ticker'] []"), ("", "practice", "[] []")]
    for p, (jobs, token, want) in zip([go(j, k) for j, k, w in cases], cases):
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0 and out.strip().splitlines()[-1] == want, (jobs, token, out[-300:], err[-300:])

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

def ask_buttons(i, name=MAYA, short="Ms Lee"): return [[dict(text=f"Approve {short}", what="approve", id=i, ckey=K5, who=name, extra=dict(absent=EVE, date="2026-10-13"))], [dict(text="Open in the app", url=BASE + "/relief#today")]]

def asked(*, pick=True):
    """Sam's relief, told, then asked to change at 09:10 -> the absence's id"""
    i = absent(by=HUGO); give(i, K5, SAM); swept(); at("09:10")
    if pick: on_cover(SAM, i, K5, "ask-change", dict(why="A parent meeting"))              # in the app: the pick is made at once
    else: CV.ask_change(i, K5, "A parent meeting", SAM)
    return i

RELIEF_K5 = "🔔 Relief for you · Tue 13 Oct\n1A, 1B Science (G2) · P6–P7 · 10:30–11:30\nRoom 2-05\nFor Ms Evelyn Koh\nNo work set yet: look in Reliefs I'm covering."
MOVED_K5 = "✔ The relief team has moved 1A, 1B Science (G2) P6–P7 on Tue 13 Oct to someone else. You're free then."
GONE_K5 = "❌ No longer needed: 1A, 1B Science (G2) P6–P7 (10:30) on Tue 13 Oct. You're free then."
KEPT_K5 = "The relief team has kept 1A, 1B Science (G2) P6–P7 on Tue 13 Oct with you."
ASK_K5 = "↩ Request to change\nMr Sam Tan · 1A, 1B Science (G2) · P6–P7 (10:30) on Tue 13 Oct\n“A parent meeting”\n"
PLANNED_EVE = "📋 Relief planned for you\nTue 13 Oct · whole day\nPlanned by Mr Hugo Ong\n2 lessons will be covered.\nPlease acknowledge and set work for the relief teachers."
REMIND_EVE = "⏰ Reminder: please acknowledge your relief for Tue 13 Oct and set work."
OFFICER_EVE = "Ms Evelyn Koh is away on Tue 13 Oct (whole day): Medical.\nRelief is being arranged."
CANCELLED_EVE = "❌ Cancelled by {}: Ms Evelyn Koh's absence on Tue 13 Oct. Its reliefs are no longer needed."
CANCELLED_BY_APP = "❌ Cancelled: Ms Evelyn Koh's absence on Tue 13 Oct. Its reliefs are no longer needed."

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
    got += "\n" + TE.relief_text("", "x", "", "", "", "", {}).splitlines()[-1] + "\n" + TE.cancelled_text("app", "{absent}", "{days}")
    got += "\n" + TE.stopped_text("{lesson}", "{periods}", "{start}", "{day}", "{why}") + "\n" + TE.again_text("{lesson}", "{periods}", "{start}", "{day}")
    for line in got.splitlines(): assert f"`{line}`" in plan, line
    assert len(got.splitlines()) == 7 + 5 + 1 + 2 + 1 + 1 + 1 + 1 + 5 + 3 + 3, got
    for label in ("✅ Acknowledge", "↩ Request to change", "✅ Acknowledge and set work", "❌ Not needed: cancel", "Open in the app"): assert f"`{label}`" in plan
    # whole, in order, with made-up words
    assert TE.relief_text("Tue 13 Oct", "2B Science", "P9–P11", "10:40–11:40", "2-06", EVE, dict(text="Notes, chapter 6.", link="https://x.org/a", files=[dict(id="a"), dict(id="b")])) == \
        "🔔 Relief for you · Tue 13 Oct\n2B Science · P9–P11 · 10:40–11:40\nRoom 2-06\nFor Ms Evelyn Koh\nWork from Ms Evelyn Koh: Notes, chapter 6.\nLink: https://x.org/a\nFiles: 2, sent after this message."
    assert TE.relief_text("Tue 13 Oct", "2B Science", "P9", "", "", EVE, {}) == "🔔 Relief for you · Tue 13 Oct\n2B Science · P9\nFor Ms Evelyn Koh\nNo work set yet: look in Reliefs I'm covering."
    for work, last in ((dict(text="", link="https://x.org/a", files=[]), ["Link: https://x.org/a"]), (dict(files=[1]), ["Files: 1, sent after this message."])):   # work, with nothing typed: it is not said that none is set
        assert TE.relief_text("d", "l", "P1", "", "", EVE, work).splitlines()[2:] == ["For Ms Evelyn Koh"] + last
    assert TE.planned_text("Tue 13 Oct", "whole day", HUGO, 2) == PLANNED_EVE and "\n1 lesson will be covered.\n" in TE.planned_text("d", "whole day", HUGO, 1)
    assert TE.remind_text("Tue 13 Oct") == REMIND_EVE and TE.officer_text(EVE, "Tue 13 Oct", "whole day", "Medical") == OFFICER_EVE
    assert TE.cancelled_text(HUGO, EVE, "Tue 13 Oct") == CANCELLED_EVE.format(HUGO) and TE.cancelled_text("app", EVE, "Tue 13 Oct") == CANCELLED_BY_APP
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
    assert not hasattr(TE, "links") and TE._links is links, "due has a parameter of that name: the module goes by another"
    assert OB.VALID is TE.still_true and TE.still_true(dict(key="any")) is True and TE.still_true(dict(key="x", kind="exam-duty", ref=None)) is True
    assert {"relief", "gone", "moved", "stopped", "again", "kept", "planned", "remind", "officer", "cancelled", "ask", "askpick", "report", "clear", "weekly"} == set(TE.CHECKS)

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
            for module, name in ((TE, "due"), (store, "published"), (links, "reachable"), (TE, "_records"), (RS, "load"), (links, "connected"), (OB, "told_for"), (AP, "staff")):
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

@t
def pressing_connect_again_keeps_when_it_was_first_connected():
    com, API = client(dict(role="committee")), "/api/relief/telegram/"
    def connect(hm): clock.now = f"2026-10-12T{hm}:00+08:00"; assert com.post(API + "connect").status_code == 200; return links.connected()["at"][11:16]
    with school(EVE):
        tgdb.set_state("bot", None); assert connect("09:00") == "09:00" and connect("10:00") == "09:00", "the same bot"
        b = tgdb.get_state("bot"); assert set(b) == {"username", "base", "at", "key"}
        for changed in (dict(b, username="another_bot"), dict(b, key=digest("another")), dict(b, at=None), "odd", None): tgdb.set_state("bot", changed); assert connect("11:00") == "11:00", changed
        com.post(API + "disconnect"); assert connect("12:00") == "12:00", "disconnected in between"
        tgdb.set_state("bot", dict(b, base="https://old.example.org")); assert connect("13:00") == "09:00" and links.connected()["base"] == "http://localhost", "the address is the new one"
        real = os.environ["SECRET_KEY"]; os.environ["SECRET_KEY"] = secrets.token_hex(16)
        try: assert connect("14:00") == "14:00", "another key"
        finally: os.environ["SECRET_KEY"] = real
        # what was done before Connect was pressed again is still told
        tgdb.set_state("bot", None); connect("09:00"); clock.now = "2026-10-12T09:30:00+08:00"; absent(by=HUGO); connect("10:00"); TE.sweep(); assert told_of() == [("planned", EVE)]

# ---- tell's own minute
class FakeStop:
    """a stand-in for the ticker's wait: keeps what it was asked to wait, and ends the loop after n"""
    def __init__(s, n): s.n, s.waits = n, []
    def wait(s, seconds): s.waits.append(seconds); return len(s.waits) > s.n
    def clear(s): pass
    def set(s): pass

@t
def the_minute_runs_every_hook_and_never_dies():
    h, seen = Grab(), []; KINDS.addHandler(h)
    def boom(): seen.append("boom"); raise LookupError(f"{SAM} a private line")
    try:
        assert TE.MINUTE == [], "nothing is hooked in a test"
        TE.MINUTE.extend([lambda: seen.append("a"), boom, lambda: seen.append("b")])
        with stand_in(TE, "_stop", FakeStop(3)): TE._loop(60); waits = TE._stop.waits
        assert seen == ["a", "boom", "b"] * 3 and 0 < waits[0] <= 10 and waits[1:] == [60, 60, 60], (seen, waits)
        assert [r.getMessage() for r in h.records].count(h.records[0].getMessage()) == 3 == len(h.records) and "LookupError" in h.records[0].getMessage()
        assert not any("private" in r.getMessage() or SAM in r.getMessage() or r.exc_info for r in h.records)
        # one daemon thread, started once, and again once it has ended
        assert not any(x.name == "relief-tell-ticker" for x in threading.enumerate()), "importing app starts none"
        del seen[:]; inside, let = threading.Event(), threading.Event()
        class Wait(FakeStop):
            def wait(s, seconds): inside.set(); let.wait(10); return True
        with stand_in(TE, "_stop", Wait(0)):
            th = TE.start(every=5); assert inside.wait(10) and TE.start() is th and TE.start(every=1) is th and th.daemon and th.name == "relief-tell-ticker"
            assert [x.name for x in threading.enumerate()].count("relief-tell-ticker") == 1
            let.set(); th.join(10); assert not th.is_alive()
            other = TE.start(); assert other is not th; other.join(10)
        # as it runs: the first time soon, whatever `every` is
        with stand_in(TE, "FIRST", 0.01):
            th = TE.start(every=60); began = time.monotonic()
            while not seen and time.monotonic() - began < 5: time.sleep(0.01)
            assert seen[:1] == ["a"] and TE.start() is th; TE._stop.set(); th.join(5); assert not th.is_alive()
    finally: TE.MINUTE.clear(); TE._stop.set(); KINDS.removeHandler(h)

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
def what_waited_is_not_sent_once_the_relief_is_theirs_again():
    """Telegram is down when gone (or moved) is to go; meanwhile the same person is approved again, and that message goes first"""
    later = lambda: OB.send_due(now=time.time() + 4000)["sent"]
    for how in ("gone", "moved"):
        with school(SAM, MAYA):
            i = absent(by=HUGO); give(i, K5, SAM); swept(); key = f"{how}:{outs()[0]['key']}"; at("09:10")
            def end():
                if how == "gone": absences.not_needed(i, K5, "x", HUGO)
                else: give(i, K5, MAYA)
            def back():
                if how == "gone": absences.needed_again(i, K5, HUGO)
                give(i, K5, SAM)
            end(); TE.sweep(); put(key, tries=4, next_at=time.time() + 1800); at("09:20"); back(); swept()
            assert said(SAM) == [RELIEF_K5] * 2 and state(key) == "queued"
            later(); assert state(key) == "dropped" and said(SAM) == [RELIEF_K5] * 2 and swept() == 0, "never said after it"
            at("09:30"); end(); swept(); swept(); assert said(SAM)[2:] == [GONE_K5 if how == "gone" else MOVED_K5], "theirs no more again: said, once"
            # dropped, and the second approval never went: what was told first still has to be said to have ended
        with school(SAM, MAYA):
            i = absent(by=HUGO); give(i, K5, SAM); swept(); key = f"{how}:{outs()[0]['key']}"; at("09:10"); end(); TE.sweep(); put(key, tries=4, next_at=time.time() + 1800)
            at("09:20"); back(); TE.sweep(); later_key = outs("relief", SAM)[-1]["key"]; put(later_key, next_at=time.time() + 9000); later(); assert state(key) == "dropped" and len(said(SAM)) == 1
            at("09:30"); end(); swept(); later(); OB.send_due(now=time.time() + 10_000)
            assert state(later_key) == "dropped" and said(SAM) == [RELIEF_K5, GONE_K5 if how == "gone" else MOVED_K5]
    for s in ("approved", "acknowledged", "change"):                                       # theirs, in each of the three states, wherever the cover is now
        with school(SAM):
            i = absent(by=HUGO); give(i, K5, SAM); swept(); ref = json.loads(outs()[0]["ref"]); at("09:10"); give(i, K5, SAM)
            if s == "acknowledged": CV.acknowledge(i, K5, SAM)
            if s == "change": CV.ask_change(i, K5, "x", SAM)
            assert CV.state(*covered(i, K5)) == s and [TE.still_true(dict(kind=k, ref=ref)) for k in ("gone", "moved")] == [False, False], s
            assert [TE.still_true(dict(kind=k, ref=dict(ref, who=MAYA))) for k in ("gone", "moved")] == [True, True], "approved to another: said"
            r = absences.load(i); x = next(x for x in r["lessons"] if x["key"] == K5); r["lessons"].remove(x); absences._save(r); absences._save(dict(r, id="dead00beef", lessons=[x]))
            assert TE.still_true(dict(kind="gone", ref=ref)) is False, "in another absence of the same teacher"
            absences.cancel("dead00beef", "x", HUGO); assert TE.still_true(dict(kind="gone", ref=ref)) is True and TE.still_true(dict(kind="moved", ref=ref)) is True
            j = absent(dates=["2026-10-16"]); open(absences._path(j), "w", encoding="utf-8").write("{ not json")
            assert [TE.still_true(dict(kind=k, ref=ref)) for k in ("gone", "moved")] == [True, True], "another one that cannot be read"
            open(absences._path(i), "w", encoding="utf-8").write("{ not json")
            for k in ("gone", "moved"):
                try: TE.still_true(dict(kind=k, ref=ref)); raise AssertionError(k)
                except ValueError: pass                                                    # the one that should hold it cannot be read: it waits

@t
def a_message_of_the_team_goes_only_to_who_is_on_it_when_it_goes():
    OFF = dict(relief=False, exams=None, admin=False)
    with school(SAM, MAYA, TEAM, LEE):
        i = asked(pick=False); at("09:12"); assert TE.sweep() == 2
        with record(LEE, extras=OFF): send(); assert links.chat_of(LEE) and said(LEE) == [] and len(said(TEAM)) == 1
        assert state(f"ask:{EVE}:{K5}:2026-10-12T09:10:00+08:00:{LEE}") == "dropped"
        new_pick(i, K5, MAYA); assert TE.sweep() == 2                                      # on it again: the ask for one, the pick for the other
        with record(LEE, extras=OFF), record(TEAM, extras=OFF): assert send() == 0 and len(said(TEAM)) == 1 and said(LEE) == []
        assert swept() == 2 and len(said(TEAM)) == 2 and len(said(LEE)) == 1 and "New pick: Ms Maya Lee" in said(LEE)[0]
    with school(EVE, ROSA, HUGO, TEAM, LEE):                                               # cancelled: as the team, or as the planner, the absent teacher, the officer
        ON = dict(OFF, relief=True)
        with record(HUGO, extras=ON), record(EVE, extras=ON), record(ROSA, extras=ON):
            i = absent(by=HUGO); swept(); absences.cancel(i, "x", SAM, team=True); TE.sweep(); assert {n for k, n in told_of("cancelled")} == {EVE, ROSA, HUGO, TEAM, LEE}
        with record(TEAM, extras=OFF): send()
        assert {r["name"]: r["state"] for r in outs("cancelled")} == {EVE: "sent", ROSA: "sent", HUGO: "sent", LEE: "sent", TEAM: "dropped"}, "none of those three is on the team now"
        with broken_accounts():
            try: TE.still_true(dict(next(r for r in outs("cancelled") if r["name"] == LEE), ref=dict(id=i, team=True))); raise AssertionError("said")
            except ValueError: pass                                                        # nobody's rights are known: it waits

@t
def nothing_goes_about_a_lesson_that_is_over_when_it_goes():
    for kind in ("ask", "askpick", "gone", "moved", "kept"):
        for hm, n in (("11:29", 1), ("11:30", 0)):                                         # P6-P7 ends at 11:30 on Tuesday
            with school(SAM, MAYA, TEAM):
                i = absent(by=HUGO); give(i, K5, SAM); swept(); at("11:00", 13)
                if kind in ("ask", "askpick", "kept"): CV.ask_change(i, K5, "x", SAM)
                if kind == "kept": CV.keep(i, K5, TEAM)
                if kind == "askpick": at("11:05", 13); swept(); new_pick(i, K5, MAYA)
                if kind == "ask": new_pick(i, K5, MAYA)
                if kind == "gone": absences.not_needed(i, K5, "x", HUGO)
                if kind == "moved": give(i, K5, MAYA)
                TE.sweep(); assert [r["state"] for r in outs(kind)] == ["queued"], kind; at(hm, 13); send()
                assert [r["state"] for r in outs(kind)] == [("dropped", "sent")[n]], (kind, hm)

@t
def a_kept_that_waited_goes_only_while_it_stands():
    for later in ("nothing", "acknowledged", "asked again", "kept again", "moved", "approved anew", "cancelled", "not needed"):
        with school(SAM, MAYA):
            i = asked(pick=False); at("09:20"); CV.keep(i, K5, TEAM); TE.sweep(); r, = outs("kept"); at("09:30")
            assert json.loads(r["ref"]) == dict(id=i, absent=EVE, ckey=K5, who=SAM, approved_at="2026-10-12T09:00:00+08:00", at="2026-10-12T09:20:00+08:00", ends="2026-10-13T11:30:00+08:00")
            if later == "acknowledged": CV.acknowledge(i, K5, SAM)
            if later in ("asked again", "kept again"): CV.ask_change(i, K5, "Again", SAM)
            if later == "kept again": CV.keep(i, K5, TEAM)
            if later == "moved": give(i, K5, MAYA)
            if later == "approved anew": give(i, K5, SAM)
            if later == "cancelled": absences.cancel(i, "x", HUGO)
            if later == "not needed": absences.not_needed(i, K5, "x", HUGO)
            send(); assert (KEPT_K5 in said(SAM)) == (later in ("nothing", "acknowledged")) and state(r["key"]) == ("sent" if later in ("nothing", "acknowledged") else "dropped"), later
            if later == "kept again": swept(); assert said(SAM)[1:] == [KEPT_K5], "the second says it, once"
            if later == "nothing": assert TE.still_true(dict(r, ref=dict(json.loads(r["ref"]), who=MAYA))) is False
    with school(SAM, MAYA):                                                                # moved and given back in the second it was kept: another approval
        i = asked(pick=False); at("09:20"); CV.keep(i, K5, TEAM); TE.sweep(); give(i, K5, MAYA); give(i, K5, SAM); send(); assert KEPT_K5 not in said(SAM)

@t
def an_ask_that_waited_goes_with_the_pick_there_is():
    with school(SAM, MAYA, TEAM):                                                          # it carried a pick that went, and then another came
        i = asked(pick=False); new_pick(i, K5, MAYA); TE.sweep(); ask_ = outs("ask")[0]["key"]; CV.drop(i, K5, "x", who=MAYA, into="change")
        assert send() == 0 and state(ask_) == "dropped" and said(TEAM) == [], "no pick now"
        new_pick(i, K5, HUGO); assert swept() == 1 and len(said(TEAM)) == 1 and "New pick: Mr Hugo Ong" in said(TEAM)[0] and told_of("askpick") == []
    with school(SAM, MAYA, TEAM):                                                          # it said there was none, and one came before it went: one message, with it
        i = asked(pick=False); at("09:12"); TE.sweep(); new_pick(i, K5, MAYA); assert send() == 0 and swept() == 1 and len(said(TEAM)) == 1 and "New pick: Ms Maya Lee" in said(TEAM)[0]
        assert swept() == 0 and told_of("askpick") == []
    with school(SAM, MAYA, TEAM):                                                          # the pick sent once more changed before it went
        i = asked(pick=False); at("09:12"); swept(); new_pick(i, K5, MAYA); TE.sweep(); CV.drop(i, K5, "x", who=MAYA, into="change"); new_pick(i, K5, HUGO)
        assert send() == 0 and swept() == 1 and len(said(TEAM)) == 2 and "New pick: Mr Hugo Ong" in said(TEAM)[1] and swept() == 0

@t
def a_request_taken_over_by_another_absence_is_not_told_again():
    def take_over(i, j="dead00beef"):
        r = absences.load(i); x = next(x for x in r["lessons"] if x["key"] == K5)
        r["lessons"].remove(x); absences._save(r); absences._save(dict(r, id=j, how="asked", by=EVE, lessons=[x], at=clock.now))
    for sent_ in (True, False):                                                            # told already, or still waiting to go
        with school(SAM, MAYA, TEAM):
            i = asked(pick=False); at("09:12"); (swept if sent_ else TE.sweep)(); take_over(i); send(); assert swept() == 0 and len(said(TEAM)) == 1, sent_
            new_pick("dead00beef", K5, MAYA); (swept if sent_ else TE.sweep)(); take_over("dead00beef", "cafe00beef"); send(); assert swept() == 0 and len(said(TEAM)) == 2 and told_of("askpick") == [("askpick", TEAM)]
            at("09:20"); CV.keep("cafe00beef", K5, TEAM); (swept if sent_ else TE.sweep)(); take_over("cafe00beef", "beef00cafe"); send(); assert swept() == 0 and said(SAM) == [RELIEF_K5, KEPT_K5]
    with school(SAM, MAYA, TEAM):                                                          # two teachers' absences of a lesson they share: each its own request
        i = absent(by=HUGO, lessons=[dict(key=K8, needed=True)]); j = absent(teacher=BUSY, lessons=[dict(key=K8, needed=True)])
        give(i, K8, SAM); give(j, K8, MAYA); CV.ask_change(i, K8, "x", SAM); CV.ask_change(j, K8, "y", MAYA); at("09:12"); swept(); assert len(said(TEAM)) == 2

@t
def a_relief_key_stays_the_same_when_the_first_persons_is_gone():
    """two approvals in one second, and the first person has blocked the bot: the queue forgets theirs, the second is told once"""
    with school(SAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); give(i, K5, MAYA); TE.sweep(); base = f"relief:{EVE}:{K5}:2026-10-12T09:00:00+08:00"
        put(base, state="sending"); OB._blocked(dict(key=base, name=SAM), CHATS[SAM]); assert item(base) is None and SAM not in links.linked()
        send(); assert swept() == 0 and swept() == 0 and said(MAYA) == [RELIEF_K5] and [r["key"] for r in outs()] == [f"{base}:{MAYA}"]
        at("09:10"); absences.cancel(i, "x", HUGO); swept(); assert said(MAYA) == [RELIEF_K5, GONE_K5]

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
            assert TE._holder(absences.all_records(), dict(ref, id=mine))[2]["relief"] == SAM and TE._holder(absences.all_records(), dict(ref, id=other))[2]["relief"] == MAYA
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
        i = absent(by=HUGO); give(i, K5, SAM); swept(); held, real = [], TE._records
        def half():
            held.append(absences._LOCK.locked()); got, unread = real()
            return got if absences._LOCK.locked() else [dict(v, lessons=[y for y in v["lessons"] if y["key"] != K5]) for v in got], unread
        with stand_in(TE, "_records", half): assert swept() == 0 and held == [False, True] and said(SAM) == [RELIEF_K5] and not absences._LOCK.locked()
        with stand_in(TE, "_records", lambda: held.append(absences._LOCK.locked()) or real()): del held[:]; assert swept() == 0 and held == [False], "read once when nothing is gone"

@t
def a_file_that_is_no_absence_stops_nobodys_messages():
    """one that cannot be read, or a stray one: its kind logged once in a sweep, and it is passed over"""
    h = Grab(); KINDS.addHandler(h)
    try:
        with school(SAM, MAYA, RUTH):
            i = absent(by=HUGO); give(i, K5, SAM); give(i, K2, RUTH); j = absent(dates=["2026-10-16"]); swept(); put_ = lambda name, text: open(os.path.join(absences.DIR, name), "w", encoding="utf-8").write(text)
            put_("my notes.json", "{}"); put_(f"{i}copy.json", json.dumps(absences.load(i))); put_("0badbad0.json", "{ a private line"); put_(f"{j}.json", "[]")
            at("09:10"); give(i, K5, MAYA); absences.not_needed(i, K2, "x", HUGO); h.records.clear(); assert TE.sweep() == 3
            assert sorted(r.getMessage() for r in h.records) == ["an absence could not be read (JSONDecodeError)", "an absence could not be read (ValueError)"], [r.getMessage() for r in h.records]
            send(); assert said(SAM) == [RELIEF_K5, MOVED_K5] and len(said(RUTH)) == 2 and said(MAYA) == [RELIEF_K5], "gone and moved, each once, and nothing from a copy of a record"
            h.records.clear(); assert swept() == 0 and len(h.records) == 2
        with school(SAM, MAYA):                                                            # its own record cannot be read: gone waits; moved is said when the cover is found with another
            i = absent(by=HUGO); give(i, K5, SAM); swept(); r = absences.load(i); good = json.dumps(r); p = absences._path(i)
            open(p, "w", encoding="utf-8").write("{ not json"); assert swept() == 0 and said(SAM) == [RELIEF_K5]
            x = json.loads(json.dumps(next(x for x in r["lessons"] if x["key"] == K5))); x.update(relief=MAYA, approved=dict(by=TEAM, at="2026-10-12T09:10:00+08:00"))
            absences._save(dict(r, id="dead00beef", lessons=[x])); at("09:10"); assert swept() == 2 and said(SAM) == [RELIEF_K5, MOVED_K5] and said(MAYA) == [RELIEF_K5]
        with school(SAM, RUTH):                                                            # both, in one sweep: the one that was read is said
            i = absent(by=HUGO); give(i, K5, SAM); j = absent(dates=["2026-10-16"]); give(j, KF, RUTH); swept(); absences.not_needed(i, K5, "x", HUGO)
            open(absences._path(j), "w", encoding="utf-8").write("{ not json"); assert swept() == 1 and told_of("gone") == [("gone", SAM)]
        with school(SAM):
            assert not os.path.isdir(absences.DIR); h.records.clear(); assert TE.sweep() == 0 and h.records == [], "no absences yet: nothing to say of it"
    finally: KINDS.removeHandler(h)

@t
def a_lesson_that_is_over_is_not_told():
    with school(SAM, MAYA, TEAM):
        i = absent(by=HUGO); at("11:29", 13); give(i, K5, SAM); assert [x["kind"] for x in dues()] == ["relief"]
        at("11:30", 13); assert dues() == [] and TE.sweep() == 0, "its end: nothing more"
        at("11:29", 13); swept(); assert said(SAM) == [RELIEF_K5]
        give(i, K5, MAYA); at("11:30", 13); assert swept() == 0 and len(said(SAM)) == 1, "nor that it moved"
        at("09:00", 14); assert dues() == []
        # queued, and over before it could go
        at("11:29", 13); TE.sweep(); at("11:30", 13); assert send() == 0 and said(MAYA) == [] and len(said(SAM)) == 1 and state(f"relief:{EVE}:{K5}:2026-10-13T11:29:00+08:00:{MAYA}") == "dropped"
    with school(SAM):                                                                      # a period with no times: over when its day is
        i = absent(by=HUGO); give(i, K5, SAM); change_record(i, lambda r: [x.update(p=20) for x in r["lessons"] if x["key"] == K5])
        at("23:59", 13); x, = dues(); assert x["ref"]["ends"] == "2026-10-14T00:00:00+08:00"; swept(); absences.cancel(i, "x", HUGO); assert [x["kind"] for x in dues()] == ["gone"]; at("00:00", 14); assert dues() == []
    with school(SAM, TEAM):
        i = absent(by=HUGO); give(i, K5, SAM); CV.ask_change(i, K5, "A meeting", SAM)
        at("11:29", 13); assert {x["kind"] for x in dues()} == {"ask"}; at("11:30", 13); assert dues() == []
        at("11:29", 13); CV.keep(i, K5, TEAM); assert {x["kind"] for x in dues()} == {"relief", "kept"}; at("11:30", 13); assert dues() == []

@t
def remind_copies_are_not_reliefs_of_their_own():
    """a reminder (Task 6: the relief again, under its key with :r1 after it) tells of the relief, under the relief's own key, and is no relief of its own"""
    def copied(base, *copies, more=()):
        """Sam's relief of K5, its message in state base and its reminders in these -> (the absence's id, its key)"""
        i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); key = f"relief:{EVE}:{K5}:{approved_at(i, K5)}"; put(key, state=base)
        for n, s in enumerate(copies, 1): assert OB.queue(f"{key}:r{n}", SAM, f"again {n}", kind="relief", ref=dict(json.loads(item(key)["ref"]), n=n, **dict(more))); put(f"{key}:r{n}", state=s)
        return i, key
    ends = dict(moved=(lambda i: give(i, K5, MAYA), MOVED_K5), gone=(lambda i: absences.cancel(i, "Better", HUGO), GONE_K5))
    for base, copies, told in (("sent", (), 1), ("unsure", (), 1), ("queued", (), 0), ("sending", (), 0), ("failed", (), 0), ("dropped", (), 0),
                               ("sent", ("sent", "sent"), 1), ("sent", ("failed",), 1), ("unsure", ("unsure",), 1), ("failed", ("sent",), 1), ("failed", ("unsure",), 1), ("failed", ("sent", "sent"), 1), ("failed", ("failed", "sent"), 1),
                               ("queued", ("sent",), 1), ("dropped", ("sent",), 1), ("dropped", ("queued",), 0), ("failed", ("queued",), 0), ("failed", ("sending", "failed"), 0), ("dropped", ("dropped",), 0)):
        for kind, (f, text) in ends.items():
            with school(SAM, MAYA):
                i, key = copied(base, *copies); at("09:10"); f(i); TE.sweep(); TE.sweep()
                got = [r for r in outs() if r["kind"] in ("moved", "gone")]
                assert [(r["key"], r["name"], r["text"]) for r in got] == [(f"{kind}:{key}", SAM, text)] * told, (base, copies, kind, [r["key"] for r in got])
                assert all(json.loads(r["ref"]) == json.loads(item(key)["ref"]) for r in got) and [r["key"] for r in outs("relief", SAM)] == [key] + [f"{key}:r{n}" for n in range(1, len(copies) + 1)], "what the relief's own message holds, and no more reliefs"
    # while it is theirs: no message more because of a reminder; the message itself is queued as its own key says, whatever reminders there are
    for base, n in (("sent", 0), ("unsure", 0), ("failed", 0), ("queued", 0), ("sending", 0), ("dropped", 1)):
        with school(SAM): i, key = copied(base, "sent", "unsure"); assert TE.sweep() == n and TE.sweep() == 0 and sorted(r["key"] for r in outs()) == [key, f"{key}:r1", f"{key}:r2"] and (n == 0 or state(key) == "queued"), base
    # the words it was told in: the message's own when it went, else the last reminder's
    for base, want in (("sent", MOVED_K5), ("failed", MOVED_K5.replace("(G2)", "(G3)"))):
        with school(SAM, MAYA): i, key = copied(base, "sent", more=dict(lesson="1A, 1B Science (G3)")); at("09:10"); give(i, K5, MAYA); TE.sweep(); assert [r["text"] for r in outs("moved")] == [want], base
    for first in (1, 2):                                                                   # whichever of two was written first
        with school(SAM, MAYA):
            i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); key = outs("relief")[0]["key"]; put(key, state="failed"); ref = json.loads(item(key)["ref"])
            for n in (first, 3 - first): OB.queue(f"{key}:r{n}", SAM, "again", kind="relief", ref=dict(ref, n=n, lesson=f"Lesson {n}")); put(f"{key}:r{n}", state="sent")
            at("09:10"); give(i, K5, MAYA); TE.sweep(); assert [r["text"] for r in outs("moved")] == [MOVED_K5.replace("1A, 1B Science (G2)", "Lesson 2")], first
    # approved anew, and told of that by a reminder alone: the last they were told of
    with school(SAM, MAYA):
        i, key = copied("sent"); at("09:05"); give(i, K5, SAM); TE.sweep(); anew = f"relief:{EVE}:{K5}:{approved_at(i, K5)}"; put(anew, state="failed"); OB.queue(anew + ":r1", SAM, "again", kind="relief", ref=dict(json.loads(item(anew)["ref"]), n=1)); put(anew + ":r1", state="sent")
        at("09:10"); give(i, K5, MAYA); TE.sweep(); TE.sweep(); assert [r["key"] for r in outs("moved")] == [f"moved:{anew}"]
    with school(SAM, MAYA):                                                                # a key of one's own (two approved in one second)
        i = absent(by=HUGO); give(i, K5, MAYA); TE.sweep(); give(i, K5, SAM); TE.sweep(); key = f"relief:{EVE}:{K5}:{approved_at(i, K5)}:{SAM}"; put(key, state="failed"); OB.queue(key + ":r1", SAM, "again", kind="relief", ref=dict(json.loads(item(key)["ref"]), n=1)); put(key + ":r1", state="sent")
        absences.cancel(i, "Better", HUGO); TE.sweep(); TE.sweep(); assert [r["key"] for r in outs("gone", SAM)] == [f"gone:{key}"]

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
        assert sorted((r["kind"], r["name"], r["key"]) for r in outs()[3:]) == sorted([("gone", SAM, f"gone:relief:{EVE}:{K5}:2026-10-12T09:00:00+08:00")] + [("cancelled", n, f"cancelled:{i}:{n}") for n in (HUGO, TEAM, LEE, ROSA)]), outs()[3:]
        assert said(HUGO) == said(TEAM) == said(LEE) == [CANCELLED_EVE.format(EVE)] and said(ROSA) == [OFFICER_EVE, CANCELLED_EVE.format(EVE)] and said(EVE) == [PLANNED_EVE] and said(SAM) == [RELIEF_K5, GONE_K5] and "made-up why" not in str(rows("outbox"))
        assert {x["name"] for x in dues(reach={TEAM: 1}, told={})} == {TEAM}, "nobody who cannot be reached"
    for by, want in ((HUGO, {TEAM, LEE, EVE, ROSA}), (TEAM, {HUGO, LEE, EVE, ROSA})):      # never the canceller
        with school(EVE, HUGO, TEAM, LEE, ROSA):
            i = absent(by=HUGO); swept(); absences.cancel(i, "Better", by, team=True); swept(); assert {n for k, n in told_of("cancelled")} == want
    with school(EVE, TEAM, LEE):                                                           # asked by the teacher: there is no planner
        i = absent(); swept(); absences.cancel(i, "Better", TEAM, team=True); swept(); assert told_of("cancelled") == [("cancelled", LEE)]
    with school(TEAM, LEE):                                                                # a team member who is the absent teacher and cancels
        i = absent(teacher=SAM, lessons=[]); absences.cancel(i, "Better", SAM); swept(); assert {n for k, n in told_of("cancelled")} == {TEAM, LEE}
    with record(EVE, extras=dict(relief=True, exams=None, admin=False)), school(EVE, TEAM):  # told of it, and on the team: one message
        i = absent(by=HUGO); swept(); absences.cancel(i, "Better", HUGO); swept(); assert sorted(told_of("cancelled")) == [("cancelled", EVE), ("cancelled", TEAM)] and said(EVE) == [PLANNED_EVE, CANCELLED_EVE.format(HUGO)]
    with school(TEAM):                                                                     # long after, to somebody on the team now: nothing about what is past
        i = absent(); absences.cancel(i, "Better", EVE); at("09:00", 14); assert dues() == []

@t
def cancelled_reaches_whoever_was_told_of_the_absence():
    """the absent teacher told it was planned, and the reporting officer told of it, hear that it is cancelled by someone else"""
    for s, told in (("sent", True), ("unsure", True), ("queued", False), ("sending", False), ("failed", False), ("dropped", False)):
        with school(EVE, ROSA, TEAM):
            i = absent(by=HUGO); TE.sweep(); [put(f"{k}:{i}", state=s) for k in ("planned", "officer")]; absences.cancel(i, "a made-up why", HUGO)
            assert {x["name"] for x in dues() if x["kind"] == "cancelled"} == {TEAM} | ({EVE, ROSA} if told else set()), s
            TE.sweep(); assert {(r["key"], r["text"]) for r in outs("cancelled")} == {(f"cancelled:{i}:{n}", CANCELLED_EVE.format(HUGO)) for n in {TEAM} | ({EVE, ROSA} if told else set())}, s
    for one, other, n in (("planned", "officer", EVE), ("officer", "planned", ROSA)):      # each by their own message alone
        with school(EVE, ROSA):
            i = absent(by=HUGO); TE.sweep(); put(f"{one}:{i}", state="sent"); put(f"{other}:{i}", state="failed"); absences.cancel(i, "x", HUGO); assert [x["name"] for x in dues()] == [n]
    with school(EVE, TEAM, since="2026-10-12T09:30:00+08:00"):                             # planned before the bot was connected: told by the reminder alone
        i = absent(by=HUGO); at("15:00"); swept(); assert said(EVE) == [REMIND_EVE]; absences.cancel(i, "x", HUGO); swept(); assert said(EVE) == [REMIND_EVE, CANCELLED_EVE.format(HUGO)]
    with school(TEAM):                                                                     # not linked then: never told of it, nor of its end
        i = absent(by=HUGO); swept(); absences.cancel(i, "x", HUGO); [links.link(n, CHATS[n], None) for n in (EVE, ROSA)]; swept(); assert said(EVE) == said(ROSA) == []
    with school(EVE, ROSA, TEAM):                                                          # queued and cancelled before it went: neither
        i = absent(by=HUGO); TE.sweep(); absences.cancel(i, "x", HUGO); send(); swept(); assert said(EVE) == said(ROSA) == [] and said(TEAM) == [CANCELLED_EVE.format(HUGO)]
    for by in (EVE, ROSA):                                                                 # the canceller never
        with school(EVE, ROSA):
            i = absent(by=HUGO); swept(); absences.cancel(i, "x", by, team=True); swept(); assert told_of("cancelled") == [("cancelled", ROSA if by == EVE else EVE)], by
    with school(EVE, ROSA):                                                                # asked by the teacher, cancelled by the team: the officer alone was told
        i = absent(); swept(); absences.cancel(i, "x", TEAM, team=True); swept(); assert told_of("cancelled") == [("cancelled", ROSA)] and said(EVE) == []
        j = absent(dates=["2026-10-16"]); swept(); absences.cancel(j, "x", TEAM, team=True); links.unlink(ROSA); assert dues() == [], "not reached now"
        links.link(ROSA, CHATS[ROSA], None); at("09:00", 17); assert dues() == [], "past"

@t
def a_cancelled_that_waited_goes_only_while_the_absence_is_not_past():
    """the bot disconnected, or Telegram down, until then: nothing of a past day is said"""
    for hm, day, goes in (("23:59", 13, True), ("00:00", 14, False), ("08:00", 20, False)):
        with school(EVE, ROSA, HUGO, TEAM, LEE):
            i = absent(by=HUGO); swept(); at("09:10"); absences.cancel(i, "Better", EVE); assert TE.sweep() == 4; b = tgdb.get_state("bot"); tgdb.set_state("bot", None); assert send() == 0; tgdb.set_state("bot", b)
            at(hm, day); assert send() == (4 if goes else 0) and {(r["name"], r["state"]) for r in outs("cancelled")} == {(n, "sent" if goes else "dropped") for n in (HUGO, ROSA, TEAM, LEE)}, (hm, day)
            assert swept() == 0 and len(outs("cancelled")) == 4, "nor made anew"
    for day, goes in ((16, True), (17, False)):                                            # its last date, of several
        with school(TEAM): i = absent(dates=["2026-10-13", "2026-10-16"]); absences.cancel(i, "Better", EVE); TE.sweep(); at("09:00", day); assert send() == goes, day
    with school(EVE, TEAM):                                                                # its record gone: nothing; not readable: it waits
        i = absent(by=HUGO); swept(); absences.cancel(i, "Better", HUGO); TE.sweep(); it = [dict(r, ref=json.loads(r["ref"])) for r in outs("cancelled")]; assert [TE.still_true(x) for x in it] == [True, True]
        p = absences._path(i); good = open(p, encoding="utf-8").read(); open(p, "w", encoding="utf-8").write("{ not json"); assert send() == 0 and {r["state"] for r in outs("cancelled")} == {"queued"}
        open(p, "w", encoding="utf-8").write(good); os.rename(p, p + ".away"); assert [TE.still_true(x) for x in it] == [False, False]; os.rename(p + ".away", p)

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
@t
def an_ask_waits_for_the_pick_then_goes():
    with school(SAM, MAYA, TEAM, LEE, HUGO, EVE):
        i = asked(pick=False); n = len(outs())
        for hm in ("09:10", "09:11:59"): at(hm); assert TE.sweep() == 0, "two minutes for the pick"
        new_pick(i, K5, MAYA); assert TE.sweep() == 2
        a, b = outs()[n:]; ask_at = "2026-10-12T09:10:00+08:00"
        assert [(r["key"], r["name"], r["kind"], r["text"]) for r in (a, b)] == [(f"ask:{EVE}:{K5}:{ask_at}:{x}", x, "ask", ASK_K5 + "New pick: Ms Maya Lee\nTeaches Science and is free then.") for x in (LEE, TEAM)]
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
        def free_then(*a, **k): calls.append(a[3]["key"]); return real(*a, **k)
        with stand_in(FR, "free_then", free_then):
            at("09:11:59"); assert TE.sweep() == 0 and calls == []
            at("09:12"); assert swept() == 2 and calls == [K5], calls
            r = outs("ask")[0]; assert r["text"] == ASK_K5 + "No new pick yet: open the app." and json.loads(r["buttons"]) == [[dict(text="Open in the app", url=BASE + "/relief#today")]]
            for hm in ("09:13", "10:00"): at(hm); assert swept() == 0
            assert calls == [K5], "asked who is free only for the message that says it"
            new_pick(i, K5, MAYA); del calls[:]; assert swept() == 2 and calls == []
        r = outs("askpick", TEAM)[0]; assert (r["key"], r["name"], r["text"]) == (f"askpick:{EVE}:{K5}:{ask_at}:{TEAM}", TEAM, ASK_K5 + "New pick: Ms Maya Lee\nTeaches Science and is free then.")
        assert buttons_of(r) == ask_buttons(i) and swept() == 0 and len(said(TEAM)) == 2
    with school(SAM, TEAM, limits=dict(fat_per_day=3, other_per_day=None, never=[MAYA, RUTH, BUSY, HUGO, LEE, TEAM, ROSA, OFFIE])):
        i = asked(pick=False); at("09:12"); swept(); assert outs("ask")[0]["text"] == ASK_K5 + "Nobody else is free then: choose someone in the app.", "Sam, who asked, does not count"
    with school(SAM, TEAM, limits=dict(fat_per_day=3, other_per_day=None, never=[MAYA, BUSY, HUGO, LEE, TEAM, ROSA, OFFIE])):
        i = absent(by=HUGO); CV.split(i, K5, 6, TEAM); give(i, K5 + "#0", SAM); CV.ask_change(i, K5 + "#0", "x", SAM); at("09:12"); swept()
        assert outs("ask")[0]["text"].endswith("No new pick yet: open the app."), "a part of a split lesson: Ruth is free for that part"
    with school(SAM, TEAM):                                                                # a date that is no longer a school day: said as plainly
        i = asked(pick=False); at("09:12")
        def odd(*a, **k): raise ValueError("made up")
        with stand_in(FR, "free_then", odd): swept()
        assert outs("ask")[0]["text"].endswith("No new pick yet: open the app.")
    with school(SAM):                                                                      # nobody on the team to tell: nothing is worked out
        i = asked(pick=False); at("09:12")
        with stand_in(FR, "free_then", lambda *a, **k: 1 / 0): assert TE.sweep() == 0

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
        r, = outs("kept"); assert (r["key"], r["name"], r["text"], json.loads(r["buttons"])) == (f"kept:{EVE}:{K5}:2026-10-12T09:20:00+08:00", SAM, KEPT_K5, [])
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
        at("09:20"); CV.ask_change(i, K5, "x", SAM); new_pick(i, K5, MAYA); assert TE.still_true(ask) is False, "another request, with the same pick"; CV.keep(i, K5, TEAM); at("09:10")
        give(i, K5, SAM); assert TE.still_true(relief) is False, "approved anew: that message is the one to go"
        absences.cancel(i, "Better", HUGO); assert TE.still_true(officer) is False and TE.still_true(relief) is False
        for kind in ("exam-duty", "anything"): assert TE.still_true(dict(kind=kind, ref=None)) is True, kind
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
        assert all(TE.still_true(x) is False for x in items), "whatever else cannot be read: its own record is gone"
        open(q_, "w", encoding="utf-8").write(other); os.rename(p + ".away", p)
        with stand_in(TE, "_records", lambda: 1 / 0): assert TE.still_true(items[0]) is True, "every record is read only when its own does not answer"

# ---- lessons an approved exam or event stops (Task 4b)
from exams import approval as EA, relief_links as RL, schedules as SC  # noqa: E402

SCHOOL["model"]["classes"] = [dict(name=c, level=f"Sec {c[0]}") for c in ("1A", "1B", "1C", "2A", "3B", "4A", "5A")]
EXAM, EXAM2, JOURNEY = "Sec 1 Zebra Exam", "Sec 1 Quokka Test", "Sec 1 Lemur Journey"
STOPPED_K5 = f"❌ Not happening: 1A, 1B Science (G2) P6–P7 (10:30) on Tue 13 Oct: 1A, 1B are on {EXAM}. You're free then."
AGAIN_K5 = "✔ On again: 1A, 1B Science (G2) P6–P7 (10:30) on Tue 13 Oct. The relief is yours as before."

@contextlib.contextmanager
def exam_school(*linked, **kw):
    """school, with no exam or event at its start, and none left after it"""
    shutil.rmtree(SC.DIR, ignore_errors=True)
    try:
        with school(*linked, **kw): yield
    finally: shutil.rmtree(SC.DIR, ignore_errors=True)

def saved_exam(s): return SC.save(s, SCHOOL, TERM, "Ms Cora Lim", check=False)["id"]
def again_on(id_): s = SC.load(id_); s.update(status="approved"); s["approved"] = EA.public(s); return saved_exam(s)
def exam(*classes, name=EXAM, date="2026-10-13", duties=(), event=False):
    """an approved exam (or event) holding these classes all day, with these people on its duties ([(name, from, to)]) -> its id"""
    s = SC.new_event(name, [], [], date, date, "Ms Cora Lim", "Ms Cora Lim") if event else SC.new("exam", name, [], date, date, "Ms Cora Lim", pub=SCHOOL)
    s["classes"] = list(classes or ("1A", "1B"))
    s["made"] = dict(seats=[], unseated=[], published_at=None, duties=[dict(key=f"{date} {a}", date=date, start=a, end=b, room="Hall", names=[n]) for n, a, b in duties])
    saved_exam(s); return again_on(s["id"])
def withdraw(id_): s = SC.load(id_); s.update(status="withdrawn", approved=None); saved_exam(s)
def backed_up(kind, going=(EVE,), in_charge=HUGO):
    """an approved exam these people (5A's) invigilate during P6-P7, or in_charge's event of 5A they go with all day, and relief's backups made
    from it -> (the schedule's id, the first one's backup)"""
    if kind == "exam": e = exam("5A", name=EXAM2, duties=[(n, 630, 690) for n in going])
    else:
        s = SC.new_event(JOURNEY, [], ["5A"], "2026-10-13", "2026-10-13", in_charge, in_charge); s["going"] = list(going); saved_exam(s); e = again_on(s["id"])
    RL.sync_all(SCHOOL, TERM, LS.today()); return e, backup_of(going[0])
def backup_of(name): return next(r["id"] for r in absences.all_records() if r.get("exams") and not r["cancelled"] and r["teacher"] == name)
@contextlib.contextmanager
def unreadable():
    """what exams.relief_links reads cannot be read (the line fill logs of it is not printed here)"""
    lg = logging.getLogger("relief.fill"); quiet = logging.NullHandler(); lg.addHandler(quiet); prop, lg.propagate = lg.propagate, False
    try:
        with stand_in(SC, "read_on_site", lambda: 1 / 0): yield
    finally: lg.removeHandler(quiet); lg.propagate = prop
def exam_links(): return RL.Links.load(SCHOOL, TERM)      # what a sweep reads, and gives due
def relief_buttons(i, ckey=K5, who_=SAM, date="2026-10-13"):
    press = dict(id=i, ckey=ckey, who=who_, extra=dict(absent=EVE, date=date))
    return [[dict(press, text="✅ Acknowledge", what="ack"), dict(press, text="↩ Request to change", what="change")]]
def told_relief(who_=SAM):
    """the relief of K5, approved to who_ and told -> (the absence's id, its key)"""
    i = absent(by=HUGO); give(i, K5, who_); swept(); return i, f"relief:{EVE}:{K5}:{approved_at(i, K5)}"
def keys(*kinds): return [r["key"] for r in outs() if r["kind"] in kinds]

@t
def the_stopped_texts_are_exact():
    assert TE.stopped_text("1A, 1B Science (G2)", "P6–P7", "10:30", "Tue 13 Oct", f"1A, 1B are on {EXAM}") == STOPPED_K5
    assert TE.again_text("1A, 1B Science (G2)", "P6–P7", "10:30", "Tue 13 Oct") == AGAIN_K5
    assert TE.stopped_text("Art", "P1", "", "Tue", "why") == "❌ Not happening: Art P1 on Tue: why. You're free then."       # a lesson with no times
    assert TE.again_text("Art", "P1", "", "Tue") == "✔ On again: Art P1 on Tue. The relief is yours as before."

@t
def a_relief_that_is_stopped_is_said_once_and_again_when_it_stands():
    with exam_school(SAM, TEAM):
        i, key = told_relief(); at("09:10"); e = exam(); assert swept() == 1
        r, = outs("stopped"); ref = json.loads(r["ref"])
        assert (r["key"], r["name"], r["text"], json.loads(r["buttons"]), json.loads(r["files"])) == (f"stopped:{key}:0", SAM, STOPPED_K5, [], []), r
        assert ref == json.loads(outs("relief")[0]["ref"]) and "Zebra" not in r["ref"], "what was said of it, and nothing of the exam"
        for hm in ("09:11", "15:00"): at(hm); assert swept() == 0, "once"
        at("09:20", 12); withdraw(e); assert swept() == 1
        r, = outs("again"); assert (r["key"], r["name"], r["text"], buttons_of(r)) == (f"again:{key}:0", SAM, AGAIN_K5, relief_buttons(i)), r
        assert swept() == 0 and said(SAM) == [RELIEF_K5, STOPPED_K5, AGAIN_K5] and said(TEAM) == []
        # stopped and stood again more than once: told each time
        at("09:30"); again_on(e); assert swept() == 1 and swept() == 0; at("09:40"); withdraw(e); assert swept() == 1 and swept() == 0
        at("09:50"); again_on(e); swept(); at("10:00"); withdraw(e); swept()
        assert said(SAM) == [RELIEF_K5] + [STOPPED_K5, AGAIN_K5] * 3 and keys("stopped") == [f"stopped:{key}:{n}" for n in (0, 1, 2)] and keys("again") == [f"again:{key}:{n}" for n in (0, 1, 2)]
        assert absences.load(i)["lessons"] and CV.state(*covered(i, K5)) == "approved" and len(outs("relief")) == 1
    with exam_school(SAM):                                                                 # an event, whatever the relief teacher answered; a second exam over the first
        i, key = told_relief(); CV.acknowledge(i, K5, SAM); e = exam(name=JOURNEY, event=True); swept()
        assert said(SAM)[1:] == [STOPPED_K5.replace(EXAM, JOURNEY)]
        f = exam(name=EXAM2); withdraw(e); assert swept() == 0, "still stopped, by another"; withdraw(f); swept(); assert said(SAM)[2:] == [AGAIN_K5]
        CV.ask_change(i, K5, "x", SAM); again_on(f); swept(); withdraw(f); swept(); assert said(SAM)[3:] == [STOPPED_K5.replace(EXAM, EXAM2), AGAIN_K5]
    with exam_school(SAM, MAYA):                                                           # an exam of one of its two classes, or of another date: it happens
        told_relief(); exam("1A"); exam("1A", "1B", date="2026-10-14"); assert swept() == 0

@t
def only_who_was_told_of_the_relief_hears_that_it_is_stopped():
    for s, n in (("sent", 1), ("unsure", 1), ("queued", 0), ("sending", 0), ("failed", 0), ("dropped", 0)):
        with exam_school(SAM):
            i, key = told_relief(); put(key, state=s); exam(); assert [x["key"] for x in dues() if x["kind"] == "stopped"] == [] , "due is not given the links"
            assert [x["key"] for x in dues(links=exam_links())] == [f"stopped:{key}:0"] * n, s
            if n: swept(); assert dues(links=None) == [] and [x["key"] for x in dues(links=RL.Links(SCHOOL, TERM, []))] == [f"again:{key}:0"]
    for s, n in (("sent", 1), ("unsure", 1), ("queued", 0), ("sending", 0), ("failed", 0), ("dropped", 0)):       # told that it was stopped: told that it is on again
        with exam_school(SAM):
            i, key = told_relief(); e = exam(); TE.sweep(); put(f"stopped:{key}:0", state=s); withdraw(e); assert [x["key"] for x in dues(links=exam_links())] == [f"again:{key}:0"] * n, s
    with exam_school(MAYA, SAM):                                                           # not reached now; a teacher it was moved from; the one it was moved to
        i, key = told_relief(); at("09:10"); give(i, K5, MAYA); swept(); exam(); assert swept() == 1 and told_of("stopped") == [("stopped", MAYA)] and said(SAM) == [RELIEF_K5, MOVED_K5]
        assert dues(reach={SAM: 1}, told={k: v for k, v in OB.told_for("").items() if not k.startswith("stopped:")}, links=exam_links()) == []
    with exam_school(SAM):                                                                 # approved to them anew, and never told of that: what they were told is stopped, then the relief is told
        i, key = told_relief(); at("09:10"); give(i, K5, SAM); e = exam(); swept(); assert said(SAM) == [RELIEF_K5, STOPPED_K5] and keys("stopped") == [f"stopped:{key}:0"]
        withdraw(e); assert [x["kind"] for x in dues(links=exam_links())] == ["relief"]; swept(); assert said(SAM)[2:] == [RELIEF_K5] and swept() == 0, "the relief itself, not also that it is on again"
        again_on(e); swept(); assert keys("stopped")[1:] == [f"stopped:relief:{EVE}:{K5}:2026-10-12T09:10:00+08:00:0"]; withdraw(e); swept(); assert said(SAM)[3:] == [STOPPED_K5, AGAIN_K5]
    with exam_school(SAM, MAYA):                                                           # both approved in one second: each one's own count
        i = absent(by=HUGO); give(i, K5, SAM); swept(); e = exam(); swept(); withdraw(e); swept(); assert said(SAM)[1:] == [STOPPED_K5, AGAIN_K5]
        give(i, K5, MAYA); swept(); base = f"relief:{EVE}:{K5}:2026-10-12T09:00:00+08:00"; assert outs("relief")[1]["key"] == f"{base}:{MAYA}"
        again_on(e); swept(); withdraw(e); swept(); assert said(MAYA) == [RELIEF_K5, STOPPED_K5, AGAIN_K5] and keys("stopped") == [f"stopped:{base}:0", f"stopped:{base}:{MAYA}:0"]
        at("09:10"); give(i, K5, SAM); swept(); again_on(e); swept(); assert said(SAM)[3:] == [MOVED_K5, RELIEF_K5, STOPPED_K5]
    with exam_school(SAM):
        i, key = told_relief(); e = exam(); told = dict(OB.told_for(""), **{f"{kind}:{key}:{MAYA}:0": dict(state="sent", at=clock.now, name=MAYA, ref=None) for kind in ("stopped", "again")})
        assert [x["key"] for x in dues(told=told, links=exam_links())] == [f"stopped:{key}:0"]; withdraw(e); assert dues(told=told, links=exam_links()) == [], "nothing of hers is counted as his"
    with exam_school(SAM, MAYA):                                                           # told that it moved, given back, and stopped before that was told: they think it is another's
        i, key = told_relief(); at("09:10"); give(i, K5, MAYA); swept(); at("09:20"); give(i, K5, SAM); e = exam(); swept(); assert said(SAM) == [RELIEF_K5, MOVED_K5] and told_of("stopped") == []
        withdraw(e); swept(); assert said(SAM)[2:] == [RELIEF_K5] and said(MAYA) == [RELIEF_K5, MOVED_K5]

@t
def a_part_of_a_split_lesson_is_stopped_with_it():
    with exam_school(SAM, MAYA):
        i = absent(by=HUGO); CV.split(i, K5, 6, TEAM); give(i, K5 + "#0", SAM); give(i, K5 + "#1", MAYA); swept(); e = exam(); assert swept() == 2
        assert said(SAM)[1:] == [STOPPED_K5.replace("P6–P7", "P6")] and said(MAYA)[1:] == [STOPPED_K5.replace("P6–P7 (10:30)", "P7 (11:00)")]
        withdraw(e); assert swept() == 2 and buttons_of(outs("again", MAYA)[0]) == relief_buttons(i, K5 + "#1", MAYA) and said(MAYA)[2:] == [AGAIN_K5.replace("P6–P7 (10:30)", "P7 (11:00)")]

@t
def nothing_is_asked_of_a_stopped_lesson():
    with exam_school(SAM, MAYA):                                                           # approved, and stopped before it was told: no relief until it stands
        i = absent(by=HUGO); give(i, K5, SAM); e = exam()
        for hm in ("09:10", "15:00"): at(hm); assert swept() == 0 and outs() == [], hm
        give(i, K2, MAYA); assert swept() == 1 and told_of() == [("relief", MAYA)], "another lesson of the same absence"
        withdraw(e); assert swept() == 1 and said(SAM) == [RELIEF_K5] and swept() == 0
    for pick in (True, False):                                                             # a request to change, before or after its pick
        with exam_school(SAM, MAYA, TEAM, LEE):
            i = asked(pick=False); e = exam()
            if pick: new_pick(i, K5, MAYA)
            at("09:30"); assert swept() == 1 and said(TEAM) == said(LEE) == [] and said(SAM) == [RELIEF_K5, STOPPED_K5]
            withdraw(e); assert swept() == 3 and len(said(TEAM)) == len(said(LEE)) == 1 and told_of("askpick") == []
            assert said(SAM)[2:] == [AGAIN_K5], "theirs until the team replies"
    with exam_school(SAM, MAYA, TEAM):                                                     # the pick after an ask without one
        i = asked(pick=False); at("09:12"); swept(); assert len(said(TEAM)) == 1; e = exam(); new_pick(i, K5, MAYA); swept(); assert told_of("askpick") == []
        withdraw(e); swept(); assert told_of("askpick") == [("askpick", TEAM)]
    with exam_school(SAM, TEAM):                                                           # kept while it is stopped: said when it stands
        i = asked(pick=False); e = exam(); swept(); at("09:20"); CV.keep(i, K5, TEAM); assert swept() == 0; withdraw(e); swept()
        assert sorted(said(SAM)[2:]) == sorted([AGAIN_K5, KEPT_K5])
    with exam_school(SAM, TEAM, limits=dict(fat_per_day=3, other_per_day=None, never=[RUTH, BUSY, HUGO, LEE, TEAM, ROSA, OFFIE])):       # somebody on a duty is not free
        i = asked(pick=False); at("09:12"); exam("5A", duties=[(MAYA, 630, 690)]); swept(); assert outs("ask")[0]["text"].endswith("Nobody else is free then: choose someone in the app.")

@t
def what_waits_about_a_stopped_lesson_is_not_sent():
    """queued, and the exam approved (or withdrawn) before it goes"""
    with exam_school(SAM):
        i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); key = outs()[0]["key"]; e = exam(); assert send() == 0 and state(key) == "dropped" and said(SAM) == []
        assert swept() == 0, "neither the relief nor that it is stopped: they were told of nothing"
        withdraw(e); assert swept() == 1 and said(SAM) == [RELIEF_K5]
        again_on(e); TE.sweep(); withdraw(e); assert send() == 0 and state(f"stopped:{key}:0") == "dropped" and swept() == 0 and said(SAM) == [RELIEF_K5], "on again before it was said to be stopped: nothing"
        again_on(e); swept(); withdraw(e); TE.sweep(); again_on(e); assert send() == 0 and state(f"again:{key}:0") == "dropped" and swept() == 0 and said(SAM)[1:] == [STOPPED_K5], "stopped again before it was said to be on"
        withdraw(e); swept(); assert said(SAM)[2:] == [AGAIN_K5] and swept() == 0
        # a copy sent as a reminder (Task 6)
        ref = json.loads(item(key)["ref"]); again_on(e); OB.queue(key + ":r1", SAM, "again", kind="relief", ref=ref); send(); assert state(key + ":r1") == "dropped"
    with exam_school(SAM, MAYA):                                                           # on again, and moved or approved anew before it went
        i, key = told_relief(); e = exam(); swept(); withdraw(e); TE.sweep(); at("09:10"); give(i, K5, SAM); send(); assert state(f"again:{key}:0") == "dropped"; swept(); assert said(SAM)[1:] == [STOPPED_K5, RELIEF_K5]
    with exam_school(SAM, MAYA):
        i, key = told_relief(); e = exam(); swept(); withdraw(e); TE.sweep(); at("09:10"); give(i, K5, MAYA); send(); assert state(f"again:{key}:0") == "dropped"; swept(); assert said(SAM)[1:] == [STOPPED_K5, MOVED_K5] and said(MAYA) == [RELIEF_K5]
    with exam_school(SAM, MAYA, TEAM):                                                     # the team's, and kept
        i = asked(pick=False); new_pick(i, K5, MAYA); TE.sweep(); e = exam(); assert send() == 0 and said(TEAM) == []; withdraw(e); swept(); assert len(said(TEAM)) == 1
        at("09:20"); CV.keep(i, K5, TEAM); TE.sweep(); again_on(e); send(); assert outs("kept")[0]["state"] == "dropped"; withdraw(e); swept(); assert KEPT_K5 in said(SAM)

@t
def a_stopped_lesson_that_is_over_is_not_told():
    with exam_school(SAM):
        i, key = told_relief(); e = exam(); at("11:30", 13); assert dues(links=exam_links()) == [] and swept() == 0
        at("11:29", 13); assert TE.sweep() == 1; at("11:30", 13); assert send() == 0 and state(f"stopped:{key}:0") == "dropped", "over before it went"
        at("11:29", 13); assert swept() == 1; withdraw(e); at("11:30", 13); assert swept() == 0; at("11:29", 13); assert TE.sweep() == 1; at("11:30", 13); assert send() == 0 and state(f"again:{key}:0") == "dropped"
        assert said(SAM) == [RELIEF_K5, STOPPED_K5]

@t
def stopped_is_neither_gone_nor_moved():
    with exam_school(SAM, MAYA):
        i, key = told_relief(); e = exam(); swept(); assert [x["kind"] for x in dues(links=exam_links())] == [] and told_of() == [("relief", SAM), ("stopped", SAM)]
        withdraw(e); swept(); at("09:10"); give(i, K5, MAYA); swept(); assert said(SAM)[1:] == [STOPPED_K5, AGAIN_K5, MOVED_K5], "moved, once it stands and is"
        again_on(e); swept(); withdraw(e); swept(); assert said(SAM)[4:] == [] and said(MAYA) == [RELIEF_K5, STOPPED_K5, AGAIN_K5]
    for how in ("cancel", "not needed"):                                                   # the cover really ends while the lesson is stopped (and then stands)
        with exam_school(SAM):
            i, key = told_relief(); e = exam(); swept(); at("09:10")
            absences.cancel(i, "x", HUGO) if how == "cancel" else absences.not_needed(i, K5, "x", HUGO)
            assert swept() == 1 and said(SAM) == [RELIEF_K5, STOPPED_K5, GONE_K5]; withdraw(e); assert swept() == 0, how
        with exam_school(SAM):                                                             # before it was said to be stopped: that it is gone, alone
            i, key = told_relief(); e = exam(); TE.sweep(); absences.cancel(i, "x", HUGO) if how == "cancel" else absences.not_needed(i, K5, "x", HUGO)
            send(); swept(); assert said(SAM) == [RELIEF_K5, GONE_K5] and state(f"stopped:{key}:0") == "dropped", how
    for hm in ("09:00", "09:10"):                                                          # moved (in the second it was approved, or later) before it was said to be stopped
        with exam_school(SAM, MAYA):
            i, key = told_relief(); e = exam(); TE.sweep(); at(hm); give(i, K5, MAYA); send(); assert state(f"stopped:{key}:0") == "dropped"
            swept(); assert said(SAM) == [RELIEF_K5, MOVED_K5] and said(MAYA) == []; withdraw(e); swept(); assert said(MAYA) == [RELIEF_K5] and len(said(SAM)) == 2, hm
    with exam_school(SAM):                                                                 # its record cannot be read: neither said
        i, key = told_relief(); e = exam(); p = absences._path(i); good = open(p, encoding="utf-8").read(); open(p, "w", encoding="utf-8").write("{ not json"); assert swept() == 0
        open(p, "w", encoding="utf-8").write(good); assert TE.sweep() == 1; open(p, "w", encoding="utf-8").write("{ not json"); assert send() == 0 and state(f"stopped:{key}:0") == "queued"

@t
def on_again_reaches_whoever_was_told_it_was_off():
    """approved anew to the same person, whose message of that never went, and answered in the app: they were told it is stopped, so they are told it is on again"""
    for answer in ("acknowledged", "change"):
        for queued in (True, False):
            with exam_school(SAM):
                i, key = told_relief(); at("09:10"); give(i, K5, SAM)
                if queued: assert TE.sweep() == 1
                CV.acknowledge(i, K5, SAM) if answer == "acknowledged" else CV.ask_change(i, K5, "A parent meeting", SAM)
                at("09:20"); e = exam(); swept(); assert said(SAM) == [RELIEF_K5, STOPPED_K5] and keys("stopped") == [f"stopped:{key}:0"] and CV.state(*covered(i, K5)) == answer
                at("09:30"); withdraw(e); assert [x["kind"] for x in dues(links=exam_links())] == ["again"] and swept() == 1, (answer, queued)
                r, = outs("again"); assert (r["key"], r["name"], r["text"], r["state"], buttons_of(r)) == (f"again:{key}:0", SAM, AGAIN_K5, "sent", relief_buttons(i)), r
                assert swept() == 0 and said(SAM) == [RELIEF_K5, STOPPED_K5, AGAIN_K5]
                again_on(e); swept(); withdraw(e); swept(); assert swept() == 0 and said(SAM)[3:] == [STOPPED_K5, AGAIN_K5] and keys("again") == [f"again:{key}:{n}" for n in (0, 1)], "each time"
    for answer, n in (("acknowledged", 1), ("change", 1), (None, 0)):                      # approved anew while it waits to go: unless the relief itself is said again
        with exam_school(SAM):
            i, key = told_relief(); e = exam(); swept(); withdraw(e); TE.sweep(); at("09:10"); give(i, K5, SAM)
            if answer == "acknowledged": CV.acknowledge(i, K5, SAM)
            if answer == "change": CV.ask_change(i, K5, "x", SAM)
            assert send() == n and state(f"again:{key}:0") == ("sent" if n else "dropped"); swept(); assert said(SAM)[2:] == [AGAIN_K5 if n else RELIEF_K5] and swept() == 0, answer
    with exam_school(SAM, MAYA):                                                           # acknowledged by another, whom it moved to: nothing to Sam but that it moved
        i, key = told_relief(); e = exam(); swept(); withdraw(e); TE.sweep(); at("09:10"); give(i, K5, MAYA); CV.acknowledge(i, K5, MAYA); send(); swept(); assert said(SAM)[2:] == [MOVED_K5]

@t
def on_again_is_not_said_of_a_lesson_that_is_not_there_any_more():
    """a publish moved it (the exam stops it still, by its own periods), or its date is a holiday now (nothing does): it does not happen either way"""
    row = next(x for x in SCHOOL["model"]["lessons"] if x["classes"] == ["1A", "1B"])
    @contextlib.contextmanager
    def moved():
        row["p"] = 6
        try: yield
        finally: row["p"] = 5
    @contextlib.contextmanager
    def holiday():
        store.write_json(RS.PATH, dict(calendar=dict(TERM, holidays=[dict(name="A made-up day", start="2026-10-13", end="2026-10-13")])))
        try: yield
        finally: store.write_json(RS.PATH, dict(calendar=TERM))
    for gone_then in (moved, holiday):
        with exam_school(SAM):
            i, key = told_relief(); e = exam(); swept()
            with gone_then(): assert bool(CV.stopped(RL.Links.load(SCHOOL, rs()["calendar"]), covered(i, K5)[1])) == (gone_then is moved) and swept() == 0, "the exam is on still"
            assert swept() == 0; withdraw(e)
            with gone_then(): assert swept() == 0 and dues(links=exam_links()) == [], "nor once it is withdrawn"
            assert TE.sweep() == 1
            with gone_then(): assert send() == 0 and state(f"again:{key}:0") == "dropped" and swept() == 0, "nor when that happens before it goes"
            assert swept() == 1 and swept() == 0 and said(SAM) == [RELIEF_K5, STOPPED_K5, AGAIN_K5], gone_then.__name__
            again_on(e); TE.sweep()
            with gone_then(): assert send() == (gone_then is moved) and state(f"stopped:{key}:1") == ("sent" if gone_then is moved else "dropped"), "on a holiday it is not so that it is stopped"
            assert swept() == (gone_then is holiday) and said(SAM)[3:] == [STOPPED_K5]

@t
def nothing_is_said_about_stopping_while_the_exams_cannot_be_read():
    h = Grab(); lg = logging.getLogger("relief.fill"); lg.addHandler(h); prop, lg.propagate = lg.propagate, False
    try:
        with exam_school(SAM, MAYA):
            i, key = told_relief(); e = exam()
            with unreadable(): assert swept() == 0 and [r.getMessage() for r in h.records] == ["the exams and events could not be read: ZeroDivisionError"], "stopped, and not known to be"
            with unreadable(): give(i, K2, MAYA); assert swept() == 1 and len(said(MAYA)) == 1, "every other message goes, as with no exams"
            swept(); assert said(SAM) == [RELIEF_K5, STOPPED_K5]
            withdraw(e)
            with unreadable(): assert swept() == 0, "on again, and not known to be"
            swept(); assert said(SAM)[2:] == [AGAIN_K5]
            again_on(e); swept()
            with unreadable(): assert swept() == 0, "nor taken back: it is stopped still"
            assert swept() == 0 and said(SAM)[3:] == [STOPPED_K5]
        with exam_school(SAM):                                                             # a relief goes, as with no exams
            i = absent(by=HUGO); give(i, K5, SAM); e = exam()
            with unreadable(): assert swept() == 1 and said(SAM) == [RELIEF_K5]
            swept(); assert said(SAM)[1:] == [STOPPED_K5]
        with exam_school(SAM):                                                             # what is queued about stopping is dropped (never failed, however long they cannot be read), and made anew once they can
            i, key = told_relief(); e = exam()
            for queued, text in ((f"stopped:{key}:0", STOPPED_K5), (f"again:{key}:0", AGAIN_K5)):
                if queued.startswith("again:"): withdraw(e)
                assert TE.sweep() == 1; n = len(said(SAM))
                with unreadable(): assert send() == 0 and state(queued) == "dropped" and [TE.sweep() for _ in range(8)] == [0] * 8 and OB.send_due(now=time.time() + 9000)["sent"] == 0
                assert len(said(SAM)) == n and swept() == 1 and swept() == 0 and said(SAM)[n:] == [text] and (item(queued)["state"], item(queued)["tries"]) == ("sent", 0), queued
            again_on(e); TE.sweep(); kind = lambda k: dict(item(f"stopped:{key}:1"), kind=k, ref=json.loads(item(f"stopped:{key}:1")["ref"]))
            with stand_in(store, "published", lambda: None): assert [TE.still_true(kind(k)) for k in ("stopped", "again")] == [False, False], "nor while nothing is published"
            for n, (module, name) in enumerate(((RS, "load"), (store, "published"), (TE, "_now"))):       # what else cannot be read: it waits
                with stand_in(module, name, lambda *a: 1 / 0): put(f"stopped:{key}:1", next_at=0); assert send() == 0 and (state(f"stopped:{key}:1"), item(f"stopped:{key}:1")["tries"]) == ("queued", n + 1), name
            assert OB.send_due(now=time.time() + 4000)["sent"] == 1 and said(SAM)[3:] == [STOPPED_K5]
    finally: lg.removeHandler(h); lg.propagate = prop

@t
def the_exams_are_read_once_a_sweep():
    calls, real = [], FL._links
    def counted(pub, cal): calls.append((pub is SCHOOL, cal["terms"] == TERM["terms"], absences._LOCK.locked())); return real(pub, cal)
    with exam_school(SAM, MAYA), stand_in(FL, "_links", counted):
        i, key = told_relief(); exam(); calls.clear(); assert TE.sweep() == 1 and calls == [(True, True, False)], calls
        absences.cancel(i, "x", HUGO); calls.clear(); assert TE.sweep() == 1 and calls == [(True, True, False)], "once, when the records are read twice too"
    with exam_school(), stand_in(FL, "_links", counted): calls.clear(); assert TE.sweep() == 0 and calls == [], "nobody to tell"

@t
def still_true_knows_what_is_stopped():
    def it(kind): r = outs(kind)[0]; return dict(r, ref=json.loads(r["ref"]))
    with exam_school(EVE, SAM, ROSA, TEAM, MAYA):
        i = asked(pick=False); new_pick(i, K5, MAYA); TE.sweep(); relief, ask, planned, officer = it("relief"), it("ask"), it("planned"), it("officer"); askpick = dict(ask, kind="askpick")
        assert all(TE.still_true(x) is True for x in (relief, ask, askpick, planned, officer))
        e = exam(); assert [TE.still_true(x) for x in (relief, ask, askpick)] == [False] * 3 and all(TE.still_true(x) is True for x in (planned, officer, dict(planned, kind="remind"))), "the absence is not stopped"
        with unreadable(): assert all(TE.still_true(x) is True for x in (relief, ask, askpick, planned, officer)), "no lesson counts as stopped"
        TE.sweep(); stopped = it("stopped"); again = dict(stopped, kind="again"); assert TE.still_true(stopped) is True and TE.still_true(again) is False
        withdraw(e); assert TE.still_true(stopped) is False and TE.still_true(again) is True and TE.still_true(relief) is True
        with unreadable(): assert TE.still_true(stopped) is False and TE.still_true(again) is False, "not known: neither goes"
        CV.keep(i, K5, TEAM); TE.sweep(); kept = it("kept"); assert TE.still_true(kept) is True; again_on(e); assert TE.still_true(kept) is False and TE.still_true(stopped) is True
        absences.not_needed(i, K5, "x", HUGO); gone = dict(relief, kind="gone"); assert TE.still_true(gone) is True and TE.still_true(dict(gone, kind="moved")) is True, "gone and moved, as it stood"
        assert TE.still_true(stopped) is False, "gone says it"

@t
def a_takeover_of_the_absence_changes_nothing_of_a_stopped_relief():
    def take_over(i, j="dead00beef"):
        r = absences.load(i); x = next(x for x in r["lessons"] if x["key"] == K5)
        r["lessons"].remove(x); absences._save(r); absences._save(dict(r, id=j, how="asked", by=EVE, lessons=[x], at=clock.now))
    with exam_school(SAM):                                                                 # the cover moves to another record while the lesson is stopped
        i, key = told_relief(); e = exam(); swept(); take_over(i); assert swept() == 0; withdraw(e); assert swept() == 1
        r, = outs("again"); assert r["key"] == f"again:{key}:0" and buttons_of(r) == relief_buttons("dead00beef") and json.loads(r["ref"])["id"] == "dead00beef", "its buttons name where it is now"
        again_on(e); swept(); assert said(SAM) == [RELIEF_K5, STOPPED_K5, AGAIN_K5, STOPPED_K5]
    with exam_school(SAM):                                                                 # stopped, and taken over before it was said
        i, key = told_relief(); e = exam(); TE.sweep(); take_over(i); assert send() == 1 and swept() == 0; withdraw(e); TE.sweep(); take_over("dead00beef", "cafe00beef"); assert send() == 1 and said(SAM)[1:] == [STOPPED_K5, AGAIN_K5]
    # as the app does it: a backup of somebody on an exam duty, its relief approved, taken over by their own absence
    def backup():
        d = exam("5A", name=EXAM2, duties=[(EVE, 630, 690)]); RL.sync_all(SCHOOL, TERM, LS.today()); b, = [r["id"] for r in absences.all_records() if r.get("exams")]
        assert [x["key"] for x in absences.load(b)["lessons"]] == [K5]; give(b, K5, SAM); swept(); return d, b
    def own(**kw):
        d = dict(teacher=EVE, dates=["2026-10-13"], periods=None, reason="Medical", reason_text="", remarks="", reporting_officer=ROSA, lessons=[])
        return absences.new(dict(d, **kw), SCHOOL, EVE, "asked", links=exam_links())["id"]
    with exam_school(SAM, EVE, TEAM):
        d, b = backup(); assert said(SAM) == [RELIEF_K5] and said(EVE)[0].startswith("📋 Relief planned for you\nTue 13 Oct · P6–P7\nPlanned by Exams committee\n1 lesson will be covered.")
        at("09:10"); j = own(); assert absences.load(b)["cancelled"]["by"] == "app" and CV.state(*covered(j, K5)) == "approved"
        assert swept() == 0 and said(SAM) == [RELIEF_K5] and said(TEAM) == [] and len(said(EVE)) == 1, "the same relief, in another absence: nobody is told that it was cancelled"
        e = exam(); assert swept() == 1; withdraw(e); assert swept() == 1 and said(SAM)[1:] == [STOPPED_K5, AGAIN_K5] and buttons_of(outs("again")[0]) == relief_buttons(j)
        at("09:20"); absences.cancel(j, "x", EVE); swept(); assert said(SAM)[3:] == [GONE_K5] and said(TEAM) == [CANCELLED_EVE.format(EVE)], "that one is cancelled"
    with exam_school(SAM, EVE, TEAM):                                                      # taken over while it is stopped: the new absence keeps it, so the relief goes with it and is on again
        d, b = backup(); e = exam(); swept(); at("09:10"); j = own(); assert covered(j, K5)[1]["needed"] is True and CV.state(*covered(j, K5)) == "approved"
        assert swept() == 0 and said(SAM) == [RELIEF_K5, STOPPED_K5] and said(TEAM) == []; withdraw(e); assert swept() == 1 and said(SAM)[2:] == [AGAIN_K5] and buttons_of(outs("again")[0]) == relief_buttons(j)
    with exam_school(SAM, EVE, TEAM):                                                      # in step with the exams: a stopped lesson leaves the backup, so its relief is gone
        d, b = backup(); e = exam(); RL.sync_all(SCHOOL, TERM, LS.today()); assert absences.load(b)["lessons"] == [] and [x["key"] for x in absences.load(b)["gone"]] == [K5]
        swept(); assert said(SAM) == [RELIEF_K5, GONE_K5] and said(EVE)[1:] == [CANCELLED_BY_APP] and said(TEAM) == [], "that backup is over, cancelled by nobody: whoever was told of it hears"
        withdraw(e); RL.sync_all(SCHOOL, TERM, LS.today()); c = [r["id"] for r in absences.all_records() if r.get("exams") and not r["cancelled"]]; assert len(c) == 1; at("09:30"); give(c[0], K5, SAM); swept(); assert said(SAM)[2:] == [RELIEF_K5]

@t
def a_backup_that_ends_by_itself_is_told_to_who_was_told_of_it_alone():
    """an exam withdrawn, its duties made anew, or handled by the committee: forty at once, and none of them to the team or the teacher in charge"""
    crowd = [f"Ms Made Up {k:02d}" for k in range(40)]; big = json.loads(json.dumps(SCHOOL)); text = "❌ Cancelled: {}'s absence on Tue 13 Oct. Its reliefs are no longer needed.".format
    for k, n in enumerate(crowd): big["model"]["setup"]["teachers"].append(dict(name=n, dept="Science")); big["model"]["lessons"].append(lesson(TUE, 5, 2, ["1C"], "Science", [n], group=f"X{k}"))
    with exam_school(TEAM, LEE, HUGO, SAM, ROSA), no_pub(big):
        for k, n in enumerate(crowd[1:]): links.link(n, 3001 + k, None)                    # all but the first
        e = exam("5A", name=EXAM2, duties=[(n, 630, 690) for n in crowd]); RL.sync_all(big, TERM, LS.today()); ids = {n: backup_of(n) for n in crowd}
        change_record(ids[crowd[5]], lambda r: r.update(reporting_officer=ROSA)); x = absences.load(ids[crowd[6]])["lessons"][0]["key"]; CV.change(ids[crowd[6]], x, SAM, TEAM, big, RS.load(big))
        assert TE.sweep() == 39 + 1 + 1; put(f"planned:{ids[crowd[1]]}", state="failed"); put(f"planned:{ids[crowd[2]]}", state="unsure"); put(f"planned:{ids[crowd[3]]}", state="failed"); send()
        at("15:00"); TE.sweep(); [put(r["key"], state="failed") for r in outs("remind") if r["name"] != crowd[3]]; send(); assert state(f"remind:{ids[crowd[3]]}") == "sent" and len(said(SAM)) == len(said(ROSA)) == 1
        at("15:30"); withdraw(e); RL.sync_all(big, TERM, LS.today()); assert all(absences.load(i)["cancelled"]["by"] == "app" for i in ids.values())
        TE.sweep(); assert sorted((r["name"], r["key"], r["text"]) for r in outs("cancelled")) == sorted([(n, f"cancelled:{ids[n]}:{n}", text(n)) for n in crowd[2:]] + [(ROSA, f"cancelled:{ids[crowd[5]]}:{ROSA}", text(crowd[5]))])
        assert [(r["kind"], r["name"]) for r in outs("gone")] == [("gone", SAM)] and all(json.loads(r["ref"])["team"] is False for r in outs("cancelled")); send(); send()
        assert said(TEAM) == said(LEE) == said(HUGO) == [] and {r["state"] for r in outs("cancelled")} == {"sent"} and collections.Counter(x for c, x in sent() if x.startswith("❌ Cancelled")) == collections.Counter([text(n) for n in crowd[2:]] + [text(crowd[5])])
        assert swept() == 0 and len(outs("cancelled")) == 39, "each hears once"
    for end in ("withdrawn", "made anew", "handled"):                                      # an event's: not its teacher in charge either, who is the planner
        with exam_school(EVE, SAM, HUGO, TEAM, LEE):
            e, b = backed_up("event"); give(b, K5, SAM); swept(); assert said(EVE)[0].splitlines()[2] == "Planned by Mr Hugo Ong" and said(SAM) == [RELIEF_K5]; at("09:10")
            if end == "withdrawn": withdraw(e)
            else:
                s = SC.load(e)
                if end == "made anew": s["going"] = [BUSY]
                else: s["handled"] = [f"{EVE}|{k}" for k in (K2, K5)]
                saved_exam(s); again_on(e)
            RL.sync_all(SCHOOL, TERM, LS.today()); assert absences.load(b)["cancelled"]["by"] == "app", end
            swept(); assert said(EVE)[1:] == [CANCELLED_BY_APP] and said(SAM) == [RELIEF_K5, GONE_K5] and said(HUGO) == said(TEAM) == said(LEE) == [], end
    with record(EVE, extras=dict(relief=True, exams=None, admin=False)), exam_school(EVE, TEAM):  # told of it, and on the team: once, as the one told
        e, b = backed_up("exam"); swept(); withdraw(e); RL.sync_all(SCHOOL, TERM, LS.today()); swept(); r, = outs("cancelled"); assert r["name"] == EVE and json.loads(r["ref"]) == dict(id=b, team=False)
    for day, goes in ((13, True), (14, False)):                                            # with no lesson left in it, the dates it had are asked of: nothing once they are past
        with exam_school(EVE, TEAM): e, b = backed_up("exam"); swept(); withdraw(e); RL.sync_all(SCHOOL, TERM, LS.today()); assert TE.sweep() == 1 and absences.load(b)["lessons"] == []; at("09:00", day); assert send() == goes, day
    with exam_school(EVE, HUGO, TEAM, LEE):                                                # a person who cancels one tells the team and the teacher in charge, as ever
        e, b = backed_up("event"); swept(); call(EVE, "post", f"/api/relief/absences/{b}/cancel", dict(why="x")); send(); assert said(HUGO)[:1] == said(TEAM) == said(LEE) == [CANCELLED_EVE.format(EVE)]
    with exam_school(EVE, HUGO, TEAM):                                                     # what is no backup too, whoever ended it
        i = absent(by=HUGO); swept(); change_record(i, lambda r: r.update(cancelled=dict(at=clock.now, by="app", why="x"))); swept(); assert said(HUGO) == said(TEAM) == said(EVE)[1:] == [CANCELLED_BY_APP]

@t
def only_the_two_messages_name_an_exam():
    with exam_school(EVE, SAM, ROSA, TEAM, LEE, HUGO, MAYA):
        d = exam("5A", name=EXAM2, duties=[(EVE, 630, 690)]); RL.sync_all(SCHOOL, TERM, LS.today()); b, = [r["id"] for r in absences.all_records() if r.get("exams")]
        give(b, K5, SAM); swept(); at("09:10"); CV.ask_change(b, K5, "A parent meeting", SAM); swept(); at("09:13"); swept(); new_pick(b, K5, MAYA); swept(); CV.keep(b, K5, TEAM); swept()
        e = exam(); swept(); withdraw(e); swept(); at("15:00"); swept(); at("15:10"); give(b, K5, MAYA); swept(); absences.cancel(b, "x", HUGO, team=True); swept()
        assert {k for k, n in told_of()} == {"planned", "relief", "ask", "askpick", "kept", "stopped", "again", "remind", "moved", "gone", "cancelled"}, {k for k, n in told_of()}
        for r in outs():
            whole = json.dumps(r, ensure_ascii=False) + r["text"]
            for word in ("Zebra", "Quokka", "Invigilating", "are on"): assert (word in whole) <= (r["kind"] == "stopped" and r["name"] == SAM and word in ("Zebra", "are on")), (word, r["kind"])
        assert sum("Zebra" in r["text"] for r in outs()) == 1

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
        assert [[x["kind"] for x in TE.due(SCHOOL, st, [r for r in records if r["id"] != i], *args[3:], unread=u)] for u in ((), {"another"}, {i})] == [["gone"], ["gone"], []], "only its own record, unread"
        assert json.dumps(a) and TE.due(SCHOOL, st, [], datetime.datetime(2026, 10, 12, 1, 10, tzinfo=datetime.timezone.utc), reach, {}, None) == []
        # no short name known: the name
        new_pick(i, K2, MAYA); got = dues(told={}); assert [x["buttons"][0][0]["text"] for x in got if x["kind"] == "ask"] == ["Approve Ms Maya Lee"]
        assert [x["buttons"][0][0]["text"] for x in dues(told={}, shorts={MAYA: "Ms Lee"}) if x["kind"] == "ask"] == ["Approve Ms Lee"]

@t
def the_sweep_is_quick():
    with exam_school(EVE, SAM, ROSA, TEAM, LEE, HUGO):
        for n in range(5): exam("3B", "4A", name=f"Exam {n}", date=f"2026-10-{13 + n}")    # exams on those days, of other classes
        i = absent(by=HUGO, dates=["2026-10-13", "2026-10-14", "2026-10-16"]); give(i, K5, SAM); give(i, KF, SAM); whole_ = absences.load(i); os.remove(absences._path(i))
        for n in range(200):
            r = json.loads(json.dumps(whole_)); r.update(id=f"{n:012x}", teacher=f"Mx Made Up {n}")
            if n % 2: r.update(dates=["2026-10-01"], lessons=[dict(x, date="2026-10-01", key=x["key"].replace("2026-10-13", "2026-10-01")) for x in r["lessons"][:3]])
            absences._save(r)
        began = time.process_time(); n = TE.sweep(); first = time.process_time() - began    # this process's own time: a busy machine does not count
        assert n == 300, n                                                                 # 100 to come: two reliefs and the officer's, each
        began = time.process_time(); assert TE.sweep() == 0; second = time.process_time() - began
        assert first < 2.0 and second < 2.0, (first, second)

# ---- Task 5: answering on Telegram ----
OLD_BUTTON, NOT_YOURS_BUTTON = "This button is no longer active.", "This button is not for you."
WHY_CHANGE = "Say why in one line. Until the relief team replies, this relief is still yours."
WHY_CANCEL = "Cancel this absence? Say why in one line, or press Keep it."
SENT_CHANGE, SENT_CANCEL = "Sent to the relief team. Until they reply, this relief is still yours.", "Cancelled. The relief team will see it."
LAST_ONE, ACKED = "Answer the question I asked last.", "This was acknowledged already."
SURE = "Cancel {}? Your reason: {}"
NOTHING, WENT_WRONG = "Nothing was changed.", "Something went wrong. Try again in the app."
A_DUTY = "This is for an exam or event duty, so it cannot be cancelled here. Ask the exams committee, or the event's teacher in charge."
ENTRY = "Relief for Ms Evelyn Koh on Tue 13 Oct: "
ON_K5 = "1A, 1B Science (G2) P6–P7 on Tue 13 Oct"
FORCE = dict(force_reply=True)

def calls(method): return [p for m, p in list(tg.PRACTICE_LOG) if m == method]
def answers(): return [(p.get("text"), p.get("show_alert")) for p in calls("answerCallbackQuery")]
def edits(): return [(p["chat_id"], p["message_id"], p["text"]) for p in calls("editMessageText")]
def talks(): return [(r["chat"], r["kind"], json.loads(r["data"]), r["until"]) for r in rows("talks")]
def talk_of(name): return next(d for c, k, d, u in talks() if c == CHATS[name])
def keep_it(name):
    """the one button of the cancel question that waits in name's chat"""
    return dict(inline_keyboard=[[dict(text="Keep it", callback_data="b:" + talk_of(name)["key"])]])
def question(name, text=WHY_CANCEL): return dict(message_id=talk_of(name)["question"], date=1, chat=dict(id=CHATS[name], type="private"), text=text)
def yes_or_keep(name):
    """the two buttons of the question that shows the reason"""
    d = talk_of(name); return dict(inline_keyboard=[[dict(text="Yes, cancel it", callback_data="b:" + d["yes"]), dict(text="Keep it", callback_data="b:" + d["key"])]])
def sure(name):
    """that question, as Telegram gives it back with a press"""
    d = talk_of(name); return question(name, SURE.format(d["days"], d["why"]))
def press_yes(name, chat=None): return press_keep(talk_of(name)["yes"], sure(name), chat)
def press_keep(token, m, chat=None):
    n = len(answers()); hook(callback("b:" + token, m, chat)); got = answers()[n:]; assert len(got) == 1, got
    return got[0]
def reply_to(name, n, text, **more): return say(name, text, reply_to_message=dict(message_id=n, chat=dict(id=CHATS[name], type="private"), date=1, text="x"), **more)
def tok(name, what):
    """the token of the last button of that kind sent to name"""
    return [r["token"] for r in rows("buttons") if (r["name"], r["what"]) == (name, what)][-1]
def button(token, **changes):
    with tgdb.db() as c:
        for k, v in changes.items(): assert c.execute(f"UPDATE buttons SET {k}=? WHERE token=?", (v, token)).rowcount == 1
def under(token):
    """the message the button is on, as Telegram gives it back with a press"""
    r = next(r for r in rows("outbox") if token in r["buttons"])
    return dict(message_id=r["message_id"], date=1, chat=dict(id=r["chat"], type="private"), text=OB._cut(r["text"]))
def callback(data, message, chat=None, **more):
    """a press of a button whose callback data is data, on that message; chat: in another chat"""
    m = dict(message, chat=dict(id=chat, type="private")) if chat else message
    q = dict(id=f"q{next(_ids)}", data=data, message=m, **more)
    if "from" not in q: q["from"] = dict(id=m["chat"]["id"], is_bot=False, first_name="T")
    return dict(update_id=next(_ids), callback_query=q)
def press_token(token, chat=None):
    n = len(answers()); assert hook(callback("b:" + token, under(token), chat)).status_code == 200
    got = answers()[n:]; assert len(got) == 1, got
    return got[0]
def press(name, what, chat=None):
    """what the last button of that kind sent to name is answered, pressed by name (or in another chat): (the text, an alert)"""
    return press_token(tok(name, what), chat)
def taken_off(name, what, sentence):
    """the one edit there was: the message of that button without its buttons, its last line the sentence"""
    m = under(tok(name, what)); return edits() == [(CHATS[name], m["message_id"], f"{m['text']}\n\n{sentence}")] and "reply_markup" not in calls("editMessageText")[0]
def say(name, text, **more): return hook(msg(text, CHATS[name], **more))
def talk_to(name, f):
    """what the bot sent name while f ran: [(text, keyboard or None)]"""
    n = len(calls("sendMessage")); f()
    return [(p["text"], p.get("reply_markup")) for p in calls("sendMessage")[n:] if p["chat_id"] == CHATS[name]]
class Since:
    """the history entries made since: (who, as, via, what, text, absence)"""
    def __init__(self): self.n = len(entries())
    def new(self):
        got = entries()[: len(entries()) - self.n]; self.n = len(entries())
        return [(e["who"], e["as"], e["via"], e["what"], e["text"], e.get("absence")) for e in reversed(got)]
def by_telegram(name, what, words, i): return (name, name, "telegram", what, ENTRY + words, i)
def file_of(i): return open(absences._path(i), "rb").read()
def state_of(i, ckey=K5): return CV.state(*covered(i, ckey))
def told_planned(by=HUGO, **kw):
    """an absence planned for Eve, told with its cancel button -> its id"""
    i = absent(by=by, **kw); swept(); return i
def told_ask():
    """Sam's request to change K5 with the new pick Maya, the team told with the Approve button -> the absence's id"""
    i = asked(pick=False); new_pick(i, K5, MAYA); swept(); return i
def moved_to(i, j="dead00beef"):
    """the lesson K5 moved whole from absence i to another of the same teacher (an exam's takeover) -> that one's id"""
    r = absences.load(i); x = next(x for x in r["lessons"] if x["key"] == K5)
    r["lessons"].remove(x); absences._save(r); absences._save(dict(r, id=j, how="asked", by=EVE, lessons=[x], at=clock.now))
    return j
def handled(u):
    with A.app.test_request_context(HOOK, method="POST"): return bot.handle(u)
@contextlib.contextmanager
def quiet_app():
    """what app.logger writes is not printed here"""
    lg = A.app.logger; old, lg.disabled = lg.disabled, True
    try: yield
    finally: lg.disabled = old
def at_once(*fs):
    """each of fs in a thread of its own, started together"""
    go, errs = threading.Barrier(len(fs)), []
    def run(f):
        go.wait(10)
        try: f()
        except BaseException as e: errs.append(repr(e))
    ths = [threading.Thread(target=run, args=(f,)) for f in fs]; [x.start() for x in ths]; [x.join(30) for x in ths]
    assert errs == [], errs

@t
def the_answers_are_the_plans():
    assert (bot.OLD_BUTTON, bot.NOT_YOURS_BUTTON, bot.WHY_CHANGE, bot.WHY_CANCEL) == (OLD_BUTTON, NOT_YOURS_BUTTON, WHY_CHANGE, WHY_CANCEL)
    assert (bot.SENT_CHANGE, bot.SENT_CANCEL, bot.NOTHING, bot.WENT_WRONG, bot.LAST_ONE, bot.KEEP, bot.YES, bot.SURE_CANCEL) == (SENT_CHANGE, SENT_CANCEL, NOTHING, WENT_WRONG, LAST_ONE, "Keep it", "Yes, cancel it", "Cancel {days}? Your reason: {why}")
    plan = open(os.path.join(ROOT, "docs", "superpowers", "plans", "2026-11-22-relief-stage-4-telegram.md"), encoding="utf-8").read()
    assert bot.A_DUTY == A_DUTY
    for text in (OLD_BUTTON, NOT_YOURS_BUTTON, WHY_CHANGE, WHY_CANCEL, bot.SURE_CANCEL, SENT_CHANGE, SENT_CANCEL, A_DUTY, NOTHING, LAST_ONE, bot.REMINDED, WENT_WRONG, bot.KEEP, bot.YES): assert f"`{text}`" in plan, text
    rights = {k: v[0] for k, v in bot.ACTIONS.items()}
    assert bot.TALK_MINUTES == 15 and {k: rights[k] for k in ("ack", "change", "cancel", "approve", "keep", "cancel-yes")} == {"ack": "relief", "change": "relief", "cancel": "relief", "approve": "relief.team", "keep": "relief", "cancel-yes": "relief"}
    assert not hasattr(bot, "NOT_CANCEL"), "no list of phrases decides what is cancelled"

@t
def pressing_acknowledge_acknowledges_and_says_so():
    with school(SAM, TEAM):
        i, key = told_relief(); h = Since(); at("09:46:30")
        assert press(SAM, "ack") == ("✅ Acknowledged 09:46.", False)
        c = covered(i, K5)[2]
        assert state_of(i) == "acknowledged" and c["ack"] == dict(at="2026-10-12T09:46:30+08:00") and [x["what"] for x in c["history"]][-1] == "acknowledged", c
        assert h.new() == [by_telegram(SAM, "relief acknowledged", f"{SAM} acknowledged {ON_K5}", i)]
        p, = calls("editMessageText"); assert p == dict(chat_id=CHATS[SAM], message_id=item(key)["message_id"], text=RELIEF_K5 + "\n\n✅ Acknowledged 09:46.", disable_web_page_preview=True), p
        assert said(SAM) == [RELIEF_K5] and rows("talks") == [], "nothing else is sent"
        q_, = calls("answerCallbackQuery"); assert q_["callback_query_id"].startswith("q") and "parse_mode" not in q_ and "parse_mode" not in p
    with school(SAM):                                                                      # theirs after all, after asking to change: the new pick is not needed now
        i, key = told_relief(); CV.ask_change(i, K5, "x", SAM); new_pick(i, K5, MAYA); at("10:05"); h = Since()
        assert press(SAM, "ack") == ("✅ Acknowledged 10:05.", False) and state_of(i) == "acknowledged" and len(h.new()) == 1
    with school(SAM):                                                                      # a time kept in another zone reads in school time
        i, key = told_relief(); at("09:46"); change_record(i, lambda r: [x.update(ack=dict(at="2026-10-12T01:15:00+00:00")) for x in r["lessons"] if x["key"] == K5])
        assert press(SAM, "ack") == ("✅ Acknowledged 09:15.", False)

@t
def pressing_twice_says_the_same():
    with school(SAM, TEAM):
        i, key = told_relief(); at("09:46"); first = press(SAM, "ack"); was, h, swept_ = file_of(i), Since(), []
        for hm in ("09:46", "09:50", "15:00"):
            at(hm)
            with stand_in(TE, "soon", lambda: swept_.append(1)): assert press(SAM, "ack") == first == ("✅ Acknowledged 09:46.", False), hm
        assert file_of(i) == was and h.new() == [] and swept_ == [], "nothing saved, nothing written down, nothing asked for"
        assert edits() == [(CHATS[SAM], item(key)["message_id"], RELIEF_K5 + "\n\n✅ Acknowledged 09:46.")] * 4, "the first edit may have failed"
        # the press comes with the text as it is by then: the line is not put there twice
        done = dict(under(tok(SAM, "ack")), text=RELIEF_K5 + "\n\n✅ Acknowledged 09:46."); tg.PRACTICE_LOG.clear()
        hook(callback("b:" + tok(SAM, "ack"), done)); assert answers() == [first] and edits() == []
        at("08:00", day=14); assert press(SAM, "ack") == first, "the day after, as the page answers"
    with school(SAM):                                                                      # acknowledged in the app, then pressed here
        i, key = told_relief(); at("09:20"); on_cover(SAM, i, K5, "acknowledge"); at("09:30"); h = Since()
        assert press(SAM, "ack") == ("✅ Acknowledged 09:20.", False) and h.new() == [] and edits()[-1][2].endswith("\n\n✅ Acknowledged 09:20.")

@t
def a_moved_relief_pressed_late_says_so():
    ways = dict(moved=lambda i: give(i, K5, MAYA), asked_then_moved=lambda i: (CV.ask_change(i, K5, "x", SAM), new_pick(i, K5, MAYA), CV.approve(i, K5, MAYA, TEAM, SCHOOL, rs())),
                not_needed=lambda i: absences.not_needed(i, K5, "x", HUGO), cancelled=lambda i: absences.cancel(i, "x", HUGO))
    for how, f in ways.items():
        for what in ("ack", "change"):
            with school(SAM, TEAM):
                i, key = told_relief(); at("09:30"); f(i); was, h = file_of(i), Since()
                assert press(SAM, what) == (CV.NOT_YOURS_COVER, True), (how, what)
                assert file_of(i) == was and h.new() == [] and taken_off(SAM, what, "This relief is not yours.") and rows("talks") == [] and said(SAM) == [RELIEF_K5], (how, what)
                on_cover(SAM, i, K5, "acknowledge" if what == "ack" else "ask-change", dict(why="x"), code=403)                  # as the page answers
    for what in ("ack", "change"):
        with school(SAM):
            i, key = told_relief(); absences.not_needed(i, K5, "x", HUGO); absences.needed_again(i, K5, HUGO); CV.split(i, K5, 6, TEAM); was = file_of(i)
            assert press(SAM, what) == (absences.CHANGED, True) and file_of(i) == was and taken_off(SAM, what, absences.CHANGED), "split since: no such cover"
        with school(SAM):
            i, key = told_relief(); was = file_of(i); at("08:00", day=14)
            assert press(SAM, what) == (absences.PAST_LESSON, True) and file_of(i) == was and rows("talks") == [] and taken_off(SAM, what, absences.PAST_LESSON)
        with school(SAM):
            i, key = told_relief(); os.remove(absences._path(i)); assert press(SAM, what) == (absences.CHANGED, True) and taken_off(SAM, what, absences.CHANGED)
        with school(SAM):
            i, key = told_relief(); was = file_of(i)
            with no_pub(): assert press(SAM, what) == (WB.NO_PUB, True) and file_of(i) == was and edits() == [], "as every page of relief answers; a publish may be swapping folders: it can be pressed again"
    with school(SAM):
        i, key = told_relief(); CV.ask_change(i, K5, "x", SAM); was = file_of(i); assert press(SAM, "change") == (CV.ASKED_ALREADY, True) and file_of(i) == was and rows("talks") == [] and taken_off(SAM, "change", CV.ASKED_ALREADY)

@t
def a_forwarded_button_is_refused_for_another_chat():
    with school(SAM, MAYA, EVE, TEAM, LEE, HUGO):
        i = told_ask(); j = told_planned(dates=["2026-10-16"]); was, h = (file_of(i), file_of(j)), Since(); tg.PRACTICE_LOG.clear()
        for name, what, others in ((SAM, "ack", (MAYA, EVE, TEAM, HUGO)), (SAM, "change", (MAYA, TEAM)), (EVE, "cancel", (SAM, HUGO, TEAM)), (TEAM, "approve", (SAM, LEE, EVE))):
            for other in others: assert press(name, what, chat=CHATS[other]) == (NOT_YOURS_BUTTON, True), (what, other)      # Lee is on the team too: each has their own button
        assert (file_of(i), file_of(j)) == was and h.new() == [] and edits() == [] and sent() == [] and rows("talks") == []
        # in a group, a channel, or by a bot: nothing at all
        token, m = tok(SAM, "ack"), under(tok(SAM, "ack")); tg.PRACTICE_LOG.clear()
        for chat in (dict(id=-100777, type="group"), dict(id=-100777, type="supergroup"), dict(id=-100777, type="channel"), dict(id=CHATS[SAM], type="group"), None, 7):
            assert hook(callback("b:" + token, dict(m, chat=chat), **{"from": dict(id=CHATS[SAM], is_bot=False)})).status_code == 200
        hook(callback("b:" + token, m, **{"from": dict(id=CHATS[SAM], is_bot=True)}))
        hook(dict(update_id=next(_ids), callback_query=dict({"id": "q1", "data": "b:" + token, "inline_message_id": "x", "from": dict(id=CHATS[SAM], is_bot=False)})))
        assert tg.PRACTICE_LOG == [] and (file_of(i), file_of(j)) == was
        # a link that moved to another phone: the old chat's button is nobody's, and the new chat's is hers alone
        links.link(MAYA, CHATS[SAM], None); assert press(SAM, "ack") == (NOT_YOURS_BUTTON, True) and (file_of(i), file_of(j)) == was

@t
def a_private_chat_is_its_own_persons():
    """Telegram gives a private chat the id of the person it is with: anything else is nobody's message or press"""
    with school(SAM, MAYA):
        i, key = told_relief(); token = tok(SAM, "ack"); was, code = file_of(i), links.new_code(HUGO)["code"]; press(SAM, "change"); kept_ = rows("talks"); tg.PRACTICE_LOG.clear()
        for f in (dict(id=CHATS[MAYA], is_bot=False), dict(id=CHATS[SAM], is_bot=True), dict(id=str(CHATS[SAM])), dict(id=float(CHATS[SAM]) + 0.5), dict(id=None), dict(is_bot=False), {}, None, 7, [], "x"):
            for text in ("/stop", "/help", code, f"/start {code}", "A meeting", "/cancel"):
                u = msg(text, CHATS[SAM]); u["message"]["from"] = f; assert hook(u).status_code == 200
            hook(callback("b:" + token, under(token), **{"from": f}))
        for text in ("/stop", "A meeting"): u = msg(text, CHATS[SAM]); del u["message"]["from"]; hook(u)
        u = callback("b:" + token, under(token)); del u["callback_query"]["from"]; hook(u)
        assert tg.PRACTICE_LOG == [] and file_of(i) == was and rows("talks") == kept_ and links.chat_of(SAM) == CHATS[SAM] and links.chat_of(HUGO) is None and not any(links.tries.fails.values())
        assert press(SAM, "ack")[0].startswith("✅")

@t
def an_unlinked_chat_that_presses_is_held_back():
    with school(SAM):
        i, key = told_relief(); was = file_of(i); token = tok(SAM, "ack"); tg.PRACTICE_LOG.clear()
        for data in ("b:" + token, "b:" + "x" * 16, "b:" + token, "odd", None, "b:" + token, "b:" + token): hook(callback(data, under(token), chat=990))
        assert answers() == [(NOT_LINKED, True)] * 5 and [m for m, p in tg.PRACTICE_LOG] == ["answerCallbackQuery"] * 5, "over the limit: nothing at all"
        assert len(links.tries.fails["tg:990"]) == 5 and file_of(i) == was
        tg.PRACTICE_LOG.clear(); hook(msg("hello", 990)); assert tg.PRACTICE_LOG == [], "presses and messages count together"
        for k in range(5): hook(msg("ABCD-EFGH", CHATS[SAM]))                              # a linked person over the limit gets nothing either
        tg.PRACTICE_LOG.clear(); hook(callback("b:" + token, under(token))); assert tg.PRACTICE_LOG == [] and file_of(i) == was
        links.tries.fails.clear(); assert press(SAM, "ack")[0].startswith("✅"), "ten minutes later"
    with school(SAM):                                                                      # unlinked since it was sent; linked again: theirs again
        i, key = told_relief(); was = file_of(i); links.unlink(SAM); assert press(SAM, "ack") == (NOT_LINKED, True) and file_of(i) == was
        links.link(SAM, CHATS[SAM], None); assert press(SAM, "ack")[0].startswith("✅") and state_of(i) == "acknowledged"
    with school(SAM):                                                                      # 16 at once: still five
        i, key = told_relief(); token = tok(SAM, "ack"); m = under(token); tg.PRACTICE_LOG.clear()
        at_once(*[lambda: hook(callback("b:" + token, m, chat=991))] * 16); assert len(answers()) == 5 == len(links.tries.fails["tg:991"])

@t
def a_button_expires():
    with school(SAM, TEAM):
        i, key = told_relief(); token, was = tok(SAM, "ack"), file_of(i); now = datetime.datetime.fromisoformat(clock.now).timestamp()
        assert next(r["until"] for r in rows("buttons") if r["token"] == token) == now + 30 * 86400
        button(token, until=now - 1); assert press(SAM, "ack") == (OLD_BUTTON, True) and file_of(i) == was and edits() == []
        with tgdb.db() as c: c.execute("DELETE FROM buttons WHERE token<>?", (token,))
        button(token, until=now)
        for data in ("b:" + "x" * 16, "b:", "b:" + token[:-1], "b:" + token + "x", "B:" + token, token, "a:" + token, "b:" + token + "\n", " b:" + token, "b:' OR 1=1 --xxxx", "", None, 7, ["b:" + token], {}):
            n = len(answers()); hook(callback(data, under(token))); assert answers()[n:] == [(OLD_BUTTON, True)], data
        assert file_of(i) == was; button(token, what="made-up"); assert press_token(token) == (OLD_BUTTON, True), "a kind that is not there"
        for odd in (None, "", "ACK", "__class__"): button(token, what=odd); assert press_token(token) == (OLD_BUTTON, True), odd
        assert file_of(i) == was; button(token, what="ack"); assert press(SAM, "ack")[0].startswith("✅"), "at its very last second"
        at("08:00", day=13); assert press(SAM, "ack") == (OLD_BUTTON, True), "and a day later it is not"

@t
def a_rights_change_between_is_honoured():
    OFF, NONE = dict(off=True), dict(group="executive")
    with school(SAM, MAYA, EVE, TEAM):
        i = told_ask(); j = told_planned(dates=["2026-10-16"]); was, h = (file_of(i), file_of(j)), Since()
        for name, what in ((SAM, "ack"), (SAM, "change"), (EVE, "cancel"), (TEAM, "approve")):
            with record(name, **OFF): links.tries.fails.clear(); assert press(name, what) == (NOT_LINKED, True), what              # switched off: nobody's chat
            with record(name, **NONE, extras=dict(relief=False, exams=None, admin=False)): assert press(name, what) == (NOT_YOURS_BUTTON, True), what      # there, without relief
            with broken_accounts(): links.tries.fails.clear(); assert press(name, what) == (NOT_LINKED, True), what
            with no_pub(RP.fake_pub([dict(name=HUGO)])): links.tries.fails.clear(); assert press(name, what) == (NOT_LINKED, True), "gone from the timetable"
        with record(TEAM, extras=dict(relief=False, exams=None, admin=False)):              # off the relief team, still a teacher
            assert press(TEAM, "approve") == (NOT_YOURS_BUTTON, True) and links.name_of(CHATS[TEAM]) == TEAM
        with record(TEAM, group="leader", extras=dict(relief=False, exams=None, admin=False)): assert press(TEAM, "approve") == (NOT_YOURS_BUTTON, True), "planning relief is not the team"
        assert (file_of(i), file_of(j)) == was and h.new() == [] and edits() == [] and rows("talks") == [] and WHY_CANCEL not in said(EVE)
        assert press(TEAM, "approve")[0].startswith("✅ Approved: Ms Maya Lee"), "given back: at once"
    # between the press and the typed line
    for change, want in ((OFF, NOT_LINKED), (NONE, NOT_LINKED)):
        with school(EVE, SAM):
            i, key = told_relief(); j = told_planned(dates=["2026-10-16"]); press(EVE, "cancel"); press(SAM, "change"); was = (file_of(i), file_of(j))
            for name in (EVE, SAM):
                with record(name, **change): assert talk_to(name, lambda: say(name, "A meeting")) == [(want, None)]
            assert (file_of(i), file_of(j)) == was and rows("talks") == [], "and the conversation is over"
            assert talk_to(EVE, lambda: say(EVE, "A meeting")) == [(NOT_READ, None)] and file_of(j) == was[1]

@t
def request_to_change_asks_why_then_sends():
    with school(SAM, TEAM):
        i, key = told_relief(); h, was = Since(), file_of(i); at("09:10"); token = tok(SAM, "change"); m = under(token)
        assert talk_to(SAM, lambda: press(SAM, "change")) == [(WHY_CHANGE, FORCE)] and answers() == [(None, None)]
        until = datetime.datetime.fromisoformat(clock.now).timestamp() + 900
        d = talk_of(SAM); assert re.fullmatch(r"[A-Za-z0-9_-]{16}", d["key"]) and type(d["question"]) is int and d["question"] > m["message_id"], d
        assert talks() == [(CHATS[SAM], "change", dict(id=i, ckey=K5, absent=EVE, token=token, message=dict(id=m["message_id"], text=RELIEF_K5), key=d["key"], question=d["question"]), until)], talks()
        assert not [r for r in rows("buttons") if r["what"] == "keep"], "the cancel question's alone"
        assert file_of(i) == was and h.new() == [] and edits() == [], "nothing is done yet: the buttons stay"
        at("09:24:59"); asked_for = []; real = FL.soon
        with stand_in(FL, "soon", lambda **kw: (asked_for.append((kw, len(entries()), absences._LOCK.locked(), bot._pressing.locked())), real(**kw))[1]):
            assert talk_to(SAM, lambda: say(SAM, "  A parent\nmeeting  ")) == [(SENT_CHANGE, None)]
        ch = covered(i, K5)[2]["change"]; assert (state_of(i), ch["why"], ch["at"]) == ("change", "A parent meeting", clock.now), ch
        assert ch["pick"]["who"] and asked_for == [(dict(ids=[i], force=True), len(entries()), False, False)], "a new pick at once, as the page asks for it"
        assert h.new() == [by_telegram(SAM, "asked to change", f"{SAM} asked to change {ON_K5}", i)] and rows("talks") == []
        assert edits() == [(CHATS[SAM], m["message_id"], RELIEF_K5 + "\n\n↩ Asked to change 09:24.")] and "reply_markup" not in calls("editMessageText")[0]
        send(); assert [x.split("\n")[0] for x in said(TEAM)] == ["↩ Request to change"] and "“A parent meeting”" in said(TEAM)[0], "and the team is asked"
        assert talk_to(SAM, lambda: say(SAM, "One more thing")) == [(NOT_READ, None)] and press(SAM, "change") == (CV.ASKED_ALREADY, True) and h.new() == []
    # refused when the line comes: the app's sentence, the conversation over, nothing saved, the buttons taken off
    ways = {CV.NOT_YOURS_COVER: lambda i: give(i, K5, MAYA), CV.ASKED_ALREADY: lambda i: CV.ask_change(i, K5, "x", SAM), absences.PAST_LESSON: None, absences.CHANGED: lambda i: os.remove(absences._path(i))}
    for sentence, f in ways.items():
        with school(SAM):
            i, key = told_relief(); at("23:50", day=13 if f is None else 12); press(SAM, "change"); at("00:01", day=14) if f is None else f(i)
            was, h = os.path.exists(absences._path(i)) and file_of(i), Since()
            assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(sentence, None)] and rows("talks") == [] and taken_off(SAM, "change", sentence) and h.new() == []
            assert (os.path.exists(absences._path(i)) and file_of(i)) == was

@t
def cancel_asks_why_then_once_more_then_cancels():
    with school(EVE, HUGO, SAM, TEAM):
        i = told_planned(); give(i, K5, SAM); swept(); h, was = Since(), file_of(i); at("09:10"); token = tok(EVE, "cancel"); m = under(token)
        assert m["text"] == PLANNED_EVE and talk_to(EVE, lambda: press(EVE, "cancel")) == [(WHY_CANCEL, keep_it(EVE))] and answers() == [(None, None)]
        d = talk_of(EVE); assert talks()[0][:3] == (CHATS[EVE], "cancel", dict(id=i, ckey=None, absent=None, token=token, message=dict(id=m["message_id"], text=PLANNED_EVE), key=d["key"], question=d["question"]))
        k, = [r for r in rows("buttons") if r["what"] == "keep"]; assert (k["token"], k["name"], k["id"], k["until"]) == (d["key"], EVE, i, talks()[0][3]) and CHATS[EVE] not in (k["id"], k["extra"]), k
        # the line: kept, shown, and nothing cancelled
        at("09:12"); assert talk_to(EVE, lambda: say(EVE, " The course\nwas called  off ")) == [("Cancel Tue 13 Oct? Your reason: The course was called off", yes_or_keep(EVE))]
        assert file_of(i) == was and h.new() == [] and edits() == [] and len(answers()) == 1, "nothing is done yet"
        e = talk_of(EVE); until = datetime.datetime.fromisoformat("2026-10-12T09:27:00+08:00").timestamp()
        assert e == dict(d, why="The course was called off", days="Tue 13 Oct", yes=e["yes"], question=e["question"]) and e["question"] > d["question"] and talks()[0][3] == until, "15 minutes from this question"
        mine = {r["what"]: r for r in rows("buttons") if r["what"] in ("keep", "cancel-yes")}; assert [(r["token"], r["name"], r["id"], r["until"]) for r in (mine["cancel-yes"], mine["keep"])] == [(e["yes"], EVE, i, until), (d["key"], EVE, i, until)]
        assert re.fullmatch(r"[A-Za-z0-9_-]{16}", e["yes"]) and len({e["yes"], d["key"], token}) == 3 and len([r for r in rows("buttons") if r["what"] == "keep"]) == 1
        # the press
        at("09:26"); order = []; real_sync, real_soon, real_tell = WB._sync_exams, WB._soon, WB._tell_soon; x = sure(EVE); tg.PRACTICE_LOG.clear()
        locks = lambda: (absences._LOCK.locked(), bot._pressing.locked())
        with stand_in(WB, "_sync_exams", lambda pub: (order.append(("sync", pub is SCHOOL, len(entries()) - h.n, *locks())), real_sync(pub))), \
                stand_in(WB, "_soon", lambda **kw: (order.append(("soon", kw, *locks())), real_soon(**kw))[1]), stand_in(WB, "_tell_soon", lambda: (order.append(("tell", *locks())), real_tell())):
            assert press_yes(EVE) == (SENT_CANCEL, False)
        assert order == [("sync", True, 1, False, False), ("soon", {}, False, False), ("tell", False, False)], order
        r = absences.load(i); assert r["cancelled"] == dict(at="2026-10-12T09:26:00+08:00", by=EVE, why="The course was called off") and state_of(i) == "cancelled"
        assert h.new() == [by_telegram(EVE, "cancelled", "cancelled", i)] and rows("talks") == [] and sent() == [], "answered by the press"
        assert edits() == [(CHATS[EVE], x["message_id"], x["text"] + "\n\n" + SENT_CANCEL), (CHATS[EVE], m["message_id"], PLANNED_EVE + "\n\n❌ Cancelled 09:26.")] and not any("reply_markup" in p for p in calls("editMessageText")), "both lose their buttons"
        send(); assert said(HUGO)[-1] == said(TEAM)[-1] == CANCELLED_EVE.format(EVE) and said(SAM)[-1] == GONE_K5, "who the page would tell"
        was = file_of(i); assert press_keep(e["yes"], x) == press_keep(e["key"], x) == (OLD_BUTTON, True) and press(EVE, "cancel") == (absences.CANCELLED, True) and rows("talks") == [] and file_of(i) == was and h.new() == []
    ways = {absences.CANCELLED: lambda i: absences.cancel(i, "x", HUGO), absences.PAST_ABSENCE: lambda i: at("00:01", day=14), absences.WRONG: lambda i: os.remove(absences._path(i)),
            absences.NOT_YOURS: lambda i: change_record(i, lambda r: r.update(teacher=RUTH))}
    for sentence, f in ways.items():
        with school(EVE):                                                                  # refused at the press: no question
            i = told_planned(); f(i); assert press(EVE, "cancel") == (sentence, True) and rows("talks") == [] and said(EVE) == [PLANNED_EVE] and taken_off(EVE, "cancel", sentence)
        if sentence == absences.PAST_ABSENCE: continue                                     # by then its conversation is over (below)
        with school(EVE):                                                                  # refused when the line comes
            i = told_planned(); press(EVE, "cancel"); f(i); was, h = os.path.exists(absences._path(i)) and file_of(i), Since()
            assert talk_to(EVE, lambda: say(EVE, "x")) == [(sentence, None)] and (os.path.exists(absences._path(i)) and file_of(i)) == was and h.new() == [] and taken_off(EVE, "cancel", sentence)
    for sentence, f in ways.items():                                                       # refused at the last press: both messages say it and lose their buttons, the conversation is over
        with school(EVE):
            i = told_planned(); at("23:50", day=13); press(EVE, "cancel"); say(EVE, "x"); x, e, m = sure(EVE), talk_of(EVE), under(tok(EVE, "cancel")); f(i)
            was, h = os.path.exists(absences._path(i)) and file_of(i), Since(); tg.PRACTICE_LOG.clear()
            assert press_keep(e["yes"], x) == (sentence, True) and (os.path.exists(absences._path(i)) and file_of(i)) == was and h.new() == [] and rows("talks") == [], sentence
            assert edits() == [(CHATS[EVE], x["message_id"], f"{x['text']}\n\n{sentence}"), (CHATS[EVE], m["message_id"], f"{m['text']}\n\n{sentence}")] and press_keep(e["yes"], x) == (OLD_BUTTON, True), sentence
    with school(EVE):
        i = told_planned(); at("23:50", day=13); press(EVE, "cancel"); at("00:01", day=14); assert talk_to(EVE, lambda: say(EVE, "x")) == [(absences.PAST_ABSENCE, None)] and not absences.load(i)["cancelled"] and taken_off(EVE, "cancel", absences.PAST_ABSENCE)
    with school(TEAM):                                                                     # the relief team's right does not count here: hers as the absent teacher, or not at all
        j = absent(by=HUGO); OB.queue("made-up", TEAM, "A made-up message", kind="made-up", buttons=[dict(text="x", what="cancel", id=j)]); send(); was = file_of(j)
        assert press(TEAM, "cancel") == (absences.NOT_YOURS, True) and file_of(j) == was

@t
def approve_needs_the_team_right_and_the_pick_shown():
    with school(SAM, MAYA, TEAM, LEE):
        i = told_ask(); h = Since(); at("09:20"); m = under(tok(TEAM, "approve"))
        assert press(TEAM, "approve") == ("✅ Approved: Ms Maya Lee, 09:20.", False)
        c = covered(i, K5)[2]; assert (c["relief"], c["approved"], state_of(i)) == (MAYA, dict(by=TEAM, at=clock.now), "approved"), c
        assert h.new() == [by_telegram(TEAM, "approved", f"{MAYA} approved for {ON_K5}", i)] and edits() == [(CHATS[TEAM], m["message_id"], m["text"] + "\n\n✅ Approved: Ms Maya Lee, 09:20.")]
        send(); assert said(SAM)[-1] == MOVED_K5 and said(MAYA) == [RELIEF_K5]
        was = file_of(i)
        for name in (TEAM, LEE): assert press(name, "approve") == (CV.NOT_WAITING, True) and file_of(i) == was and h.new() == [], name      # too late
    # the pick moved on: never approved by a message that showed another
    def drop(i): CV.drop(i, K5, "x", who=MAYA, into="change")
    for f in (drop, lambda i: (drop(i), new_pick(i, K5, HUGO)), lambda i: CV.acknowledge(i, K5, SAM)):
        with school(SAM, MAYA, TEAM):
            i = told_ask(); f(i); was, h = file_of(i), Since(); want = CV.NOT_WAITING if state_of(i) == "acknowledged" else CV.PICK_CHANGED
            assert press(TEAM, "approve") == (want, True) and file_of(i) == was and h.new() == [] and (edits() == [] if want == CV.PICK_CHANGED else taken_off(TEAM, "approve", want)), want
            on_cover(TEAM, i, K5, "approve", dict(who=MAYA), code=400)
    with school(SAM, MAYA, TEAM):                                                          # no longer free
        i = told_ask(); store.write_json(RS.PATH, dict(calendar=TERM, limits=dict(fat_per_day=3, other_per_day=None, never=[MAYA]))); was, h = file_of(i), Since()
        assert press(TEAM, "approve") == ("Ms Maya Lee is no longer free then. Choose someone else.", True) and file_of(i) == was and h.new() == [] and edits() == []
    with school(SAM, MAYA, TEAM):
        i = told_ask(); was = file_of(i); assert press(SAM, "ack")[0].startswith("✅"); assert press(TEAM, "approve") == (CV.NOT_WAITING, True)
    with school(SAM, MAYA, TEAM):                                                          # the name is the button's own: nothing typed or sent with the press counts
        i = told_ask(); button(tok(TEAM, "approve"), who=HUGO); was = file_of(i); assert press(TEAM, "approve") == (CV.PICK_CHANGED, True) and file_of(i) == was
        button(tok(TEAM, "approve"), who=None); assert press(TEAM, "approve") == (CV.PICK_CHANGED, True) and file_of(i) == was

@t
def a_refused_button_is_taken_off():
    """the groups of the ruling, each kind of button: refused by the app (off), the two refusals of Approve that keep it, what is no refusal (as it was)"""
    def off(name, what, f, sentence):
        with school(SAM, MAYA, EVE, TEAM):
            i = told_ask() if what == "approve" else told_planned()
            if what in ("ack", "change"): give(i, K5, SAM); swept()
            f(i); tg.PRACTICE_LOG.clear(); assert press(name, what) == (sentence, True) and taken_off(name, what, sentence), (what, sentence)
            assert [m for m, p in tg.PRACTICE_LOG] == ["answerCallbackQuery", "editMessageText"], "answered first"
            done = dict(under(tok(name, what))); done["text"] += f"\n\n{sentence}"; tg.PRACTICE_LOG.clear()             # pressed again before the edit came: not said twice
            hook(callback("b:" + tok(name, what), done)); assert answers() == [(sentence, True)] and edits() == [], what
    cancel_it = lambda i: absences.cancel(i, "x", HUGO)
    for what in ("ack", "change"):
        for f in (lambda i: give(i, K5, MAYA), cancel_it, lambda i: absences.not_needed(i, K5, "x", HUGO)): off(SAM, what, f, "This relief is not yours.")
        off(SAM, what, lambda i: at("08:00", day=14), "This lesson is in the past."); off(SAM, what, lambda i: os.remove(absences._path(i)), absences.CHANGED)
    off(SAM, "change", lambda i: CV.ask_change(i, K5, "x", SAM), "You asked to change this relief already.")
    off(EVE, "cancel", cancel_it, "This absence was cancelled."); off(EVE, "cancel", lambda i: at("08:00", day=14), "This absence is in the past.")
    off(EVE, "cancel", lambda i: change_record(i, lambda r: r.update(teacher=RUTH)), "You cannot change this absence."); off(EVE, "cancel", lambda i: os.remove(absences._path(i)), absences.WRONG)
    off(TEAM, "approve", lambda i: CV.keep(i, K5, LEE), CV.NOT_WAITING); off(TEAM, "approve", lambda i: give(i, K5, HUGO), CV.NOT_WAITING); off(TEAM, "approve", cancel_it, "This absence was cancelled.")
    off(TEAM, "approve", lambda i: at("08:00", day=14), "This lesson is in the past."); off(TEAM, "approve", lambda i: os.remove(absences._path(i)), absences.CHANGED)
    def stays(name, what, f, answer):
        with school(SAM, MAYA, EVE, TEAM):
            i = told_ask() if what == "approve" else told_planned()
            if what in ("ack", "change"): give(i, K5, SAM); swept()
            tg.PRACTICE_LOG.clear(); got = f(i); assert got == answer and edits() == [] and calls("editMessageReplyMarkup") == [], (what, got)
    def never_free(i): store.write_json(RS.PATH, dict(calendar=TERM, limits=dict(fat_per_day=3, other_per_day=None, never=[MAYA])))
    stays(TEAM, "approve", lambda i: (CV.drop(i, K5, "x", who=MAYA, into="change"), press(TEAM, "approve"))[1], (CV.PICK_CHANGED, True))
    stays(TEAM, "approve", lambda i: (CV.drop(i, K5, "x", who=MAYA, into="change"), new_pick(i, K5, HUGO), press(TEAM, "approve"))[2], (CV.PICK_CHANGED, True))
    stays(TEAM, "approve", lambda i: (never_free(i), press(TEAM, "approve"))[1], ("Ms Maya Lee is no longer free then. Choose someone else.", True))
    def within(cm, name, what):
        with cm: return press(name, what)
    def boom(*a, **k): raise RuntimeError("made up")
    for name, what, module, f in ((SAM, "ack", CV, "acknowledge_once"), (SAM, "change", CV, "_mine"), (EVE, "cancel", absences, "_editable"), (TEAM, "approve", CV, "approve")):        # (the second press of a cancel: its own test)
        stays(name, what, lambda i: press(name, what, chat=CHATS[MAYA]), (NOT_YOURS_BUTTON, True))
        stays(name, what, lambda i: (button(tok(name, what), until=0), press(name, what))[1], (OLD_BUTTON, True))
        stays(name, what, lambda i: within(record(name, group="executive", extras=dict(relief=False, exams=None, admin=False)), name, what), (NOT_YOURS_BUTTON, True))
        stays(name, what, lambda i: within(record(name, off=True), name, what), (NOT_LINKED, True))
        stays(name, what, lambda i: within(stand_in(module, f, boom), name, what), (WENT_WRONG, True))
        stays(name, what, lambda i: within(no_pub(), name, what), (WB.NO_PUB, True))
    # when its why was typed: the sentence is said, and the message loses its buttons; what is no refusal leaves it
    for name, what, module, f, undo, sentence in ((SAM, "change", CV, "ask_change", lambda i: give(i, K5, MAYA), CV.NOT_YOURS_COVER), (EVE, "cancel", absences, "_editable", cancel_it, absences.CANCELLED)):
        def told(i): give(i, K5, SAM); swept()
        with school(SAM, MAYA, EVE): i = told_planned(); told(i); press(name, what); undo(i); assert talk_to(name, lambda: say(name, "x")) == [(sentence, None)] and taken_off(name, what, sentence)
        for make, want in ((lambda: stand_in(module, f, boom), WENT_WRONG), (no_pub, WB.NO_PUB), (contextlib.nullcontext, OLD_BUTTON)):
            with school(SAM, MAYA, EVE):
                i = told_planned(); told(i); press(name, what); tg.PRACTICE_LOG.clear()
                if want == OLD_BUTTON: button(tok(name, what), until=0)
                with make(): assert talk_to(name, lambda: say(name, "x")) == [(want, None)] and rows("talks") == [] and edits() == [], (what, want)
    # Telegram not doing it changes nothing; too old for its text: the buttons alone go
    with school(SAM):
        i, key = told_relief(); give(i, K5, MAYA); was, real = file_of(i), tg.call
        def failing_(method, params=None, **kw): return dict(real(method, params, **kw), ok=method != "editMessageText", kind=None if method != "editMessageText" else "refused")
        with stand_in(tg, "call", failing_): assert press(SAM, "ack") == (CV.NOT_YOURS_COVER, True) and file_of(i) == was
        m = under(tok(SAM, "ack")); tg.PRACTICE_LOG.clear(); hook(callback("b:" + tok(SAM, "ack"), dict(message_id=m["message_id"], chat=m["chat"], date=0)))
        assert answers() == [(CV.NOT_YOURS_COVER, True)] and edits() == [] and calls("editMessageReplyMarkup") == [dict(chat_id=CHATS[SAM], message_id=m["message_id"])]
        # the lock is let go before the message is changed
        held = []
        with stand_in(tg, "call", lambda method, params=None, **kw: (held.append((bot._pressing.locked(), absences._LOCK.locked())), real(method, params, **kw))[1]): press(SAM, "ack")
        assert held == [(False, False)] * 2

@t
def what_stops_a_lesson_is_said_as_the_page_says_it():
    with exam_school(SAM, MAYA, TEAM):
        i = told_ask(); e = exam(); was, h = file_of(i), Since(); why = f"This lesson is not happening: 1A, 1B are on {EXAM}."
        assert press(TEAM, "approve") == (why, True) and file_of(i) == was and h.new() == [] and edits() == [] and calls("editMessageReplyMarkup") == [], "its button stays: it may be on again"
        assert on_cover(TEAM, i, K5, "approve", dict(who=MAYA), code=400) == dict(error=why)
        with unreadable(), quiet_app(): assert press(TEAM, "approve")[0].startswith("✅ Approved"), "the exams cannot be read: as if there were none, as on the page"
    with exam_school(SAM, MAYA, TEAM):                                                     # withdrawn: the same button does it, once
        i = told_ask(); e, token, h, m = exam(), tok(TEAM, "approve"), Since(), under(tok(TEAM, "approve")); assert [press(TEAM, "approve") for _ in range(2)] == [(why, True)] * 2
        withdraw(e); at("09:20"); assert tok(TEAM, "approve") == token and [press(TEAM, "approve") for _ in range(2)] == [("✅ Approved: Ms Maya Lee, 09:20.", False), (CV.NOT_WAITING, True)]
        c = covered(i, K5)[2]; assert (c["relief"], c["approved"]) == (MAYA, dict(by=TEAM, at=clock.now)) and h.new() == [by_telegram(TEAM, "approved", f"{MAYA} approved for {ON_K5}", i)]
        assert edits()[0] == (CHATS[TEAM], m["message_id"], m["text"] + "\n\n✅ Approved: Ms Maya Lee, 09:20."); send(); assert said(MAYA) == [RELIEF_K5]
    with exam_school(SAM, MAYA, TEAM):                                                     # on an exam duty then: not free
        i = told_ask(); exam("5A", name=EXAM2, duties=[(MAYA, 630, 690)]); was = file_of(i)
        assert press(TEAM, "approve") == ("Ms Maya Lee is no longer free then. Choose someone else.", True) and file_of(i) == was
    with exam_school(SAM, EVE, TEAM):                                                      # cancelling an absence of one's own gives its lesson back to the backup at once
        exam("5A", name=EXAM2, duties=[(EVE, 630, 690)]); j = told_planned(); backups = lambda: [r for r in absences.all_records() if r.get("exams") and not r["cancelled"]]
        assert backups() == []; press(EVE, "cancel"); say(EVE, "Better"); assert backups() == [] and press_yes(EVE) == (SENT_CANCEL, False) and absences.load(j)["cancelled"] and [x["key"] for r in backups() for x in r["lessons"]] == [K5]

@t
def a_backup_is_not_cancelled_on_telegram():
    """an exam's or event's backup would be made again at once: no button for it, and one on an older message is refused, at each step"""
    OLDER = [[dict(text="❌ Not needed: cancel", what="cancel", id=None)]]
    def older(i):
        """a message with the button, as it was before -> its token"""
        OB.queue("older", EVE, "An older message", kind="made-up", buttons=[[dict(OLDER[0][0], id=i)]]); send(); return tok(EVE, "cancel")
    for kind, by in (("exam", "Exams committee"), ("event", HUGO)):
        with exam_school(EVE, SAM, HUGO, TEAM):
            e, b = backed_up(kind); give(b, K5, SAM); swept(); r, = outs("planned")
            assert r["name"] == EVE and f"\nPlanned by {by}\n" in r["text"] and buttons_of(r) == [[dict(text="✅ Acknowledge and set work", url=BASE + "/relief#mine")]], (kind, buttons_of(r))
            assert not any(x["what"] == "cancel" for x in rows("buttons")), kind
            token, was, h, n = older(b), file_of(b), Since(), len(sent()); assert press(EVE, "cancel") == (A_DUTY, True) and len(A_DUTY) <= bot.ANSWER_MOST
            assert taken_off(EVE, "cancel", A_DUTY) and rows("talks") == [] and file_of(b) == was and h.new() == [] and len(sent()) == n and swept() == 0 and state_of(b) == "approved", kind
            at("09:20"); absences.update_exams(b, (), [], None, None, LS.today()); assert press(EVE, "cancel") == (absences.CANCELLED, True), "over meanwhile: that is what is said"
    with exam_school(EVE, HUGO, TEAM):                                                     # on the page as before: it goes, and comes back
        e, b = backed_up("exam"); call(EVE, "post", f"/api/relief/absences/{b}/cancel", dict(why="x")); assert absences.load(b)["cancelled"]["by"] == EVE and backup_of(EVE) != b
    # judged as it is at that moment: a backup by the time its why is typed, or by the second press
    becomes = lambda i: change_record(i, lambda r: r.update(exams=dict(id="abcd1234", kind="exam")))
    with exam_school(EVE, TEAM):
        i = told_planned(); press(EVE, "cancel"); becomes(i); was, h = file_of(i), Since(); assert talk_to(EVE, lambda: say(EVE, "The course is off")) == [(A_DUTY, None)] and file_of(i) == was and h.new() == []
        assert rows("talks") == [] and taken_off(EVE, "cancel", A_DUTY)
    with exam_school(EVE, TEAM):
        i = told_planned(); press(EVE, "cancel"); say(EVE, "The course is off"); becomes(i); x, e, m, was, h = sure(EVE), talk_of(EVE), under(tok(EVE, "cancel")), file_of(i), Since(); tg.PRACTICE_LOG.clear()
        assert press_keep(e["yes"], x) == (A_DUTY, True) and file_of(i) == was and h.new() == [] and rows("talks") == [] and sent() == []
        assert edits() == [(CHATS[EVE], x["message_id"], f"{x['text']}\n\n{A_DUTY}"), (CHATS[EVE], m["message_id"], f"{m['text']}\n\n{A_DUTY}")] and press_keep(e["yes"], x) == (OLD_BUTTON, True)
    # ... and one that is none any more, whatever it was when it was told: its own absence, which took the backup's lesson over, is cancelled as any other
    with exam_school(EVE, TEAM):
        i = told_planned(); becomes(i); token = tok(EVE, "cancel"); change_record(i, lambda r: r.pop("exams")); press(EVE, "cancel"); say(EVE, "The course is off"); assert press_yes(EVE) == (SENT_CANCEL, False) and absences.load(i)["cancelled"]["by"] == EVE
    with exam_school(EVE, TEAM):
        e, b = backed_up("exam"); swept(); j = absences.new(dict(teacher=EVE, dates=["2026-10-13"], periods=None, reason="Course", reason_text="", remarks="", reporting_officer=ROSA, lessons=[]), SCHOOL, HUGO, "planned", may_choose=True, links=exam_links())["id"]
        assert absences.load(b)["cancelled"]["by"] == "app" and "exams" not in absences.load(j); swept(); r = outs("planned")[-1]; assert json.loads(r["ref"]) == dict(id=j) and buttons_of(r)[1:] == [[dict(text="❌ Not needed: cancel", what="cancel", id=j)]]
        press(EVE, "cancel"); say(EVE, "The course is off"); assert press_yes(EVE) == (SENT_CANCEL, False) and absences.load(j)["cancelled"] and older(b) and press(EVE, "cancel") == (absences.CANCELLED, True)
    # not theirs at all: that comes first
    with exam_school(EVE, TEAM):
        e, b = backed_up("exam"); OB.queue("older", TEAM, "An older message", kind="made-up", buttons=[[dict(OLDER[0][0], id=b)]]); send(); assert press(TEAM, "cancel") == (absences.NOT_YOURS, True)

@t
def the_history_names_the_person_and_telegram():
    def each(f):
        """the entries of the four steps, taken by f, one school each -> [(who, as, what, text)]"""
        out = []
        for what in ("ack", "change", "cancel", "approve"):
            with school(SAM, MAYA, EVE, TEAM):
                i = told_ask() if what == "approve" else told_planned()
                if what in ("ack", "change"): give(i, K5, SAM); swept()
                at("09:30"); h = Since(); f(what, i); got = h.new(); assert len(got) == 1 and got[0][5] == i, (what, got); out.append(got[0])
        return out
    def here(what, i):
        name = dict(ack=SAM, change=SAM, cancel=EVE, approve=TEAM)[what]; press(name, what)
        if what in ("change", "cancel"): say(name, "zebra-why")
        if what == "cancel": press_yes(name)
    def page(what, i):
        if what == "ack": on_cover(SAM, i, K5, "acknowledge")
        if what == "change": on_cover(SAM, i, K5, "ask-change", dict(why="zebra-why"))
        if what == "cancel": call(EVE, "post", f"/api/relief/absences/{i}/cancel", dict(why="zebra-why"))
        if what == "approve": on_cover(TEAM, i, K5, "approve", dict(who=MAYA))
    old = dict(CHATS); CHATS.update({n: 987650000 + k for k, n in enumerate(CHATS)})        # chats that can be told from any other number
    try: a, b = each(here), each(page)
    finally: CHATS.update(old)
    assert [(x[0], x[1], x[3], x[4]) for x in a] == [(x[0], x[1], x[3], x[4]) for x in b] and {x[2] for x in a} == {"telegram"} and {x[2] for x in b} == {"code"}, (a, b)
    assert [x[4] for x in a] == [ENTRY + f"{SAM} acknowledged {ON_K5}", ENTRY + f"{SAM} asked to change {ON_K5}", ENTRY + "cancelled", ENTRY + f"{MAYA} approved for {ON_K5}"], a
    raw = "".join(open(os.path.join(history.DIR, f), encoding="utf-8").read() for f in os.listdir(history.DIR))
    for bad in ("zebra-why", "98765"): assert bad not in raw, bad

@t
def everything_is_done_before_the_press_is_answered_and_nothing_is_held():
    real, seen = tg.call, []
    def spy(method, params=None, **kw):
        seen.append((method, len(entries()), absences._LOCK.locked(), bot._pressing.locked(), bot._counting.locked())); return real(method, params, **kw)
    with school(SAM, MAYA, EVE, TEAM):
        told_ask(); j = told_planned(dates=["2026-10-16"])
        ASK, SAID, DONE = ["sendMessage", "answerCallbackQuery"], ["sendMessage"], ["answerCallbackQuery", "editMessageText"]
        for who_, what, line, want in ((TEAM, "approve", None, DONE), (MAYA, "ack", None, DONE), (MAYA, "change", "x", ASK + SAID + ["editMessageText"]), (EVE, "cancel", "x", ASK + SAID + DONE + ["editMessageText"])):
            swept(); n = len(entries()); del seen[:]
            with stand_in(tg, "call", spy):
                press(who_, what)
                if line: say(who_, line)
                if what == "cancel": assert [x[1] for x in seen] == [n] * 3; press_yes(who_)
            assert [x[0] for x in seen] == want and [x[1] for x in seen[-2:]] == [n + 1] * 2, (what, seen)
            assert not any(any(x[2:]) for x in seen), (what, seen)
        assert absences.load(j)["cancelled"]
    assert bot.TIMEOUT == 8

@t
def a_talk_that_is_over_is_like_no_talk():
    with school(EVE, SAM):
        i, key = told_relief(); j = told_planned(dates=["2026-10-16"])
        at("09:10"); press(SAM, "change"); at("09:25"); assert talks(), "fifteen minutes to the second"
        at("09:25:01"); was, h = (file_of(i), file_of(j)), Since()
        assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(NOT_READ, None)] and rows("talks") == [], "met, and deleted"
        press(SAM, "change"); at("09:45"); tg.PRACTICE_LOG.clear()
        say(SAM, "ABCD-EFGH", message_id=41); assert sent() == [(CHATS[SAM], BAD_CODE)] and deleted() == [(CHATS[SAM], 41)] and rows("talks") == [], "a code is a code again"
        press(EVE, "cancel"); at("10:30"); assert talk_to(EVE, lambda: say(EVE, "/cancel")) == [(NOT_READ, None)] and rows("talks") == []
        assert (file_of(i), file_of(j)) == was and h.new() == []
        at("10:31"); press(SAM, "change"); at("10:46"); assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(SENT_CHANGE, None)], "in its last second"
    with school(SAM):                                                                      # the button ran out between the press and the line
        i, key = told_relief(); press(SAM, "change"); button(tok(SAM, "change"), until=0); was = file_of(i)
        assert talk_to(SAM, lambda: say(SAM, "x")) == [(OLD_BUTTON, None)] and file_of(i) == was and rows("talks") == []
    with school(SAM, MAYA):                                                                # and the chat is another's by then
        i, key = told_relief(); press(SAM, "change"); was = file_of(i); kept_ = rows("talks")[0]; links.unlink(SAM); links.link(MAYA, CHATS[SAM], None)
        with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, ?, ?, ?)", (kept_["chat"], kept_["kind"], kept_["data"], kept_["until"]))
        assert talk_to(SAM, lambda: say(SAM, "x")) == [(NOT_YOURS_BUTTON, None)] and file_of(i) == was and rows("talks") == []

@t
def a_new_talk_replaces_the_old_one():
    with school(SAM, EVE):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); a = tok(SAM, "change"); give(i, K2, SAM); swept(); b = tok(SAM, "change"); assert a != b
        press_token(a); press_token(b); assert [(x[0], x[2]["ckey"], x[2]["token"]) for x in talks()] == [(CHATS[SAM], K2, b)], "one conversation a chat"
        assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(SENT_CHANGE, None)] and (state_of(i, K2), state_of(i, K5)) == ("change", "approved")
        assert edits()[-1][1] == under(b)["message_id"] and talk_to(SAM, lambda: say(SAM, "A meeting")) == [(NOT_READ, None)] and state_of(i, K5) == "approved"
        # pressed twice: asked twice, and one answer
        assert talk_to(SAM, lambda: (press_token(a), press_token(a))) == [(WHY_CHANGE, FORCE)] * 2 and len(talks()) == 1
        press(EVE, "cancel"); assert sorted(x[0] for x in talks()) == sorted((CHATS[SAM], CHATS[EVE])), "each chat its own"
        say(SAM, "Another meeting"); assert state_of(i, K5) == "change" and not absences.load(i)["cancelled"] and [x[0] for x in talks()] == [CHATS[EVE]]
    with school(SAM):                                                                      # acknowledged meanwhile: what is typed next is not the why
        i = absent(by=HUGO); give(i, K5, SAM); swept(); press(SAM, "change"); assert press(SAM, "ack")[0].startswith("✅") and rows("talks") == []
        assert talk_to(SAM, lambda: say(SAM, "Thanks")) == [(NOT_READ, None)] and state_of(i) == "acknowledged"
        give(i, K2, SAM); swept(); press(SAM, "change"); press_token([r["token"] for r in rows("buttons") if (r["what"], r["ckey"]) == ("ack", K5)][0]); assert [x[2]["ckey"] for x in talks()] == [K2], "another relief's conversation goes on"

@t
def a_talk_replaced_meanwhile_is_neither_acted_on_nor_ended():
    """a line or a press that had read the talk there was before: nothing is done, and the talk there is now goes on"""
    def with_old(old, f):
        kept_ = rows("talks")
        with stand_in(bot, "_talk", lambda chat: old): got = f()
        assert rows("talks") == kept_ and len(kept_) == 1; return got
    with school(SAM, EVE):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); a = tok(SAM, "change"); give(i, K2, SAM); swept(); b = tok(SAM, "change"); press_token(a); old = bot._talk(CHATS[SAM]); press_token(b); was, h = file_of(i), Since()
        for text in ("A meeting", "/cancel"): assert with_old(old, lambda: talk_to(SAM, lambda: say(SAM, text))) == [(NOT_READ, None)], text
        assert with_old(old, lambda: talk_to(SAM, lambda: say(SAM, "/help"))) == [(HELLO.format(name=SAM), None)] and file_of(i) == was and h.new() == [] and edits() == []
        assert with_old(old, lambda: talk_to(SAM, lambda: say(SAM, "ok"))) == [(WHY_CHANGE, FORCE)], "asked again: its id is not noted as the other's"
    with school(EVE):                                                                      # the reason changed, or the question was asked anew, between
        for anew in (lambda: say(EVE, "Another reason"), lambda: press(EVE, "cancel")):
            i = told_planned(dates=[f"2026-10-{13 if not outs('planned') else 16}"]); was, h = file_of(i), Since(); press(EVE, "cancel"); say(EVE, "The course is off"); x, e, old = sure(EVE), talk_of(EVE), bot._talk(CHATS[EVE]); anew()
            for part in ("yes", "key"): assert with_old(old, lambda: press_keep(e[part], x)) == (OLD_BUTTON, True), part
            assert with_old(old, lambda: talk_to(EVE, lambda: say(EVE, "A third"))) == [(NOT_READ, None)] and file_of(i) == was and h.new() == [] and edits() == []
            say(EVE, "/cancel")

@t
def cancel_and_the_other_commands_end_a_talk():
    with school(SAM, EVE):
        i, key = told_relief(); j = told_planned(dates=["2026-10-16"]); was, h = (file_of(i), file_of(j)), Since()
        for text in ("/cancel", " /cancel ", "/CANCEL", "/cancel@practice_bot", "/cancel it was a mistake"):
            press(SAM, "change"); assert talk_to(SAM, lambda: say(SAM, text)) == [(NOTHING, None)] and rows("talks") == [], text
        press(EVE, "cancel"); assert talk_to(EVE, lambda: say(EVE, "/cancel")) == [(NOTHING, None)] and rows("talks") == []
        assert talk_to(SAM, lambda: say(SAM, "/cancel")) == [(NOT_READ, None)], "with nothing to end"
        for text in ("/help", "/start", "/start hello there", "/HELP@practice_bot"):
            press(EVE, "cancel"); assert talk_to(EVE, lambda: say(EVE, text)) == [(HELLO.format(name=EVE), None)] and rows("talks") == [], text
        press(EVE, "cancel"); assert [x for x, b in talk_to(EVE, lambda: say(EVE, "/relief"))] == ["Hi Ms Evelyn Koh. Which day are you away?"] and [x[1] for x in talks()] == ["ask"], "asking for relief is another"
        assert (file_of(i), file_of(j)) == was and h.new() == []
        press(EVE, "cancel"); c = links.new_code(EVE)["code"]; assert talk_to(EVE, lambda: say(EVE, f"/start {c}"))[0] == (HELLO.format(name=EVE), None) and rows("talks") == [], "a link is a link"
        press(EVE, "cancel"); tg.PRACTICE_LOG.clear(); say(EVE, "/start ABCD-EFGH"); assert sent() == [(CHATS[EVE], BAD_CODE)] and rows("talks") == []
        press(SAM, "change"); c = links.new_code(HUGO)["code"]; tg.PRACTICE_LOG.clear(); hook(msg(f"/start {c}", CHATS[SAM])); assert links.name_of(CHATS[SAM]) == HUGO and rows("talks") == []
        press(EVE, "cancel"); assert talk_to(EVE, lambda: say(EVE, "/stop")) == [(STOPPED, None)] and rows("talks") == [] and EVE not in links.linked()
        assert (file_of(i), file_of(j)) == was

@t
def a_line_that_replies_to_another_message_acts_on_nothing():
    ids, real = [], tg.call
    def spy(method, params=None, **kw):
        r = real(method, params, **kw)
        if method == "sendMessage": ids.append((params["text"], r["result"]["message_id"]))
        return r
    with school(SAM, EVE), stand_in(tg, "call", spy):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); a = tok(SAM, "change"); give(i, K2, SAM); swept(); b = tok(SAM, "change"); was, h = file_of(i), Since(); del ids[:]
        press_token(a); press_token(b); (t1, q1), (t2, q2) = ids; assert t1 == t2 == WHY_CHANGE and q1 != q2 and talk_of(SAM)["question"] == q2, "the last question is the one"
        until = talks()[0][3]
        # to the older question (the other cover), to a message with a button, to nothing that can be told: nothing is done, and the same is asked again
        for n, k in enumerate((q1, under(a)["message_id"], under(b)["message_id"], 1)):
            del ids[:]; assert talk_to(SAM, lambda: reply_to(SAM, k, "A parent meeting")) == [(LAST_ONE, None), (WHY_CHANGE, FORCE)], n
            assert talk_of(SAM)["question"] == ids[-1][1] and (talk_of(SAM)["ckey"], talks()[0][3], len(talks())) == (K2, until, 1), "no new talk, and no longer"
        for odd in (dict(), dict(message_id=None), dict(message_id=str(talk_of(SAM)["question"])), dict(message_id=True), 7, "x", []):
            assert talk_to(SAM, lambda: say(SAM, "A parent meeting", reply_to_message=odd)) == [(LAST_ONE, None), (WHY_CHANGE, FORCE)], odd
        assert talk_to(SAM, lambda: say(SAM, "A parent meeting", external_reply=dict(origin=dict(type="user")))) == [(LAST_ONE, None), (WHY_CHANGE, FORCE)], "to a message of another chat"
        assert talk_to(SAM, lambda: reply_to(SAM, q2, "A parent meeting")) == [(LAST_ONE, None), (WHY_CHANGE, FORCE)], "the question as it was asked before"
        assert file_of(i) == was and h.new() == [] and edits() == [] and state_of(i, K5) == state_of(i, K2) == "approved", "neither"
        assert talk_to(SAM, lambda: reply_to(SAM, talk_of(SAM)["question"], "A parent meeting")) == [(SENT_CHANGE, None)], "the one asked last"
        assert (state_of(i, K2), state_of(i, K5)) == ("change", "approved") and [x[4] for x in h.new()] == [ENTRY + f"{SAM} asked to change 1C Science P3–P5 on Tue 13 Oct"]
        press_token(a); reply_to(SAM, 1, "/cancel"); assert rows("talks") == [], "a command is a command"
        press_token(a); assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(SENT_CHANGE, None)] and state_of(i, K5) == "change", "to nothing: the answer"
    # the cancel question after a change question: Sam's relief, and an absence planned for him
    with school(SAM, TEAM):
        i, key = told_relief(); j = absent(teacher=SAM, by=HUGO); swept(); was, h = (file_of(i), file_of(j)), Since(); del ids[:]
        with stand_in(tg, "call", spy): press(SAM, "change"); press(SAM, "cancel")
        (t1, q1), (t2, q2) = ids; assert (t1, t2) == (WHY_CHANGE, WHY_CANCEL) and [x[1] for x in talks()] == ["cancel"]
        assert talk_to(SAM, lambda: reply_to(SAM, q1, "A parent meeting")) == [(LAST_ONE, None), (WHY_CANCEL, keep_it(SAM))]
        assert (file_of(i), file_of(j)) == was and h.new() == [] and [x[1] for x in talks()] == ["cancel"], "neither changed nor cancelled"
        assert talk_to(SAM, lambda: reply_to(SAM, talk_of(SAM)["question"], "The course is off")) == [(SURE.format("Tue 13 Oct", "The course is off"), yes_or_keep(SAM))] and (file_of(i), file_of(j)) == was
        assert talk_to(SAM, lambda: reply_to(SAM, q2, "Another reason")) == [(LAST_ONE, None), (SURE.format("Tue 13 Oct", "The course is off"), yes_or_keep(SAM))], "to the question before: the reason shown stays"
        assert press_yes(SAM) == (SENT_CANCEL, False) and absences.load(j)["cancelled"]["why"] == "The course is off" and file_of(i) == was[0]
    with school(SAM, TEAM):                                                                # and the other way about
        i, key = told_relief(); j = absent(teacher=SAM, by=HUGO); swept(); was = (file_of(i), file_of(j)); del ids[:]
        with stand_in(tg, "call", spy): press(SAM, "cancel"); press(SAM, "change")
        assert talk_to(SAM, lambda: reply_to(SAM, ids[0][1], "The course is off")) == [(LAST_ONE, None), (WHY_CHANGE, FORCE)] and (file_of(i), file_of(j)) == was
    # another question asked while the first one is on its way: the first's id is not taken for the last one's
    with school(SAM):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); a = tok(SAM, "change"); give(i, K2, SAM); swept(); b = tok(SAM, "change"); nested = []; del ids[:]
        def slow(method, params=None, **kw):
            r = spy(method, params, **kw)
            if method == "sendMessage" and not nested: nested.append(1); hook(callback("b:" + b, under(b)))
            return r
        with stand_in(tg, "call", slow): hook(callback("b:" + a, under(a)))
        assert len(ids) == 2 and (talk_of(SAM)["ckey"], talk_of(SAM)["question"]) == (K2, ids[1][1]), (talk_of(SAM), ids)
    # a question whose id Telegram did not say: only a line that replies to nothing is the answer
    with school(SAM):
        i, key = told_relief(); was = file_of(i)
        for result in (None, True, {}, dict(message_id="7"), dict(message_id=None)):
            with stand_in(tg, "call", lambda method, params=None, **kw: dict(real(method, params, **kw), **({"result": result} if method == "sendMessage" else {}))):
                press(SAM, "change"); assert talk_of(SAM)["question"] is None
                assert talk_to(SAM, lambda: reply_to(SAM, 7, "A meeting")) == [(LAST_ONE, None), (WHY_CHANGE, FORCE)] and file_of(i) == was, result
        assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(SENT_CHANGE, None)]
    # asked again and not sent: the talk is as it was
    with school(SAM):
        i, key = told_relief(); press(SAM, "change"); was = talks()
        with stand_in(tg, "call", lambda method, params=None, **kw: dict(ok=False, result=None, kind="unsure", retry_after=None)): reply_to(SAM, 1, "A meeting"); say(SAM, "ok")
        assert talks() == was and state_of(i) == "approved"

@t
def an_acknowledgement_on_the_page_ends_a_waiting_change():
    with school(SAM, TEAM):
        i, key = told_relief(); at("09:10"); press(SAM, "change"); at("09:12"); on_cover(SAM, i, K5, "acknowledge"); was, h = file_of(i), Since(); at("09:14")
        assert talk_to(SAM, lambda: say(SAM, "Thanks for asking")) == [(ACKED, None)] and rows("talks") == [] and file_of(i) == was and h.new() == [], "what was typed is not the why"
        assert taken_off(SAM, "change", ACKED) and state_of(i) == "acknowledged" and absences.ACKED == ACKED
        assert talk_to(SAM, lambda: say(SAM, "Thanks")) == [(NOT_READ, None)]
    with school(SAM):                                                                      # kept in another zone: the moment counts
        i, key = told_relief(); at("09:10"); press(SAM, "change"); change_record(i, lambda r: [x.update(ack=dict(at="2026-10-12T01:12:00+00:00")) for x in r["lessons"] if x["key"] == K5])
        assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(ACKED, None)]
    for before in ("09:05", "09:10"):                                                      # acknowledged before the question was asked: they may still ask
        with school(SAM):
            i, key = told_relief(); at(before); on_cover(SAM, i, K5, "acknowledge"); at("09:10"); press(SAM, "change"); at("09:24")
            assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(SENT_CHANGE, None)] and state_of(i) == "change", before
    with school(SAM):                                                                      # the page's Acknowledge after a request to change made there: theirs after all
        i, key = told_relief(); at("09:10"); press(SAM, "change"); at("09:11"); on_cover(SAM, i, K5, "ask-change", dict(why="x")); at("09:12"); on_cover(SAM, i, K5, "acknowledge"); was = file_of(i)
        assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(ACKED, None)] and file_of(i) == was

@t
def keep_it_ends_the_cancel_question():
    with school(EVE, MAYA):
        i = told_planned(); was, h = file_of(i), Since(); at("09:10"); press(EVE, "cancel"); key, m = talk_of(EVE)["key"], question(EVE)
        assert press_keep(key, m, chat=CHATS[MAYA]) == (NOT_YOURS_BUTTON, True) and len(talks()) == 1, "another's press"
        tg.PRACTICE_LOG.clear(); assert press_keep(key, m) == (NOTHING, False) and rows("talks") == [] and file_of(i) == was and h.new() == []
        assert edits() == [(CHATS[EVE], m["message_id"], WHY_CANCEL + "\n\n" + NOTHING)] and "reply_markup" not in calls("editMessageText")[0] and sent() == [], "its buttons off; the absence's message keeps its own"
        assert press_keep(key, m) == (OLD_BUTTON, True) and len(edits()) == 1, "once"
        assert talk_to(EVE, lambda: say(EVE, "The course is off")) == [(NOT_READ, None)] and file_of(i) == was
        # asked anew: another button; the old one keeps nothing
        press(EVE, "cancel"); new = talk_of(EVE)["key"]; assert new != key and press_keep(key, m) == (OLD_BUTTON, True) and len(talks()) == 1
        # asked again (no answer in it): the same one, on either message
        say(EVE, "No"); assert talk_of(EVE)["key"] == new and press_keep(new, m) == (NOTHING, False) and rows("talks") == []
    late = dict(answered=lambda i: (say(EVE, "The course is off"), press_yes(EVE)), over=lambda i: at("09:25:01"), ended=lambda i: say(EVE, "/cancel"), helped=lambda i: say(EVE, "/help"))
    for how, f in late.items():
        with school(EVE, SAM):
            i = told_planned(); at("09:10"); press(EVE, "cancel"); key, m = talk_of(EVE)["key"], question(EVE); f(i); n, was, h = len(edits()), file_of(i), Since()
            got = press_keep(key, m); assert got == (OLD_BUTTON, True) and len(edits()) == n and file_of(i) == was and h.new() == [], (how, got)       # never "Nothing was changed."
            assert bool(absences.load(i)["cancelled"]) == (how == "answered")
    with school(EVE, SAM):                                                                 # another question in its place: that one goes on
        i, key_ = told_relief(); j = absent(teacher=SAM, by=HUGO); swept(); press(SAM, "cancel"); key, m = talk_of(SAM)["key"], question(SAM); press(SAM, "change")
        assert press_keep(key, m) == (OLD_BUTTON, True) and [x[1] for x in talks()] == ["change"] and edits() == []
    with school(EVE):                                                                      # nothing published, switched off, without relief
        i = told_planned(); press(EVE, "cancel"); key, m = talk_of(EVE)["key"], question(EVE)
        with record(EVE, off=True): assert press_keep(key, m) == (NOT_LINKED, True)
        with record(EVE, group="executive", extras=dict(relief=False, exams=None, admin=False)): assert press_keep(key, m) == (NOT_YOURS_BUTTON, True)
        with no_pub(): assert press_keep(key, m) == (NOTHING, False), "it changes nothing"
    with school(EVE):                                                                      # the question did not come: no talk, and its button keeps nothing
        i = told_planned(); real = tg.call
        with stand_in(tg, "call", lambda method, params=None, **kw: dict(real(method, params, **kw), ok=method != "sendMessage")): assert press(EVE, "cancel") == (WENT_WRONG, True)
        key = tok(EVE, "keep"); assert rows("talks") == [] and press_keep(key, under(tok(EVE, "cancel"))) == (OLD_BUTTON, True)
    for _ in range(3):                                                                     # pressed and typed in the same moment: whichever came first, it is kept
        with school(EVE):
            i = told_planned(); was = file_of(i); press(EVE, "cancel"); key, m = talk_of(EVE)["key"], question(EVE); h = Since()
            at_once(lambda: hook(callback("b:" + key, m)), lambda: say(EVE, "The course is off")); assert answers()[-1] == (NOTHING, False) and h.new() == [] and rows("talks") == [] and file_of(i) == was, answers()
    with school(EVE):                                                                      # pressed while the id of its question is being noted: it is that talk all the same
        for what in ("key", "yes"):
            i = told_planned(dates=["2026-10-13" if what == "key" else "2026-10-16"]); press(EVE, "cancel"); say(EVE, "The course is off"); x, e, t_ = sure(EVE), talk_of(EVE), bot._talk(CHATS[EVE])
            with tgdb.db() as c: c.execute("UPDATE talks SET data=?", (json.dumps(dict(e, question=e["question"] + 1)),))
            with stand_in(bot, "_talk", lambda chat: t_): assert press_keep(e[what], x) == ((NOTHING, False) if what == "key" else (SENT_CANCEL, False)) and rows("talks") == [], what
            assert bool(absences.load(i)["cancelled"]) == (what == "yes")
    with school(EVE, MAYA):                                                                # on the question that shows the reason, and on the one before
        for on in ("sure", "before"):
            i = told_planned(dates=["2026-10-13" if on == "sure" else "2026-10-16"]); was, h = file_of(i), Since(); press(EVE, "cancel"); before = question(EVE); say(EVE, "The course is off"); x, e = sure(EVE), talk_of(EVE); tg.PRACTICE_LOG.clear()
            m = x if on == "sure" else before; assert press_keep(e["key"], m, chat=CHATS[MAYA]) == (NOT_YOURS_BUTTON, True) and press_keep(e["key"], m) == (NOTHING, False)
            assert edits() == [(CHATS[EVE], m["message_id"], m["text"] + "\n\n" + NOTHING)] and rows("talks") == [] and file_of(i) == was and h.new() == [], on
            assert press_keep(e["yes"], x) == (OLD_BUTTON, True) and file_of(i) == was, "and then it cannot be cancelled by the other button"

@t
def a_word_that_is_no_reason_is_asked_again():
    listed = ("no", "n", "nope", "yes", "y", "ok", "okay", "thanks", "thank you", "cancel", "keep", "stop")
    shapes = [x for w in listed for x in (w, w.upper(), w.title(), f" {w}. ", f"“{w}”!", f"({w})", f"_{w}_", f"{w} 👍", f"...{w}?")] + ["thank  you", "Thank\nyou", "/no", "/keep"]
    more = ["keep it", "Keep it.", "No, thanks", "ok thanks!", "Yes, cancel it", "no no", "?", "👍", "...", "//", "@", "“”"]               # the button's own words, the same words together, and no word at all
    with school(SAM, EVE):
        i, key = told_relief(); j = told_planned(dates=["2026-10-16"]); press(SAM, "change"); press(EVE, "cancel"); was, h = (file_of(i), file_of(j)), Since()
        for name, want in ((SAM, (WHY_CHANGE, FORCE)), (EVE, (WHY_CANCEL, keep_it(EVE)))):
            for text in shapes + more: assert talk_to(name, lambda: say(name, text)) == [want], (name, text)
        assert (file_of(i), file_of(j)) == was and h.new() == [] and edits() == [] and len(talks()) == 2
        say(SAM, "No, I have a meeting"); say(EVE, "Stop: the course is off"); press_yes(EVE); assert covered(i, K5)[2]["change"]["why"] == "No, I have a meeting" and absences.load(j)["cancelled"]["why"] == "Stop: the course is off"
    for why in ("Nobody is away", "Not needed", "Course off", "It rained", "Okayed by HOD", "I am well", "不用了", "nooo"):       # a word of its own is a reason
        with school(EVE): i = told_planned(); press(EVE, "cancel"); say(EVE, why); press_yes(EVE); assert (absences.load(i)["cancelled"] or {}).get("why") == why, why

@t
def a_typed_line_never_cancels():
    with school(EVE, MAYA):
        i = told_planned(dates=["2026-10-13", "2026-10-14"]); was, h = file_of(i), Since(); at("09:10"); press(EVE, "cancel"); key = talk_of(EVE)["key"]; yes = []
        # whatever it is, it is shown, and nothing more; the latest is the reason
        for n, why in enumerate(("Don't cancel please", "No, don't cancel", "Don’t cancel", "Never mind", "wait", "Not now", "cancel it now!!!", "Yes cancel it please", "x" * 200, "{why} {days} {0} %s", "<b>x</b>", "不用了", "/ill", "ABCD-EFGH", "Course postponed")):
            at(f"09:{10 + n}"); assert talk_to(EVE, lambda: say(EVE, f"  {why} ")) == [("Cancel Tue 13 Oct, Wed 14 Oct? Your reason: " + why, yes_or_keep(EVE))], why
            d = talk_of(EVE); assert (d["why"], d["key"], len(talks())) == (why, key, 1) and talks()[0][3] == datetime.datetime.fromisoformat(clock.now).timestamp() + 900, why
            yes.append((d["yes"], sure(EVE)))
        assert file_of(i) == was and h.new() == [] and edits() == [] and deleted() == [] and len({t_ for t_, m in yes}) == len(yes)
        # no reason in it, or a reply to something else: the same is asked again, with the same buttons and the same reason, and no longer
        last, until = talk_of(EVE), talks()[0][3]; at("09:30"); markup = yes_or_keep(EVE); again = ("Cancel Tue 13 Oct, Wed 14 Oct? Your reason: Course postponed", markup)
        for text in ("yes", "Yes!", "OK", "no", "Keep it", "cancel", "", "  ", "x" * 201, None, "👍"): assert talk_to(EVE, lambda: say(EVE, text)) == [again], text
        assert talk_to(EVE, lambda: reply_to(EVE, yes[0][1]["message_id"], "Another reason")) == [(LAST_ONE, None), again]
        assert dict(talk_of(EVE), question=0) == dict(last, question=0) and talks()[0][3] == until and file_of(i) == was and h.new() == []
        # a Yes that showed another reason; another's press; the cancel button's own token under it
        for token, m in yes[:-1]: assert press_keep(token, m) == (OLD_BUTTON, True)
        assert press_yes(EVE, chat=CHATS[MAYA]) == (NOT_YOURS_BUTTON, True) and file_of(i) == was and h.new() == [] and edits() == [] and dict(talk_of(EVE), question=0) == dict(last, question=0)
        assert press_yes(EVE) == (SENT_CANCEL, False) and absences.load(i)["cancelled"] == dict(at=clock.now, by=EVE, why="Course postponed") and len(h.new()) == 1, "its own, with the reason it shows"
    for text, want in (("/cancel", NOTHING), ("/help", HELLO.format(name=EVE)), ("/start", HELLO.format(name=EVE)), ("/relief", "Hi Ms Evelyn Koh. Which day are you away?")):       # a command ends it, and the Yes with it
        with school(EVE):
            i = told_planned(); was = file_of(i); press(EVE, "cancel"); say(EVE, "x"); token, m = talk_of(EVE)["yes"], sure(EVE)
            assert [x for x, b in talk_to(EVE, lambda: say(EVE, text))] == [want] and press_keep(token, m) == (OLD_BUTTON, True) and file_of(i) == was, text
    with school(EVE, SAM):                                                                 # another question in its place
        i, key_ = told_relief(); j = absent(teacher=SAM, by=HUGO); swept(); was = file_of(j); press(SAM, "cancel"); say(SAM, "x"); token, m = talk_of(SAM)["yes"], sure(SAM); press(SAM, "change")
        assert press_keep(token, m) == (OLD_BUTTON, True) and file_of(j) == was and [x[1] for x in talks()] == ["change"]
        press(SAM, "cancel"); assert "yes" not in talk_of(SAM) and press_keep(token, m) == (OLD_BUTTON, True) and file_of(j) == was, "asked anew: from the beginning"

@t
def the_second_press_is_judged_when_it_is_pressed():
    def ready(*more):
        i = told_planned(); at("09:10"); press(EVE, "cancel"); at("09:12"); say(EVE, "The course is off"); tg.PRACTICE_LOG.clear()
        return i, file_of(i), Since(), talk_of(EVE)["yes"], sure(EVE)
    with school(EVE, MAYA):
        i, was, h, token, m = ready(); kept_ = talks()
        with record(EVE, off=True): assert press_keep(token, m) == (NOT_LINKED, True)
        with record(EVE, group="executive", extras=dict(relief=False, exams=None, admin=False)): assert press_keep(token, m) == (NOT_YOURS_BUTTON, True)
        with broken_accounts(): links.tries.fails.clear(); assert press_keep(token, m) == (NOT_LINKED, True)
        with no_pub(RP.fake_pub([dict(name=HUGO)])): links.tries.fails.clear(); assert press_keep(token, m) == (NOT_LINKED, True)
        with no_pub(): assert press_keep(token, m) == (WB.NO_PUB, True), "a publish swaps folders: pressed again, it works"
        assert press_keep(token, m, chat=CHATS[MAYA]) == (NOT_YOURS_BUTTON, True)
        assert talks() == kept_ and file_of(i) == was and h.new() == [] and edits() == []
        assert press_keep(token, m) == (SENT_CANCEL, False) and absences.load(i)["cancelled"] and len(h.new()) == 1
    for hm, want in (("09:27", (SENT_CANCEL, False)), ("09:27:01", (OLD_BUTTON, True))):     # fifteen minutes from that question, to the second
        with school(EVE):
            i, was, h, token, m = ready(); at(hm); assert press_keep(token, m) == want and bool(absences.load(i)["cancelled"]) == (hm == "09:27") and (len(edits()) == 2) == (hm == "09:27"), hm
    with school(EVE):                                                                      # something that fails: nothing is cancelled, the messages stay as they are
        i, was, h, token, m = ready()
        with stand_in(absences, "cancel", lambda *a, **k: 1 / 0): assert press_keep(token, m) == (WENT_WRONG, True)
        assert file_of(i) == was and h.new() == [] and edits() == [] and rows("talks") == [] and press_keep(token, m) == (OLD_BUTTON, True), "one press is one try"
    with school(EVE, MAYA):                                                                # unlinked, and the chat another's
        i, was, h, token, m = ready(); kept_ = rows("talks")[0]; links.unlink(EVE); links.link(MAYA, CHATS[EVE], None)
        with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, ?, ?, ?)", (kept_["chat"], kept_["kind"], kept_["data"], kept_["until"]))
        assert press_keep(token, m) == (NOT_YOURS_BUTTON, True) and talk_to(EVE, lambda: say(EVE, "x")) == [(NOT_YOURS_BUTTON, None)] and file_of(i) == was
    with school(EVE):                                                                      # the question did not come: no talk
        i = told_planned(); was, real = file_of(i), tg.call; press(EVE, "cancel")
        with stand_in(tg, "call", lambda method, params=None, **kw: dict(real(method, params, **kw), ok=method != "sendMessage")): said_ = talk_to(EVE, lambda: say(EVE, "The course is off"))
        assert [x for x, b in said_] == [SURE.format("Tue 13 Oct", "The course is off"), WENT_WRONG] and rows("talks") == [] and press_keep(tok(EVE, "cancel-yes"), under(tok(EVE, "cancel"))) == (OLD_BUTTON, True) and file_of(i) == was
    with school(EVE):                                                                      # what is not a sentence of the app's is never shown, nor kept
        i, was, h, token, m = ready(); say(EVE, "a \ud800"); assert press_yes(EVE) == (WENT_WRONG, True) and file_of(i) == was and h.new() == []

@t
def a_code_shaped_why_is_the_answer():
    for why in ("Sent them", "ABCD-EFGH", access.staff_code(SAM), "/ill", "/starting late", "<b>x</b>", "“quoted”", "No relief is needed", "Keep the class with me", "7"):
        with school(SAM):
            i, key = told_relief(); press(SAM, "change"); tg.PRACTICE_LOG.clear()
            assert talk_to(SAM, lambda: say(SAM, why)) == [(SENT_CHANGE, None)] and covered(i, K5)[2]["change"]["why"] == why and deleted() == [] and not links.tries.fails.get(f"tg:{CHATS[SAM]}"), why
    with school(EVE):
        i = told_planned(); c = links.new_code(SAM)["code"]; press(EVE, "cancel"); say(EVE, c); assert press_yes(EVE) == (SENT_CANCEL, False) and absences.load(i)["cancelled"]["why"] == c and links.name_of(CHATS[EVE]) == EVE and links.chat_of(SAM) is None, "not even a link code"
    with school(SAM):                                                                      # over the limit (wrong codes before): nothing at all
        i, key = told_relief(); was = file_of(i)
        for k in range(5): say(SAM, "ABCD-EFGH")
        with tgdb.db() as c: c.execute("INSERT INTO talks(chat, kind, data, until) VALUES (?, 'change', ?, 9e12)", (CHATS[SAM], json.dumps(dict(id=i, ckey=K5, absent=EVE, token=tok(SAM, "change"), key="k", question=1, message=dict(id=1, text="x")))))
        tg.PRACTICE_LOG.clear(); say(SAM, "A meeting"); assert tg.PRACTICE_LOG == [] and file_of(i) == was

@t
def a_blank_or_long_why_is_asked_again():
    with school(SAM, EVE):
        i, key = told_relief(); j = told_planned(dates=["2026-10-16"]); was, h = (file_of(i), file_of(j)), Since(); press(SAM, "change"); press(EVE, "cancel")
        less = lambda: [(c, k, dict(d, question=None), u) for c, k, d, u in talks()]; kept_ = less()
        for name, asked_, markup in ((SAM, WHY_CHANGE, FORCE), (EVE, WHY_CANCEL, keep_it(EVE))):
            for text in ("", "   ", "\n\t ", "x" * 201, "x " * 101, "é" * 4096, None, 7, ["x"]):
                was_ = talk_of(name)["question"]; assert talk_to(name, lambda: say(name, text)) == [(asked_, markup)] and talk_of(name)["question"] > was_, (name, text)
        m = msg("x", CHATS[SAM]); del m["message"]["text"]; m["message"].update(photo=[dict(file_id="f")], caption="A meeting"); assert talk_to(SAM, lambda: hook(m)) == [(WHY_CHANGE, FORCE)], "a photo is not a line"
        assert (file_of(i), file_of(j)) == was and h.new() == [] and less() == kept_, "the same conversation, its time not longer"
        say(SAM, " " + "x" * 200 + " "); say(EVE, "x"); press_yes(EVE); assert covered(i, K5)[2]["change"]["why"] == "x" * 200 and absences.load(j)["cancelled"]["why"] == "x"
        assert "\n" not in covered(i, K5)[2]["change"]["why"]
    with school(SAM, TEAM):                                                                # a line of their own never reads as one of the app's to the team
        i, key = told_relief(); press(SAM, "change"); say(SAM, "A meeting”\nNew pick: Mx Made Up\r\n x"); assert covered(i, K5)[2]["change"]["why"] == "A meeting” New pick: Mx Made Up x"

@t
def two_presses_at_once_save_once():
    for _ in range(3):
        with school(SAM, MAYA, TEAM, LEE):
            i, key = told_relief(); token, m, h = tok(SAM, "ack"), under(tok(SAM, "ack")), Since(); saves, real = [], absences._save
            with stand_in(absences, "_save", lambda r: (saves.append(1), real(r))):
                at_once(*[lambda: hook(callback("b:" + token, m))] * 6)
            assert len(saves) == 1 and len(h.new()) == 1 and answers() == [("✅ Acknowledged 09:00.", False)] * 6 and [x["what"] for x in covered(i, K5)[2]["history"]].count("acknowledged") == 1, saves
        with school(SAM, MAYA, TEAM, LEE):                                                 # each of the team has a button of their own
            i = told_ask(); h, saves = Since(), []; both = [(tok(n, "approve"), under(tok(n, "approve"))) for n in (TEAM, LEE)]
            with stand_in(absences, "_save", lambda r: (saves.append(1), real(r))):
                at_once(*[lambda b=b: hook(callback("b:" + b[0], b[1])) for b in both * 3])
            got = h.new(); assert len(saves) == 1 and len(got) == 1 and got[0][0] in (TEAM, LEE) and covered(i, K5)[2]["approved"]["by"] == got[0][0], got
            assert sorted(answers()) == sorted([("✅ Approved: Ms Maya Lee, 09:10.", False)] + [(CV.NOT_WAITING, True)] * 5), answers()
        with school(SAM, EVE):                                                             # two lines at once: one is the why
            i, key = told_relief(); j = told_planned(dates=["2026-10-16"]); press(SAM, "change"); press(EVE, "cancel"); h, saves = Since(), []; tg.PRACTICE_LOG.clear()
            with stand_in(absences, "_save", lambda r: (saves.append(1), real(r))), stand_in(WB, "_soon", lambda **kw: True):
                at_once(*[lambda k=k: say(SAM, f"Why {k}") for k in range(3)], *[lambda k=k: say(EVE, f"Why {k}") for k in range(3)])
            assert len(saves) == 1 and [x[3] for x in h.new()] == ["asked to change"] and [x[0] for x in talks()] == [CHATS[EVE]] and not absences.load(j)["cancelled"]
            assert sorted(sent(CHATS[SAM])) == sorted([(CHATS[SAM], SENT_CHANGE)] + [(CHATS[SAM], NOT_READ)] * 2), sent()
            mine = [x for c, x in sent(CHATS[EVE])]; assert len(mine) == 3 and all(x == NOT_READ or re.fullmatch(r"Cancel Fri 16 Oct\? Your reason: Why [012]", x) for x in mine), mine
            # Yes pressed at once, again and again: one cancel, one entry
            x, e = sure(EVE), talk_of(EVE); saves.clear(); tg.PRACTICE_LOG.clear()
            with stand_in(absences, "_save", lambda r: (saves.append(1), real(r))): at_once(*[lambda: hook(callback("b:" + e["yes"], x))] * 6)
            assert len(saves) == 1 and [(y[0], y[3]) for y in h.new()] == [(EVE, "cancelled")] and sorted(answers()) == sorted([(SENT_CANCEL, False)] + [(OLD_BUTTON, True)] * 5) and absences.load(j)["cancelled"]["why"] == e["why"], answers()
        with school(EVE):                                                                  # Yes and Keep it at once: one of them
            i = told_planned(); press(EVE, "cancel"); say(EVE, "x"); x, e, h = sure(EVE), talk_of(EVE), Since()
            at_once(lambda: hook(callback("b:" + e["yes"], x)), lambda: hook(callback("b:" + e["key"], x))); gone = bool(absences.load(i)["cancelled"])
            assert sorted(answers()[-2:]) == sorted([(SENT_CANCEL, False) if gone else (NOTHING, False), (OLD_BUTTON, True)]) and len(h.new()) == gone and rows("talks") == [], answers()
    # one at a time: another's press, and a typed line, wait until the one that is going is done
    with school(SAM, EVE, MAYA):
        i, key = told_relief(); j = told_planned(dates=["2026-10-16"]); give(i, K2, MAYA); swept(); press(MAYA, "change"); inside, go, real_once = threading.Event(), threading.Event(), CV.acknowledge_once
        def slow(*a, **k): inside.set(); assert go.wait(10) and bot._pressing.locked(); return real_once(*a, **k)
        with stand_in(CV, "acknowledge_once", slow):
            ups = [callback("b:" + tok(n, what), under(tok(n, what))) for n, what in ((SAM, "ack"), (EVE, "cancel"))] + [msg("A meeting", CHATS[MAYA])]
            ths = [threading.Thread(target=hook, args=(u,)) for u in ups]
            ths[0].start(); assert inside.wait(10); [x.start() for x in ths[1:]]; time.sleep(0.3)
            assert [x[0] for x in talks()] == [CHATS[MAYA]] and state_of(i, K2) == "approved", "neither has begun"
            go.set(); [x.join(10) for x in ths]
        assert [x[0] for x in talks()] == [CHATS[EVE]] and state_of(i, K2) == "change" and state_of(i) == "acknowledged"
    # on the page and on Telegram in the same moment: whoever is second saves and writes down nothing
    for first in ("page", "here"):
        with school(SAM):
            i, key = told_relief(); h, real_once, done = Since(), CV.acknowledge_once, []
            def once(*a, **k):
                if not done:
                    done.append(1)
                    on_cover(SAM, i, K5, "acknowledge") if first == "page" else hook(callback("b:" + tok(SAM, "ack"), under(tok(SAM, "ack"))))
                return real_once(*a, **k)
            if first == "page":
                with stand_in(bot._cover, "acknowledge_once", once): assert press(SAM, "ack") == ("✅ Acknowledged 09:00.", False)
            else:
                with stand_in(WB._cover, "acknowledge_once", once): assert on_cover(SAM, i, K5, "acknowledge")["state"] == "acknowledged"
            got = h.new(); assert len(got) == 1 and got[0][2] == ("code" if first == "page" else "telegram"), (first, got)

@t
def a_takeover_moves_the_cover_and_the_button_finds_it():
    with school(SAM, TEAM):
        i, key = told_relief(); j = moved_to(i); h = Since(); at("09:30")
        assert press(SAM, "ack") == ("✅ Acknowledged 09:30.", False) and state_of(j) == "acknowledged" and h.new() == [by_telegram(SAM, "relief acknowledged", f"{SAM} acknowledged {ON_K5}", j)]
    with school(SAM, TEAM):                                                                # taken over between the press and the line; the new pick is asked for where it is now
        i, key = told_relief(); press(SAM, "change"); j = moved_to(i); h, kw = Since(), []
        with stand_in(FL, "soon", lambda **k: kw.append(k)): say(SAM, "A meeting")
        assert state_of(j) == "change" and kw == [dict(ids=[j], force=True)] and [x[5] for x in h.new()] == [j]
    with school(SAM, MAYA, TEAM):
        i = told_ask(); j = moved_to(i); h = Since(); at("09:30"); assert press(TEAM, "approve") == ("✅ Approved: Ms Maya Lee, 09:30.", False) and covered(j, K5)[2]["relief"] == MAYA and [x[5] for x in h.new()] == [j]
    with school(SAM):                                                                      # the old record gone altogether
        i, key = told_relief(); j = moved_to(i); os.remove(absences._path(i)); assert press(SAM, "ack")[0].startswith("✅") and state_of(j) == "acknowledged"
    with school(SAM):                                                                      # taken over, and that absence cancelled
        i, key = told_relief(); j = moved_to(i); absences.cancel(j, "x", EVE); was = file_of(j); assert press(SAM, "ack") == (absences.CHANGED, True) and file_of(j) == was
    with school(SAM):                                                                      # taken over, and given to another there
        i, key = told_relief(); j = moved_to(i); give(j, K5, MAYA); was = file_of(j); assert press(SAM, "ack") == (CV.NOT_YOURS_COVER, True) and file_of(j) == was
    with school(SAM, BUSY):                                                                # the same key in another teacher's absence is not it
        i, key = told_relief(); j = moved_to(i); change_record(j, lambda r: r.update(teacher=BUSY)); was = file_of(j); assert press(SAM, "ack") == (absences.CHANGED, True) and file_of(j) == was
    with school(SAM):                                                                      # two absences with that lesson: the one whose cover is approved
        i, key = told_relief(); j = moved_to(i); x = json.loads(json.dumps(covered(j, K5)[1])); x.update(CV.OPEN)
        for k, day in (("0000aa", 11), ("ffffaa", 13)): absences._save(dict(absences.load(j), id=k, lessons=[dict(x, needed=False)], at=f"2026-10-{day}T09:00:00+08:00"))
        assert press(SAM, "ack")[0].startswith("✅") and state_of(j) == "acknowledged"
    with school(SAM):                                                                      # a button with nothing to find it by
        i, key = told_relief(); moved_to(i)
        for extra in (None, "null", "[]", '"x"', "{}"): button(tok(SAM, "ack"), extra=extra); assert press(SAM, "ack") == (absences.CHANGED, True), extra
    with exam_school(SAM, EVE, TEAM):                                                      # as the app does it: an exam's backup taken over by her own absence
        exam("5A", name=EXAM2, duties=[(EVE, 630, 690)]); RL.sync_all(SCHOOL, TERM, LS.today()); b, = [r["id"] for r in absences.all_records() if r.get("exams")]
        give(b, K5, SAM); swept(); d = dict(teacher=EVE, dates=["2026-10-13"], periods=None, reason="Medical", reason_text="", remarks="", reporting_officer=ROSA, lessons=[])
        j = absences.new(d, SCHOOL, EVE, "asked", links=exam_links())["id"]; assert absences.load(b)["cancelled"]["by"] == "app"
        assert press(SAM, "ack")[0].startswith("✅") and state_of(j) == "acknowledged"

@t
def a_failed_edit_or_question_never_undoes_the_press():
    for kind in ("refused", "network", "unsure", "blocked", "slow"):
        real = tg.call
        def failing_(*methods):
            def f(method, params=None, **kw):
                r = real(method, params, **kw)
                return dict(ok=False, result=None, kind=kind, retry_after=5) if method in methods else r
            return f
        with school(SAM, EVE, TEAM):
            i, key = told_relief(); at("09:46"); h = Since()
            with stand_in(tg, "call", failing_("editMessageText", "answerCallbackQuery")): assert press(SAM, "ack") == ("✅ Acknowledged 09:46.", False)
            assert state_of(i) == "acknowledged" and len(h.new()) == 1 and links.chat_of(SAM) == CHATS[SAM], kind
            give(i, K2, SAM); swept()
            with stand_in(tg, "call", failing_("sendMessage")): got = press(SAM, "change")       # the question may not have come: what is typed next is not taken for the why
            assert got == (WENT_WRONG, True) and rows("talks") == [] and talk_to(SAM, lambda: say(SAM, "hello")) == [(NOT_READ, None)] and state_of(i, K2) == "approved", kind
            press(SAM, "change"); h.new()
            with stand_in(tg, "call", failing_("sendMessage", "editMessageText")): say(SAM, "A meeting")
            assert state_of(i, K2) == "change" and len(h.new()) == 1 and rows("talks") == [], kind
    with school(SAM):                                                                      # a message too old for Telegram to give its text: its buttons go
        i, key = told_relief(); m = under(tok(SAM, "ack")); tg.PRACTICE_LOG.clear()
        for old in (dict(message_id=m["message_id"], chat=m["chat"], date=0), dict(m, text=None), dict(m, text=7)):
            tg.PRACTICE_LOG.clear(); hook(callback("b:" + tok(SAM, "ack"), old)); assert answers() == [("✅ Acknowledged 09:00.", False)] and edits() == [] and calls("editMessageReplyMarkup") == [dict(chat_id=CHATS[SAM], message_id=m["message_id"])]
        for odd in (None, "7", True, 1.5): tg.PRACTICE_LOG.clear(); hook(callback("b:" + tok(SAM, "ack"), dict(m, message_id=odd))); assert [x for x, p in tg.PRACTICE_LOG] == ["answerCallbackQuery"], odd
    with school(SAM):                                                                      # a long one is still one Telegram takes
        i, key = told_relief(); m = dict(under(tok(SAM, "ack")), text="x" * 4096); hook(callback("b:" + tok(SAM, "ack"), m)); x = edits()[-1][2]; assert len(x) == 4096 and x.endswith("xxx\n\n✅ Acknowledged 09:00.")

@t
def a_press_is_answered_whatever_happens():
    def boom(*a, **k): raise RuntimeError(f"{SAM} a private line")
    def odd(*a, **k): json.loads("{ not json")                                             # a ValueError that is no sentence of the app's
    with school(SAM, MAYA, EVE, TEAM):
        i = told_ask(); j = told_planned(dates=["2026-10-16"]); was, h = (file_of(i), file_of(j)), Since(); token = tok(SAM, "ack"); m = under(token)
        for f in (boom, odd):
            for module, name in ((CV, "acknowledge_once"), (absences, "load"), (store, "published"), (tgdb, "db"), (links, "person"), (links, "rights_named"), (absences, "_LOCK")):
                with stand_in(module, name, f): n = len(answers()); handled(callback("b:" + token, m)); assert answers()[n:] == [(WENT_WRONG, True)], name
            with stand_in(CV, "approve", f): assert press(TEAM, "approve") == (WENT_WRONG, True)
            press(EVE, "cancel")
            with stand_in(absences, "_editable", f): assert talk_to(EVE, lambda: say(EVE, "x")) == [(WENT_WRONG, None)] and rows("talks") == []
            press(EVE, "cancel"); say(EVE, "x"); x, e = sure(EVE), talk_of(EVE)
            with stand_in(absences, "cancel", f): assert press_keep(e["yes"], x) == (WENT_WRONG, True) and rows("talks") == []
        def long(*a, **k): raise ValueError("x" * 300)
        assert edits() == [], "the generic sentence leaves every message as it is"
        with stand_in(CV, "approve", long): assert press(TEAM, "approve") == ("x" * 200, True) and taken_off(TEAM, "approve", "x" * 300), "what Telegram takes of an answer"
        assert (file_of(i), file_of(j)) == was and h.new() == []
        for bad in ("{ not json", "[]", "null", "7"):
            with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, 'change', ?, 9e12)", (CHATS[SAM], bad))
            assert talk_to(SAM, lambda: say(SAM, "x")) == [(NOT_READ, None)] and rows("talks") == [], "a conversation that cannot be read is none"
        with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, 'change', '{}', 9e12)", (CHATS[SAM],))
        assert talk_to(SAM, lambda: say(SAM, "x")) == [(WENT_WRONG, None)] and rows("talks") == []
        for data in ("{}", "{ not json"):
            with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, 'made-up', ?, 9e12)", (CHATS[SAM], data))
            assert talk_to(SAM, lambda: say(SAM, "x")) == [(NOT_READ, None)] and len(rows("talks")) == 1, "one of a kind not known here is left alone"
        # the save happened: what follows it never turns the answer
        with stand_in(WB, "_tell_soon", boom), stand_in(WB, "_soon", boom): assert press(TEAM, "approve")[0].startswith("✅ Approved")
        assert len(h.new()) == 1
        for q_ in (dict(), dict(id=7), dict(id=""), dict(id=None), dict(id=["x"])):           # nothing to answer it by: done all the same
            with tgdb.db() as c: c.execute("DELETE FROM talks")
            u = callback("b:" + tok(EVE, "cancel"), under(tok(EVE, "cancel"))); del u["callback_query"]["id"]; u["callback_query"].update(q_)
            n = len(answers()); assert handled(u) is None and len(answers()) == n and len(rows("talks")) == 1, q_
        for u in (dict(callback_query=7), dict(callback_query=[]), dict(callback_query={}), dict(callback_query=dict(message=None)), dict(callback_query=dict(message=dict(chat=[]))),
                  dict(callback_query=dict(message=7, data="b:" + "x" * 16)), dict(callback_query=dict(id="q", data="b:" + "x" * 16, message=dict(chat=dict(id=CHATS[SAM], type="private"))))): assert handled(u) is None, u
        with stand_in(tg, "call", boom): assert handled(callback("b:" + token, m)) is None, "handle never raises"
        assert not bot._pressing.locked() and not absences._LOCK.locked()

@t
def nothing_private_is_logged_by_a_press():
    h, root = Grab(), logging.getLogger(); old = root.level; root.addHandler(h); KINDS.addHandler(h); root.setLevel(logging.DEBUG)
    real = tg.call
    def boom(*a, **k): raise LookupError(f"{SAM} {EVE} zebra-why 987654 {K5}")
    def failing_(method, params=None, **kw): return tg._fail("refused") if method != "sendMessage" else real(method, params, **kw)
    tokens = []
    try:
        with school(SAM, MAYA, EVE, TEAM):
            i = told_ask(); j = told_planned(dates=["2026-10-16"]); tokens += [r["token"] for r in rows("buttons")]
            with stand_in(tg, "call", failing_):
                for name, what in ((SAM, "ack"), (SAM, "change"), (TEAM, "approve")): hook(callback("b:" + tok(name, what), under(tok(name, what))))
                say(SAM, "zebra-why")
            hook(callback("b:" + tokens[0], under(tokens[0]), chat=987654)); hook(callback("b:" + tokens[0], under(tokens[0]), chat=CHATS[MAYA]))
            with stand_in(absences, "cancel", boom): press(EVE, "cancel"); say(EVE, "zebra-why"); press_yes(EVE)
            with stand_in(absences, "_may_change", boom): press(EVE, "cancel")
            with stand_in(links, "person", boom): press(SAM, "ack")
            with stand_in(WB, "_noted", boom): press(EVE, "cancel"); say(EVE, "zebra-why"); tokens.append(talk_of(EVE)["yes"]); press_yes(EVE)
            assert absences.load(j)["cancelled"]
        mine = "\n".join(r.getMessage() for r in h.records if r.name.startswith("relief"))
        assert "LookupError" in mine and "refused" in mine, mine
        everything = "\n".join(r.getMessage() + str(r.exc_info or "") + str(r.args or "") for r in h.records)
        for bad in [SAM, EVE, MAYA, TEAM, "Evelyn", "zebra", "987654", K5, "Acknowledged", "Say why", tg.hook_secret() or "x" * 64, *tokens, *(str(c) for c in CHATS.values())]:
            assert bad not in everything, bad
    finally: root.removeHandler(h); KINDS.removeHandler(h); root.setLevel(old)

@t
def a_press_is_acted_on_once():
    with school(SAM, EVE, TEAM):
        i, key = told_relief(); u = callback("b:" + tok(SAM, "ack"), under(tok(SAM, "ack"))); h = Since()
        for _ in range(3): assert hook(u).status_code == 200
        assert len(answers()) == 1 and len(h.new()) == 1 and hook(u, secret="x").status_code == 403
        give(i, K2, SAM); swept(); press(SAM, "change"); line = msg("A meeting", CHATS[SAM])
        for _ in range(3): hook(line)
        assert state_of(i, K2) == "change" and [x[3] for x in h.new()] == ["asked to change"]
        # a token is a person's own, never another message's
        assert len({r["token"] for r in rows("buttons")}) == len(rows("buttons")) and all(re.fullmatch(r"[A-Za-z0-9_-]{16}", r["token"]) for r in rows("buttons"))

@t
def the_page_still_answers_as_it_did():
    with school(SAM, TEAM):
        i, key = told_relief(); at("09:20"); a = on_cover(SAM, i, K5, "acknowledge"); b = on_cover(SAM, i, K5, "acknowledge"); assert a == b and a["state"] == "acknowledged" and a["ack"] == dict(at="2026-10-12T09:20:00+08:00")
    assert set(WB.STEPS) == {"ack", "change", "cancel", "approve"}, "one row for both ways"
    with school():
        i = absent(by=HUGO); give(i, K5, SAM); r, first = CV.acknowledge_once(i, K5, SAM); assert first is True and r == absences.load(i)
        was = file_of(i); r, first = CV.acknowledge_once(i, K5, SAM); assert first is False and r == absences.load(i) and file_of(i) == was and CV.acknowledge(i, K5, SAM) == r

# ---- Task 6: Remind, the not-acknowledged report and all clear ----
import importlib  # noqa: E402
from relief import report as RE  # noqa: E402

D13 = "2026-10-13"
TODAY_BUTTON = [dict(text="Open relief today", url=BASE + "/relief#today")]
SAM_LINE, MAYA_LINE = "\n• Mr Sam Tan · 1A, 1B Science (G2) P6–P7 · starts 10:30 · ", "\n• Ms Maya Lee · 1C Science P3–P5 · starts 09:00 · "
STARTED, SAM_STARTED, MAYA_STARTED = "\nStarted without acknowledgement:", "\n• Mr Sam Tan · 1A, 1B Science (G2) P6–P7 (10:30)", "\n• Ms Maya Lee · 1C Science P3–P5 (09:00)"
NOBODY, NOT_ON, TOO_SOON, TRIED = "Nobody to remind.", "Not on Telegram.", "Sent at {}: wait a few minutes.", "Last tried at {}: wait a few minutes."
BY = (TEAM, "telegram")
def head(hm, n): return f"⏰ {hm} · Not yet acknowledged ({n})"
def all_clear(hm, n): return f"✅ {hm} · All {n} reliefs for today are acknowledged."
def none_waits(hm, k): return f"✅ {hm} · No reliefs are waiting now: {k} started without acknowledgement."
def ticked(hm, day=13): at(hm, day); return RE.tick()
def keyed(hhmm, *names): return [f"report:{D13}:{hhmm}:{n}" for n in names or (TEAM,)]
def cleared(n, *names): return [f"clear:{D13}:{n}:{x}" for x in names or (TEAM,)]
def texts_to(name=TEAM): return [r["text"] for r in outs(name=name) if r["kind"] in ("report", "clear")]
def today_reliefs(*given):
    """an absence of Eve's on Tue 13 Oct, sent at 06:50 that day, with these (cover key, relief teacher) approved and told -> its id"""
    at("06:50", 13); i = absent(by=HUGO)
    for ckey, who_ in given: give(i, ckey, who_)
    swept(); return i
def relief_key_of(i, ckey): return f"relief:{EVE}:{ckey}:{approved_at(i, ckey)}"
def asks(i, *ckeys): return [dict(id=i, ckey=k, absent=EVE) for k in ckeys]
def remind(covers, date=D13): return RE.remind(date, covers, BY)
def listed(i, *ckeys): return [dict(id=i, ckey=k, absent=EVE, approved_at=approved_at(i, k)) for k in ckeys]
def every(n): store.write_json(RS.PATH, dict(calendar=TERM, times=dict(report_every=n)))
def skips(got): return [(v["ckey"], v["name"], v["why"]) for v in got["skipped"]]
def tell_today(i, ckey=K5): t_ = TE.said().of(relief_key_of(i, ckey)); return t_["state"], t_["at"]

@t
def the_report_texts_are_the_plans():
    plan = open(os.path.join(ROOT, "docs", "superpowers", "plans", "2026-11-22-relief-stage-4-telegram.md"), encoding="utf-8").read()
    v = dict(who="{who}", lesson="{lesson}", periods="{periods}", start="{start}", how="sent {hh:mm}")
    got = RE.report_text("{hh:mm}", [v], [v]).replace("(1)", "({n})", 1) + "\n" + RE.clear_text("{hh:mm}", 4, 0).replace(" 4 ", " {n} ")
    assert len(got.splitlines()) == 5
    for line in got.splitlines(): assert f"`{line}`" in plan, line
    assert "`sent {hh:mm} · not on Telegram now`" in plan
    assert RE.clear_text("08:00", 4, 2) == none_waits("08:00", 2) and "`No reliefs are waiting now: {k} started without acknowledgement.`" in plan
    assert RE.clear_text("08:00", 1, 0) == "✅ 08:00 · The 1 relief for today is acknowledged." and RE.clear_text("08:00", 1, 1) == none_waits("08:00", 1)
    for label in (RE.AGAIN, RE.OPEN_TODAY): assert f"`{label}`" in plan
    assert (RE.AGAIN, RE.OPEN_TODAY, RE.NOBODY, RE.NOT_ON, RE.TOO_SOON.format(at="07:20"), RE.TRIED.format(at="07:20"), bot.REMINDED.format(n=2)) == ("Remind them again", "Open relief today", NOBODY, NOT_ON, TOO_SOON.format("07:20"), TRIED.format("07:20"), "Reminded 2.")
    for text in (NOBODY, NOT_ON, TOO_SOON.format("{hh:mm}"), TRIED.format("{hh:mm}")): assert f"`{text}`" in plan, text
    v = dict(who=SAM, lesson="1A Art", periods="P1", start="", how="not on Telegram")                          # a lesson with no times
    assert RE.report_text("07:00", [v], [v]) == head("07:00", 1) + "\n• Mr Sam Tan · 1A Art P1 · not on Telegram" + STARTED + "\n• Mr Sam Tan · 1A Art P1"
    assert RE.report_text("07:00", [v], []) == head("07:00", 1) + "\n• Mr Sam Tan · 1A Art P1 · not on Telegram" and RE.report_text("07:00", [], [v]).splitlines()[:2] == [head("07:00", 0), STARTED[1:]]

@t
def a_state_is_raised_once():
    with telegram():
        got = lambda *ks: [tgdb.get_state(k) for k in ks]
        assert tgdb.raise_state("n", 5) is True and got("n") == [5] and tgdb.raise_state("n", 5, ["x"]) is False and tgdb.raise_state("n", 4, ["x"]) is False and got("n", "x") == [5, None]
        assert tgdb.raise_state("n", 6, ["x", "y"]) is True and got("n", "x", "y") == [6, 6, 6] and tgdb.raise_state("m", 0) is True and tgdb.raise_state("m", 0) is False
        for odd in ("odd", None, [9], {}): tgdb.set_state("n", odd); assert tgdb.raise_state("n", 1) is True and got("n") == [1], odd
        done = []; at_once(*[lambda: done.append(tgdb.raise_state("k", 7))] * 8); assert sorted(done) == [False] * 7 + [True]

# ---- the report
@t
def the_report_goes_at_its_marks_and_once_each():
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM), (K2, MAYA)); assert ticked("06:59") == [] and outs("report") == []
        OB._wake.clear(); assert ticked("07:00") == keyed("0700") and OB._wake.is_set(); r, = outs("report")
        assert (r["name"], r["text"], json.loads(r["files"]), r["state"]) == (TEAM, head("07:00", 2) + MAYA_LINE + "sent 06:50" + SAM_LINE + "sent 06:50", [], "queued"), r["text"]
        assert buttons_of(r) == [[dict(text="Remind them again", what="remind", extra=dict(date=D13, covers=listed(i, K2, K5)))], TODAY_BUTTON], buttons_of(r)
        assert send() == 1 and json.loads(r["ref"])["made"] == "2026-10-13T07:00:00+08:00" and tgdb.get_state(f"report_last:{D13}") == 420
        OB._wake.clear()
        for hm in ("07:00", "07:01", "07:14:59"): assert ticked(hm) == [] and not OB._wake.is_set(), hm
        assert ticked("07:15") == keyed("0715") and texts_to()[-1] == head("07:15", 2) + MAYA_LINE + "sent 06:50" + SAM_LINE + "sent 06:50"
        on_cover(MAYA, i, K2, "acknowledge"); assert send() == 1 and ticked("07:29") == [] and ticked("07:30") == keyed("0730") and texts_to()[-1] == head("07:30", 1) + SAM_LINE + "sent 06:50"
        assert buttons_of(outs("report")[-1])[0][0]["extra"] == dict(date=D13, covers=listed(i, K5)) and send() == 1
        assert [x.split("\n")[0] for x in said(TEAM)] == [head("07:00", 2), head("07:15", 2), head("07:30", 1)] and said(SAM) == [RELIEF_K5], "the team alone"
    with school(SAM, MAYA, TEAM):                                                          # in time order, whoever they are
        today_reliefs((K5, MAYA), (K2, SAM)); ticked("07:00"); assert texts_to()[-1] == head("07:00", 2) + MAYA_LINE.replace(MAYA, SAM) + "sent 06:50" + SAM_LINE.replace(SAM, MAYA) + "sent 06:50"
    with school(SAM, TEAM, base=None):                                                     # an address that is not https, or not known: no such button goes
        today_reliefs((K5, SAM)); assert ticked("07:00") == keyed("0700") and send() == 1 and [len(row) for row in calls("sendMessage")[-1]["reply_markup"]["inline_keyboard"]] == [1]
        assert calls("sendMessage")[-1]["reply_markup"]["inline_keyboard"][0][0]["text"] == "Remind them again"

@t
def a_late_tick_or_a_restart_sends_a_mark_once():
    with school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); assert ticked("07:33") == keyed("0730") and texts_to()[-1].startswith(head("07:33", 1)), "late: the time now"
        assert ticked("07:34") == [] and ticked("07:44:59") == [] and ticked("07:46") == keyed("0745") and ticked("07:44") == [] and ticked("07:30") == [], "nor a mark before it"
        importlib.reload(RE); assert bot._report is RE and ticked("07:47") == [] and ticked("08:00") == keyed("0800") and ticked("08:00") == [], "nothing is kept in memory"
        def dies(*a, **k): raise Killed()
        with stand_in(OB, "queue", dies):                                                  # it stops between the mark and the queue: the mark is not sent again
            try: ticked("08:15")
            except Killed: pass
        assert tgdb.get_state(f"report_last:{D13}") == 495 and ticked("08:16") == [] and ticked("08:30") == keyed("0830")
        # a mark nothing waits at is done with, too: what is approved after it is in the next
        on_cover(SAM, i, K5, "acknowledge"); assert ticked("08:45") == cleared(1) and ticked("09:00") == []; give(i, K2, RUTH); assert ticked("09:01") == [] and texts_to()[-1] == "✅ 08:45 · The 1 relief for today is acknowledged."
        # what cannot be worked out is worked out a minute later, the mark still to go
        j = absent(dates=["2026-10-16"]); assert j
        with no_pub(): assert ticked("09:15") == []
        with broken_accounts(): assert ticked("09:16") == []
        with stand_in(TE, "_records", lambda: 1 / 0): assert ticked("09:17") == []
        assert tgdb.get_state(f"report_last:{D13}") == 540 and ticked("09:18") == keyed("0915")
    with school(SAM, TEAM):                                                                # the store cannot be written: nothing goes, and a minute later it does
        today_reliefs((K5, SAM))
        def locked(*a, **k): raise sqlite3.OperationalError("made up")
        with stand_in(tgdb, "raise_state", locked): assert ticked("07:00") == [] and outs("report") == []
        assert ticked("07:01") == keyed("0700")
    with school(SAM, TEAM, LEE):                                                           # one that cannot be queued never stops the rest
        today_reliefs((K5, SAM)); real = OB.queue
        with stand_in(OB, "queue", lambda key, name, *a, **k: 1 / 0 if name == LEE else real(key, name, *a, **k)): assert ticked("07:00") == keyed("0700")
        assert ticked("07:15") == keyed("0715", LEE, TEAM)
    with school(SAM, TEAM):                                                                # another day: its own marks
        i = absent(by=HUGO, dates=["2026-10-13", "2026-10-14"]); give(i, K5, SAM); give(i, KW, SAM); swept(); assert ticked("10:15") == keyed("1015") and ticked("07:00", 14) == [f"report:2026-10-14:0700:{TEAM}"]
        assert texts_to()[-1] == head("07:00", 1) + "\n• Mr Sam Tan · 2A Science P2 · starts 08:30 · sent Mon 09:00"

@t
def two_copies_of_the_app_send_a_mark_once():
    with school(SAM, MAYA, TEAM, LEE):
        today_reliefs((K2, MAYA), (K5, SAM)); at("09:00", 13); got = []
        at_once(*[lambda: got.append(RE.tick())] * 6)
        assert sorted(x for g in got for x in g) == keyed("0900", LEE, TEAM) and sum(1 for g in got if g) == 1 and {r["text"] for r in outs("report")} == {head("09:00", 1) + SAM_LINE + "sent 06:50" + STARTED + MAYA_STARTED}

@t
def changing_how_often_never_sends_twice():
    with school(SAM, TEAM):
        today_reliefs((K5, SAM)); assert ticked("07:30") == keyed("0730"); every(10); assert ticked("07:31") == [] and ticked("07:39") == [] and ticked("07:40") == keyed("0740")
        every(60); assert ticked("07:45") == [] and ticked("07:59") == [] and ticked("08:00") == keyed("0800"); every(5); assert ticked("08:04") == [] and ticked("08:05") == keyed("0805")
        tgdb.set_state(f"report_last:{D13}", "odd"); assert ticked("08:05") == [] and tgdb.get_state(f"report_last:{D13}") == 485, "what is kept, changed by hand: the queue still has it once"
        every(7); assert ticked("08:06") == [] and ticked("08:09") == [] and ticked("08:10") == keyed("0810"); every(15); assert ticked("08:14") == [] and ticked("08:15") == keyed("0815")
        for bad in ("x", None, 0, -5, True, [1], 10 ** 9, 7.5):                             # changed by hand: every 15
            every(bad); n = len(outs("report")); store.write_json(RS.PATH, dict(calendar=TERM, times="odd" if bad == "x" else dict(report_every=bad)))
            with tgdb.db() as c: c.execute("DELETE FROM state WHERE k LIKE 'report_last:%'"); c.execute("DELETE FROM outbox WHERE kind='report'")
            assert ticked("08:35") == keyed("0830") and ticked("08:44") == [] and ticked("08:45") == keyed("0845"), (bad, n)

@t
def not_before_an_hour_before_the_first_period():
    m = SCHOOL["model"]; old = dict(m["school"])
    try:
        with school(SAM, TEAM):
            today_reliefs((K5, SAM)); m["school"].update(start_time="07:40")                # from 06:40: the first mark is 06:45
            for hm in ("00:00", "06:30", "06:39", "06:40", "06:44:59"): assert ticked(hm) == [] and tgdb.get_state(f"report_last:{D13}") is None, hm
            assert ticked("06:45") == keyed("0645")
        with school(SAM, TEAM):
            m["school"].update(old); today_reliefs((K5, SAM)); assert ticked("06:59:59") == [] and ticked("07:14") == keyed("0700"), "08:00: at 07:00 itself"
        with school(SAM, TEAM):                                                            # a timetable with no times: no report
            today_reliefs((K5, SAM)); m["school"].pop("start_time"); assert ticked("09:00") == [] and tgdb.get_state(f"report_last:{D13}") is None
    finally: m["school"].clear(); m["school"].update(old)

@t
def a_started_relief_is_listed_once_then_dropped():
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K2, MAYA), (K5, SAM)); key = relief_key_of(i, K2)
        assert ticked("08:45") == keyed("0845") and texts_to()[-1] == head("08:45", 2) + MAYA_LINE + "sent 06:50" + SAM_LINE + "sent 06:50" and tgdb.get_state(f"started:{key}") is None
        assert ticked("09:00") == keyed("0900") and texts_to()[-1] == head("09:00", 1) + SAM_LINE + "sent 06:50" + STARTED + MAYA_STARTED and tgdb.get_state(f"started:{key}")
        assert buttons_of(outs("report")[-1])[0][0]["extra"]["covers"] == listed(i, K5), "those not started alone"
        assert ticked("09:15") == keyed("0915") and texts_to()[-1] == head("09:15", 1) + SAM_LINE + "sent 06:50"; importlib.reload(RE); assert ticked("10:29") == keyed("1015") and "Started" not in texts_to()[-1]
        assert ticked("10:30") == keyed("1030") and texts_to()[-1] == head("10:30", 0) + STARTED + SAM_STARTED and buttons_of(outs("report")[-1]) == [TODAY_BUTTON], "nobody to remind: no such button"
        assert ticked("10:45") == cleared(1) and texts_to()[-1] == none_waits("10:45", 2)
        for hm in ("11:00", "12:15", "23:59"): assert ticked(hm) == [], hm
    with school(MAYA, TEAM):                                                               # told to nobody, and first seen when it is over: listed too
        i = today_reliefs((K2, RUTH), (K5, MAYA)); CV.acknowledge(i, K5, MAYA); assert outs("relief", RUTH) == [] and ticked("11:45") == keyed("1145")
        assert texts_to()[-1] == head("11:45", 0) + STARTED + "\n• Ms Ruth Goh · 1C Science P3–P5 (09:00)" and tgdb.get_state(f"started:{relief_key_of(i, K2)}") and ticked("12:00") == cleared(1) and texts_to()[-1] == none_waits("12:00", 1)
    with school(SAM, MAYA, TEAM):                                                          # acknowledged late, before the report: not listed; after it: all are acknowledged
        i = today_reliefs((K2, MAYA), (K5, SAM)); ticked("08:45"); at("09:02", 13); on_cover(MAYA, i, K2, "acknowledge"); ticked("09:15"); assert texts_to()[-1] == head("09:15", 1) + SAM_LINE + "sent 06:50"
        ticked("10:30"); assert texts_to()[-1] == head("10:30", 0) + STARTED + SAM_STARTED; at("10:40", 13); on_cover(SAM, i, K5, "acknowledge"); assert ticked("10:45") == cleared(1) and texts_to()[-1] == all_clear("10:45", 2)
    with school(SAM, MAYA, TEAM):                                                          # given to another since: that is another relief
        i = today_reliefs((K2, MAYA)); ticked("09:00"); assert texts_to()[-1] == head("09:00", 0) + STARTED + MAYA_STARTED; at("09:05", 13); give(i, K2, SAM); swept(); assert ticked("09:15") == keyed("0915")
        assert texts_to()[-1] == head("09:15", 0) + STARTED + MAYA_STARTED.replace(MAYA, SAM) and ticked("09:30") == cleared(1) and texts_to()[-1] == none_waits("09:30", 1)
    with school(SAM, TEAM):                                                                # moved to another absence of the same teacher's: the same relief
        i = today_reliefs((K5, SAM)); ticked("10:30"); moved_to(i); assert ticked("10:45") == cleared(1)
    with school(SAM, TEAM):                                                                # a part of a split lesson starts at its own time
        at("06:50", 13); i = absent(by=HUGO); CV.split(i, K2, 3, TEAM); give(i, K2 + "#1", SAM); swept(); ticked("09:15"); assert texts_to()[-1] == head("09:15", 1) + "\n• Mr Sam Tan · 1C Science P4–P5 · starts 09:30 · sent 06:50"
        ticked("09:30"); assert texts_to()[-1] == head("09:30", 0) + STARTED + "\n• Mr Sam Tan · 1C Science P4–P5 (09:30)"
    with school(SAM, TEAM):                                                                # a period past the day's last, changed by hand: started when the day's periods are over
        i = today_reliefs((K5, SAM)); change_record(i, lambda r: [x.update(p=20) for x in r["lessons"] if x["key"] == K5]); ticked("13:45"); assert texts_to()[-1].startswith(head("13:45", 1))
        ticked("14:00"); assert texts_to()[-1].startswith(head("14:00", 0) + STARTED) and ticked("14:15") == cleared(1) and ticked("14:30") == []

@t
def all_clear_goes_once_and_again_after_new_waiting():
    with school(SAM, MAYA, RUTH, TEAM):
        i = today_reliefs((K2, MAYA), (K5, SAM)); CV.acknowledge(i, K2, MAYA); assert ticked("07:00") == keyed("0700") and send() == 1; on_cover(SAM, i, K5, "acknowledge")
        assert ticked("07:14") == [] and ticked("07:15") == cleared(1) and texts_to()[-1] == all_clear("07:15", 2); r, = outs("clear")
        assert (r["name"], buttons_of(r), json.loads(r["ref"])["made"]) == (TEAM, [], "2026-10-13T07:15:00+08:00")
        assert send() == 1 and len(said(TEAM)) == 2
        for hm in ("07:16", "07:30", "07:45"): assert ticked(hm) == [], "once"
        on_lesson(EVE, i, K8, "needed"); give(i, K8, RUTH); swept(); assert ticked("08:00") == keyed("0800") and texts_to()[-1] == head("08:00", 1) + "\n• Ms Ruth Goh · 5A Art P9 · starts 12:00 · sent 07:45"
        assert ticked("08:15") == keyed("0815"); on_cover(RUTH, i, K8, "acknowledge"); assert ticked("08:30") == cleared(2) and texts_to()[-1] == all_clear("08:30", 3) and ticked("08:45") == []
        # moved to another, who waits: a third time; one that started without: the other sentence
        give(i, K8, MAYA); swept(); ticked("09:00"); assert texts_to()[-1].startswith(head("09:00", 1)) and ticked("12:00") == keyed("1200") and ticked("12:15") == cleared(3) and texts_to()[-1] == none_waits("12:15", 1)
        assert [r["key"] for r in outs("clear")] == cleared(1) + cleared(2) + cleared(3)
    with school(SAM, MAYA, TEAM):                                                          # no report went: no all clear
        i = today_reliefs((K5, SAM)); CV.acknowledge(i, K5, SAM); assert [ticked(hm) for hm in ("07:00", "07:15", "10:45")] == [[]] * 3
    with school(SAM, MAYA, TEAM):                                                          # the reports were never sent (too old by then): no all clear of them
        i = today_reliefs((K5, SAM)); ticked("07:00"); at("07:31", 13); assert send() == 0 and outs("report")[0]["state"] == "dropped"; on_cover(SAM, i, K5, "acknowledge"); assert ticked("07:45") == []
    with school(SAM, MAYA, TEAM):                                                          # every relief taken away: nothing is said to be acknowledged
        i = today_reliefs((K5, SAM)); ticked("07:00"); absences.cancel(i, "Better", HUGO); assert ticked("07:15") == [] and ticked("07:30") == []
    with school(SAM, MAYA, TEAM):                                                          # a request to change waits for the team, so it is not said that none waits; nor that all are acknowledged
        i = today_reliefs((K2, MAYA), (K5, SAM)); ticked("07:00"); CV.acknowledge(i, K2, MAYA); CV.ask_change(i, K5, "x", SAM); assert ticked("07:15") == [] and ticked("07:30") == []
        CV.keep(i, K5, TEAM); assert ticked("07:45") == keyed("0745") and texts_to()[-1].startswith(head("07:45", 1)); CV.ask_change(i, K5, "x", SAM); at("07:50", 13); give(i, K5, HUGO); CV.acknowledge(i, K5, HUGO)
        assert ticked("08:00") == cleared(1) and texts_to()[-1] == all_clear("08:00", 2)
    with school(SAM, MAYA, TEAM):                                                          # ... until its lesson starts
        i = today_reliefs((K2, MAYA), (K5, SAM)); ticked("07:00"); CV.acknowledge(i, K2, MAYA); CV.ask_change(i, K5, "x", SAM); assert ticked("10:15") == [] and ticked("10:30") == cleared(1) and texts_to()[-1] == none_waits("10:30", 1)

@t
def nothing_is_sent_when_nothing_waits():
    with school(SAM, MAYA, TEAM):
        for hm in ("07:00", "10:00", "23:59"): assert ticked(hm, 14) == [] and ticked(hm, 12) == [], "no reliefs"
        at("06:50", 13); i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)]); assert ticked("07:00", 13) == [], "a pick nobody has approved"
        on_cover(TEAM, i, K5, "approve", dict(who=SAM)); assert ticked("07:15") == keyed("0715"), "approved"
    for f in (lambda i: CV.acknowledge(i, K5, SAM), lambda i: CV.ask_change(i, K5, "x", SAM), lambda i: absences.cancel(i, "x", HUGO), lambda i: absences.not_needed(i, K5, "x", HUGO), lambda i: os.remove(absences._path(i))):
        with school(SAM, TEAM): i = today_reliefs((K5, SAM)); f(i); assert ticked("07:00") == [] and outs("report") == [] and ticked("10:30") == [] and texts_to() == []
    with school(SAM, TEAM): i = absent(by=HUGO, dates=["2026-10-16"]); give(i, KF, SAM); swept(); assert ticked("07:00", 13) == [], "another day's"
    holiday = dict(TERM, holidays=[dict(start=D13, end=D13, name="Made-up Day")])
    for cal in (holiday, dict(terms=[], holidays=[]), dict(TERM, terms=[dict(TERM["terms"][0], end="2026-10-12")])):      # not a school day
        with school(SAM, TEAM): today_reliefs((K5, SAM)); store.write_json(RS.PATH, dict(calendar=cal)); assert ticked("07:00") == [] and ticked("10:30") == [] and tgdb.get_state(f"report_last:{D13}") is None
    h = Grab(); KINDS.addHandler(h)
    with school(SAM, TEAM):
        today_reliefs((K5, SAM)); b = tgdb.get_state("bot"); tgdb.set_state("bot", None); assert ticked("07:00") == [] and tgdb.get_state(f"report_last:{D13}") is None, "not connected"
        tgdb.set_state("bot", b); os.environ.pop("TELEGRAM_BOT_TOKEN")
        with stand_in(tgdb, "db", lambda read=False: 1 / 0): assert RE.tick() == [], "no token: not even the store is opened"
        os.environ["TELEGRAM_BOT_TOKEN"] = "practice"; links.unlink(TEAM); assert ticked("07:01") == [] and tgdb.get_state(f"report_last:{D13}") is None, "nobody to send it to"
        with no_pub(): assert ticked("07:01") == []
        links.link(TEAM, CHATS[TEAM], None); assert ticked("07:02") == keyed("0700"), "the mark is still theirs"
    KINDS.removeHandler(h); assert h.records == [], "none of it is a failure"

@t
def a_relief_approved_after_the_report_started():
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K2, MAYA)); ticked("07:00"); assert texts_to()[-1] == head("07:00", 1) + MAYA_LINE + "sent 06:50"
        at("07:08", 13); give(i, K5, SAM); swept(); assert ticked("07:09") == [] and ticked("07:15") == keyed("0715") and texts_to()[-1] == head("07:15", 2) + MAYA_LINE + "sent 06:50" + SAM_LINE + "sent 07:08"
        at("10:35", 13); on_cover(MAYA, i, K2, "acknowledge"); on_lesson(EVE, i, K8, "needed"); give(i, K8, MAYA); ticked("10:45"); assert texts_to()[-1].startswith(head("10:45", 1)) and STARTED + SAM_STARTED in texts_to()[-1]
    with school(SAM, TEAM):                                                                # approved when its lesson is over already (who took it, written down after): said once
        at("12:50", 13); i = absent(by=HUGO); give(i, K5, SAM); swept(); assert outs("relief") == [] and ticked("13:00") == keyed("1300") and texts_to()[-1] == head("13:00", 0) + STARTED + SAM_STARTED
        assert ticked("13:15") == cleared(1) and ticked("13:30") == []

@t
def the_report_goes_to_team_members_only():
    with school(SAM, EVE, HUGO, ROSA, TEAM, LEE, MAYA):
        today_reliefs((K5, SAM)); assert ticked("07:00") == keyed("0700", LEE, TEAM) and {r["name"] for r in outs("report")} == {TEAM, LEE}
        links.unlink(LEE); assert ticked("07:15") == keyed("0715"); links.link(LEE, CHATS[LEE], None); assert ticked("07:30") == keyed("0730", LEE, TEAM)
        with record(LEE, extras=dict(relief=False, exams=None, admin=False)): assert ticked("07:45") == keyed("0745")
        with record(LEE, off=True): assert ticked("08:00") == keyed("0800")
        # the right at sending: whoever lost it since gets neither
        ticked("08:15"); i = absences.all_records()[0]["id"]; CV.acknowledge(i, K5, SAM); ticked("08:30"); assert [r["name"] for r in outs("clear")] == [LEE, TEAM]
        with record(LEE, extras=dict(relief=False, exams=None, admin=False)): send()
        assert {r["state"] for r in outs(name=LEE) if r["key"].split(":")[0] == "clear" or ":0815:" in r["key"]} == {"dropped"} and said(LEE) == []
        assert said(TEAM)[-1].startswith("✅") and [c for c, x in sent() if "acknowledged" in x and c != CHATS[TEAM]] == []

@t
def not_on_telegram_is_said_in_the_report():
    def line(i=None): ticked(hm()); return texts_to()[-1].split("\n")[1].split(" · ")[-1]
    marks = iter(f"{h:02d}:{m:02d}" for h in (7, 8, 9, 10) for m in (0, 15, 30, 45)); hm = lambda: next(marks)
    with school(TEAM):
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); assert line() == "not on Telegram"
        links.link(SAM, CHATS[SAM], None); assert line() == "not told yet", "linked later, and not swept yet"
        TE.sweep(); assert line() == "not told yet", "waiting in the queue"
        for s, want in (("sending", "not told yet"), ("failed", "not told yet"), ("dropped", "not told yet"), ("unsure", "sent 07:41")):
            put(key, state=s, sent_at="2026-10-13T07:41:00+08:00"); assert line() == want, s
        put(key, state="sent"); assert line() == "sent 07:41"
        with record(SAM, off=True): assert line() == "not on Telegram now" and texts_to()[-1].endswith(SAM_LINE + "sent 07:41 · not on Telegram now"), "told, whatever came after; and what is so now"
        links.unlink(SAM); assert line() == "not on Telegram now" and texts_to()[-1].endswith(SAM_LINE + "sent 07:41 · not on Telegram now")
        put(key, state="unsure"); assert line() == "not on Telegram now" and texts_to()[-1].endswith("sent 07:41 · not on Telegram now"), "may have been told"
        for s in ("failed", "dropped"): put(key, state=s); assert line() == "not on Telegram", s
    marks = iter(f"{h:02d}:{m:02d}" for h in (7, 8, 9) for m in (0, 15, 30, 45))
    with school(SAM, TEAM):                                                                # unlinked, and linked again
        i = today_reliefs((K5, SAM)); links.unlink(SAM); assert line() == "not on Telegram now"; links.link(SAM, CHATS[SAM], None); assert line() == "sent 06:50"
        assert SAM_LINE.strip("\n") in texts_to()[-1]
    marks = iter(f"{h:02d}:{m:02d}" for h in (7, 8, 9) for m in (0, 15, 30, 45))
    with school(SAM, TEAM):                                                                # a reminder is the relief told, too: the latest of those that went
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); at("06:56", 13); remind(asks(i, K5)); assert line() == "sent 06:50", "the reminder still waits"
        send(); assert item(key + ":r1")["state"] == "sent" and line() == "sent 07:00"; put(key, state="failed"); assert line() == "sent 07:00"; put(key + ":r1", state="failed"); assert line() == "not told yet"
        put(key + ":r1", state="unsure"); assert line() == "sent 07:00"
        at("08:20", 13); give(i, K5, SAM); assert line() == "not told yet", "approved anew: what was said of it before is not this"; swept(); assert line().startswith("sent 08:")
    marks = iter(f"{h:02d}:{m:02d}" for h in (7, 8, 9) for m in (0, 15, 30, 45))
    with school(SAM, MAYA, TEAM):                                                          # two approved in one second have a key each
        i = today_reliefs((K5, SAM)); give(i, K5, MAYA); swept(); assert item(f"{relief_key_of(i, K5)}:{MAYA}")["state"] == "sent"; ticked(hm())
        assert texts_to()[-1] == head("07:00", 1) + SAM_LINE.replace(SAM, MAYA) + "sent 06:50"; links.unlink(MAYA); put(f"{relief_key_of(i, K5)}:{MAYA}", state="failed"); assert line() == "not on Telegram"

@t
def the_line_says_the_day_when_it_was_not_today():
    marks = iter(f"{m // 60:02d}:{m % 60:02d}" for m in range(420, 630, 15))
    def line(): ticked(next(marks)); return texts_to()[-1].split("\n")[1].split(" · ")[-1]
    with school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); assert line() == "sent 06:50"
        for sent_at, want in (("2026-10-13T00:00:00+08:00", "sent 00:00"), ("2026-10-12T23:59:59+08:00", "sent Mon 23:59"), ("2026-10-12T15:00:00+08:00", "sent Mon 15:00"), ("2026-10-09T08:05:00+08:00", "sent Fri 08:05"),
                              ("2026-10-12T16:30:00+00:00", "sent 00:30"), ("2026-10-12T15:30:00+00:00", "sent Mon 23:30")):                     # school time, whatever it was kept in
            for s in ("sent", "unsure"): put(key, state=s, sent_at=sent_at); assert line() == want, (sent_at, s)
    with school(SAM, TEAM):                                                                # planned the day before: approved and told on Monday afternoon
        at("15:00", 12); i = absent(by=HUGO); give(i, K5, SAM); swept(); ticked("07:00"); assert texts_to()[-1] == head("07:00", 1) + SAM_LINE + "sent Mon 15:00"
        links.unlink(SAM); ticked("07:15"); assert texts_to()[-1] == head("07:15", 1) + SAM_LINE + "sent Mon 15:00 · not on Telegram now"; links.link(SAM, CHATS[SAM], None)
        at("07:20", 13); remind(asks(i, K5)); send(); ticked("07:30"); assert texts_to()[-1] == head("07:30", 1) + SAM_LINE + "sent 07:20", "reminded today"

@t
def a_stopped_lesson_is_left_out_of_the_report():
    with exam_school(SAM, MAYA, TEAM):
        i = today_reliefs((K2, MAYA), (K5, SAM)); e = exam(); swept(); assert outs("stopped", SAM)[0]["state"] == "sent" and ticked("07:00") == keyed("0700")
        assert texts_to()[-1] == head("07:00", 1) + MAYA_LINE + "sent 06:50" and "Zebra" not in texts_to()[-1]; CV.acknowledge(i, K2, MAYA)
        assert ticked("07:15") == cleared(1) and texts_to()[-1] == "✅ 07:15 · The 1 relief for today is acknowledged.", "what is stopped does not count"
        # it stands again: not told, until they are sure to have been
        withdraw(e); assert ticked("07:30") == keyed("0730") and texts_to()[-1] == head("07:30", 1) + SAM_LINE + "not told yet"
        TE.sweep(); again = outs("again")[0]["key"]; assert ticked("07:45") == keyed("0745") and texts_to()[-1].endswith("not told yet"), "waiting in the queue"
        for s in ("unsure", "failed", "sending", "dropped"): put(again, state=s); ticked({"unsure": "08:00", "failed": "08:15", "sending": "08:30", "dropped": "08:45"}[s]); assert texts_to()[-1].endswith("not told yet"), s
        put(again, state="sent"); ticked("09:00"); assert texts_to()[-1].endswith("sent 06:50")
        # a second time
        at("09:01", 13); again_on(e); swept(); ticked("09:15"); assert "Sam" not in texts_to()[-1]; withdraw(e); ticked("09:30"); assert texts_to()[-1].endswith("not told yet"); swept(); ticked("09:45"); assert texts_to()[-1].endswith("sent 06:50")
    with exam_school(SAM, TEAM):                                                           # reminded since: they know of it; not when the reminder may not have gone
        i = today_reliefs((K5, SAM)); e = exam(); swept(); withdraw(e); TE.sweep(); put(outs("again")[0]["key"], state="failed"); ticked("07:00"); assert texts_to()[-1].endswith("not told yet")
        at("07:05", 13); assert remind(asks(i, K5))["sent"] == 1; ticked("07:15"); assert texts_to()[-1].endswith("not told yet"); send(); ticked("07:30"); assert texts_to()[-1].endswith("sent 07:15")
        put(relief_key_of(i, K5) + ":r1", state="unsure"); ticked("07:45"); assert texts_to()[-1].endswith("not told yet")
    with exam_school(TEAM): i = today_reliefs((K5, SAM)); e = exam(); withdraw(e); ticked("07:00"); assert texts_to()[-1].endswith("not on Telegram")
    with exam_school(SAM, TEAM):                                                           # stopped when it would have started: nothing of it
        today_reliefs((K5, SAM)); exam(); assert [ticked(hm) for hm in ("07:00", "10:30", "10:45")] == [[]] * 3

@t
def while_the_exams_cannot_be_read_nothing_is_said_to_have_started():
    with exam_school(SAM, MAYA, TEAM):
        i = today_reliefs((K2, MAYA), (K5, SAM)); exam()
        with unreadable(): ticked("07:00"); assert texts_to()[-1] == head("07:00", 2) + MAYA_LINE + "sent 06:50" + SAM_LINE + "sent 06:50", "as if none were stopped"
        with unreadable(): ticked("09:00"); assert texts_to()[-1] == head("09:00", 1) + SAM_LINE + "sent 06:50" and tgdb.get_state(f"started:{relief_key_of(i, K2)}") is None
        with unreadable(): assert ticked("10:30") == [], "neither waiting nor, as far as is known, started: no all clear either"
        assert ticked("10:45") == keyed("1045") and texts_to()[-1] == head("10:45", 0) + STARTED + MAYA_STARTED, "read again: once, and not the one that is stopped"
        with unreadable(): assert ticked("11:00") == [], "the stopped one counts as started, and is not listed yet: nothing is said of it"
        assert ticked("11:15") == cleared(1) and texts_to()[-1] == none_waits("11:15", 1)

@t
def an_old_report_or_all_clear_is_not_sent():
    with school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); ticked("07:00"); r = dict(outs("report")[0]); r["ref"] = json.loads(r["ref"])
        at("07:29:59", 13); assert TE.still_true(r) is True; at("07:30", 13); assert TE.still_true(r) is False and TE.still_true(dict(r, kind="clear")) is False
        at("07:29", 13); assert send() == 1; CV.acknowledge(i, K5, SAM); ticked("07:30"); c = dict(outs("clear")[0]); c["ref"] = json.loads(c["ref"]); assert TE.still_true(c) is True
        with record(TEAM, extras=dict(relief=False, exams=None, admin=False)): assert TE.still_true(c) is False and TE.still_true(dict(r, ref=c["ref"])) is False
        with broken_accounts():
            try: TE.still_true(c); raise AssertionError("nobody's rights are known")
            except ValueError: pass
        at("08:00", 13); assert send() == 0 and outs("clear")[0]["state"] == "dropped" and len(said(TEAM)) == 1
        # older than the pause Telegram asked for: dropped, not sent late
    with school(SAM, TEAM):
        today_reliefs((K5, SAM)); f, seen = tele(SLOW(2400)); os.environ["TELEGRAM_BOT_TOKEN"] = "made-up-" + secrets.token_hex(6)
        tgdb.set_state("bot", dict(username="ctss_made_up_bot", base=BASE, at="2026-10-12T08:00:00+08:00", key=digest(tg.hook_secret()))); ticked("07:00")
        with_send(f, lambda: OB.send_due(now=1000)); at("07:45", 13); with_send(f, lambda: OB.send_due(now=4000)); assert outs("report")[0]["state"] == "dropped" and len(texts(seen)) == 1
        os.environ["TELEGRAM_BOT_TOKEN"] = "practice"

@t
def the_report_never_raises_and_reads_once():
    h = Grab(); KINDS.addHandler(h)
    def boom(*a, **k): raise LookupError(f"{SAM} a private line")
    try:
        with school(SAM, MAYA, TEAM):
            i = today_reliefs((K5, SAM), (K2, MAYA)); n = 0
            for module, name in ((store, "published"), (links, "connected"), (links, "reachable"), (RS, "load"), (TE, "_records"), (AP, "staff"), (OB, "told_for"), (OB, "states_for"), (tgdb, "get_state"), (RE, "report_text")):
                h.records.clear()
                with stand_in(module, name, boom): assert ticked("07:00") == [], name
                assert [r.getMessage() for r in h.records] and all("LookupError" in r.getMessage() and "private" not in r.getMessage() and SAM not in r.getMessage() and r.exc_info is None for r in h.records), name
            reads = []
            def counted(f, name): return lambda *a, **k: (reads.append(name), f(*a, **k))[1]
            with stand_in(TE, "_records", counted(TE._records, "records")), stand_in(RS, "load", counted(RS.load, "settings")), stand_in(FL, "_links", counted(FL._links, "links")), stand_in(links, "reachable", counted(links.reachable, "reach")):
                assert ticked("07:01") == keyed("0700") and sorted(reads) == ["links", "reach", "records", "settings"], reads
                reads.clear(); assert ticked("07:02") == [] and "records" not in reads and "links" not in reads, "nothing to do: next to nothing is read"
            # a record changed by hand is passed over, and the rest is said
            h.records.clear()
            for odd in (dict(id="odd1", teacher=EVE, lessons=[5]), dict(id="odd2", lessons=[dict(date=D13, needed=True, relief=SAM, approved=5)]), dict(id="odd3", teacher=EVE, lessons=[dict(date=D13, key="k", needed=True, relief=SAM, approved=dict(by=TEAM), p="a private word")]),
                        dict(id="odd7", teacher="Mx Odd", lessons=[dict(date=D13, key="k", needed=True, relief=5, approved=dict(by=TEAM, at="2026-10-13T06:50:00+08:00"), p=2, n=3, classes=["1C"], subject="Science", start="09:00")]),
                        dict(id="odd4", teacher=SAM, lessons=None), dict(id="odd5", lessons="x"), dict(id="odd6", teacher=["x"], lessons=[dict(date=D13, key="k", needed=True, relief=["x"], approved=dict(at=5), p=1)])): absences._save(odd)
            assert ticked("07:15") == keyed("0715") and texts_to()[-1].endswith(MAYA_LINE + "sent 06:50" + SAM_LINE + "sent 06:50"), texts_to()[-1]
            assert h.records and not any("private" in r.getMessage() or "odd" in r.getMessage() or r.exc_info for r in h.records)
            assert remind(asks(i, K5))["sent"] == 1 and call(TEAM, "get", "/api/relief/me")
    finally: KINDS.removeHandler(h)

@t
def the_report_is_quick():
    with exam_school(SAM, TEAM):
        exam("3B", name=EXAM2); i = today_reliefs((K5, SAM)); whole_ = absences.load(i)
        for n in range(300):
            r = json.loads(json.dumps(whole_)); r.update(id=f"{n:012x}", teacher=f"Mx Made Up {n}")
            if n % 10: r.update(dates=["2026-10-01"], lessons=[dict(x, date="2026-10-01", key=x["key"].replace(D13, "2026-10-01")) for x in r["lessons"]])
            absences._save(r)
        was, = outs("relief")
        with tgdb.db() as c:                                                               # a year of messages
            c.executemany("INSERT INTO outbox(key, name, chat, kind, text, ref, at, state, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          [(f"{k}:Mx Old {n}:2026-09-01/x:2026-09-01T07:00:00+08:00{x}", *[was[v] for v in ("name", "chat", "kind", "text", "ref", "at", "state", "sent_at")])
                           for n in range(3000) for k, x in (("relief", ""), ("relief", ":r1"), ("stopped:relief", ":0"), ("report", ""))])
        at("07:00", 13); began = time.process_time(); assert RE.tick() == keyed("0700") and len(texts_to()[-1].splitlines()) == 32; first = time.process_time() - began
        began = time.process_time(); assert ticked("07:01") == []; second = time.process_time() - began
        assert first < 2.0 and second < 1.0, (first, second)

@t
def the_report_never_carries_a_reason():
    with school(SAM, EVE, ROSA, TEAM, MAYA):
        at("06:50", 13); i = absent(by=HUGO, reason="Other", reason_text="zebra-reason", remarks="quokka-remark", lessons=[dict(key=K5, relief=SAM)])
        change_record(i, lambda r: [x.update(pick=dict(who=SAM, by="ai", reason="lemur-pick", at=clock.now), work=dict(text="okapi-work", link="", files=[])) for x in r["lessons"] if x["key"] == K5])
        on_cover(TEAM, i, K5, "approve", dict(who=SAM)); give(i, K2, MAYA); CV.ask_change(i, K2, "walrus-why", MAYA); CV.keep(i, K2, TEAM); send(); ticked("07:00"); ticked("10:30"); remind(asks(i, K5)); ticked("11:00"); swept()
        got = [r for r in outs() if r["kind"] in ("report", "clear")]; assert len(got) == 3
        for r in got:
            for word in ("zebra", "quokka", "lemur", "walrus", "okapi", "Medical", "Other", EVE): assert word not in r["text"], (word, r["text"])
            for word in ("zebra", "quokka", "lemur", "walrus", "okapi"): assert word not in json.dumps(r, ensure_ascii=False), word
        assert "okapi-work" in outs("relief", SAM)[-1]["text"], "the reminder carries the work, as the relief does"
        raw = "".join(open(os.path.join(history.DIR, f), encoding="utf-8").read() for f in os.listdir(history.DIR)); assert not any(w in raw for w in ("zebra-reason", "quokka", "lemur", "okapi"))

# ---- Remind
@t
def remind_resends_once_every_five_minutes():
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM), (K2, MAYA)); key = relief_key_of(i, K5); base = item(key)
        for hm in ("06:50", "06:54", "06:55"): at(hm, 13); assert skips(remind(asks(i, K5, K2))) == [(K5, SAM, TOO_SOON.format("06:50")), (K2, MAYA, TOO_SOON.format("06:50"))] and len(outs("relief")) == 2, hm
        at("06:55:01", 13); OB._wake.clear(); assert remind(asks(i, K5)) == dict(sent=1, skipped=[]) and OB._wake.is_set(); r = item(key + ":r1")
        assert (r["name"], r["kind"], r["text"], r["state"], buttons_of(r), r["files"]) == (SAM, "relief", RELIEF_K5, "queued", relief_buttons(i), "[]"), r
        assert json.loads(r["ref"]) == dict(json.loads(base["ref"]), n=1)
        assert skips(remind(asks(i, K5))) == [(K5, SAM, TRIED.format("06:55"))], "one that waits counts as much"
        at("06:57", 13); assert send() == 1 and said(SAM) == [RELIEF_K5] * 2; at("07:01", 13); assert skips(remind(asks(i, K5))) == [(K5, SAM, TOO_SOON.format("06:57"))], "from when it went"
        at("07:02:01", 13); assert remind(asks(i, K5))["sent"] == 1 and item(key + ":r2") and json.loads(item(key + ":r2")["ref"])["n"] == 2
        # it waits (Telegram cannot be reached), or is on its way: nothing more is queued, however long, so that they never come all at once
        for st in ("queued", "sending"):
            put(key + ":r2", state=st)
            for hm in ("07:08", "07:30", "09:59"): at(hm, 13); assert skips(remind(asks(i, K5))) == [(K5, SAM, TRIED.format("07:02"))] and item(key + ":r3") is None, (st, hm)
        put(key + ":r2", state="queued"); assert send() == 1 and said(SAM) == [RELIEF_K5] * 3 and [state(f"{key}:r{n}") for n in (1, 2, 3)] == ["sent", "sent", None] and TE.sweep() == 0
        at("10:05", 13); assert remind(asks(i, K5))["sent"] == 1 and state(key + ":r3") == "queued", "five minutes from when it went"
        assert remind(asks(i, K2))["sent"] == 1 and item(f"{relief_key_of(i, K2)}:r1"), "each relief has its own five minutes"
    with school(SAM, TEAM):                                                                # the relief itself waits for Telegram: it goes by itself, once
        i = absent(by=HUGO); at("06:50", 13); give(i, K5, SAM); TE.sweep(); key = relief_key_of(i, K5)
        for st in ("queued", "sending"):
            put(key, state=st)
            for hm in ("06:56", "07:30", "09:59"): at(hm, 13); assert skips(remind(asks(i, K5))) == [(K5, SAM, TRIED.format("06:50"))] and [r["key"] for r in outs("relief")] == [key], (st, hm)
        put(key, state="queued"); assert send() == 1 and swept() == 0 and said(SAM) == [RELIEF_K5]
        put(key, state="unsure", sent_at="2026-10-13T09:59:00+08:00"); at("10:05", 13); assert remind(asks(i, K5))["sent"] == 1 and item(key + ":r1"), "it may have gone, long enough ago"
    with school(SAM, TEAM):                                                                # the press of one listing it twice; a covers list with nothing in it
        i = today_reliefs((K5, SAM)); at("07:00", 13); got = remind(asks(i, K5, K5)); assert got["sent"] == 1 and skips(got) == [(K5, SAM, TRIED.format("07:00"))] and remind([]) == dict(sent=0, skipped=[])
    with school(SAM, TEAM):                                                                # a message that failed told nobody: at once
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); put(key, state="failed"); at("06:51", 13); assert remind(asks(i, K5))["sent"] == 1 and item(key + ":r1"); put(key + ":r1", state="failed"); assert remind(asks(i, K5))["sent"] == 1 and item(key + ":r2")
        put(key + ":r2", state="unsure", sent_at="2026-10-13T06:51:00+08:00"); at("06:53", 13); assert skips(remind(asks(i, K5))) == [(K5, SAM, TRIED.format("06:51"))], "it may have gone"
    with school(TEAM):                                                                     # not told at all yet (linked this minute): the message itself, which the sweep does not send again
        i = today_reliefs((K5, SAM)); links.link(SAM, CHATS[SAM], None); key = relief_key_of(i, K5); assert remind(asks(i, K5))["sent"] == 1 and [r["key"] for r in outs("relief")] == [key] and "n" not in json.loads(item(key)["ref"])
        assert TE.sweep() == 0 and swept() == 0 and said(SAM) == [RELIEF_K5]; put(key, state="dropped"); at("07:00", 13); assert remind(asks(i, K5))["sent"] == 1 and state(key) == "queued" and len(outs("relief")) == 1
    with school(SAM, TEAM):                                                                # the clock put back: never sooner
        i = today_reliefs((K5, SAM)); at("06:30", 13); assert remind(asks(i, K5))["sent"] == 0

@t
def a_reminder_asked_for_soon_after_the_relief_says_when_that_went():
    why = "Sent at 06:57: wait a few minutes."                                             # nobody has been reminded: the relief alone has gone
    with school(SAM, TEAM):
        i = today_reliefs(); at("06:57", 13); give(i, K5, SAM); swept(); key = relief_key_of(i, K5); assert [(r["key"], r["state"]) for r in outs("relief")] == [(key, "sent")] and said(SAM) == [RELIEF_K5]
        assert ticked("07:00") == keyed("0700"); send(); h = Since()
        assert skips(remind(asks(i, K5))) == [(K5, SAM, why)]
        assert call(TEAM, "post", "/api/relief/today/remind", dict(date=D13, covers=[dict(id=i, ckey=K5)])) == dict(sent=0, skipped=[dict(ckey=K5, name=SAM, why=why)]), "on the page"
        assert press(TEAM, "remind") == (why, True), "under the report on Telegram"
        assert [r["key"] for r in outs("relief")] == [key] and h.new() == []

@t
def too_soon_says_whether_the_last_message_went():
    with school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); at("06:53", 13); ask = lambda: skips(remind(asks(i, K5)))
        # the relief itself alone: gone, or it may have, or waits, or is on its way
        for st, text in (("sent", TOO_SOON), ("unsure", TRIED), ("queued", TRIED), ("sending", TRIED)): put(key, state=st); assert ask() == [(K5, SAM, text.format("06:50"))], st
        put(key, state="unsure"); assert tell_today(i) == ("unsure", "2026-10-13T06:50:00+08:00"), "as Today says: it may not have been sent"
        # a reminder after it is the last
        put(key, state="sent"); at("06:56", 13); assert remind(asks(i, K5))["sent"] == 1; at("06:58", 13)
        for st, text in (("queued", TRIED), ("sending", TRIED), ("unsure", TRIED), ("sent", TOO_SOON)): put(key + ":r1", state=st, sent_at="2026-10-13T06:57:00+08:00" if st in ("sent", "unsure") else None); assert ask() == [(K5, SAM, text.format("06:57" if st in ("sent", "unsure") else "06:56"))], st
        # one that told nobody (failed, dropped) is not the last, so it does not say when; in the same minute as another, the later one counts
        for st in ("failed", "dropped"): put(key + ":r1", state=st); put(key, sent_at="2026-10-13T06:55:00+08:00"); assert ask() == [(K5, SAM, TOO_SOON.format("06:55"))], st
        put(key, sent_at="2026-10-13T06:57:00+08:00"); put(key + ":r1", state="unsure", sent_at="2026-10-13T06:57:00+08:00"); assert ask() == [(K5, SAM, TRIED.format("06:57"))]
    with school(SAM, TEAM):                                                                # somebody else was first (a key is queued once): what became of that one
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); at("07:00", 13); before = OB.states_for("relief:"); remind(asks(i, K5))
        for st, text in (("queued", TRIED), ("sending", TRIED), ("unsure", TRIED), ("sent", TOO_SOON), ("failed", TRIED)):
            put(key + ":r1", state=st, sent_at="2026-10-13T07:00:00+08:00")
            with stand_in(OB, "states_for", lambda *prefixes: dict(before)): assert skips(remind(asks(i, K5))) == [(K5, SAM, text.format("07:00"))], st

@t
def two_reminders_at_once_are_one():
    with school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); at("07:00", 13); got = []
        at_once(*[lambda: got.append(remind(asks(i, K5)))] * 4)
        assert sorted(g["sent"] for g in got) == [0, 0, 0, 1] and [r["key"] for r in outs("relief")] == [key, key + ":r1"] and all(skips(g) == [(K5, SAM, TRIED.format("07:00"))] for g in got if not g["sent"])
    with school(SAM, TEAM):                                                                # another copy of the app put it in the queue meanwhile
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); at("07:00", 13); before = OB.states_for("relief:"); remind(asks(i, K5))
        with stand_in(OB, "states_for", lambda *prefixes: dict(before)): assert skips(remind(asks(i, K5))) == [(K5, SAM, TRIED.format("07:00"))] and len(outs("relief")) == 2
        put(key + ":r1", state="sent", sent_at="2026-10-13T07:00:00+08:00"); links.unlink(SAM); at("07:30", 13)
        with stand_in(links, "reachable", lambda pub=None: {SAM: CHATS[SAM]}): 
            assert skips(remind(asks(i, K5))) == [(K5, SAM, NOT_ON)], "unlinked meanwhile"
            put(key, state="dropped"); put(key + ":r1", state="dropped"); assert skips(remind(asks(i, K5))) == [(K5, SAM, NOT_ON)] and state(key) == "dropped"

@t
def who_is_not_reminded_and_why():
    def skipped(f=None, covers=None, date=D13, linked=(SAM, MAYA, TEAM), hm="07:00", day=13, give_=(K5, SAM), m=exam_school):
        with m(*linked):
            i = today_reliefs(give_)
            if f: f(i)
            at(hm, day); n, h = len(outs("relief")), Since(); got = remind(covers(i) if covers else asks(i, K5), date); assert got["sent"] == 0 and len(outs("relief")) == n and h.new() == [], got
            return skips(got)
    assert skipped(linked=(MAYA, TEAM)) == [(K5, SAM, NOT_ON)]
    for f in (lambda i: CV.acknowledge(i, K5, SAM), lambda i: CV.ask_change(i, K5, "x", SAM)): assert skipped(f) == [(K5, SAM, NOBODY)]
    for f in (lambda i: absences.not_needed(i, K5, "x", HUGO), lambda i: absences.cancel(i, "x", HUGO), lambda i: os.remove(absences._path(i))): assert skipped(f) == [(K5, None, NOBODY)]
    assert skipped(give_=(K2, MAYA)) == [(K5, None, NOBODY)], "open"
    assert skipped(hm="11:30") == [(K5, SAM, NOBODY)], "over"; assert skipped(day=14) == [(K5, SAM, NOBODY)]
    assert skipped(date="2026-10-14") == [(K5, SAM, NOBODY)], "another date"
    assert skipped(lambda i: exam()) == [(K5, SAM, NOBODY)], "stopped"
    assert skipped(covers=lambda i: [dict(id="abcdef123456", ckey=K5)]) == [(K5, None, NOBODY)] and skipped(covers=lambda i: [dict(id=i, ckey="nokey")]) == [("nokey", None, NOBODY)]
    assert skipped(covers=lambda i: [dict(id=i, ckey=K5 + "#0", absent=EVE)]) == [(K5 + "#0", None, NOBODY)] and skipped(covers=lambda i: [dict(id=i, ckey=K5, absent=RUTH)]) == [(K5, None, NOBODY)]
    # given to another since the report was made: the one listed is not theirs any more
    def again(i): at("06:55", 13); give(i, K5, MAYA); swept()
    assert skipped(again, covers=lambda i: [dict(id=i, ckey=K5, absent=EVE, approved_at="2026-10-13T06:50:00+08:00")], hm="07:30") == [(K5, MAYA, NOBODY)]
    with school(SAM, MAYA, TEAM): i = today_reliefs((K5, SAM)); again(i); at("07:30", 13); assert remind(asks(i, K5))["sent"] == 1 and outs("relief")[-1]["name"] == MAYA and remind(listed(i, K5))["sent"] == 0
    # while it lasts, and while the exams cannot be read: reminded
    with exam_school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); exam(); at("11:29", 13)
        with unreadable(): assert remind(asks(i, K5))["sent"] == 1
    with school(SAM, TEAM):                                                                # moved to another absence of the same teacher's (a takeover): found there, by whatever absence it was sent for
        i = today_reliefs((K5, SAM)); moved_to(i); at("07:00", 13); assert remind(listed_ := [dict(id=i, ckey=K5, absent=EVE)])["sent"] == 1 and listed_ and send() == 1
        at("07:10", 13); assert remind([dict(id=i, ckey=K5)])["sent"] == 1 and json.loads(outs("relief")[-1]["ref"])["id"] == "dead00beef" and outs("relief")[-1]["key"].endswith(":r2")
    for bad in (None, "x", 5, {}, [None], [5], [{}], [dict(id="a")], [dict(ckey=K5)], [dict(id=5, ckey=K5)], [dict(id="", ckey=K5)], [dict(id="a", ckey="")], [dict(id="a", ckey=K5), 5]):
        with school(TEAM):
            try: remind(bad); raise AssertionError(bad)
            except ValueError as e: assert str(e) == absences.WRONG, bad
    for bad in (None, "x", 5, "13/10/2026", "2026-13-40", ["2026-10-13"]):
        with school(TEAM):
            try: RE.remind(bad, [], BY); raise AssertionError(bad)
            except ValueError as e: assert str(e) == absences.WRONG, bad
    with school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); at("07:00", 13); assert RE.remind(datetime.date(2026, 10, 13), asks(i, K5), BY)["sent"] == 1 and send() == 1 and RE.remind(D13, asks(i, K5), BY, now="2026-10-13T07:20:00+08:00")["sent"] == 1
        with no_pub():
            try: remind(asks(i, K5)); raise AssertionError()
            except ValueError as e: assert str(e) == WB.NO_PUB

@t
def a_reminder_is_the_relief_again_and_no_relief_of_its_own():
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM)); change_record(i, lambda r: [x.update(work=dict(text="Read p.4", link="", files=[dict(id="f1", name="a.pdf", size=1)])) for x in r["lessons"] if x["key"] == K5]); at("07:00", 13); remind(asks(i, K5)); r, = [x for x in outs("relief") if x["key"].endswith(":r1")]
        assert r["text"].endswith("\nWork from Ms Evelyn Koh: Read p.4\nFiles: 1, sent after this message.") and json.loads(r["files"]) == [dict(id=i, file="f1", name="a.pdf")], "the work set since"
        put(r["key"], state="sent", sent_at="2026-10-13T07:00:00+08:00"); assert TE.sweep() == 0; at("07:10", 13); give(i, K5, MAYA); swept(); swept()
        assert told_of("moved") == [("moved", SAM)] and [x["key"] for x in outs("relief", MAYA)] == [relief_key_of(i, K5)], "one moved, and her own message"
        absences.cancel(i, "Better", HUGO); swept(); assert told_of("gone") == [("gone", MAYA)]
    def copy(): r = next(x for x in outs("relief") if x["key"].endswith(":r1")); return dict(r, ref=json.loads(r["ref"]))
    for f, want in ((lambda i: None, True), (lambda i: CV.acknowledge(i, K5, SAM), False), (lambda i: CV.ask_change(i, K5, "x", SAM), False), (lambda i: give(i, K5, MAYA), False), (lambda i: absences.cancel(i, "x", HUGO), False),
                    (lambda i: absences.not_needed(i, K5, "x", HUGO), False), (lambda i: exam(), False), (lambda i: at("11:30", 13), False), (lambda i: at("11:29", 13), True), (lambda i: (at("07:05", 13), give(i, K5, SAM)), False), (lambda i: moved_to(i), True)):
        with exam_school(SAM, MAYA, TEAM): i = today_reliefs((K5, SAM)); at("07:00", 13); remind(asks(i, K5)); f(i); assert TE.still_true(copy()) is want, want; n = len(said(SAM)); send(); assert (len(said(SAM)) == n + 1) is want
    with school(SAM, MAYA, TEAM):                                                          # pressed on the reminder as on the relief
        i = today_reliefs((K5, SAM)); at("07:00", 13); remind(asks(i, K5)); send(); assert press(SAM, "ack") == ("✅ Acknowledged 07:00.", False) and state_of(i) == "acknowledged" and remind(asks(i, K5))["sent"] == 0

@t
def who_was_told_only_by_a_reminder_hears_what_becomes_of_it():
    def only_reminded():
        """Sam's relief of K5: its own message failed, the reminder went -> (the absence's id, its key); nothing said so far"""
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); put(key, state="failed"); at("07:00", 13); assert remind(asks(i, K5))["sent"] == 1 and send() == 1 and state(key + ":r1") == "sent"
        tg.PRACTICE_LOG.clear(); return i, key
    def more(): swept(); swept(); return said(SAM)
    with school(SAM, MAYA): i, key = only_reminded(); at("07:10", 13); give(i, K5, MAYA); assert more() == [MOVED_K5] and keys("moved", "gone") == [f"moved:{key}"] and said(MAYA) == [RELIEF_K5]
    with school(SAM, MAYA): i, key = only_reminded(); at("07:10", 13); absences.cancel(i, "Better", HUGO); assert more() == [GONE_K5] and keys("moved", "gone") == [f"gone:{key}"]
    with school(SAM, MAYA): i, key = only_reminded(); at("07:10", 13); absences.not_needed(i, K5, "x", HUGO); assert more() == [GONE_K5]
    for answered in (False, True):                                                         # acknowledged: the reminder itself would not go any more, these do
        with exam_school(SAM, MAYA, TEAM):
            i, key = only_reminded()
            if answered: CV.acknowledge(i, K5, SAM)
            at("07:05", 13); e = exam(); assert more() == [STOPPED_K5] and keys("stopped") == [f"stopped:{key}:0"]
            at("07:10", 13); withdraw(e); TE.sweep(); r, = outs("again"); assert (r["key"], r["text"], buttons_of(r)) == (f"again:{key}:0", AGAIN_K5, relief_buttons(i)) and "n" not in json.loads(r["ref"])
            if not answered: ticked("07:15"); assert texts_to()[-1].endswith("not told yet")
            assert more() == [STOPPED_K5, AGAIN_K5]
            if not answered: ticked("07:30"); assert texts_to()[-1].endswith("sent 07:00"), "the reminder, which is all they were told"
            at("07:40", 13); again_on(e); more(); at("07:41", 13); withdraw(e); assert more() == [STOPPED_K5, AGAIN_K5] * 2 and keys("stopped") == [f"stopped:{key}:{n}" for n in (0, 1)] and keys("again") == [f"again:{key}:{n}" for n in (0, 1)]
            at("07:45", 13); give(i, K5, MAYA); assert more() == [STOPPED_K5, AGAIN_K5] * 2 + [MOVED_K5] and [x["key"] for x in outs("relief", SAM)] == [key, key + ":r1"]
    with school(SAM, MAYA):                                                                # its own message went, and two reminders: one moved
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5)
        for hm in ("07:00", "07:10"): at(hm, 13); assert remind(asks(i, K5))["sent"] == 1 and send() == 1
        at("07:20", 13); give(i, K5, MAYA); assert more() == [RELIEF_K5] * 3 + [MOVED_K5] and keys("moved") == [f"moved:{key}"]
    with exam_school(SAM, MAYA):                                                           # its own message dropped, the reminder still in the queue: told nothing, so nothing is said
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); at("07:00", 13); remind(asks(i, K5)); put(key, state="dropped"); tg.PRACTICE_LOG.clear(); e = exam(); TE.sweep(); assert keys("stopped") == []; withdraw(e); TE.sweep(); assert keys("again") == []
        put(key, state="dropped"); at("07:10", 13); give(i, K5, MAYA); TE.sweep(); assert keys("moved", "gone") == []; absences.cancel(i, "Better", HUGO); TE.sweep(); assert keys("moved", "gone") == []; send(); assert said(SAM) == []
    # a reminder's own check is asked of reminders alone
    with exam_school(SAM, MAYA, TEAM):
        i, key = only_reminded(); ref = dict(json.loads(item(key + ":r1")["ref"])); assert ref["n"] == 1; it = lambda kind: TE.still_true(dict(kind=kind, name=SAM, ref=ref)); CV.acknowledge(i, K5, SAM); e = exam()
        assert it("relief") is False and it("stopped") is True and it("again") is False; withdraw(e); assert it("again") is True and it("stopped") is False and it("moved") is False and it("gone") is False and it("relief") is False
        give(i, K5, MAYA); assert it("moved") is True and it("gone") is True and it("again") is False

@t
def the_page_reminds_and_the_history_says_so():
    URL = "/api/relief/today/remind"
    with school(SAM, MAYA, TEAM, EVE):
        i = today_reliefs((K5, SAM), (K2, MAYA)); body = dict(date=D13, covers=[dict(id=i, ckey=K5), dict(id=i, ckey=K2), dict(id=i, ckey=K8)]); h = Since()
        got = call(TEAM, "post", URL, body); assert got == dict(sent=0, skipped=[dict(ckey=K5, name=SAM, why=TOO_SOON.format("06:50")), dict(ckey=K2, name=MAYA, why=TOO_SOON.format("06:50")), dict(ckey=K8, name=None, why=NOBODY)]) and h.new() == [], got
        at("07:00", 13); assert call(TEAM, "post", URL, body) == dict(sent=2, skipped=[dict(ckey=K8, name=None, why=NOBODY)]) and h.new() == [(TEAM, TEAM, "code", "reminded", "Reminded 2 relief teachers on Tue 13 Oct", None)]
        assert len([r for r in outs("relief") if r["key"].endswith(":r1")]) == 2 and send() == 2
        at("07:10", 13); call(LEE, "post", URL, dict(date=D13, covers=[dict(id=i, ckey=K5)])); assert h.new() == [(LEE, LEE, "code", "reminded", "Reminded 1 relief teacher on Tue 13 Oct", None)]
        # the relief team's alone
        was = len(outs())
        for name in (SAM, EVE, HUGO, MAYA): assert call(name, "post", URL, body, code=403) == dict(error=WB.TEAM_ONLY)
        assert client(None).post(URL, json=body).status_code in (302, 401) and client(dict(role="committee")).post(URL, json=body).status_code == 401
        # a body that is not what the page sends
        for bad in ({}, [], None, "x", dict(date=D13), dict(covers=body["covers"]), dict(date="13/10/2026", covers=[]), dict(date=5, covers=[]), dict(date=D13, covers="x"), dict(date=D13, covers={}), dict(date=D13, covers=[5]), dict(date=D13, covers=[dict(id=i)]),
                    dict(date=D13, covers=[dict(id=[i], ckey=K5)]), dict(date=D13, covers=[dict(id=i, ckey=K5), None])):
            r = who(TEAM).post(URL, json=bad); assert r.status_code == 400 and r.get_json() == dict(error=absences.WRONG), (bad, r.get_data(as_text=True)[:200])
        assert who(TEAM).post(URL, data=b"{ not json").status_code == 400 and call(TEAM, "post", URL, dict(date=D13, covers=[])) == dict(sent=0, skipped=[])
        # only what the page sends is read: who and when it was approved are the app's own
        send(); at("07:20", 13); assert call(TEAM, "post", URL, dict(date=D13, covers=[dict(id=i, ckey=K5, absent=RUTH, approved_at="x", who=HUGO)]))["sent"] == 1 and outs("relief")[-1]["name"] == SAM; h.new()
        for other in ("2026-10-12", "2026-10-14", "1999-01-01"): assert call(TEAM, "post", URL, dict(date=other, covers=body["covers"][:1])) == dict(sent=0, skipped=[dict(ckey=K5, name=SAM, why=NOBODY)])
        was = len(outs()); tgdb.set_state("bot", None); assert call(TEAM, "post", URL, body, code=409) == dict(error=tgweb.NOT_CONNECTED) and len(outs()) == was and h.new() == []
    with school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); at("07:00", 13)
        with no_pub(): call(TEAM, "post", URL, dict(date=D13, covers=[dict(id=i, ckey=K5)]), code=409)
        def lost(*a, **k): raise RuntimeError("made up")
        with stand_in(history, "add", lost): assert call(TEAM, "post", URL, dict(date=D13, covers=[dict(id=i, ckey=K5)]))["sent"] == 1, "a history entry that cannot be made never fails it"
    with school(SAM, TEAM):                                                                # one teacher, two reliefs: two messages, one teacher
        i = today_reliefs((K5, SAM), (K2, SAM)); at("07:00", 13); h = Since(); assert remind(asks(i, K2, K5))["sent"] == 2 and h.new() == [(TEAM, TEAM, "telegram", "reminded", "Reminded 1 relief teacher on Tue 13 Oct", None)]
    with school(SAM, MAYA, TEAM):                                                          # the store fails half-way: what was put in the queue is written down, and it is not said to be done
        i = today_reliefs((K5, SAM), (K2, MAYA)); at("07:00", 13); real, h = OB.queue, Since()
        def half(key, name, *a, **k):
            if name == MAYA: raise sqlite3.OperationalError("made up")
            return real(key, name, *a, **k)
        with stand_in(OB, "queue", half):
            try: remind(asks(i, K5, K2)); raise AssertionError("said to be done")
            except sqlite3.OperationalError: pass
        assert [x[4] for x in h.new()] == ["Reminded 1 relief teacher on Tue 13 Oct"] and len(outs("relief")) == 3
        lg = Grab(); KINDS.addHandler(lg)
        def private(*a, **k): raise LookupError(f"{MAYA} a private line")
        with stand_in(OB, "queue", private): assert skips(remind(asks(i, K2))) == [(K2, MAYA, NOBODY)], "one that cannot be made"
        KINDS.removeHandler(lg); assert [r.getMessage() for r in lg.records] == ["a reminder could not be made (LookupError)"] and lg.records[0].exc_info is None

@t
def remind_them_again_on_telegram():
    with school(SAM, MAYA, TEAM, LEE, EVE, HUGO):
        i = today_reliefs((K2, MAYA), (K5, SAM)); ticked("07:00"); send(); h, n = Since(), len(edits()); m = under(tok(TEAM, "remind"))
        assert press(TEAM, "remind") == ("Reminded 2.", False) and h.new() == [(TEAM, TEAM, "telegram", "reminded", "Reminded 2 relief teachers on Tue 13 Oct", None)]
        assert [r["key"] for r in outs("relief")][-2:] == [relief_key_of(i, K2) + ":r1", relief_key_of(i, K5) + ":r1"] and edits() == [] and calls("editMessageReplyMarkup") == [], "its message stays as it is"
        assert press(LEE, "remind") == (TRIED.format("07:00"), True) == press(TEAM, "remind") and h.new() == [] and edits() == [] and calls("editMessageReplyMarkup") == []
        send(); assert said(SAM) == [RELIEF_K5] * 2 and m
        at("07:10", 13); CV.acknowledge(i, K2, MAYA); assert press(TEAM, "remind") == ("Reminded 1.", False); send(); assert len(said(SAM)) == 3 and len(said(MAYA)) == 2
        at("07:20", 13); CV.acknowledge(i, K5, SAM); assert press(LEE, "remind") == (NOBODY, True) and edits() == [] and h.new()[-1][0] == TEAM
        # not one's own, and not without the right at that moment
        was = len(outs())
        for other in (SAM, EVE, HUGO, LEE): assert press(TEAM, "remind", chat=CHATS[other]) == (NOT_YOURS_BUTTON, True)
        with record(TEAM, extras=dict(relief=False, exams=None, admin=False)): assert press(TEAM, "remind") == (NOT_YOURS_BUTTON, True)
        with record(TEAM, off=True): assert press(TEAM, "remind") == (NOT_LINKED, True)
        button(tok(TEAM, "remind"), until=0); assert press(TEAM, "remind") == (OLD_BUTTON, True) and len(outs()) == was and edits() == [] and bot.ACTIONS["remind"][0] == "relief.team"
    with school(SAM, TEAM):                                                                # refused whatever it is for: the buttons stay
        i = today_reliefs((K5, SAM)); ticked("07:00"); send(); links.unlink(SAM); at("07:10", 13); assert press(TEAM, "remind") == (NOT_ON, True)
        with no_pub(): assert press(TEAM, "remind") == (WB.NO_PUB, True)
        with stand_in(RE, "remind", lambda *a, **k: 1 / 0): assert press(TEAM, "remind") == (WENT_WRONG, True)
        for extra in ("null", "{}", "[]", '{"date": "x", "covers": []}', '{"date": "2026-10-13", "covers": [5]}'): button(tok(TEAM, "remind"), extra=extra); assert press(TEAM, "remind") == (absences.WRONG, True), extra
        button(tok(TEAM, "remind"), extra='{"date": "2026-10-13", "covers": []}'); assert press(TEAM, "remind") == (NOBODY, True)
        assert edits() == [] and calls("editMessageReplyMarkup") == []; at("08:00", 14); assert press(TEAM, "remind")[0] == NOBODY, "yesterday's report"
    with school(SAM, MAYA, TEAM):                                                          # those it listed, and only while they are theirs
        i = today_reliefs((K2, MAYA), (K5, SAM)); ticked("07:00"); send(); at("07:10", 13); give(i, K5, HUGO); links.link(HUGO, CHATS[HUGO], None); swept(); at("07:30", 13); assert press(TEAM, "remind") == ("Reminded 1.", False) and [r["name"] for r in outs("relief") if r["key"].endswith(":r1")] == [MAYA]
        on_lesson(EVE, i, K8, "needed"); give(i, K8, SAM); swept(); at("07:40", 13); assert press(TEAM, "remind") == ("Reminded 1.", False), "not one approved since"
    with school(SAM, TEAM):                                                                # nothing is held, and all is written down, before the press is answered
        i = today_reliefs((K5, SAM)); ticked("07:00"); send(); real, seen, n = tg.call, [], len(entries())
        def spy(method, params=None, **kw): seen.append((method, len(entries()) - n, absences._LOCK.locked(), bot._pressing.locked(), bot._counting.locked())); return real(method, params, **kw)
        with stand_in(tg, "call", spy): press(TEAM, "remind")
        assert seen == [("answerCallbackQuery", 1, False, False, False)], seen

# ---- Today's rows
@t
def today_rows_say_when_it_was_told_and_if_not_on_telegram():
    def row(ckey=K5, name=TEAM):
        v = next(v for v in call(name, "get", f"/api/relief/today?date={D13}")["rows"] if v["ckey"] == ckey); return v["told"], v["linked"]
    with school(MAYA, TEAM):
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); assert row() == (None, False) and row(K2) == (None, False), "not on Telegram; open"
        links.link(SAM, CHATS[SAM], None); assert row() == (None, True); TE.sweep(); assert row() == (dict(state="queued", at=clock.now), True)
        at("06:58", 13); send(); assert row() == (dict(state="sent", at="2026-10-13T06:58:00+08:00"), True)
        for s in ("unsure", "failed", "dropped"): put(key, state=s); assert row()[0]["state"] == s, s
        put(key, state="sending"); assert row()[0]["state"] == "queued"; put(key, state="sent")
        # the last of it and its reminders
        at("07:10", 13); remind(asks(i, K5)); assert row()[0] == dict(state="queued", at="2026-10-13T07:10:00+08:00"); put(key + ":r1", state="failed"); assert row()[0] == dict(state="failed", at="2026-10-13T07:10:00+08:00")
        put(key + ":r1", state="dropped"); assert row()[0] == dict(state="sent", at="2026-10-13T06:58:00+08:00"), "as if it had never been"; put(key + ":r1", state="sent", sent_at="2026-10-13T07:11:00+08:00"); assert row()[0] == dict(state="sent", at="2026-10-13T07:11:00+08:00")
        # whatever was answered; another's, and approved anew, from the start
        CV.acknowledge(i, K5, SAM); assert row()[0]["state"] == "sent"; CV.ask_change(i, K5, "x", SAM); assert row()[0]["state"] == "sent"
        at("07:20", 13); give(i, K5, MAYA); assert row() == (None, True); swept(); assert row()[0] == dict(state="sent", at=clock.now); links.unlink(MAYA); assert row() == (dict(state="sent", at=clock.now), False), "told, and not reached any more"
        absences.not_needed(i, K5, "x", HUGO); assert all(v["ckey"] != K5 for v in call(TEAM, "get", f"/api/relief/today?date={D13}")["rows"])
    with school(SAM, TEAM):                                                                # a pick nobody has approved: nobody told, and whether they could be
        at("06:50", 13); i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM), dict(key=K2, relief=MAYA)]); assert row() == (None, True) and row(K2) == (None, False); absences.cancel(i, "x", HUGO)
        assert all((v["state"], v["told"], v["linked"]) == ("cancelled", None, False) for v in call(TEAM, "get", f"/api/relief/today?date={D13}")["rows"])
    with exam_school(SAM, TEAM):                                                           # stopped: nothing; stood again, and not sure to have been told so: nothing
        i = today_reliefs((K5, SAM)); e = exam(); assert row() == (None, True); swept(); assert row() == (None, True); withdraw(e); assert row()[0] is None; TE.sweep(); again = outs("again")[0]["key"]
        for s in ("queued", "unsure", "failed"): put(again, state=s); assert row()[0] is None, s
        put(again, state="sent"); assert row()[0] == dict(state="sent", at="2026-10-13T06:50:00+08:00"); put(again, state="failed"); at("07:00", 13); remind(asks(i, K5)); assert row()[0] == dict(state="queued", at=clock.now); send(); assert row()[0] == dict(state="sent", at=clock.now)
    with school(SAM, MAYA, TEAM):                                                          # read once a request, however many absences and rows
        i = today_reliefs((K5, SAM), (K2, MAYA)); absent(teacher=RUTH); reads = []
        def counted(f, name): return lambda *a, **k: (reads.append(name), f(*a, **k))[1]
        with stand_in(links, "reachable", counted(links.reachable, "reach")), stand_in(OB, "states_for", counted(OB.states_for, "said")): assert row()[0]["state"] == "sent" == row(K2)[0]["state"]
        assert sorted(reads) == ["reach", "reach", "said", "said"], reads
        # Telegram's side never fails the page
        for module, name in ((links, "reachable"), (OB, "states_for"), (tgdb, "db")):
            with quiet_app(), stand_in(module, name, lambda *a, **k: 1 / 0): assert row() == (None, False), name
        os.environ.pop("TELEGRAM_BOT_TOKEN")
        opened = []
        with stand_in(tgdb, "db", lambda read=False: opened.append(1)): assert row() == (None, False) and opened == [], "no token: the store is not opened"
        os.environ["TELEGRAM_BOT_TOKEN"] = "practice"; assert row()[1] is True

@t
def today_says_whether_the_bot_is_connected():
    def day_(name=TEAM): return call(name, "get", f"/api/relief/today?date={D13}")
    with school(SAM, TEAM):
        i = today_reliefs((K5, SAM)); got = day_(); assert got["telegram"] is True and set(got) == {"date", "filling", "counts", "rows", "telegram"}, set(got)
        assert call(TEAM, "get", "/api/relief/today?date=2026-10-20")["telegram"] is True and call(TEAM, "get", "/api/relief/today?date=2026-10-20")["rows"] == [], "a day with nothing on it too"
        bot_ = tgdb.get_state("bot"); tgdb.set_state("bot", None); got = day_(); assert got["telegram"] is False and next(v for v in got["rows"] if v["ckey"] == K5)["linked"] is True, "a token, and not connected: what the rows say is not shown"
        for odd in ("x", dict(bot_, key=digest("another")), dict(bot_, username="")): tgdb.set_state("bot", odd); assert day_()["telegram"] is False, odd
        tgdb.set_state("bot", bot_); assert day_()["telegram"] is True
        real = os.environ.pop("SECRET_KEY")
        try:
            with A.app.test_request_context(): assert WB._connected() is False
        finally: os.environ["SECRET_KEY"] = real
        os.environ["TELEGRAM_BOT_TOKEN"] = "made-up-" + secrets.token_hex(10); assert day_()["telegram"] is False, "connected under another token"; os.environ["TELEGRAM_BOT_TOKEN"] = "practice"
        errs = []
        for e in (sqlite3.OperationalError, KeyError, OSError):                                # never the page's failure, and its kind alone is written down
            def boom(*a, **k): raise e(f"{SAM} a private line")
            with stand_in(links, "connected", boom), stand_in(A.app.logger, "error", lambda *a: errs.append(a)): got = day_()
            assert got["telegram"] is False and next(v for v in got["rows"] if v["ckey"] == K5)["told"]["state"] == "sent", e
        assert [a[1:] for a in errs] == [("OperationalError",), ("KeyError",), ("OSError",)] and SAM not in str(errs), errs
        with quiet_app(), stand_in(tgdb, "db", lambda *a, **k: 1 / 0): assert day_()["telegram"] is False
        text = json.dumps(day_()); assert all(x not in text for x in (BASE, "practice_bot", digest(tg.hook_secret()), str(CHATS[SAM]))), "whether, and no more"
        os.environ.pop("TELEGRAM_BOT_TOKEN"); opened = []
        with stand_in(tgdb, "db", lambda read=False: opened.append(1)): assert day_()["telegram"] is False and opened == [], "no token: the store is not opened"
        os.environ["TELEGRAM_BOT_TOKEN"] = "practice"; assert day_()["telegram"] is True
        for name, code in ((HUGO, 403), (SAM, 403)): assert "telegram" not in call(name, "get", f"/api/relief/today?date={D13}", code=code), name

@t
def the_telegram_pages_are_there():
    read = lambda f: open(os.path.join(ROOT, "static", f), encoding="utf-8").read()
    html, js, card, sets, sets_html = read("relief.html"), read("relief.js"), read("relief-telegram.js"), read("relief-settings.js"), read("relief-settings.html")
    assert html.count('<script src="/static/relief-telegram.js"></script>') == 1 and html.index("/static/relief.js") < html.index("/static/relief-telegram.js")
    assert '<div id="mineTelegram"></div><div id="mineList"></div>' in js and "R.linkCard(" in card and '"/api/relief/telegram"' in card
    for word in ("localStorage", "sessionStorage", "indexedDB", "cookie", "location", "history.", "console.", "eval(", "//cdn", "http://"): assert word not in card, word
    assert card.count("https://") == 1 and 'startsWith("https://")' in card and 'addEventListener("pagehide"' in card and 'addEventListener("pageshow"' in card
    assert 'id="telegram"' in sets_html and "/api/relief/telegram/admin" in sets and "docs/DEPLOY.md" in sets
    for word in ("api.telegram.org", "//t.me"): assert all(word not in x for x in (html, js, card, sets, sets_html)), word

# ---- Task 6, fix round 1
KR = next(x["key"] for x in LS.on_date(SCHOOL, TERM, RUTH, datetime.date(2026, 10, 13)) if x["p"] == 6)

@t
def the_answer_is_the_first_reason_that_says_something():
    def answer(f, linked=(SAM, MAYA, TEAM)):
        """what the button of a report that lists Maya's relief, then Sam's, is answered after f"""
        with school(*linked):
            i = today_reliefs((K2, MAYA), (K5, SAM)); ticked("07:00"); send(); f(i); got = press(TEAM, "remind"); assert edits() == [] and calls("editMessageReplyMarkup") == [], got
            return got
    def acked(i, ckey, who_): CV.acknowledge(i, ckey, who_)
    def reminded(i, ckey): at("07:10", 13); assert remind(asks(i, ckey))["sent"] == 1; at("07:11", 13)
    assert answer(lambda i: (acked(i, K2, MAYA), reminded(i, K5))) == (TRIED.format("07:10"), True)
    assert answer(lambda i: (acked(i, K5, SAM), reminded(i, K2))) == (TRIED.format("07:10"), True)
    assert answer(lambda i: (acked(i, K2, MAYA), links.unlink(SAM), at("07:10", 13))) == (NOT_ON, True)
    assert answer(lambda i: (acked(i, K2, MAYA), acked(i, K5, SAM), at("07:10", 13))) == (NOBODY, True)
    assert answer(lambda i: (links.unlink(MAYA), reminded(i, K5))) == (NOT_ON, True) and answer(lambda i: (links.unlink(SAM), reminded(i, K2))) == (TRIED.format("07:10"), True), "the first of them"
    assert answer(lambda i: (acked(i, K2, MAYA), at("07:10", 13))) == ("Reminded 1.", False)
    assert bot.ACTIONS["remind"][2] is bot.ANY and not isinstance(bot.ANY, (tuple, str)) and [k for k, v in bot.ACTIONS.items() if v[2] is bot.ANY] == ["remind", "ask"]
    with school(SAM, TEAM):                                                                # whatever the sentence looks like
        today_reliefs((K5, SAM)); ticked("07:00"); send()
        for text in ("{why}", "a {name} {", "x"):
            def says(*a, **k): raise ValueError(text)
            with stand_in(RE, "remind", says): assert press(TEAM, "remind") == (text, True) and edits() == []

@t
def no_all_clear_while_something_cannot_be_read():
    def two():
        """a report at 07:00 of Sam's relief (for Eve) and Maya's (for Ruth), then Sam acknowledged -> Ruth's absence"""
        i = today_reliefs((K5, SAM)); j = absent(teacher=RUTH, by=HUGO); give(j, KR, MAYA); swept(); assert ticked("07:00") == keyed("0700") and texts_to()[-1].startswith(head("07:00", 2)) and send() == 1; CV.acknowledge(i, K5, SAM); return j
    for bad in ("{ not json", "[]", "{}", "", '{"id": "another"}'):                          # its file
        with school(SAM, MAYA, TEAM):
            j = two(); p = absences._path(j); good = open(p, encoding="utf-8").read(); open(p, "w", encoding="utf-8").write(bad)
            assert ticked("07:15") == [] and tgdb.get_state(f"report_last:{D13}") == 435 and ticked("07:16") == [], bad
            assert ticked("07:30") == [] and outs("clear") == []; open(p, "w", encoding="utf-8").write(good); CV.acknowledge(j, KR, MAYA); assert ticked("07:45") == cleared(1) and texts_to()[-1] == all_clear("07:45", 2), bad
    def odd(f): return lambda r: [f(x) for x in r["lessons"] if x["key"] == KR]
    covers_ = [odd(f) for f in (lambda x: x.update(relief=5), lambda x: x.update(approved=5), lambda x: x.update(p="a"), lambda x: x.update(p=None), lambda x: x.update(subject=5), lambda x: x.update(parts=5), lambda x: x.update(parts=[5]), lambda x: x.pop("key"), lambda x: x.pop("date"), lambda x: x.update(date=None))]
    lessons_ = [lambda r: r["lessons"].insert(0, 5), lambda r: r["lessons"].append(None), lambda r: r.update(lessons="x"), lambda r: r.update(lessons=5), lambda r: r.update(lessons=dict(a=1))]
    for n, f in enumerate(covers_ + lessons_):                                             # a cover, or a lesson (of any date, that cannot be read), of it
        with school(SAM, MAYA, TEAM):
            j = two(); p = absences._path(j)
            if n >= len(covers_): CV.acknowledge(j, KR, MAYA)                              # the odd one alone is left
            good = open(p, encoding="utf-8").read(); change_record(j, f); assert ticked("07:15") == [] and tgdb.get_state(f"report_last:{D13}") == 435, n
            open(p, "w", encoding="utf-8").write(good)
            if n < len(covers_): CV.acknowledge(j, KR, MAYA)
            assert ticked("07:30") == cleared(1) and texts_to()[-1] == all_clear("07:30", 2), n
    # what could be read is reported; the waiting cover after an odd one too
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM)); j = absent(teacher=RUTH, by=HUGO); give(j, KR, MAYA); open(absences._path(j), "w", encoding="utf-8").write("{ not json"); assert ticked("07:00") == keyed("0700") and texts_to()[-1] == head("07:00", 1) + SAM_LINE + "sent 06:50"
    for f in (lambda x: x.update(approved=5), lambda x: x.update(relief=5), lambda x: x.update(p="a")):
        with school(SAM, MAYA, TEAM):
            i = today_reliefs((K2, MAYA), (K5, SAM)); change_record(i, lambda r: [f(x) for x in r["lessons"] if x["key"] == K2]); assert ticked("07:00") == keyed("0700") and texts_to()[-1] == head("07:00", 1) + SAM_LINE + "sent 06:50"
            CV.acknowledge(i, K5, SAM); assert ticked("07:15") == [], "no all clear: Maya's cannot be read"
    with school(SAM, RUTH, MAYA, TEAM):                                                    # a part of a split lesson
        at("06:50", 13); i = absent(by=HUGO); CV.split(i, K2, 3, TEAM); give(i, K2 + "#0", MAYA); give(i, K2 + "#1", RUTH); swept(); change_record(i, lambda r: [x["parts"][0].update(relief=5) for x in r["lessons"] if x["key"] == K2])
        assert ticked("07:00") == keyed("0700") and texts_to()[-1] == head("07:00", 1) + "\n• Ms Ruth Goh · 1C Science P4–P5 · starts 09:30 · sent 06:50"
    # what is not today's, or is not to be covered, holds nothing up
    for f in (lambda r: (r.update(cancelled=dict(by=HUGO, at=clock.now)), r["lessons"].append(5)), odd(lambda x: x.update(needed=False, relief=5, approved=5))):
        with school(SAM, MAYA, TEAM): j = two(); change_record(j, f); assert ticked("07:15") == cleared(1) and texts_to()[-1] == "✅ 07:15 · The 1 relief for today is acknowledged."
    with school(SAM, MAYA, TEAM):
        j = two(); CV.acknowledge(j, KR, MAYA); change_record(j, lambda r: r["lessons"].append(dict(date="2026-10-14", key="k", needed=True, relief=5, approved=5, parts=5))); assert ticked("07:15") == cleared(1) and texts_to()[-1] == all_clear("07:15", 2)
    # read whole, under the lock (a takeover is two saves), and nothing private is logged; no absence ever sent is no failure
    h, seen, real = Grab(), [], TE._records; KINDS.addHandler(h)
    with school(TEAM): assert not os.path.isdir(absences.DIR) and ticked("07:00") == [] and tgdb.get_state(f"report_last:{D13}") == 420 and h.records == []
    with school(SAM, MAYA, TEAM):
        j = two(); change_record(j, odd(lambda x: x.update(relief=5, subject="a private word")))
        with stand_in(TE, "_records", lambda: (seen.append(absences._LOCK.locked()), real())[1]): ticked("07:15")
        assert seen == [True] and not absences._LOCK.locked()
    KINDS.removeHandler(h); assert h.records and all(r.getMessage().endswith(")") and "private" not in r.getMessage() and RUTH not in r.getMessage() and r.exc_info is None for r in h.records)

@t
def a_started_relief_is_listed_again_when_its_report_never_went():
    R9 = f"report:{D13}:0900:{TEAM}"
    def listed_at(hm): ticked(hm); return texts_to()[-1] if STARTED in texts_to()[-1] else None
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K2, MAYA), (K5, SAM)); key = f"started:{relief_key_of(i, K2)}"; assert listed_at("09:00") == head("09:00", 1) + SAM_LINE + "sent 06:50" + STARTED + MAYA_STARTED and tgdb.get_state(key) == 540
        assert listed_at("09:15") is None and tgdb.get_state(key) == 540, "it may still go"; at("09:30", 13); assert send() == 1 and state(R9) == "dropped"
        assert listed_at("09:30") == head("09:30", 1) + SAM_LINE + "sent 06:50" + STARTED + MAYA_STARTED and tgdb.get_state(key) == 570 and send() == 1
        for hm in ("09:45", "10:00", "10:15"): assert listed_at(hm) is None, hm
    for s, again in (("queued", 0), ("sending", 0), ("sent", 0), ("unsure", 0), ("failed", 1), ("dropped", 1)):
        with school(SAM, MAYA, TEAM): today_reliefs((K2, MAYA), (K5, SAM)); ticked("09:00"); put(R9, state=s); assert bool(listed_at("09:15")) == bool(again), s
    for a, b, again in (("sent", "dropped", 0), ("failed", "unsure", 0), ("dropped", "queued", 0), ("dropped", "failed", 1)):      # any copy of it
        with school(SAM, MAYA, TEAM, LEE): today_reliefs((K2, MAYA), (K5, SAM)); ticked("09:00"); put(R9, state=a); put(R9.replace(TEAM, LEE), state=b); assert bool(listed_at("09:15")) == bool(again), (a, b)
    with school(SAM, MAYA, TEAM):                                                          # the only one it went to blocked the bot: there is no such message any more
        today_reliefs((K2, MAYA), (K5, SAM)); ticked("09:00")
        with tgdb.db() as c: c.execute("DELETE FROM outbox WHERE key=?", (R9,))
        assert listed_at("09:15")
    def dies(*a, **k): raise Killed()
    for f in (dies, lambda *a, **k: False, lambda *a, **k: 1 / 0):                          # it stopped between the mark and the queue; nobody's could be queued
        with school(SAM, MAYA, TEAM):
            i = today_reliefs((K2, MAYA), (K5, SAM))
            with stand_in(OB, "queue", f):
                try: ticked("09:00")
                except Killed: pass
            assert tgdb.get_state(f"started:{relief_key_of(i, K2)}") == 540 and outs("report") == [] and listed_at("09:15")
    with school(SAM, MAYA, TEAM):                                                          # as it was kept before marks: listed; and another day's report of that time is not this one
        i = today_reliefs((K2, MAYA), (K5, SAM)); tgdb.set_state(f"started:{relief_key_of(i, K2)}", True); assert listed_at("09:00") is None
        for odd in ("x", [540], dict(a=1)):                                                # changed by hand: said once more
            tgdb.set_state(f"started:{relief_key_of(i, K2)}", odd); tgdb.set_state(f"report_last:{D13}", 525)
            with tgdb.db() as c: c.execute("DELETE FROM outbox WHERE kind='report'")
            assert listed_at("09:00") and tgdb.get_state(f"started:{relief_key_of(i, K2)}") == 540, odd
        tgdb.set_state(f"started:{relief_key_of(i, K2)}", 540); put(R9, state="dropped"); OB.queue(f"report:2026-10-12:0900:{TEAM}", TEAM, "x", kind="report", ref=dict(date="2026-10-12", mark=540, made=clock.now)); assert listed_at("09:15")
    with school(SAM, MAYA, TEAM):                                                          # acknowledged since: not again; nothing waiting: the report of it first, then the all clear
        i = today_reliefs((K2, MAYA), (K5, SAM)); ticked("09:00"); put(R9, state="dropped"); CV.acknowledge(i, K2, MAYA); assert listed_at("09:15") is None
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K2, MAYA)); ticked("08:45"); ticked("09:00"); put(R9, state="dropped"); assert listed_at("09:15") == head("09:15", 0) + STARTED + MAYA_STARTED and ticked("09:30") == cleared(1) and texts_to()[-1] == none_waits("09:30", 1)

@t
def an_older_report_never_follows_a_newer_one():
    R = lambda hhmm, name=TEAM: f"report:{D13}:{hhmm}:{name}"
    def true(key): r = item(key); return TE.still_true(dict(r, ref=json.loads(r["ref"])))
    with school(SAM, TEAM, LEE):
        today_reliefs((K5, SAM)); ticked("07:00"); ticked("07:15"); assert send() == 2 and [state(R("0700", n)) for n in (TEAM, LEE)] == ["dropped"] * 2 and [x.split("\n")[0] for x in said(TEAM)] == [head("07:15", 1)] == [x.split("\n")[0] for x in said(LEE)]
    for s, goes in (("queued", False), ("sending", False), ("sent", False), ("unsure", False), ("failed", True), ("dropped", True)):
        with school(SAM, TEAM, LEE):
            today_reliefs((K5, SAM)); ticked("07:00"); ticked("07:15"); put(R("0715"), state=s); assert true(R("0700")) is goes and true(R("0715", LEE)) is True, s
            with tgdb.db() as c: c.execute("DELETE FROM outbox WHERE key=?", (R("0715"),))
            assert true(R("0700")) is True and true(R("0700", LEE)) is False, "another's does not count"
    with school(SAM, TEAM):                                                                # the all clear; and a report after it
        i = today_reliefs((K5, SAM)); ticked("07:00"); CV.acknowledge(i, K5, SAM); assert ticked("07:15") == cleared(1) and true(R("0700")) is False and send() == 1 and said(TEAM) == ["✅ 07:15 · The 1 relief for today is acknowledged."] and state(R("0700")) == "dropped"
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM)); ticked("07:00"); send(); CV.acknowledge(i, K5, SAM); assert ticked("07:15") == cleared(1); give(i, K2, MAYA); swept_ = TE.sweep(); assert ticked("07:30") == keyed("0730") and swept_
        assert true(cleared(1)[0]) is False and true(R("0730")) is True; put(R("0730"), state="dropped"); assert true(cleared(1)[0]) is True
        OB.queue(f"report:2026-10-14:2300:{TEAM}", TEAM, "x", kind="report", ref=dict(date="2026-10-14", mark=1380, made=clock.now)); assert true(cleared(1)[0]) is True, "another day's"

@t
def a_row_that_cannot_be_worked_out_never_fails_today():
    def rows_(): return {v["ckey"]: v for v in call(TEAM, "get", f"/api/relief/today?date={D13}")["rows"]}
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM), (K2, MAYA)); errs = []; change_record(i, lambda r: [x.update(approved=5) for x in r["lessons"] if x["key"] == K5])
        with stand_in(A.app.logger, "error", lambda *a: errs.append(a)): got = rows_()
        assert (got[K5]["state"], got[K5]["told"], got[K5]["linked"]) == ("approved", None, True) and (got[K2]["told"], got[K2]["linked"]) == (dict(state="sent", at="2026-10-13T06:50:00+08:00"), True), got
        assert [a[1:] for a in errs] == [("AttributeError",)] and SAM not in str(errs), errs
    with exam_school(SAM, MAYA, TEAM):                                                     # a relief that is no name, of a lesson that is stopped
        i = today_reliefs((K5, SAM), (K2, MAYA)); exam(); change_record(i, lambda r: [x.update(relief=["x"]) for x in r["lessons"] if x["key"] == K5]); got = rows_()
        assert (got[K5]["state"], got[K5]["told"], got[K5]["linked"]) == ("stopped", None, False) and got[K2]["linked"] is True

@t
def a_reminder_that_fails_on_the_page_is_answered_plainly():
    URL, SAY = "/api/relief/today/remind", "Telegram could not be reached just now. Try again."
    def locked(*a, **k): raise sqlite3.OperationalError(f"{SAM} a private line")
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM), (K2, MAYA)); at("07:00", 13); body = dict(date=D13, covers=[dict(id=i, ckey=K5), dict(id=i, ckey=K2)]); h, apps = Grab(), []; KINDS.addHandler(h)
        for e in (TypeError, KeyError, AttributeError):
            def odd(*a, **k): raise e(f"{SAM} a private line")
            with stand_in(RE, "remind", odd), stand_in(A.app.logger, "exception", lambda *a, **k: apps.append(a)): assert call(TEAM, "post", URL, body, code=400) == dict(error=absences.WRONG)
        for module, name in ((RE, "remind"), (links, "connected"), (OB, "queue"), (OB, "states_for")):
            with stand_in(module, name, locked): assert call(TEAM, "post", URL, body, code=503) == dict(error=SAY), name
        KINDS.removeHandler(h); assert apps == [] and len(h.records) == 7 and all("private" not in r.getMessage() and SAM not in r.getMessage() and r.exc_info is None for r in h.records) and [r.getMessage().split("(")[-1] for r in h.records] == ["TypeError)", "KeyError)", "AttributeError)"] + ["OperationalError)"] * 4
        # one was put in the queue before it failed: written down, and pressed again it is not sent twice
        real, n, ent = OB.queue, len(outs("relief")), Since()
        with stand_in(OB, "queue", lambda key, name, *a, **k: locked() if name == MAYA else real(key, name, *a, **k)): assert call(TEAM, "post", URL, body, code=503) == dict(error=SAY)
        assert len(outs("relief")) == n + 1 and [x[4] for x in ent.new()] == ["Reminded 1 relief teacher on Tue 13 Oct"]
        assert call(TEAM, "post", URL, body) == dict(sent=1, skipped=[dict(ckey=K5, name=SAM, why=TRIED.format("07:00"))]) and len(outs("relief")) == n + 2
    with school(SAM, TEAM):                                                                # on Telegram: the app's general words, and the button stays
        today_reliefs((K5, SAM)); ticked("07:00"); send()
        with stand_in(OB, "queue", locked): at("07:10", 13); assert press(TEAM, "remind") == (WENT_WRONG, True) and edits() == []

@t
def what_was_said_is_read_without_what_it_holds():
    with school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM), (K2, MAYA)); key = relief_key_of(i, K5); both = {relief_key_of(i, k): dict(state="sent", at="2026-10-13T06:50:00+08:00", name=n) for k, n in ((K5, SAM), (K2, MAYA))}
        assert OB.states_for("relief:", "stopped:") == both and OB.states_for() == {} and OB.states_for("stopped:") == {} and OB.states_for("%") == {} and OB.states_for("relie_:") == {} and OB.states_for(key) == {key: both[key]}
        for s in ("queued", "sending", "sent", "unsure", "failed", "dropped"):                  # the same as told says
            put(key, state=s, at="2026-10-13T06:40:00+08:00", sent_at="2026-10-13T06:50:00+08:00"); got = OB.states_for("relief:")[key]
            assert got == {k: OB.told(key)[k] for k in ("state", "at", "name")} == dict(state=s, at=f"2026-10-13T06:{50 if s in ('sent', 'unsure') else 40}:00+08:00", name=SAM), s
        put(key, state="sent", ref="{ not json", buttons="x", text=None); assert TE.said().sent_at(key) and TE.said().of(key) == dict(state="sent", at="2026-10-13T06:50:00+08:00")
        with stand_in(OB, "told_for", lambda prefix: 1 / 0): assert TE.said().of(key)["state"] == "sent"

# ---- Task 6b: main's stopped lessons: what a stopped one is answered, a date that cannot be read, a lesson stopped when its absence was sent ----
NOT_ON_K5 = f"This lesson is not happening: 1A, 1B are on {EXAM}."
D14 = "2026-10-14"
PLANNED_N = lambda n: PLANNED_EVE.replace("2 lessons will be covered.\n", {0: "", 1: "1 lesson will be covered.\n"}.get(n, f"{n} lessons will be covered.\n"))

@contextlib.contextmanager
def damage(date=D13):
    """that date, and no other, cannot be read: an approved exam of it (of a class that nobody here is relieved in) has a duty that cannot (the line the exams log of it is not printed here)"""
    id_ = exam("3B", name="A damaged exam", date=date, duties=[(OFFIE, 630, 690)]); s = SC.load(id_); s["approved"]["made"]["duties"][0]["start"] = None; saved_exam(s)
    old, RL.logger.disabled = RL.logger.disabled, True
    try: yield
    finally: RL.logger.disabled = old; SC.delete(id_)
@contextlib.contextmanager
def broken_file():
    """a schedule's file cannot be read, so no date can"""
    os.makedirs(SC.DIR, exist_ok=True); p = os.path.join(SC.DIR, "broken1.json")
    with open(p, "w", encoding="utf-8") as f: f.write("{not json")
    try: yield
    finally: os.remove(p)
@contextlib.contextmanager
def raising():
    """whether a date could be read cannot be told"""
    with stand_in(RL.Links, "unread", lambda self, date: 1 / 0): yield
UNREAD = (damage, broken_file, raising)

@t
def what_is_known_is_known_by_the_date():
    with exam_school():
        exam(); x = exam_links(); assert TE.known(None, D13) is None and TE.known(x, D13) is x and TE.known(x, D14) is x
        with damage(): x = exam_links(); assert TE.known(x, D13) is None and TE.known(x, D14) is x and x.stopped(dict(key=K5, date=D13)) == f"1A, 1B are on {EXAM}", "what can be read is there, and is not all"
        with broken_file(): x = exam_links(); assert TE.known(x, D13) is TE.known(x, D14) is None
        with raising(): assert TE.known(exam_links(), D13) is None

@t
def nothing_is_said_about_stopping_of_a_date_that_cannot_be_read():
    for unread in UNREAD:
        with exam_school(SAM, MAYA):
            i, key = told_relief(); e = exam()
            with unread(): assert swept() == 0, "stopped, and not all is known"
            swept(); assert said(SAM) == [RELIEF_K5, STOPPED_K5]; withdraw(e)
            with unread(): assert swept() == 0, "on again, as far as is known"
            swept(); assert said(SAM)[2:] == [AGAIN_K5]; again_on(e); swept()
            with unread(): assert swept() == 0, "nor taken back"
            assert swept() == 0 and said(SAM)[3:] == [STOPPED_K5]; at("09:10"); give(i, K5, MAYA)
            with unread(): assert swept() == 2 and said(SAM)[4:] == [MOVED_K5] and said(MAYA) == [RELIEF_K5], "that it is another's is said as ever, and the relief, as with no exams"
        with exam_school(SAM):                                                             # queued, and the date unread when it would go: dropped (never failed), and made anew once it can be read
            i, key = told_relief(); e = exam()
            for queued, text in ((f"stopped:{key}:0", STOPPED_K5), (f"again:{key}:0", AGAIN_K5)):
                if queued.startswith("again:"): withdraw(e)
                assert TE.sweep() == 1; n = len(said(SAM))
                with unread(): assert send() == 0 and state(queued) == "dropped" and [TE.sweep() for _ in range(3)] == [0] * 3 and OB.send_due(now=time.time() + 9000)["sent"] == 0
                assert len(said(SAM)) == n and swept() == 1 and swept() == 0 and said(SAM)[n:] == [text] and (item(queued)["state"], item(queued)["tries"]) == ("sent", 0), (unread.__name__, queued)
    # a date alone: what is stopped, and on again, of another is said
    with exam_school(SAM, MAYA):
        i = absent(by=HUGO, dates=[D13, D14]); give(i, K5, SAM); give(i, KW, MAYA); swept(); e, f = exam(), exam("2A", name=EXAM2, date=D14)
        with damage(): assert swept() == 1 and told_of("stopped") == [("stopped", MAYA)]
        assert swept() == 1 and told_of("stopped") == [("stopped", MAYA), ("stopped", SAM)]; withdraw(e); withdraw(f)
        with damage(D14): assert swept() == 1 and told_of("again") == [("again", SAM)]
        again_on(f); withdraw(f); TE.sweep()
        with damage(): assert send() == 1 and told_of("again") == [("again", SAM), ("again", MAYA)] and said(SAM)[1:] == [STOPPED_K5, AGAIN_K5], "read again when it goes, for its own date"

@t
def no_lesson_counts_as_stopped_on_a_date_that_cannot_be_read():
    def it(kind): r = outs(kind)[0]; return dict(r, ref=json.loads(r["ref"]))
    for unread in UNREAD:
        with exam_school(SAM):                                                             # the relief goes, as with no exams
            i = absent(by=HUGO); give(i, K5, SAM); e = exam(); assert swept() == 0
            with damage(D14): assert swept() == 0, "another date's: stopped still"
            with unread(): assert swept() == 1 and said(SAM) == [RELIEF_K5]
            swept(); assert said(SAM)[1:] == [STOPPED_K5]
        with exam_school(SAM, MAYA, TEAM):                                                 # so do the ask, its pick and the kept
            i = asked(pick=False); e = exam(); at("09:12")
            with unread(): assert swept() == 1 and len(said(TEAM)) == 1; new_pick(i, K5, MAYA); assert swept() == 1 and told_of("askpick") == [("askpick", TEAM)]
            at("09:20"); CV.keep(i, K5, TEAM)
            with unread(): assert swept() == 1 and said(SAM)[-1] == KEPT_K5
        with exam_school(SAM, MAYA, TEAM):                                                 # and when they go
            i = asked(pick=False); new_pick(i, K5, MAYA); TE.sweep(); e = exam(); relief, ask = it("relief"), it("ask"); swept(); stopped = it("stopped"); again = dict(stopped, kind="again")
            assert [TE.still_true(x) for x in (relief, ask, dict(ask, kind="askpick"), stopped, again)] == [False, False, False, True, False]
            with unread(): assert [TE.still_true(x) for x in (relief, ask, dict(ask, kind="askpick"), stopped, again)] == [True, True, True, False, False]
            with damage(D14): assert [TE.still_true(x) for x in (relief, ask, stopped)] == [False, False, True]
            CV.keep(i, K5, TEAM); withdraw(e); TE.sweep(); kept = it("kept"); again_on(e); assert TE.still_true(kept) is False
            with unread(): assert TE.still_true(kept) is True
            withdraw(e); assert TE.still_true(again) is True
            with unread(): assert TE.still_true(again) is False
        with exam_school(SAM, TEAM, limits=dict(fat_per_day=3, other_per_day=None, never=[RUTH, BUSY, HUGO, LEE, TEAM, ROSA, OFFIE])):      # nor does anybody as on a duty
            i = asked(pick=False); at("09:12"); exam("5A", name=EXAM2, duties=[(MAYA, 630, 690)])
            with unread(): swept(); assert outs("ask")[0]["text"].endswith("No new pick yet: open the app.")

@t
def a_day_that_cannot_be_read_is_reported_as_while_the_exams_cannot():
    for unread in UNREAD:
        with exam_school(SAM, MAYA, TEAM):
            i = today_reliefs((K2, MAYA), (K5, SAM)); exam()
            with unread(): ticked("07:00"); assert texts_to()[-1] == head("07:00", 2) + MAYA_LINE + "sent 06:50" + SAM_LINE + "sent 06:50", "as if none were stopped"
            with unread(): ticked("09:00"); assert texts_to()[-1] == head("09:00", 1) + SAM_LINE + "sent 06:50" and tgdb.get_state(f"started:{relief_key_of(i, K2)}") is None
            with unread(): assert ticked("10:30") == [], "nothing is said to have started"
            assert ticked("10:45") == keyed("1045") and texts_to()[-1] == head("10:45", 0) + STARTED + MAYA_STARTED, "read again: once, and not the one that is stopped"
            with unread(): assert ticked("11:00") == []
            assert ticked("11:15") == cleared(1) and texts_to()[-1] == none_waits("11:15", 1)
        with exam_school(SAM, TEAM):                                                       # every one acknowledged: how many there are is not known
            i = today_reliefs((K5, SAM)); ticked("07:00"); on_cover(SAM, i, K5, "acknowledge")
            with unread(): assert ticked("07:15") == []
            with unreadable(): assert ticked("07:30") == [], "nor while nothing of the exams can be read"
            with damage(D14): assert ticked("07:45") == cleared(1)
    with exam_school(SAM, MAYA, TEAM):                                                     # another date's: as ever
        i = today_reliefs((K2, MAYA), (K5, SAM)); exam()
        with damage(D14): ticked("07:00"); assert texts_to()[-1] == head("07:00", 1) + MAYA_LINE + "sent 06:50"; ticked("09:00"); assert texts_to()[-1] == head("09:00", 0) + STARTED + MAYA_STARTED and ticked("09:15") == cleared(1)

@t
def a_lesson_stopped_is_reminded_of_only_while_its_date_cannot_be_read():
    for unread in UNREAD:
        with exam_school(SAM, TEAM):
            i = today_reliefs((K5, SAM)); exam(); at("07:00", 13); assert skips(remind(asks(i, K5))) == [(K5, SAM, NOBODY)]
            with damage(D14): assert remind(asks(i, K5))["sent"] == 0
            with unread(): assert remind(asks(i, K5))["sent"] == 1 and send() == 1 and said(SAM)[1:] == [RELIEF_K5]

@t
def planned_says_how_many_will_be_covered():
    assert TE.planned_text("Tue 13 Oct", "whole day", HUGO, 0) == PLANNED_N(0) == "📋 Relief planned for you\nTue 13 Oct · whole day\nPlanned by Mr Hugo Ong\nPlease acknowledge and set work for the relief teachers."
    for classes, n in ((("3B",), 2), (("1A", "1B"), 1), (("1C",), 1), (("1A", "1B", "1C"), 0)):
        with exam_school(EVE): exam(*classes); absent(by=HUGO); swept(); assert said(EVE) == [PLANNED_N(n)], classes
    with exam_school(EVE): exam(); absent(by=HUGO, lessons=[dict(key=K2, needed=False)]); swept(); assert said(EVE) == [PLANNED_N(0)], "one not needed, one stopped"
    for unread in (*UNREAD, unreadable):                                                   # not known: counted
        with exam_school(EVE):
            exam("1A", "1B", "1C"); absent(by=HUGO)
            with unread(): swept(); assert said(EVE) == [PLANNED_N(2)], unread.__name__
    with exam_school(EVE):                                                                 # a date alone
        exam(); exam("2A", name=EXAM2, date=D14); absent(by=HUGO, dates=[D13, D14])
        with damage(): swept(); assert said(EVE) == [PLANNED_N(2).replace("Tue 13 Oct", "Tue 13 Oct, Wed 14 Oct")]

@t
def a_stopped_lesson_is_refused_as_on_the_page():
    page = dict(ack="acknowledge", change="ask-change")
    def untouched(): return edits() == [] and calls("editMessageReplyMarkup") == []
    for what in ("ack", "change"):
        with exam_school(SAM, TEAM):
            i, key = told_relief(); e = exam(); was, h, asked_for = file_of(i), Since(), []
            with stand_in(TE, "soon", lambda: asked_for.append(1)): assert press(SAM, what) == (NOT_ON_K5, True)
            assert file_of(i) == was and h.new() == [] and asked_for == [] and rows("talks") == [] and untouched() and said(SAM) == [RELIEF_K5], "its buttons stay: it may be on again"
            assert on_cover(SAM, i, K5, page[what], dict(why="x"), code=400) == dict(error=NOT_ON_K5), "as the page"
            # on again: fresh buttons, which do it
            swept(); at("09:30"); withdraw(e); swept(); assert said(SAM)[1:] == [STOPPED_K5, AGAIN_K5]; tg.PRACTICE_LOG.clear()
            if what == "ack": assert press(SAM, "ack") == ("✅ Acknowledged 09:30.", False) and state_of(i) == "acknowledged" and edits() == [(CHATS[SAM], outs("again")[0]["message_id"], AGAIN_K5 + "\n\n✅ Acknowledged 09:30.")]
            else: assert talk_to(SAM, lambda: press(SAM, "change")) == [(WHY_CHANGE, FORCE)] and talk_to(SAM, lambda: say(SAM, "A meeting")) == [(SENT_CHANGE, None)] and state_of(i) == "change"
            assert [x[3] for x in h.new()] == [dict(ack="relief acknowledged", change="asked to change")[what]]
        with exam_school(SAM):                                                             # what can be read stops it, whatever else cannot (as the page has it); nothing of the exams can: as if there were none
            i, key = told_relief(); e = exam()
            for unread in UNREAD:
                with unread(): assert press(SAM, what) == (NOT_ON_K5, True) and on_cover(SAM, i, K5, page[what], dict(why="x"), code=400) == dict(error=NOT_ON_K5), unread.__name__
            with unreadable(), quiet_app(): assert press(SAM, what) == (("✅ Acknowledged 09:00.", False) if what == "ack" else (None, None))
        for f, sentence in ((lambda i: give(i, K5, MAYA), CV.NOT_YOURS_COVER), (lambda i: at("08:00", day=14), absences.PAST_LESSON), (lambda i: absences.cancel(i, "x", HUGO), CV.NOT_YOURS_COVER)):      # what the page would say first
            with exam_school(SAM): i, key = told_relief(); f(i); exam(); assert press(SAM, what) == (sentence, True) and "Zebra" not in json.dumps(tg.PRACTICE_LOG) and taken_off(SAM, what, sentence), what
    with exam_school(SAM, TEAM):                                                           # when its why is typed
        i, key = told_relief(); press(SAM, "change"); e = exam(); was, h = file_of(i), Since()
        assert talk_to(SAM, lambda: say(SAM, "A meeting")) == [(NOT_ON_K5, None)] and rows("talks") == [] and file_of(i) == was and h.new() == [] and untouched()
        withdraw(e); assert talk_to(SAM, lambda: press(SAM, "change")) == [(WHY_CHANGE, FORCE)] and talk_to(SAM, lambda: say(SAM, "A meeting")) == [(SENT_CHANGE, None)] and [x[3] for x in h.new()] == ["asked to change"], "the same button, once it is withdrawn"
        assert edits() == [(CHATS[SAM], item(key)["message_id"], RELIEF_K5 + "\n\n↩ Asked to change 09:00.")]
    with exam_school(SAM):                                                                 # withdrawn before any sweep, so nobody was told of it: the same button does it, once
        i, key = told_relief(); e, token, h = exam(), tok(SAM, "ack"), Since(); assert [press(SAM, "ack") for _ in range(2)] == [(NOT_ON_K5, True)] * 2 and untouched()
        withdraw(e); at("09:10"); assert [press(SAM, "ack") for _ in range(2)] == [("✅ Acknowledged 09:10.", False)] * 2 and tok(SAM, "ack") == token and state_of(i) == "acknowledged"
        assert h.new() == [by_telegram(SAM, "relief acknowledged", f"{SAM} acknowledged {ON_K5}", i)] and [x["what"] for x in covered(i, K5)[2]["history"]].count("acknowledged") == 1 and edits()[0] == (CHATS[SAM], item(key)["message_id"], RELIEF_K5 + "\n\n✅ Acknowledged 09:10.")
        assert swept() == 0 and said(SAM) == [RELIEF_K5]
    with exam_school(SAM, TEAM):                                                           # asked to change already, and it is stopped since: that it is stopped, first, as the page; nor taken after all
        i, key = told_relief(); CV.ask_change(i, K5, "x", SAM); exam(); was = file_of(i); assert press(SAM, "change") == press(SAM, "ack") == (NOT_ON_K5, True) and file_of(i) == was
        assert [on_cover(SAM, i, K5, x, dict(why="x"), code=400) for x in page.values()] == [dict(error=NOT_ON_K5)] * 2
    with exam_school(SAM):                                                                 # acknowledged already: answered as it is, as the page answers
        i, key = told_relief(); press(SAM, "ack"); exam(); was, h = file_of(i), Since(); at("09:30"); assert press(SAM, "ack") == ("✅ Acknowledged 09:00.", False) and file_of(i) == was and h.new() == []
        assert on_cover(SAM, i, K5, "acknowledge")["state"] == "acknowledged" and press(SAM, "change") == (NOT_ON_K5, True)
    with exam_school(SAM):                                                                 # it is the save itself that refuses, under the lock
        i, key = told_relief(); exam(); was = file_of(i)
        for f in (CV.acknowledge_once, CV.acknowledge, lambda *a, **k: CV.ask_change(i, K5, "x", SAM, **k)):
            try: f(i, K5, SAM, links=exam_links()); raise AssertionError("saved")
            except ValueError as e: assert str(e) == NOT_ON_K5 and file_of(i) == was
        CV.acknowledge(i, K5, SAM); was = file_of(i)                                       # in the page's order: whose it is, then whether it happens, then whether it is answered already
        for f in (CV.acknowledge_once, CV.acknowledge):
            for who_, sentence in ((SAM, NOT_ON_K5), (MAYA, CV.NOT_YOURS_COVER)):
                try: f(i, K5, who_, links=exam_links()); raise AssertionError(sentence)
                except ValueError as e: assert str(e) == sentence and file_of(i) == was

@t
def a_lesson_stopped_when_its_absence_was_sent_is_told_once_it_is_on():
    def row(ckey=K5): return next(v for v in call(TEAM, "get", f"/api/relief/today?date={D13}")["rows"] if v["ckey"] == ckey)
    def sent_by(who_, **kw): return call(who_, "post", "/api/relief/absences", dict(dict(dates=[D13], reason="Medical", reporting_officer=ROSA, lessons=[]), **kw))["id"]
    for planned in (True, False):
        with exam_school(EVE, SAM, MAYA, TEAM, LEE):
            at("15:30"); e = exam(); i = sent_by(HUGO, teacher=EVE, lessons=[dict(key=K5, relief=SAM)]) if planned else sent_by(EVE)
            x = covered(i, K5)[1]; assert (x["needed"], x["not_needed"], x["relief"], state_of(i)) == (True, None, None, "open"), x
            swept(); assert said(EVE) == ([PLANNED_N(1)] if planned else [])
            # nothing of it while it is stopped: no pick, no message, no line of the report, nothing on Today
            assert FL.run(ids=[i])["picked"] == 1 and state_of(i) == "open" and state_of(i, K2) == "waiting"; give(i, K2, MAYA); swept(); assert told_of("relief") == [("relief", MAYA)]
            assert [(row()["state"], row()["told"]), row(K2)["told"]["state"]] == [("stopped", None), "sent"]
            at("06:50", 13); swept(); assert ticked("07:00") == keyed("0700", LEE, TEAM) and "Science (G2)" not in texts_to()[-1]; send(); CV.acknowledge(i, K2, MAYA); assert ticked("07:15") == cleared(1, LEE, TEAM) and texts_to()[-1].endswith("The 1 relief for today is acknowledged."); send()
            assert remind(asks(i, K5))["sent"] == 0 and said(SAM) == [] and {k for k, n in told_of()} <= {"planned", "remind", "relief", "report", "clear"}, told_of()
            # withdrawn: it needs a relief, which is told as any other
            at("07:20", 13); withdraw(e); assert swept() == 0 and row()["state"] == "open" and FL.run(ids=[i])["picked"] == 1 and swept() == 0 and said(SAM) == [], "a pick is nobody's message"
            on_cover(TEAM, i, K5, "approve", dict(who=SAM)); send(); assert said(SAM) == [RELIEF_K5] and row()["told"] == dict(state="sent", at=clock.now) and not told_of("again")
            assert ticked("07:30") == keyed("0730", LEE, TEAM) and texts_to()[-1] == head("07:30", 1) + SAM_LINE + "sent 07:20" and press(SAM, "ack") == ("✅ Acknowledged 07:30.", False)
            again_on(e); swept(); assert said(SAM)[1:] == [STOPPED_K5] and row()["told"] is None
    with exam_school(EVE, SAM, TEAM):                                                      # every lesson of it stopped: the absence is taken, and says nothing of them
        exam("1A", "1B", "1C"); i = sent_by(HUGO, teacher=EVE); swept(); assert told_of() == [("planned", EVE)] and said(EVE) == [PLANNED_N(0)] and FL.run(ids=[i]) == dict(picked=0, nobody=0) and swept() == 0
        absences.cancel(i, "x", HUGO); swept(); assert said(EVE)[1:] == said(TEAM) == [CANCELLED_EVE.format(HUGO)] and said(SAM) == []

# ---- Task 6b, fix round 1
@t
def stopped_is_said_again_once_something_said_that_it_is_on():
    def stopped(i): return [x["key"] for x in dues(links=exam_links()) if x["kind"] == "stopped"]
    for unread in (*UNREAD, unreadable):                                                   # reminded by the team while it is not known, and stopped still
        with exam_school(SAM, TEAM):
            i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); e = exam(); at("06:55", 13); assert swept() == 1 and said(SAM) == [RELIEF_K5, STOPPED_K5]
            for hm in ("06:56", "06:57", "06:59"): at(hm, 13); assert swept() == 0, "once, while nothing said since that it is on"
            at("07:00", 13)
            with unread(): assert remind(asks(i, K5))["sent"] == 1 and send() == 1 and swept() == 0 and said(SAM)[2:] == [RELIEF_K5]
            at("07:05", 13); assert swept() == 1 and said(SAM)[3:] == [STOPPED_K5] and keys("stopped") == [f"stopped:{key}:0", f"stopped:{key}:1"], unread.__name__
            for hm in ("07:06", "07:30"): at(hm, 13); assert swept() == 0, "once again"
            assert TE.said().sent_at(key) is None and TE.said().of(key) is None, "they know of no relief"
            withdraw(e); ticked("07:45"); assert texts_to()[-1].endswith("not told yet"); assert swept() == 1 and keys("again") == [f"again:{key}:1"] and said(SAM)[4:] == [AGAIN_K5]
            assert f"{TE.said().sent_at(key):%H:%M}" == "07:00"; at("07:50", 13); again_on(e); assert swept() == 1 and swept() == 0 and keys("stopped")[2:] == [f"stopped:{key}:2"] and said(SAM)[5:] == [STOPPED_K5]
    for remind_ in (True, False):                                                          # on again was never told: stopped again is news only to who was reminded
        with exam_school(SAM, TEAM):
            i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); e = exam(); at("06:55", 13); swept(); withdraw(e); TE.sweep(); put(f"again:{key}:0", state="failed"); at("07:00", 13)
            if remind_: assert remind(asks(i, K5))["sent"] == 1; send()
            at("07:05", 13); again_on(e); assert swept() == int(remind_) and keys("stopped")[1:] == [f"stopped:{key}:1"] * remind_ and swept() == 0
            withdraw(e); at("07:10", 13); assert swept() == int(remind_) and said(SAM)[2:] == ([RELIEF_K5, STOPPED_K5, AGAIN_K5] if remind_ else [])
    with exam_school(SAM, TEAM):                                                           # the states of what said so, and when it went
        i = today_reliefs((K5, SAM)); key = relief_key_of(i, K5); exam(); at("06:55", 13); swept(); at("07:00", 13); one = [f"stopped:{key}:1"]
        with damage(): remind(asks(i, K5)); send()
        at("07:10", 13)
        for s, n in (("sent", 1), ("unsure", 1), ("queued", 0), ("sending", 0), ("failed", 0), ("dropped", 0)): put(key + ":r1", state=s); assert stopped(i) == one * n, s
        put(key + ":r1", state="sent", sent_at="2026-10-13T06:54:59+08:00"); assert stopped(i) == [], "before it"
        put(key + ":r1", sent_at="2026-10-13T06:55:00+08:00"); assert stopped(i) == [], "in that second: not known to be after it"
        put(key + ":r1", sent_at="2026-10-13T06:55:01+08:00"); assert stopped(i) == one
        put(key + ":r1", state="dropped"); put(key, sent_at="2026-10-13T07:01:00+08:00"); assert stopped(i) == one, "the message itself, that went later"
        put(key, sent_at="2026-10-13T06:50:00+08:00"); assert stopped(i) == []
        other = {f"{key}:{MAYA}{n}": dict(state="sent", at=clock.now, name=MAYA, ref=None) for n in ("", ":r1")}; assert [x["key"] for x in dues(told={**OB.told_for(""), **other}, links=exam_links()) if x["kind"] == "stopped"] == [], "another's"

@t
def nobody_else_is_not_said_of_a_date_that_cannot_be_read():
    nobody, unsure = "Nobody else is free then: choose someone in the app.", "No new pick yet: open the app."
    for cm, text in ((contextlib.nullcontext, nobody), (lambda: damage(D14), nobody), *((u, unsure) for u in (*UNREAD, unreadable))):
        with exam_school(SAM, TEAM, limits=dict(fat_per_day=3, other_per_day=None, never=[RUTH, BUSY, HUGO, LEE, TEAM, ROSA, OFFIE, MAYA])):
            i = asked(pick=False); at("09:12")
            with cm(): swept(); assert outs("ask")[0]["text"].endswith(text), text

@t
def an_absence_with_nothing_to_cover_says_nothing_of_relief():
    alone = "Ms Evelyn Koh is away on Tue 13 Oct (whole day): Medical."; assert TE.officer_text(EVE, "Tue 13 Oct", "whole day", "Medical", False) == alone == OFFICER_EVE.split("\n")[0]
    with exam_school(EVE, ROSA):
        e = exam("1A", "1B", "1C"); i = absent(by=HUGO); swept(); assert said(ROSA) == [alone] and said(EVE) == [PLANNED_N(0)]; at("15:00"); assert swept() == 0
        withdraw(e); assert swept() == 1 and said(EVE)[1:] == [REMIND_EVE] and said(ROSA) == [alone], "something to cover: reminded"
    with exam_school(EVE, ROSA): exam(); absent(by=HUGO); swept(); at("15:00"); swept(); assert said(ROSA) == [OFFICER_EVE] and said(EVE) == [PLANNED_N(1), REMIND_EVE], "one is left"
    with exam_school(EVE):                                                                 # queued, and then nothing is left: dropped, and made anew
        i = absent(by=HUGO); swept(); at("15:00"); assert TE.sweep() == 1; e = exam("1A", "1B", "1C"); assert send() == 0 and state(f"remind:{i}") == "dropped" and swept() == 0
        withdraw(e); assert swept() == 1 and swept() == 0 and said(EVE) == [PLANNED_EVE, REMIND_EVE]
    with exam_school(EVE):                                                                 # none of them needed
        i = absent(by=HUGO); swept(); at("15:00"); TE.sweep(); absences.not_needed(i, K2, "x", HUGO); r, = outs("remind"); r = dict(r, ref=json.loads(r["ref"])); assert TE.still_true(r) is True
        absences.not_needed(i, K5, "x", HUGO); assert TE.still_true(r) is False and send() == 0 and swept() == 0 and said(EVE) == [PLANNED_EVE]
    for unread in (*UNREAD, unreadable):                                                   # not known: to be covered
        with exam_school(EVE, ROSA):
            exam("1A", "1B", "1C"); absent(by=HUGO)
            with unread(): swept(); at("15:00"); swept(); assert said(ROSA) == [OFFICER_EVE] and said(EVE) == [PLANNED_N(2), REMIND_EVE], unread.__name__
    with exam_school(EVE, ROSA):                                                           # a duty and no lesson
        exam("5A", name=EXAM2, date="2026-10-15", duties=[(EVE, 630, 690)]); d = dict(teacher=EVE, dates=["2026-10-15"], periods=None, reason="Medical", reason_text="", remarks="", reporting_officer=ROSA, lessons=[])
        assert absences.new(d, SCHOOL, HUGO, "planned", may_choose=True, links=exam_links())["lessons"] == []; swept(); at("15:00", 14); assert swept() == 0
        assert said(ROSA) == [alone.replace("Tue 13", "Thu 15")] and said(EVE) == [PLANNED_N(0).replace("Tue 13", "Thu 15")]

# ---- Task 7: the weekly summary ----
from relief import summary as SU  # noqa: E402

MON12, W12, SUMMARY_URL = datetime.date(2026, 10, 12), "2026-10-12", "/api/relief/summary"
WEEK_SCHOOL = RP.fake_pub([dict(name=EVE, dept="Science", dept2="Art"), dict(name=RUTH, dept="Science"), dict(name=MAYA, dept="Mathematics"), dict(name=ROSA, dept="English"), dict(name=HUGO),
                           dict(name=SAM, dept="Science", role="FAT"), dict(name=BUSY, dept="Humanities", role="FAT"), dict(name=LEE, dept="Mathematics", role="HOD")])
WEEK_SCHOOL["model"]["school"].update(start_time="08:00", period_minutes=30)
WEEK_SCHOOL["model"]["NP"] = 12
ZERO = dict(periods=0, absences=0, fat_periods=0, fat_percent=0, ahead=0, on_day=0, on_time=0, late=0, never=0, waiting=0, asked=0, moved=0, kept=0)
def st(day, hm): return f"2026-10-{day:02d}T{hm}:00+08:00"
def cov(relief=None, approved=None, ack=None, change=None, history=(), **more):
    """the cover's fields, as relief.cover writes them"""
    return dict(dict(relief=relief, relief_by=None, pick=None, approved=dict(by=TEAM, at=approved) if approved else None, ack=dict(at=ack) if ack else None,
                     change=dict(why="walrus-why", at=change, pick=None) if change else None, history=list(history)), **more)
def on(day, p, n=1, relief=None, *a, classes=("4D",), subject="Maths", needed=True, group="", **kw):
    """a lesson of an absence, on that day of October, with its cover"""
    d = f"2026-10-{day:02d}"
    return cov(relief, *a, **dict(dict(key=f"{d}/{p}/{classes[0]}", date=d, p=p, n=n, classes=list(classes), subject=subject, group=group, needed=needed, room="2-05"), **kw))
_made = itertools.count(1)
def away(teacher, *lessons, **kw): return dict(dict(id=f"{next(_made):012x}", teacher=teacher, dates=sorted({x["date"] for x in lessons}), reason="Other", reason_text="zebra-reason", remarks="quokka-remark", how="asked", by=teacher, cancelled=None, lessons=list(lessons)), **kw)
def hist(what, who_, day, hm="07:30", why=None): return dict(what=what, who=who_, by=TEAM, at=st(day, hm), why=why)
def wk(*records, now=st(15, "10:00"), monday=MON12, pub=WEEK_SCHOOL, **kw):
    more = {k: kw.pop(k) for k in list(kw) if k == "links"}
    return SU.week(pub, dict(dict(fat_role="FAT", calendar=TERM), **kw), list(records), monday, now, **more)
def nums(v, *names): return {k: v[k] for k in names or ZERO}
def adds_up(v):
    """what is in periods adds up to them -> v"""
    for ks in (("ahead", "on_day"), ("on_time", "late", "never", "waiting")): assert sum(v[k] for k in ks) == v["periods"], (ks, v)
    assert sum(v["by_day"].values()) == sum(n for _, n in v["by_dept"]) == v["periods"] >= v["fat_periods"] and v["asked"] >= v["moved"] + v["kept"], v
    return v
def a_week():
    """a week made by hand, each case in it, as it stands at 10:00 on Thu 15 Oct"""
    return [away(EVE, on(12, 2, 3, SAM, st(9, "15:00"), st(9, "15:20")), on(13, 0, 1, MAYA, st(13, "07:00"), st(13, "07:15")), on(13, 4, needed=False), on(14, 4), on(14, 6, 2, BUSY), on(9, 0, 2, SAM, st(9, "07:00")), on(19, 0, 2, SAM, st(9, "07:00"))),
            away(RUTH, on(13, 5, 2, MAYA, st(13, "07:10"), st(13, "10:31"), classes=("1B", "1A"), subject="Science", group="G1")),
            away(ROSA, on(14, 1, 1, SAM, st(13, "16:00")), on(15, 0, 2, BUSY, st(14, "15:00"), None, st(15, "07:00"), [hist("asked to change", BUSY, 15)])),
            away(MAYA, on(16, 0, 2, RUTH, st(14, "15:00"), None, None, [hist("asked to change", SAM, 14), hist("approved", RUTH, 14, "15:00")])),
            away(GONE_, on(15, 3, 2, RUTH, st(15, "07:00"), None, None, [hist("asked to change", RUTH, 15), hist("kept", RUTH, 15, "08:00")])),
            away(HUGO, on(16, 2, 1, MAYA, st(12, "08:00"), st(12, "09:00"))),
            away(LEE, on(16, 4), on(16, 6, 2, SAM))]

@t
def the_numbers_add_up():
    v = adds_up(wk(*a_week()))
    assert nums(v) == dict(periods=14, absences=6, fat_periods=6, fat_percent=43, ahead=9, on_day=5, on_time=5, late=2, never=3, waiting=4, asked=3, moved=1, kept=1), nums(v)
    assert (v["start"], v["end"], v["label"], v["fat_role"]) == (W12, "2026-10-16", "Week 6 (12–16 Oct)", True)
    assert v["top"] == [(SAM, 4), (MAYA, 4), (RUTH, 4)] and v["by_dept"] == [("Science", 6), ("English", 3), ("No department", 3), ("Mathematics", 2)] and v["by_day"] == dict(Mon=3, Tue=3, Wed=1, Thu=4, Fri=3) and list(v["by_day"]) == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    row = lambda date, lesson_, absent_, relief, ack: dict(date=f"2026-10-{date}", lesson=lesson_, absent=absent_, relief=relief, ack=ack)
    assert v["rows"] == [row(12, "4D Maths P3–P5", EVE, SAM, "Fri 9 Oct, 15:20"), row(13, "4D Maths P1", EVE, MAYA, "07:15"), row(13, "1B, 1A Science (G1) P6–P7", RUTH, MAYA, "late 10:31"), row(14, "4D Maths P2", ROSA, SAM, "never"),
                         row(15, "4D Maths P1–P2", ROSA, BUSY, "never"), row(15, "4D Maths P4–P5", GONE_, RUTH, "waiting"), row(16, "4D Maths P1–P2", MAYA, RUTH, "waiting"), row(16, "4D Maths P3", HUGO, MAYA, "Mon 12 Oct, 09:00")], v["rows"]
    assert set(v) == {"start", "end", "label", "fat_role", "top", "by_dept", "by_day", "rows", *ZERO}
    # whatever order the records come in, and nothing of them is changed
    recs = a_week(); was = json.dumps(recs); assert wk(*reversed(recs)) == v == wk(*recs) and json.dumps(recs) == was
    # the next week's and the one before are theirs alone; a week with nothing is zeros
    w19, w5 = adds_up(wk(*a_week(), monday=datetime.date(2026, 10, 19))), adds_up(wk(*a_week(), monday=datetime.date(2026, 10, 5)))
    assert nums(w19, "periods", "absences", "ahead", "waiting") == dict(periods=2, absences=1, ahead=2, waiting=2) and w19["label"] == "Week 7 (19–23 Oct)" and nums(w5, "periods", "absences", "on_day", "never") == dict(periods=2, absences=1, on_day=2, never=2)
    for v in (wk(), wk(away(LEE, on(16, 4), on(16, 6, 2, SAM))), wk(away(EVE)), wk(*a_week(), monday=datetime.date(2027, 1, 4))): assert nums(v) == ZERO and (v["top"], v["by_dept"], v["rows"], v["by_day"]) == ([], [], [], dict(Mon=0, Tue=0, Wed=0, Thu=0, Fri=0))
    # any day of the week, and a date as text, say which week
    assert all(wk(*a_week(), monday=d) == wk(*a_week()) for d in (datetime.date(2026, 10, 14), datetime.date(2026, 10, 18), "2026-10-12", "2026-10-16"))
    # as many periods: by name, whoever came first
    v = wk(away(EVE, on(12, 0, 1, RUTH, st(12, "07:00"))), away(ROSA, on(13, 0, 1, MAYA, st(12, "08:00")))); assert v["top"] == [(MAYA, 1), (RUTH, 1)] and v["by_dept"] == [("English", 1), ("Science", 1)]
    # two on one date and period go by who is absent
    assert [x["absent"] for x in wk(away(RUTH, on(13, 0, 1, SAM, st(12, "08:00"))), away(EVE, on(13, 0, 1, MAYA, st(12, "08:00"))))["rows"]] == [EVE, RUTH]
    # and of one absent teacher by the lesson, then by who relieves it, whichever came first (two records, or one)
    three = [on(13, 0, 1, RUTH, st(12, "08:00"), classes=("1A",)), on(13, 0, 1, SAM, st(12, "08:00"), classes=("1B",)), on(13, 0, 1, MAYA, st(12, "08:00"), classes=("1B",))]
    for order in itertools.permutations(three):
        for records in ([away(EVE, x) for x in order], [away(EVE, *order)]): assert [(x["lesson"], x["relief"]) for x in wk(*records)["rows"]] == [("1A Maths P1", RUTH), ("1B Maths P1", SAM), ("1B Maths P1", MAYA)]

@t
def a_percentage_is_whole_and_half_goes_up():
    def pc(fat, other, **kw): return wk(away(EVE, *[on(13, p, 1, SAM if p < fat else MAYA, st(12, "08:00")) for p in range(fat + other)]), **kw)
    for fat, other, want in ((0, 1, 0), (1, 0, 100), (1, 2, 33), (2, 1, 67), (1, 1, 50), (1, 7, 13), (3, 5, 38), (5, 3, 63), (1, 5, 17)): v = pc(fat, other); assert (v["fat_periods"], v["fat_percent"]) == (fat, want), (fat, other, v["fat_percent"])
    for none in ("", None): v = pc(3, 5, fat_role=none); assert (v["fat_role"], v["fat_periods"], v["fat_percent"]) == (False, 0, 0)
    v = pc(3, 5, fat_role="HOD"); assert (v["fat_role"], v["fat_periods"]) == (True, 0), "the role there is now"
    assert nums(wk(away(EVE, on(13, 0, 1, LEE, st(12, "08:00"))), fat_role="HOD"), "fat_periods", "fat_percent") == dict(fat_periods=1, fat_percent=100)
    assert wk(away(EVE, on(13, 0, 1, GONE_, st(12, "08:00"))))["fat_periods"] == 0, "not on the timetable any more"

@t
def a_cancelled_absence_does_not_count():
    one = lambda **kw: on(13, 0, 2, MAYA, st(12, "08:00"), st(12, "09:00"), None, [hist("asked to change", SAM, 12), hist("approved", MAYA, 12)], **kw)
    gone = dict(at=st(12, "10:00"), by=EVE, why="Better")
    assert nums(wk(away(EVE, one())), "periods", "asked", "moved") == dict(periods=2, asked=1, moved=1)
    for records in ([away(EVE, one(), cancelled=gone)], [away(EVE, one(needed=False))], [away(EVE, one(date="2026-10-17"))], [away(EVE, one(date="2026-10-18"))], [away(EVE, one(date="2026-10-11"))]): assert nums(wk(*records)) == ZERO, records
    v = wk(away(EVE, one(), cancelled=gone), away(RUTH, one())); assert nums(v, "periods", "absences", "asked") == dict(periods=2, absences=1, asked=1) and v["by_dept"] == [("Science", 2)] and [x["absent"] for x in v["rows"]] == [RUTH]
    with school(SAM, MAYA):                                                                # as the app does it
        i, j = absent(by=HUGO), absent(teacher=RUTH, by=HUGO); give(i, K5, SAM); give(j, KR, MAYA); now_ = lambda: SU.week(SCHOOL, rs(), absences.all_records(), MON12, clock.now)
        assert nums(now_(), "periods", "absences") == dict(periods=3, absences=2); absences.not_needed(i, K5, "x", HUGO); assert nums(now_(), "periods", "absences") == dict(periods=1, absences=1); absences.needed_again(i, K5, HUGO); assert now_()["periods"] == 1, "its relief ended"
        absences.cancel(j, "Better", HUGO); assert nums(now_()) == ZERO

@t
def ahead_and_on_the_day_by_approval_date():
    for at_, ahead in ((st(12, "23:59"), 2), (st(13, "00:00"), 0), (st(13, "07:00"), 0), (st(13, "12:00"), 0), (st(14, "08:00"), 0), (st(1, "08:00"), 2),
                       ("2026-10-12T15:59:59+00:00", 2), ("2026-10-12T16:00:00+00:00", 0), ("2026-10-12T20:00:00+00:00", 0), ("2026-10-13T00:30:00+09:00", 2), ("2026-10-12T08:00:00", 2)):      # school time, whatever it was kept in
        v = adds_up(wk(away(EVE, on(13, 2, 2, MAYA, at_)))); assert (v["ahead"], v["on_day"]) == (ahead, 2 - ahead), at_
    assert (lambda v: (v["ahead"], v["on_day"]))(wk(away(EVE, on(13, 2, 2, MAYA, st(13, "07:00"), None, None, [hist("approved", SAM, 9)])))) == (0, 2), "the approval there is now"

@t
def ack_on_time_late_never_waiting():
    def ack(at_=None, now=st(15, "10:00"), change=None, p=2, n=2, **kw):
        v = adds_up(wk(away(EVE, on(13, p, n, MAYA, st(12, "08:00"), at_, change)), now=now, **kw)); got, = [k for k in ("on_time", "late", "never", "waiting") if v[k]]; assert v[got] == n
        return got, v["rows"][0]["ack"]
    # P3-P4 of Tue 13 is 09:00-10:00
    for at_, want in ((st(12, "15:20"), ("on_time", "Mon 12 Oct, 15:20")), (st(13, "00:00"), ("on_time", "00:00")), (st(13, "07:15"), ("on_time", "07:15")), ("2026-10-13T08:59:59+08:00", ("on_time", "08:59")), ("2026-10-13T09:00:00+08:00", ("on_time", "09:00")),
                      ("2026-10-13T09:00:01+08:00", ("on_time", "09:00")), ("2026-10-13T09:00:59+08:00", ("on_time", "09:00")), ("2026-10-13T09:01:00+08:00", ("late", "late 09:01")), ("2026-10-13T01:00:59+00:00", ("on_time", "09:00")), ("2026-10-13T01:01:00+00:00", ("late", "late 09:01")),
                      (st(13, "09:30"), ("late", "late 09:30")), (st(13, "18:00"), ("late", "late 18:00")), (st(14, "08:05"), ("late", "late Wed 14 Oct, 08:05")), ("2026-10-12T23:15:00+00:00", ("on_time", "07:15")), ("2026-10-13T01:30:00+00:00", ("late", "late 09:30")), ("2026-10-12T15:30:00+00:00", ("on_time", "Mon 12 Oct, 23:30"))):
        assert ack(at_) == want, at_
        assert ack(at_, now=st(12, "08:00")) == want, "whatever the time is now"
    for now, want in ((st(12, "08:00"), "waiting"), (st(13, "09:00"), "waiting"), (st(13, "09:59"), "waiting"), (st(13, "10:00"), "never"), (st(13, "23:00"), "never"), (st(14, "00:00"), "never"), ("2026-10-13T01:59:00+00:00", "waiting"), ("2026-10-13T02:00:00+00:00", "never")):
        assert ack(now=now) == (want, want) == ack(now=datetime.datetime.fromisoformat(now)), now
        assert ack(now=now, change=st(12, "09:00")) == (want, want) and ack(st(12, "08:30"), now=now, change=st(12, "09:00")) == (want, want), "asked to change: not acknowledged"
    # a lesson with no times is over with its day
    bare = RP.fake_pub([dict(name=EVE, dept="Science"), dict(name=MAYA, dept="Mathematics")])
    for pub, p in ((bare, 2), (WEEK_SCHOOL, 12)): assert ack(st(13, "23:59"), pub=pub, p=p) == ("on_time", "23:59") and ack(st(14, "00:01"), pub=pub, p=p)[0] == "late" and ack(now=st(13, "23:59"), pub=pub, p=p) == ("waiting",) * 2 and ack(now=st(14, "00:00"), pub=pub, p=p) == ("never",) * 2
    assert ack(now=st(13, "13:59"), p=11, n=3)[0] == "waiting" and ack(now=st(13, "14:00"), p=11, n=3)[0] == "never", "past the last period: over with it"

@t
def a_split_lesson_counts_its_parts():
    part = lambda p, n, *a, **kw: cov(*a, **dict(kw, p=p, n=n))
    x = on(13, 2, 5, parts=[part(5, 2, RUTH, st(13, "07:00"), st(13, "07:20")), part(2, 2, SAM, st(12, "08:00"), st(13, "09:10")), part(4, 1, MAYA, st(12, "08:00"))], history=[hist("split", None, 12)])
    v = adds_up(wk(away(EVE, x))); assert nums(v) == dict(ZERO, periods=5, absences=1, fat_periods=2, fat_percent=40, ahead=3, on_day=2, on_time=2, late=2, never=1), nums(v)
    assert [(r["lesson"], r["relief"], r["ack"]) for r in v["rows"]] == [("4D Maths P3–P4", SAM, "late 09:10"), ("4D Maths P5", MAYA, "never"), ("4D Maths P6–P7", RUTH, "07:20")] and v["top"] == [(SAM, 2), (RUTH, 2), (MAYA, 1)] and v["by_dept"] == [("Science", 5)]
    for c in x["parts"][1:]: c.update(CV.OPEN)                                              # a part not approved is not a relief
    v = adds_up(wk(away(EVE, x))); assert nums(v, "periods", "absences", "on_time") == dict(periods=2, absences=1, on_time=2)
    x["parts"][0]["history"], x["parts"][1]["history"] = [hist("asked to change", MAYA, 12), hist("approved", RUTH, 13)], [hist("asked to change", SAM, 12)]; v = wk(away(EVE, x)); assert nums(v, "asked", "moved", "kept", "periods") == dict(asked=2, moved=1, kept=0, periods=2), "in covers"
    with school(SAM, RUTH):                                                                 # as the app splits one
        at("06:50", 13); i = absent(by=HUGO); CV.split(i, K2, 3, TEAM); give(i, K2 + "#0", MAYA); give(i, K2 + "#1", RUTH); CV.acknowledge(i, K2 + "#1", RUTH); v = adds_up(SU.week(SCHOOL, rs(), absences.all_records(), MON12, clock.now))
        assert [(r["lesson"], r["relief"], r["ack"]) for r in v["rows"]] == [("1C Science P3", MAYA, "waiting"), ("1C Science P4–P5", RUTH, "06:50")] and nums(v, "periods", "absences", "on_day") == dict(periods=3, absences=1, on_day=3)

@t
def a_lesson_an_exam_stops_is_no_relief():
    with exam_school(SAM, MAYA):
        i = absent(by=HUGO); give(i, K5, SAM); give(i, K2, MAYA); CV.ask_change(i, K5, "walrus-why", SAM); got = lambda **kw: nums(SU.week(SCHOOL, rs(), absences.all_records(), MON12, clock.now, **kw), "periods", "absences", "asked")
        assert got() == dict(periods=5, absences=1, asked=1); e = exam(); assert got() == dict(periods=5, absences=1, asked=1) == got(links=None), "no links: none is stopped"
        assert got(links=exam_links()) == dict(periods=3, absences=1, asked=0); j = exam("1C", name=EXAM2); assert got(links=exam_links()) == dict(periods=0, absences=0, asked=0); withdraw(j); withdraw(e); assert got(links=exam_links()) == dict(periods=5, absences=1, asked=1)

@t
def a_request_to_change_is_moved_kept_or_still_waiting():
    A = hist("asked to change", SAM, 12, "09:00")
    def what(*h, **kw):
        v = wk(away(EVE, on(13, 0, 1, **dict(dict(history=list(h)), **kw)))); return v["asked"], v["moved"], v["kept"]
    for h, want in (([], (0, 0, 0)), ([hist("pick", SAM, 12), hist("approved", SAM, 12), hist("acknowledged", SAM, 12)], (0, 0, 0)), ([A], (1, 0, 0)), ([A, hist("pick", MAYA, 12)], (1, 0, 0)), ([A, hist("pick", MAYA, 12), hist("dropped", MAYA, 12)], (1, 0, 0)),
                    ([A, hist("pick", MAYA, 12), hist("approved", MAYA, 12)], (1, 1, 0)), ([A, hist("dropped", SAM, 12), hist("pick", RUTH, 12), hist("changed", RUTH, 12)], (1, 1, 0)), ([A, hist("kept", SAM, 12)], (1, 0, 1)), ([A, hist("pick", SAM, 12), hist("changed", SAM, 12)], (1, 0, 1)),
                    ([A, hist("approved", SAM, 12)], (1, 0, 1)), ([A, hist("acknowledged", SAM, 12)], (1, 0, 1)), ([A, hist("approved", MAYA, 12), hist("acknowledged", MAYA, 12)], (1, 1, 0)), ([A, hist("approved", MAYA, 12), hist("dropped", MAYA, 12)], (1, 1, 0)),
                    ([hist("approved", MAYA, 12), A], (1, 0, 0)), ([A, hist("kept", SAM, 12), A], (1, 0, 0)), ([A, hist("kept", SAM, 12), A, hist("approved", MAYA, 12)], (1, 1, 0)), ([A, hist("approved", MAYA, 12), hist("asked to change", MAYA, 12)], (1, 0, 0)),
                    ([A, hist("approved", MAYA, 12), hist("asked to change", MAYA, 12), hist("approved", SAM, 12)], (1, 1, 0)), ([A, hist("approved", MAYA, 12), hist("changed", SAM, 12)], (1, 0, 1)), ([A, hist("dropped", SAM, 12)], (1, 0, 0))):
        for state in (dict(relief=SAM, approved=st(12, "08:00")), dict(relief=MAYA, approved=st(12, "08:00"), change=st(12, "09:00")), dict(), dict(relief=MAYA)): assert what(*h, **state) == want, (h, state)
    assert what(dict(A, at="2026-09-28T09:00:00+08:00")) == (1, 0, 0), "whenever it was asked"
    # each way there is, in the app
    def app(f):
        with school(SAM, MAYA):
            i = asked(pick=False); new_pick(i, K5, MAYA); f(i); v = adds_up(SU.week(SCHOOL, rs(), absences.all_records(), MON12, clock.now)); return v["asked"], v["moved"], v["kept"]
    assert app(lambda i: None) == (1, 0, 0) and app(lambda i: CV.approve(i, K5, MAYA, TEAM, SCHOOL, rs())) == (1, 1, 0) and app(lambda i: give(i, K5, LEE)) == (1, 1, 0) and app(lambda i: CV.keep(i, K5, TEAM)) == (1, 0, 1)
    assert app(lambda i: CV.acknowledge(i, K5, SAM)) == (1, 0, 1) and app(lambda i: give(i, K5, SAM)) == (1, 0, 1) and app(lambda i: (CV.approve(i, K5, MAYA, TEAM, SCHOOL, rs()), CV.ask_change(i, K5, "x", MAYA))) == (1, 0, 0)
    assert app(lambda i: absences.not_needed(i, K5, "x", HUGO)) == (0, 0, 0) == app(lambda i: absences.cancel(i, "x", HUGO)) and app(lambda i: (absences.not_needed(i, K5, "x", HUGO), absences.needed_again(i, K5, HUGO))) == (1, 0, 0)

@t
def the_week_is_named():
    cal = lambda *terms: dict(terms=[dict(name=f"T{n}", start=a, end=b, starts_as="Odd") for n, (a, b) in enumerate(terms)], holidays=[])
    name = lambda monday, cal: wk(monday=datetime.date.fromisoformat(monday), calendar=cal)["label"]
    T4 = cal(("2026-09-07", "2026-11-20"))
    for monday, want in (("2026-09-07", "Week 1 (7–11 Sep)"), ("2026-09-14", "Week 2 (14–18 Sep)"), ("2026-09-28", "Week 4 (28 Sep–2 Oct)"), ("2026-10-12", "Week 6 (12–16 Oct)"), ("2026-11-16", "Week 11 (16–20 Nov)"), ("2026-11-23", "23–27 Nov"), ("2026-08-31", "31 Aug–4 Sep"), ("2026-12-28", "28 Dec–1 Jan")): assert name(monday, T4) == want, monday
    # a term that starts mid-week: that week is its first; any of Mon to Fri in it will do
    MID = cal(("2026-09-09", "2026-11-17"))
    assert name("2026-09-07", MID) == "Week 1 (7–11 Sep)" and name("2026-09-14", MID) == "Week 2 (14–18 Sep)" and name("2026-11-16", MID) == "Week 11 (16–20 Nov)" and name("2026-11-23", MID) == "23–27 Nov"
    for start, want in (("2026-09-11", "Week 1 (7–11 Sep)"), ("2026-09-12", "7–11 Sep"), ("2026-09-13", "7–11 Sep")): assert name("2026-09-07", cal((start, "2026-11-17"))) == want, start      # a Saturday is not of the week
    assert name("2026-09-14", cal(("2026-06-29", "2026-09-15"), ("2026-09-17", "2026-11-20"))) == "Week 12 (14–18 Sep)", "two terms in it: the earlier"
    for odd in ({}, dict(terms=[]), dict(terms=None), dict(terms=[dict(name="x")]), dict(terms=[5]), dict(terms=[dict(start="x", end=5)]), dict(terms="x"), None, "x"): assert name("2026-10-12", odd) == "12–16 Oct", odd

@t
def what_cannot_be_read_is_passed_over():
    h = Grab(); KINDS.addHandler(h)
    try:
        good = adds_up(wk(*a_week())); ok = lambda **kw: dict(on(13, 8, 1, MAYA, st(12, "08:00"), st(12, "09:00")), **kw); assert h.records == []
        bad_covers = [ok(relief=5), ok(relief=["x"]), ok(approved=5), ok(approved=dict(by=TEAM)), ok(approved=dict(by=TEAM, at=5)), ok(approved=dict(by=TEAM, at="private yesterday")), ok(ack=dict(at="private")), ok(ack=dict(at=None)), ok(ack=7), ok(p="a private word"), ok(p=None), ok(p=-1), ok(n="x"), ok(n=-3),
                      ok(parts=[5]), ok(parts=5), ok(history=5), ok(history=[5]), ok(classes=[5]), ok(subject=5), ok(date=None), ok(date=["2026-10-13"]), 5, None, "private", dict(), dict(date="2026-10-13", needed=True, relief=SAM, approved=dict(at=st(12, "08:00")))]
        for n, x in enumerate(bad_covers):
            h.records.clear(); r = away(LEE); r["lessons"] = [x]; assert wk(*a_week(), r) == good, (n, x)
            assert h.records and all(m.getMessage().endswith(")") and m.exc_info is None and "private" not in m.getMessage() and LEE not in m.getMessage() for m in h.records), (n, x)
            r["lessons"] = [x, ok(), x]; v = adds_up(wk(*a_week(), r)); assert (v["periods"], v["absences"], v["on_time"]) == (good["periods"] + 1, good["absences"] + 1, good["on_time"] + 1), ("the rest of its absence counts", n, x)
        for n, r in enumerate([5, None, "x", [], {}, dict(id="x"), dict(id="x", teacher=EVE, lessons=5), dict(id="x", teacher=EVE, lessons="private"), dict(id="x", teacher=["x"], lessons=[ok()]), dict(id="x", teacher=None, lessons=[ok()]), dict(id="x", teacher=5, lessons=[ok()]), dict(id="x", lessons=[ok()])]): assert wk(*a_week(), r) == good == wk(r, *a_week()), (n, r)
        h.records.clear(); v = wk(*a_week(), away(LEE, ok(), lessons=[on(13, 8, 5, parts=[cov(5, st(12, "08:00"), p=8, n=2), cov(MAYA, st(12, "08:00"), st(12, "09:00"), p=10, n=1)])])); assert v["periods"] == good["periods"] + 1 and len(h.records) == 1, "a part alone"
        h.records.clear(); assert wk(*a_week(), away(LEE, ok(cancelled=1), cancelled=dict(by=LEE)), away(LEE, dict(on(12, 0), needed=False, relief=5, approved=5, history=5)), away(LEE, dict(on(9, 0, 1, 5), p="x"))) == good and h.records == [], "what does not count is not read"
    finally: KINDS.removeHandler(h)

@t
def the_summary_stands_alone():
    """pure: no Flask, and no file is read or written"""
    code = "import sys; import relief.summary; print([m for m in ('relief.web', 'relief.bot', 'relief.tgweb', 'relief.report', 'flask') if m in sys.modules])"
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=dict(os.environ, DATA_DIR=tempfile.mkdtemp()), capture_output=True, text=True); assert p.stdout.strip() == "[]", (p.stdout, p.stderr[-400:])
    boom = lambda *a, **k: 1 / 0
    with stand_in(store, "read_json", boom), stand_in(store, "published", boom), stand_in(AP, "load", boom), stand_in(AP, "_read", boom), stand_in(tgdb, "db", boom), stand_in(absences, "load", boom), stand_in(absences, "all_records", boom): assert wk(*a_week())["periods"] == 14

@t
def no_reason_is_in_the_numbers():
    r = a_week()[2]; r["lessons"][1].update(pick=dict(who=BUSY, by="ai", reason="lemur-pick", at=st(14, "15:00")), work=dict(text="okapi-work", link="", files=[]))
    r["lessons"][1]["history"] += [hist("pick", BUSY, 14, why="lemur-pick"), hist("dropped", SAM, 14, why="tapir-drop")]; v = wk(*a_week(), r); text = json.dumps(v, ensure_ascii=False) + RE.summary_text(v)
    for word in ("zebra", "quokka", "lemur", "walrus", "okapi", "tapir", "Other", "asked to"): assert word not in text, word

@t
def the_summary_text_is_the_briefs():
    v = dict(label="Week 6 (12–16 Oct)", periods=38, absences=9, fat_role=True, fat_periods=21, fat_percent=55, ahead=12, on_day=26, on_time=35, late=2, never=1, waiting=0, asked=3, moved=3, kept=0,
             top=[("Ms Irene Chua", 9), ("Mdm Kavitha Pillai", 8), ("Mr Darren Lim", 6)], by_dept=[("Science", 14), ("Maths", 10), ("English", 8), ("Art", 4), ("PE", 2)])
    MOCKUP = ("📊 Relief summary · Week 6 (12–16 Oct)\n38 relief periods for 9 absences\n• Flexi Adjuncts covered 21 (55%)\n• Planned ahead 12 · arranged on the day 26\n• Acknowledged on time 35 · late 2 · never 1\n• Asked to change 3 (all moved)\n"
              "Most relief this week:\nMs Irene Chua 9 · Mdm Kavitha Pillai 8 · Mr Darren Lim 6\nBy department of the absent teacher:\nScience 14 · Maths 10 · English 8 · others 6")
    assert RE.summary_text(v) == MOCKUP and RE.OPEN_SUMMARY == "Open the full summary"
    mock = re.sub(r"<[^>]+>", "", open(os.path.join(ROOT, "docs", "superpowers", "specs", "2026-11-20-relief-module-mockups.html"), encoding="utf-8").read())
    for line in MOCKUP.split("\n"): assert line in mock, line
    line = lambda n, **kw: RE.summary_text(dict(v, **kw)).split("\n")[n]
    assert line(1, periods=1, absences=1) == "1 relief period for 1 absence" and line(1, periods=1) == "1 relief period for 9 absences" and line(1, absences=1) == "38 relief periods for 1 absence"
    assert line(4, waiting=4) == "• Acknowledged on time 35 · late 2 · never 1 · waiting 4"
    for asked_, moved, want in ((0, 0, "0"), (3, 0, "3 (0 moved)"), (3, 2, "3 (2 moved)"), (3, 3, "3 (all moved)"), (1, 1, "1 (all moved)"), (1, 0, "1 (0 moved)")): assert line(5, asked=asked_, moved=moved) == f"• Asked to change {want}"
    got = RE.summary_text(dict(v, fat_role=False)); assert got == MOCKUP.replace("• Flexi Adjuncts covered 21 (55%)\n", ""), got
    assert line(2, fat_periods=0, fat_percent=0) == "• Flexi Adjuncts covered 0 (0%)", "a role is set, and none of them covered"
    for n, want in ((1, "Science 14"), (2, "Science 14 · Maths 10"), (3, "Science 14 · Maths 10 · English 8"), (4, "Science 14 · Maths 10 · English 8 · others 4")): assert line(-1, by_dept=v["by_dept"][:n]) == want
    assert line(7, top=v["top"][:1]) == "Ms Irene Chua 9" and len(RE.summary_text(v).split("\n")) == 10

# ---- the message
def weekly(hm, day=16): at(hm, day); return [k for k in RE.tick() if k.startswith("weekly:")]
def weeked(*names, monday=W12): return [f"weekly:{monday}:{n}" for n in names or (TEAM,)]
def marked(): return tgdb.get_state("weekly_last")
def a_relief():
    """Sam's relief of K5, approved and told on the day, acknowledged at 07:15 -> the absence's id"""
    i = today_reliefs((K5, SAM)); at("07:15", 13); CV.acknowledge(i, K5, SAM); return i
TEXT_K5 = ("📊 Relief summary · Week 6 (12–16 Oct)\n2 relief periods for 1 absence\n• Planned ahead 0 · arranged on the day 2\n• Acknowledged on time 2 · late 0 · never 0\n• Asked to change 0\nMost relief this week:\nMr Sam Tan 2\nBy department of the absent teacher:\nScience 2")

@t
def the_message_goes_once_at_its_time_and_not_without_reliefs():
    with school(SAM, TEAM, LEE, EVE, HUGO):
        a_relief()
        for hm, day in (("08:00", 13), ("15:00", 15), ("00:00", 16), ("14:59:59", 16)): assert weekly(hm, day) == [] and marked() is None and outs("weekly") == [], (hm, day)
        OB._wake.clear(); assert weekly("15:00") == weeked(LEE, TEAM) and OB._wake.is_set() and marked() == MON12.toordinal(); a, b = outs("weekly")
        assert (a["name"], b["name"], a["kind"], json.loads(a["files"])) == (LEE, TEAM, "weekly", []) and a["text"] == b["text"] == TEXT_K5, a["text"]
        assert buttons_of(a) == [[dict(text="Open the full summary", url=BASE + "/relief?week=2026-10-12#summary")]] and json.loads(a["ref"])["made"] == "2026-10-16T15:00:00+08:00"
        OB._wake.clear()
        for hm, day in (("15:00", 16), ("15:01", 16), ("23:59", 16), ("14:59", 17), ("15:00", 17), ("08:00", 18), ("15:00", 19), ("15:00", 22)): assert weekly(hm, day) == [] and not OB._wake.is_set(), (hm, day)
        at("15:02", 16); assert send() >= 2 and said(TEAM)[-1] == TEXT_K5 == said(LEE)[-1] and not any("summary" in x for n in (EVE, HUGO, SAM) for x in said(n)), "the team alone"
        # the next week's, its own; none of it without a relief, and it is done with
        at("08:00", 19); assert weekly("15:00", 23) == [] and marked() == datetime.date(2026, 10, 19).toordinal(); j = absent(dates=["2026-10-27"]); kn = absences.load(j)["lessons"][0]["key"]; give(j, kn, MAYA); assert weekly("15:01", 23) == []
        assert weekly("15:00", 30) == weeked(LEE, TEAM, monday="2026-10-26") and outs("weekly", TEAM)[-1]["text"].startswith("📊 Relief summary · Week 8 (26–30 Oct)\n")
    for f in (lambda i: absences.cancel(i, "x", HUGO), lambda i: absences.not_needed(i, K5, "x", HUGO)):                  # no relief that week: nothing, and done with
        with school(SAM, TEAM): i = today_reliefs((K5, SAM)); f(i); assert weekly("15:00") == [] and marked() == MON12.toordinal() and outs("weekly") == []
    with school(TEAM): assert not os.path.isdir(absences.DIR) and weekly("15:00") == [] and marked() == MON12.toordinal()
    with exam_school(SAM, TEAM): a_relief(); exam(); assert weekly("15:00") == [] and marked() == MON12.toordinal(), "its one lesson is stopped"
    with school(SAM, TEAM, fat_role="Adjunct"): a_relief(); weekly("15:00"); assert "\n• Flexi Adjuncts covered 0 (0%)\n" in outs("weekly")[0]["text"]
    with school(SAM, TEAM, times=dict(weekly_at="07:30")): today_reliefs((K5, SAM)); j = absent(dates=["2026-10-16"]); give(j, KF, MAYA); assert weekly("07:30") == weeked(); assert "\n4 relief periods for 2 absences\n• Planned ahead 2 · arranged on the day 2\n• Acknowledged on time 0 · late 0 · never 2 · waiting 2\n" in outs("weekly")[0]["text"], outs("weekly")[0]["text"]

@t
def the_week_it_is_about_goes_by_the_day_it_is_sent():
    for day_, sent_on in (("Mon", 19), ("Tue", 20), ("Wed", 21), ("Thu", 22), ("Fri", 16)):
        with school(SAM, TEAM, times=dict(weekly_day=day_, weekly_at="08:30")):
            a_relief(); assert weekly("08:29:59", sent_on) == [] and marked() is None; assert weekly("08:30", sent_on) == weeked() and marked() == MON12.toordinal() and outs("weekly")[0]["text"] == TEXT_K5, day_
            assert buttons_of(outs("weekly")[0])[0][0]["url"].endswith("?week=2026-10-12#summary") and weekly("08:31", sent_on) == []
    with school(SAM, TEAM, times=dict(weekly_day="Wed", weekly_at="08:30")): a_relief(); assert weekly("08:30", 14) == [] and marked() == datetime.date(2026, 10, 5).toordinal(), "in the week itself it is about the one before, which had none"
    # late: until 24 hours after its time, still about its own week; then not at all
    for hm, day, goes in (("15:07", 16, True), ("23:59", 16, True), ("00:30", 17, True), ("14:59:59", 17, True), ("15:00", 17, False), ("10:00", 18, False), ("08:00", 19, False), ("14:59", 23, False)):
        with school(SAM, TEAM): a_relief(); assert weekly(hm, day) == (weeked() if goes else []) and (marked() is None) is not goes, (hm, day)
    with school(SAM, TEAM, times=dict(weekly_day="Mon", weekly_at="23:30")): a_relief(); assert weekly("10:00", 20) == weeked(), "a Monday's, on Tuesday: the same week"
    # a holiday, and outside every term, too
    for cal in (dict(TERM, holidays=[dict(start="2026-10-16", end="2026-10-16", name="A holiday")]), dict(terms=[dict(TERM["terms"][0], end="2026-10-15")], holidays=[])):
        with school(SAM, TEAM): a_relief(); store.write_json(RS.PATH, dict(calendar=cal)); assert weekly("15:00") == weeked()
    with school(SAM, TEAM): a_relief(); store.write_json(RS.PATH, dict(calendar=dict(terms=[], holidays=[]))); assert weekly("15:00") == weeked() and outs("weekly")[0]["text"].startswith("📊 Relief summary · 12–16 Oct\n"), "no calendar"
    m = SCHOOL["model"]; old = dict(m["school"])
    try:
        with school(SAM, TEAM): a_relief(); m["school"].pop("start_time"); assert weekly("15:00") == weeked(), "nor does a timetable with no times stop it"
    finally: m["school"].clear(); m["school"].update(old)
    # the day or the time changed meanwhile: a week goes once
    with school(SAM, TEAM):
        a_relief(); assert weekly("15:00") == weeked(); store.write_json(RS.PATH, dict(calendar=TERM, times=dict(weekly_day="Fri", weekly_at="16:00"))); assert weekly("16:00") == []
        store.write_json(RS.PATH, dict(calendar=TERM, times=dict(weekly_day="Mon", weekly_at="08:00"))); assert weekly("08:00", 19) == []; store.write_json(RS.PATH, dict(calendar=TERM, times=dict(weekly_day="Thu", weekly_at="23:00"))); assert weekly("08:30", 16) == [] and len(outs("weekly")) == 1
    # what is kept, changed by hand: the queue still has it once
    with school(SAM, TEAM):
        a_relief(); weekly("15:00")
        for odd in ("odd", None, [1], {}, 0): tgdb.set_state("weekly_last", odd); assert weekly("15:05") == [] and marked() == MON12.toordinal() and len(outs("weekly")) == 1, odd
    with school(SAM, TEAM):                                                                # times that cannot be read: Fri, 15:00
        a_relief()
        for bad in ("x", None, 5, [], {}, dict(weekly_day="Sun"), dict(weekly_day=5), dict(weekly_day=["Fri"]), dict(weekly_at="x"), dict(weekly_at="25:00"), dict(weekly_at=None), dict(weekly_at=15), dict(weekly_at="9:00"), dict(weekly_at="15:00 "), dict(weekly_day=None, weekly_at=None)):
            store.write_json(RS.PATH, dict(calendar=TERM, times=bad))
            with tgdb.db() as c: c.execute("DELETE FROM state WHERE k='weekly_last'"); c.execute("DELETE FROM outbox WHERE kind='weekly'")
            assert weekly("14:59") == [] and weekly("15:00") == weeked(), bad
        store.write_json(RS.PATH, dict(calendar=TERM, times=dict(weekly_day="Thu", weekly_at="x")))
        with tgdb.db() as c: c.execute("DELETE FROM state WHERE k='weekly_last'"); c.execute("DELETE FROM outbox WHERE kind='weekly'")
        assert weekly("14:59", 22) == [] and weekly("15:00", 22) == weeked(), "each on its own"

@t
def the_message_waits_while_nothing_can_be_worked_out():
    with exam_school(SAM, TEAM):
        a_relief(); bot_ = tgdb.get_state("bot")
        with no_pub(): assert weekly("15:00") == [] and marked() is None
        with broken_accounts(): assert weekly("15:01") == [] and marked() is None
        with unreadable(): assert weekly("15:02") == [] and marked() is None
        for name in ("_links", "_when"):
            with stand_in(FL, name, lambda *a, **k: 1 / 0): assert weekly("15:03") == [] and marked() is None
        tgdb.set_state("bot", dict(bot_, key="another")); assert weekly("15:04") == [] and marked() is None; tgdb.set_state("bot", bot_)
        os.environ.pop("TELEGRAM_BOT_TOKEN"); assert weekly("15:05") == [] and marked() is None; os.environ["TELEGRAM_BOT_TOKEN"] = "practice"
        chat = links.unlink(TEAM); assert weekly("15:06") == [] and marked() is None; links.link(TEAM, chat, None)
        with record(TEAM, extras=dict(relief=False, exams=None, admin=False)): assert weekly("15:07") == [] and marked() is None
        with record(TEAM, off=True): assert weekly("15:08") == [] and marked() is None
        for module, name in ((TE, "_records"), (RS, "load"), (SU, "week"), (AP, "staff"), (links, "reachable"), (RE, "summary_text")):
            with stand_in(module, name, lambda *a, **k: 1 / 0): assert weekly("15:09") == [] and outs("weekly") == [], name
        assert marked() is None, "nothing is marked before the text is there"
        def locked(*a, **k): raise sqlite3.OperationalError("made up")
        with stand_in(tgdb, "raise_state", locked): assert weekly("15:10") == [] and outs("weekly") == []
        assert weekly("15:11") == weeked() and marked() == MON12.toordinal()
    with school(SAM, TEAM):                                                                # it stops between the mark and the queue: not sent again
        a_relief()
        def dies(*a, **k): raise Killed()
        with stand_in(OB, "queue", dies):
            try: weekly("15:00"); raise AssertionError("it should have stopped")
            except Killed: pass
        assert marked() == MON12.toordinal() and weekly("15:01") == [] and outs("weekly") == []
    with school(SAM, TEAM, LEE):                                                           # one that cannot be queued never stops the rest
        a_relief(); real = OB.queue
        with stand_in(OB, "queue", lambda key, name, *a, **k: 1 / 0 if name == LEE else real(key, name, *a, **k)): assert weekly("15:00") == weeked()
    with school(SAM, TEAM, LEE):                                                           # two copies of the app
        a_relief(); at("15:00", 16); got = []; at_once(*[lambda: got.append(RE.tick())] * 6); assert sorted(x for g in got for x in g) == weeked(LEE, TEAM) and sum(1 for g in got if g) == 1
    with school(SAM, TEAM):                                                                # a file of an absence that cannot be read: the rest counts, its kind logged
        a_relief(); j = absent(teacher=RUTH, by=HUGO); open(absences._path(j), "w", encoding="utf-8").write("{ a private word"); h, seen, real = Grab(), [], TE._records; KINDS.addHandler(h)
        with stand_in(TE, "_records", lambda: (seen.append(absences._LOCK.locked()), real())[1]): assert weekly("15:00") == weeked() and outs("weekly")[0]["text"] == TEXT_K5
        KINDS.removeHandler(h); assert set(seen) == {True} and not absences._LOCK.locked() and h.records and all("private" not in r.getMessage() and j not in r.getMessage() and r.exc_info is None for r in h.records)

@t
def a_week_with_an_absence_that_cannot_be_read_and_no_relief_is_not_done_with():
    def damage_(i):
        """the absence's file cannot be read -> what makes it good again"""
        p = absences._path(i); good = open(p, encoding="utf-8").read(); open(p, "w", encoding="utf-8").write("{ a private word"); return lambda: open(p, "w", encoding="utf-8").write(good)
    with school(SAM, TEAM):                                                                # the only file there is: said once it can be read
        good = damage_(a_relief())
        for hm in ("15:00", "15:01", "15:09:59"): assert weekly(hm) == [] and marked() is None and outs("weekly") == [], hm
        good(); assert weekly("15:10") == weeked() and marked() == MON12.toordinal() and outs("weekly")[0]["text"] == TEXT_K5 and weekly("15:11") == [] and len(outs("weekly")) == 1
    h = Grab()
    with school(SAM, TEAM):                                                                # never: nothing, and nothing raised; made good after the 24 hours, nothing either
        good = damage_(a_relief()); KINDS.addHandler(h)
        for hm, day in (("15:00", 16), ("15:01", 16), ("23:59", 16), ("00:00", 17), ("14:59:59", 17), ("15:00", 17), ("12:00", 18), ("15:00", 19), ("15:00", 22)): assert weekly(hm, day) == [] and marked() is None and outs("weekly") == [], (hm, day)
        KINDS.removeHandler(h); good(); assert weekly("15:01", 22) == [] and marked() is None
        assert h.records and {r.getMessage().split(" (")[0] for r in h.records} == {"an absence could not be read"} and not any("private" in r.getMessage() or r.exc_info for r in h.records), [r.getMessage() for r in h.records]
        at("08:00", 22); j = absent(dates=["2026-10-27"]); give(j, absences.load(j)["lessons"][0]["key"], MAYA); assert weekly("15:00", 30) == weeked(monday="2026-10-26"), "the weeks after it go as ever"
    with school(SAM, TEAM):                                                                # one that can be read, with no relief of that week, changes nothing
        good = damage_(a_relief()); absent(teacher=RUTH, by=HUGO); assert weekly("15:00") == [] and marked() is None; good(); assert weekly("15:01") == weeked()
    with school(SAM, MAYA, TEAM):                                                          # with a relief that can be read, it goes: the rest counts
        damage_(a_relief()); j = absent(teacher=RUTH, by=HUGO); give(j, KR, MAYA); assert weekly("15:00") == weeked() and "\n1 relief period for 1 absence\n" in outs("weekly")[0]["text"] and marked() == MON12.toordinal()
    with school(SAM, TEAM): good = damage_(a_relief()); good(); absences.cancel(absences.all_records()[0]["id"], "x", HUGO); assert weekly("15:00") == [] and marked() == MON12.toordinal(), "all can be read, and no relief: done with"

@t
def the_report_and_the_summary_do_not_stop_each_other():
    def both(hm="07:30"): at(hm, 16); return [k.split(":")[0] for k in RE.tick()]
    def week_(): a_relief(); j = absent(dates=["2026-10-16"]); give(j, KF, SAM); swept()
    early = dict(times=dict(weekly_at="07:30"))
    h = Grab(); KINDS.addHandler(h)
    def boom(*a, **k): raise LookupError(f"{SAM} a private line")
    try:
        with school(SAM, TEAM, **early): week_(); assert both() == ["report", "weekly"] and both() == [] and both("07:45") == ["report"]
        for module, name, want in ((SU, "week", ["report"]), (RE, "summary_text", ["report"]), (RE, "report_text", ["weekly"]), (TE, "said", ["weekly"]), (RE, "_mark", ["weekly"]), (RE, "school_day", ["weekly"])):
            with school(SAM, TEAM, **early):
                week_(); h.records.clear()
                with stand_in(module, name, boom): assert both() == want, name
                assert len(h.records) == 1 and "LookupError" in h.records[0].getMessage() and "private" not in h.records[0].getMessage() and h.records[0].exc_info is None, [r.getMessage() for r in h.records]
                assert both("07:31") == (["weekly"] if want == ["report"] else ["report"]), "a minute later"
        with school(SAM, TEAM, **early):                                                   # what both go by is read once
            week_(); reads = []
            def counted(f, name): return lambda *a, **k: (reads.append(name), f(*a, **k))[1]
            with stand_in(RS, "load", counted(RS.load, "settings")), stand_in(links, "connected", counted(links.connected, "bot")): assert both() == ["report", "weekly"]
            assert reads.count("settings") == 1, reads
            for hm in ("07:31", "07:32"):                                                  # done with: next to nothing is read
                reads.clear()
                with stand_in(TE, "_records", counted(TE._records, "records")), stand_in(FL, "_links", counted(FL._links, "links")), stand_in(links, "reachable", counted(links.reachable, "reach")): assert both(hm) == []
                assert reads == [], reads
    finally: KINDS.removeHandler(h)

@t
def an_old_summary_is_not_sent_nor_to_who_left_the_team():
    with school(SAM, TEAM, LEE):
        a_relief(); weekly("15:00"); r = dict(outs("weekly", TEAM)[0]); r["ref"] = json.loads(r["ref"])
        at("14:59:59", 17); assert TE.still_true(r) is True; at("15:00", 17); assert TE.still_true(r) is False; at("15:30", 16)
        with record(TEAM, extras=dict(relief=False, exams=None, admin=False)): assert TE.still_true(r) is False
        with broken_accounts():
            try: TE.still_true(r); raise AssertionError("nobody's rights are known")
            except ValueError: pass
        with record(LEE, extras=dict(relief=False, exams=None, admin=False)): send()
        assert state(weeked(LEE)[0]) == "dropped" and state(weeked()[0]) == "sent" and said(LEE) == [] and said(TEAM)[-1] == TEXT_K5 and weekly("15:31") == []
    with school(SAM, TEAM): a_relief(); weekly("15:00"); at("15:00", 17); send(); assert state(weeked()[0]) == "dropped" and not any("summary" in x for x in said(TEAM))
    with school(SAM, TEAM, base=None): a_relief(); weekly("15:00"); send(); assert "reply_markup" not in calls("sendMessage")[-1], "an address that is not known: no button"

@t
def a_date_that_cannot_be_read_stops_no_lesson_of_the_message():
    with exam_school(SAM, MAYA, TEAM):
        i = today_reliefs((K5, SAM), (K2, MAYA)); exam()
        with damage(): assert weekly("15:00") == weeked() and "\n5 relief periods for 1 absence\n" in outs("weekly")[0]["text"]
    with exam_school(SAM, MAYA, TEAM):
        today_reliefs((K5, SAM), (K2, MAYA)); exam()
        with damage("2026-10-14"): assert weekly("15:00") == weeked() and "\n3 relief periods for 1 absence\n" in outs("weekly")[0]["text"], "another date's"

# ---- the page
@t
def the_summary_route_needs_the_team():
    with exam_school(SAM, TEAM):
        i = today_reliefs((K5, SAM), (K2, MAYA)); at("09:30", 13); CV.acknowledge(i, K5, SAM)
        for name in (EVE, SAM, ROSA): assert call(name, "get", SUMMARY_URL, code=403) == dict(error=WB.TEAM_ONLY)
        assert call(HUGO, "get", SUMMARY_URL, code=403) == dict(error=WB.TEAM_ONLY), "management plans; the summary is the team's"
        assert client({}).get(SUMMARY_URL).get_json() == AGAIN == who(EXE).get(SUMMARY_URL).get_json() == client(dict(role="committee")).get(SUMMARY_URL).get_json()
        with no_pub(): assert call(TEAM, "get", SUMMARY_URL, code=409) == dict(error=WB.NO_PUB)
        def made(monday=MON12, **kw): return json.loads(json.dumps(SU.week(SCHOOL, rs(), absences.all_records(), monday, clock.now, **kw)))
        got = call(TEAM, "get", SUMMARY_URL); assert got == made() and got["periods"] == 5 and got["label"] == "Week 6 (12–16 Oct)" and got["fat_role"] is False and [x["ack"] for x in got["rows"]] == ["waiting", "09:30"], got
        for d in (12, 13, 14, 15, 16, 17, 18): assert call(LEE, "get", f"{SUMMARY_URL}?week=2026-10-{d}") == got, d
        for d, monday in ((11, datetime.date(2026, 10, 5)), (19, datetime.date(2026, 10, 19))): other = call(TEAM, "get", f"{SUMMARY_URL}?week=2026-10-{d}"); assert other == made(monday) and other["rows"] == [] and nums(other) == ZERO, d
        assert call(TEAM, "get", SUMMARY_URL + "?week=") == got; at("10:00", 20); assert call(TEAM, "get", SUMMARY_URL)["start"] == "2026-10-19", "left out: this week"; at("09:30", 13)
        for odd in ("x", "2026-13-01", "2026-10-32", "2026-10", "12 Oct", "2026-10-12T09:00", "0", "-1", "%00", "2026-10-12%0a", "9" * 400, "٢٠٢٦-١٠-١٢"): assert call(TEAM, "get", f"{SUMMARY_URL}?week={odd}", code=400) == dict(error=absences.WRONG), odd
        for far in ("0001-01-01", "0001-01-07", "9999-12-31"): assert nums(call(TEAM, "get", f"{SUMMARY_URL}?week={far}")) == ZERO, far
        # what an approved exam stops is left out; exams that cannot be read stop nothing
        e = exam(); got = call(TEAM, "get", SUMMARY_URL); assert got == made(links=exam_links()) and got["periods"] == 3
        with stand_in(SC, "read_on_site", lambda: 1 / 0), stand_in(A.app.logger, "exception", lambda *a, **k: None): assert call(TEAM, "get", SUMMARY_URL)["periods"] == 5
        withdraw(e)
        # no token, nobody linked, no bot: the page works; nothing is sent, or marked as sent
        os.environ.pop("TELEGRAM_BOT_TOKEN"); wipe(); assert call(TEAM, "get", SUMMARY_URL)["periods"] == 5 and marked() is None and outs("weekly") == []
        shutil.rmtree(absences.DIR); assert nums(call(TEAM, "get", SUMMARY_URL)) == ZERO
    assert next(r for r in A.app.url_map.iter_rules() if r.rule == SUMMARY_URL).methods - {"HEAD", "OPTIONS"} == {"GET"}

@t
def the_page_never_holds_a_reason():
    with school(SAM, MAYA, TEAM):
        at("06:50", 13); i = absent(by=HUGO, reason="Other", reason_text="zebra-reason", remarks="quokka-remark"); give(i, K5, SAM); CV.ask_change(i, K5, "walrus-why", SAM); new_pick(i, K5, MAYA, "lemur-pick")
        change_record(i, lambda r: [x.update(work=dict(text="okapi-work", link="", files=[])) for x in r["lessons"]])
        on_cover(TEAM, i, K5, "approve", dict(who=MAYA)); raw = who(TEAM).get(SUMMARY_URL).get_data(as_text=True); assert json.loads(raw)["moved"] == 1; weekly("15:00"); raw += json.dumps(outs("weekly"), ensure_ascii=False)
        for word in ("zebra", "quokka", "walrus", "lemur", "okapi", "Medical", "Other"): assert word not in raw, word

@t
def the_summary_page_is_there_for_the_team():
    read = lambda f: open(os.path.join(ROOT, "static", f), encoding="utf-8").read()
    html, js, page = read("relief.html"), read("relief.js"), read("relief-summary.js")
    assert re.search(r'id="tab-load".*?</button>\s*<button type="button" role="tab" id="tab-summary" data-tab="summary" aria-controls="pane-summary" hidden>Weekly summary</button>', html) and '<section class="pane" id="pane-summary" role="tabpanel" aria-labelledby="tab-summary" hidden></section>' in html
    assert html.index("/static/relief-load.js") < html.index('<script src="/static/relief-summary.js"></script>') and '["load", me => !!me.can_team], ["summary", me => !!me.can_team]]' in js
    assert 'R.tab("summary"' in page and "/api/relief/summary?week=" in page and 'aria-label="Week before"' in page and 'aria-label="Week after"' in page and "No relief this week." in page
    for word in ("localStorage", "eval(", "//cdn", "http://", "https://"): assert word not in page, word

@t
def the_summary_is_quick():
    with exam_school(SAM, TEAM):
        exam("3B", name=EXAM2); i = today_reliefs((K5, SAM), (K2, MAYA)); whole_ = absences.load(i)
        for n in range(600):
            r = json.loads(json.dumps(whole_)); r.update(id=f"{n:012x}", teacher=f"Mx Made Up {n}")
            if n % 10: r.update(dates=["2026-10-01"], lessons=[dict(x, date="2026-10-01", key=x["key"].replace(D13, "2026-10-01")) for x in r["lessons"]])
            absences._save(r)
        began = time.process_time(); v = SU.week(SCHOOL, rs(), absences.all_records(), MON12, clock.now, links=exam_links()); took = time.process_time() - began; assert adds_up(v)["absences"] == 61 and len(v["rows"]) == 122 and took < 1.5, took
        at("15:00", 16); began = time.process_time(); assert weekly("15:00") == weeked(); first = time.process_time() - began; began = time.process_time(); assert weekly("15:01") == []; second = time.process_time() - began; assert first < 2.0 and second < 0.5, (first, second)

# ---- Task 8: asking for relief on Telegram ----
import glob, io  # noqa: E402
from relief import asking as AK, files as FI  # noqa: E402

HI, DAY_ROWS = "Hi Ms Evelyn Koh. Which day are you away?", [["Today, Mon 12 Oct"], ["Tomorrow, Tue 13 Oct"], ["Several days"], ["Another day"]]
SPAN, SPAN_ROWS = "Whole day, or some periods?", [["Whole day", "Some periods"]]
WHICH_DAY, WHICH_DAYS, TICK_ONE = "Which day?", "Which days? Tick them, then press Done.", "Tick at least one day."
FROM_P, TO_P, NO_DAYS = "From which period?", "To which period?", "There are no school days coming up in the calendar."
REASON, REASON_ROWS, SAY_WHY = "Reason?", [["Medical", "Child sick"], ["Course", "Other"]], "Say why in one line."
RIGHT_ROSA, WHO_IS = "Your reporting officer is Ms Rosa Ng. Right?", "Who is your reporting officer? Type part of their name."
WHO_HIT, NOT_HERE, NOBODY_MATCHES = "Who is your reporting officer?", "Not here? Type more of the name.", "Nobody on the staff list matches that. Type part of their name."
WORK_2 = "Work for 1C Science P3–P5 on Tue 13 Oct (09:00)? Type it, send a file or a photo, or tap Later."
WORK_5 = "Work for 1A, 1B Science (G2) P6–P7 on Tue 13 Oct (10:30)? Type it, send a file or a photo, or tap Later."
WORK_W = "Work for 2A Science P2 on Wed 14 Oct (08:30)? Type it, send a file or a photo, or tap Later."
NO_LESSONS, PRESS_ONE, SEND_ONE = "There are no lessons to cover in that time.", "Please press one of the buttons.", "Send text, a file or a photo."
NOT_SENT, NOTHING_SENT = "Your request for relief was not sent. Send /relief to start again.", "Cancelled: nothing was sent."
ON_2, ON_5 = "• 1C Science P3–P5 on Tue 13 Oct: ", "• 1A, 1B Science (G2) P6–P7 on Tue 13 Oct: "
LIST_HEAD, NONE_YET = "Relief for Tue 13 Oct · whole day\nReason: Medical\nReporting officer: Ms Rosa Ng", "no work yet"
SET_, SET_LINK, SET_FILE, SET_BOTH = "work set (text)", "work set (link)", "work set (1 file)", "work set (text, 1 file)"
NOT_TAKEN = "That was not attached to any lesson: add it in the app."
LIST_ROWS, FIRST_ROWS, LAST_ROWS = [["Send", "Start again"]], [["Later, in the app"], ["Later for all the rest"]], [["Same as before", "Later, in the app"]]
TOO_MANY = "A lesson can have at most 5 files."
OPEN_MINE = [["Open in the app"]]
LINE = "a line"

def sent_text(n, m, tail="Ms Rosa Ng will be told."): return f"✅ Sent to the relief team: {n}, {m}. {tail}"
def keyboard(markup):
    """what a message offers: the rows of its buttons' labels, LINE (the line opens for the answer), or None"""
    return None if not markup else LINE if "force_reply" in markup else [[b["text"] for b in row] for row in markup["inline_keyboard"]]
def heard(name, f): return [(x, keyboard(b)) for x, b in talk_to(name, f)]
def board(name):
    """the last question with buttons in name's chat, as it is now: (its text, {label: callback data})"""
    got = None
    for m, p in list(tg.PRACTICE_LOG):
        kb = (p.get("reply_markup") or {}).get("inline_keyboard")
        if p.get("chat_id") != CHATS[name] or not kb or not any("callback_data" in b for row in kb for b in row): continue
        got = (p["text"] if "text" in p else got[0], {b["text"]: b["callback_data"] for row in kb for b in row if "callback_data" in b})
    return got
def rows_now(name):
    """the rows of labels of that question, as they are now"""
    return [keyboard(p["reply_markup"]) for m, p in list(tg.PRACTICE_LOG) if p.get("chat_id") == CHATS[name] and (p.get("reply_markup") or {}).get("inline_keyboard")][-1]
def asking_of(name): return next((d for c, k, d, u in talks() if (c, k) == (CHATS[name], "ask")), None)
def tapping(name, label, chat=None):
    """a press of that button of the last question, as Telegram posts it"""
    text, keys_ = board(name); d = asking_of(name)
    return callback(keys_[label], dict(message_id=(d or {}).get("question") or 1, date=1, chat=dict(id=CHATS[name], type="private"), text=text), chat)
def tap(name, *labels):
    """what the bot says to a press of that button (of each, one after another: to the last)"""
    for label in labels: u = tapping(name, label); got = heard(name, lambda: hook(u))
    return got
def answered(u):
    """what the press is answered: (the text, an alert); pressed again, it is another update"""
    n = len(answers()); hook(dict(u, update_id=next(_ids))); got = answers()[n:]; assert len(got) == 1, got
    return got[0]
def relief_(name=EVE): return heard(name, lambda: say(name, "/relief"))
def says(name, text, **more): return heard(name, lambda: say(name, text, **more))
def _with(name, **more):
    u = msg(None, CHATS[name]); del u["message"]["text"]; u["message"].update(more); return u
def a_doc(name, file_name="Worksheet.pdf", file_id="F1", size=1000, **more):
    return _with(name, document=dict(file_id=file_id, file_unique_id="u", file_name=file_name, file_size=size), **more)
def a_photo(name, file_id="P1", **more):
    return _with(name, photo=[dict(file_id=file_id + "-s", file_unique_id="a", width=90, height=67, file_size=1200), dict(file_id=file_id, file_unique_id="c", width=1280, height=960, file_size=210000),
                              dict(file_id=file_id + "-m", file_unique_id="b", width=320, height=240, file_size=20000)], **more)
def doc(name, *a, **k): return heard(name, lambda: hook(a_doc(name, *a, **k)))
def photo(name, *a, **k): return heard(name, lambda: hook(a_photo(name, *a, **k)))
def to_work(name=EVE, day="Tomorrow, Tue 13 Oct", reason="Medical"):
    """/relief, as far as the first lesson's work (or what is asked in its place) -> what was said last"""
    say(name, "/relief"); tap(name, day, "Whole day", reason)
    if reason == "Other": say(name, "zebra-reason")
    if board(name)[0] == RIGHT_ROSA: return tap(name, "Yes")
    say(name, "rosa"); return tap(name, "Ms Rosa Ng")
def to_list(name=EVE, **kw): to_work(name, **kw); return tap(name, "Later for all the rest")
def sends(name=EVE): return tap(name, "Send")
def mine(name=EVE): return absences.for_teacher(name)
def only(name=EVE):
    r, = mine(name); return r
def plain(r):
    """a record without what is never the same twice (its id, its files' ids) or says how it came (via)"""
    r = json.loads(json.dumps({k: v for k, v in r.items() if k not in ("id", "via")}))
    for x in r["lessons"]:
        for f in x["work"]["files"]: f.pop("id")
    return r
def by_page(name=EVE, files=(), **body):
    """the same absence sent by the page's form (static/relief.js's send and attach) -> its record"""
    c = who(name); d = dict(dict(dates=["2026-10-13"], periods=None, reason="Medical", reason_text="", reporting_officer=ROSA, lessons=[]), **body)
    r = c.post("/api/relief/absences", json=d); assert r.status_code == 200, r.get_json()
    i = r.get_json()["id"]
    for key, name_, data in files:
        f = c.post(f"/api/relief/absences/{i}/files", data=dict(file=(io.BytesIO(data), name_)), content_type="multipart/form-data").get_json()
        w = next(x for x in absences.load(i)["lessons"] if x["key"] == key)["work"]
        r = c.put(f"/api/relief/absences/{i}/lessons/{quoted(key)}/work", json=dict(text=w["text"], link=w["link"], files=[dict(id=f["id"], name=f["name"])], known=[])); assert r.status_code == 200, r.get_json()
    return absences.load(i)
def raw_store():
    """every byte of the Telegram store's files"""
    return b"".join(open(p, "rb").read() for p in glob.glob(tgdb.PATH + "*"))
def secs(hm, day=12):
    return datetime.datetime.fromisoformat(f"2026-10-{day:02d}T{hm if len(hm) > 5 else hm + ':00'}+08:00").timestamp()

@t
def the_asking_texts_are_the_plans():
    assert (AK.HI, AK.SEVERAL, AK.ANOTHER, AK.WHICH_DAY, AK.WHICH_DAYS, AK.DONE, AK.TICK_ONE, AK.NO_DAYS) == ("Hi {name}. Which day are you away?", "Several days", "Another day", WHICH_DAY, WHICH_DAYS, "Done", TICK_ONE, NO_DAYS)
    assert (AK.WHOLE_OR_SOME, AK.WHOLE, AK.SOME, AK.FROM, AK.TO, AK.REASON, AK.SAY_WHY) == (SPAN, "Whole day", "Some periods", FROM_P, TO_P, REASON, SAY_WHY)
    assert (AK.RIGHT, AK.YES, AK.SOMEONE_ELSE, AK.WHO, AK.NOT_HERE, AK.NOBODY) == ("Your reporting officer is {name}. Right?", "Yes", "Someone else", WHO_IS, NOT_HERE, NOBODY_MATCHES)
    assert (AK.SAME, AK.LATER, AK.LATER_ALL, AK.PRESS_ONE, AK.SEND_ONE, AK.SEND, AK.START_AGAIN) == ("Same as before", "Later, in the app", "Later for all the rest", PRESS_ONE, SEND_ONE, "Send", "Start again")
    assert (AK.NOT_SENT, AK.CANCELLED, AK.NOT_ATTACHED, AK.NOT_TOLD) == (NOT_SENT, NOTHING_SENT, "{name} could not be attached: add it in the app.", "{officer} is not on Telegram: please tell them yourself.")
    own = lambda m: {n for n, v in vars(m).items() if callable(v) and getattr(v, "__module__", "") == m.__name__} | ({"_note"} if m is bot else set())
    assert AK.NOT_TAKEN == NOT_TAKEN and own(AK) & own(bot) == set(), "no name of the one is another's in the other"
    assert set(bot.TALKS) == {"change", "cancel"} and all(callable(f) for f in bot.TALKS.values()) and "needed_or_stopped" in absences.something_to_cover.__code__.co_varnames
    assert absences.NO_LESSONS == NO_LESSONS and absences.TOO_MANY == TOO_MANY and AK.MINUTES == 30 and bot.ACTIONS["ask"][0] == "relief" and bot.ACTIONS["ask"][2] is bot.ANY

@t
def a_whole_conversation_sends_an_absence():
    with school():
        page = by_page(lessons=[dict(key=K2, work=dict(text="Textbook p. 112, Q1–10.\nCollect at the end.", link="", files=[])), dict(key=K5, work=dict(text="", link="https://sls.example.org/ratio-2", files=[])),
                                dict(key=K8, work=dict(text="", link="", files=[]))])
    with school(EVE, ROSA, TEAM):
        h, n = Since(), len(answers())
        assert relief_() == [(HI, DAY_ROWS)] and [x[:2] for x in talks()] == [(CHATS[EVE], "ask")] and talks()[0][3] == secs("09:30")
        assert tap(EVE, "Tomorrow, Tue 13 Oct") == [(SPAN, SPAN_ROWS)] and tap(EVE, "Whole day") == [(REASON, REASON_ROWS)] and tap(EVE, "Medical") == [(WHO_IS, LINE)]
        assert says(EVE, "rosa") == [(WHO_HIT, [["Ms Rosa Ng"]])] and tap(EVE, "Ms Rosa Ng") == [(WORK_2, FIRST_ROWS)]
        assert says(EVE, " Textbook p. 112, Q1–10.\nCollect at the end. ") == [(WORK_5, LAST_ROWS)]
        assert says(EVE, "https://sls.example.org/ratio-2") == [(f"{LIST_HEAD}\n{ON_2}{SET_}\n{ON_5}{SET_LINK}", LIST_ROWS)]
        assert mine() == [] and h.new() == [] and answers()[n:] == [(None, None)] * 4, "nothing is sent before Send; each press is answered, with no word"
        assert talk_to(EVE, lambda: hook(tapping(EVE, "Send"))) == [(sent_text("2 lessons", "work set for 2"), dict(inline_keyboard=[[dict(text="Open in the app", url=BASE + "/relief#mine")]]))]
        r = only(); assert plain(r) == plain(page), (plain(r), plain(page))
        assert r["how"] == "asked" and r["by"] == EVE == r["teacher"] and r["id"] != page["id"] and absences._path(r["id"]) and [x["needed"] for x in r["lessons"]] == [True, True, False]
        assert h.new() == [by_telegram(EVE, "asked", "asked", r["id"])] and talks() == [] and answers()[-1] == (None, None)
        send(); assert said(ROSA) == [OFFICER_EVE] and [x for x in said(EVE) if x.startswith("✅")] == [sent_text("2 lessons", "work set for 2")], "the officer is told as by the page"
        assert [e[2] for e in edits()][-1] == f"{LIST_HEAD}\n{ON_2}{SET_}\n{ON_5}{SET_LINK}\n\nSend"
        assert says(EVE, "Thanks") == [(NOT_READ, None)] and len(mine()) == 1, "and it is over"

@t
def every_press_takes_its_buttons_off_and_says_the_choice():
    with school(EVE, ROSA):
        relief_()
        for label in ("Several days", "Tue 13 Oct", "Wed 14 Oct", "Done", "Some periods", "P3 · 09:00", "P7 · 11:30", "Other"):
            q_, text = asking_of(EVE)["question"], board(EVE)[0]; n, k, c = len(edits()), len(calls("editMessageReplyMarkup")), len(tg.PRACTICE_LOG); tap(EVE, label)
            assert [m for m, p in tg.PRACTICE_LOG[c:]] == ["answerCallbackQuery"] + (["editMessageReplyMarkup"] if label in ("Tue 13 Oct", "Wed 14 Oct") else ["editMessageText", "sendMessage"]), "answered at once, then changed, then asked"
            if label in ("Tue 13 Oct", "Wed 14 Oct"): assert len(edits()) == n and calls("editMessageReplyMarkup")[k:][0]["message_id"] == q_ == asking_of(EVE)["question"], "a tick: the same message"
            else: assert edits()[n:] == [(CHATS[EVE], q_, f"{text}\n\n" + ("Tue 13 Oct, Wed 14 Oct" if label == "Done" else label))] and "reply_markup" not in calls("editMessageText")[-1], label
        # typed: the question the line answers has no buttons (why), or loses them (who)
        k = len(calls("editMessageReplyMarkup")); say(EVE, "zebra-reason"); assert len(calls("editMessageReplyMarkup")) == k
        say(EVE, "m"); q_ = asking_of(EVE)["question"]; k = len(calls("editMessageReplyMarkup")); say(EVE, "rosa"); assert calls("editMessageReplyMarkup")[k:] == [dict(chat_id=CHATS[EVE], message_id=q_)], "its buttons off"
        tap(EVE, "Ms Rosa Ng"); q_ = asking_of(EVE)["question"]; k, n = len(calls("editMessageReplyMarkup")), len(edits()); say(EVE, "Read p. 5")
        assert calls("editMessageReplyMarkup")[k:] == [dict(chat_id=CHATS[EVE], message_id=q_)] and len(edits()) == n and asking_of(EVE)["question"] > q_
        q_ = asking_of(EVE)["question"]; doc(EVE); assert calls("editMessageReplyMarkup")[-1] == dict(chat_id=CHATS[EVE], message_id=q_), "a file is an answer too"

@t
def an_absence_asked_on_telegram_is_marked_so():
    with school(EVE, TEAM):
        to_list(); sends(); r = only(); assert r["via"] == "telegram" and file_of(r["id"]).count(b'"via"') == 1
        j = by_page(dates=["2026-10-16"])["id"]; assert "via" not in absences.load(j), "the page's has none"
        v = {x["id"]: x for x in call(TEAM, "get", "/api/relief/absences")["absences"]}; assert v[r["id"]]["via"] == "telegram" and v[r["id"]]["how"] == "asked" and "via" not in v[j]
        assert absences.set_via(j, "telegram")["via"] == "telegram" == absences.load(j)["via"] and plain(absences.load(j)) == plain(dict(absences.load(j)))
        for bad in ("dead00beef", "../x"):
            try: absences.set_via(bad, "telegram"); assert False, bad
            except ValueError as e: assert str(e) == absences.WRONG
        seen = []
        with stand_in(absences, "_save", lambda r: seen.append(absences._LOCK.locked())): absences.set_via(j, "telegram")
        assert seen == [True], "under the lock"
    # nothing else shows it: not the message to the officer, the team, the relief teacher, nor the planned relief sheet
    with school(EVE, ROSA, SAM, TEAM):
        to_list(); sends(); i = only()["id"]; give(i, K5, SAM); swept(); send(); sheet = who(TEAM).get("/api/relief/planned.csv?start=2026-10-13").get_data(as_text=True)
        assert "elegram" not in "".join(said(ROSA) + said(SAM) + said(TEAM)) and "elegram" not in sheet

@t
def several_days_and_some_periods():
    ten = ["Mon 12 Oct", "Tue 13 Oct", "Wed 14 Oct", "Thu 15 Oct", "Fri 16 Oct", "Mon 19 Oct", "Tue 20 Oct", "Wed 21 Oct", "Thu 22 Oct", "Fri 23 Oct"]
    pairs = lambda labels: [labels[i:i + 2] for i in range(0, len(labels), 2)]
    with school(EVE, ROSA):
        relief_(); assert tap(EVE, "Several days") == [(WHICH_DAYS, pairs(ten) + [["Done"]])]
        was = talks(); u = tapping(EVE, "Done"); assert answered(u) == (TICK_ONE, True) and talks() == was and edits()[-1][2].endswith("Several days"), "nothing ticked"
        assert tap(EVE, "Wed 14 Oct") == [] and rows_now(EVE) == pairs(["✓ " + x if x == "Wed 14 Oct" else x for x in ten]) + [["Done"]]
        tap(EVE, "Fri 23 Oct", "Tue 13 Oct", "✓ Fri 23 Oct"); ticked = pairs(["✓ " + x if x in ("Wed 14 Oct", "Tue 13 Oct") else x for x in ten]) + [["Done"]]
        assert rows_now(EVE) == ticked and asking_of(EVE)["dates"] == [] and len(said(EVE)) == 2 and {p["message_id"] for p in calls("editMessageReplyMarkup")} == {asking_of(EVE)["question"]}
        assert tap(EVE, "Done") == [(SPAN, SPAN_ROWS)] and asking_of(EVE)["dates"] == ["2026-10-13", "2026-10-14"]
        got = tap(EVE, "Some periods"); assert got == [(FROM_P, [["P1 · 08:00", "P2 · 08:30", "P3 · 09:00"], ["P4 · 09:30", "P5 · 10:00", "P6 · 10:30"], ["P7 · 11:00", "P8 · 11:30", "P9 · 12:00"], ["P10 · 12:30", "P11 · 13:00", "P12 · 13:30"]])]
        assert tap(EVE, "P2 · 08:30") == [(TO_P, [["P2 · 09:00", "P3 · 09:30", "P4 · 10:00"], ["P5 · 10:30", "P6 · 11:00", "P7 · 11:30"], ["P8 · 12:00", "P9 · 12:30", "P10 · 13:00"], ["P11 · 13:30", "P12 · 14:00"]])]
        assert tap(EVE, "P5 · 10:30") == [(REASON, REASON_ROWS)]
        tap(EVE, "Course"); say(EVE, "ng rosa"); assert tap(EVE, "Ms Rosa Ng") == [(WORK_2, FIRST_ROWS)] and tap(EVE, "Later, in the app") == [(WORK_W, [["Later, in the app"]])]
        assert says(EVE, "p. 3")[0][0] == f"Relief for Tue 13 Oct, Wed 14 Oct · P2–P5\nReason: Course\nReporting officer: Ms Rosa Ng\n{ON_2}{NONE_YET}\n• 2A Science P2 on Wed 14 Oct: {SET_}"
        assert sends() == [(sent_text("2 lessons", "work set for 1"), OPEN_MINE)]
        r = only(); assert (r["dates"], r["periods"], r["reason"], r["reason_text"], [x["key"] for x in r["lessons"]]) == (["2026-10-13", "2026-10-14"], [1, 4], "Course", "", [K2, KW]) and r["lessons"][1]["work"]["text"] == "p. 3"
        absences.cancel(r["id"], "x", EVE); want = plain(dict(r, cancelled=None)); page = by_page(dates=["2026-10-13", "2026-10-14"], periods=[1, 4], reason="Course", lessons=[dict(key=KW, work=dict(text="p. 3"))]); assert plain(page) == want
    with school(EVE, ROSA):                                                                # one period; one lesson
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Some periods", "P6 · 10:30", "P6 · 11:00", "Child sick"); say(EVE, "rosa"); assert tap(EVE, "Ms Rosa Ng") == [(WORK_5, [["Later, in the app"]])]
        assert tap(EVE, "Later, in the app")[0][0] == f"Relief for Tue 13 Oct · P6\nReason: Child sick\nReporting officer: Ms Rosa Ng\n{ON_5}{NONE_YET}" and sends() == [(sent_text("1 lesson", "no work set yet"), OPEN_MINE)]
        assert only()["periods"] == [5, 5]

@t
def another_day_is_one_of_the_next_ten():
    with school(EVE, ROSA):
        relief_(); got = tap(EVE, "Another day"); assert got[0][0] == WHICH_DAY and sum(got[0][1], []) == ["Mon 12 Oct", "Tue 13 Oct", "Wed 14 Oct", "Thu 15 Oct", "Fri 16 Oct", "Mon 19 Oct", "Tue 20 Oct", "Wed 21 Oct", "Thu 22 Oct", "Fri 23 Oct"]
        assert tap(EVE, "Fri 16 Oct") == [(SPAN, SPAN_ROWS)] and asking_of(EVE)["dates"] == ["2026-10-16"] and edits()[-1][2] == "Which day?\n\nFri 16 Oct"
    # only school days are offered: a weekend, a holiday, the end of term, the days between two terms
    def first(hm_day, **cal):
        with school(EVE, calendar=dict(TERM, **cal)): at("09:00", hm_day); got = relief_(); return got
    assert first(16) == [(HI, [["Today, Fri 16 Oct"], ["Several days"], ["Another day"]])] and first(17) == [(HI, [["Several days"], ["Another day"]])] and first(18) == [(HI, [["Tomorrow, Mon 19 Oct"], ["Several days"], ["Another day"]])]
    assert first(12, holidays=[dict(name="Made up", start="2026-10-12", end="2026-10-13")]) == [(HI, [["Several days"], ["Another day"]])]
    two = [dict(name="Term 4", start="2026-09-07", end="2026-10-14", starts_as="Odd"), dict(name="Term 1", start="2026-11-02", end="2026-11-30", starts_as="Odd")]
    with school(EVE, calendar=dict(terms=two, holidays=[])):
        relief_(); assert sum(tap(EVE, "Another day")[0][1], []) == ["Mon 12 Oct", "Tue 13 Oct", "Wed 14 Oct", "Mon 2 Nov", "Tue 3 Nov", "Wed 4 Nov", "Thu 5 Nov", "Fri 6 Nov", "Mon 9 Nov", "Tue 10 Nov"]
    last = lambda day: [dict(name="T", start="2026-09-07", end="2026-10-09", starts_as="Odd"), dict(name="U", start=day, end="2027-03-01", starts_as="Odd")]
    with school(EVE, calendar=dict(terms=last("2026-12-11"), holidays=[])): assert relief_() == [(HI, [["Several days"], ["Another day"]])] and tap(EVE, "Another day")[0][1] == [["Fri 11 Dec"]], "60 days on"
    with school(EVE, calendar=dict(terms=last("2026-12-14"), holidays=[])): assert relief_() == [(NO_DAYS, None)] and talks() == []
    with school(EVE, calendar=dict(terms=last("2026-12-14"), holidays=[])): at("09:00", 15); assert relief_() == [(HI, [["Several days"], ["Another day"]])], "60 days on, again"
    with school(EVE, calendar=dict(terms=last("2026-12-15"), holidays=[])): at("09:00", 15); assert relief_() == [(NO_DAYS, None)], "61"

@t
def what_cannot_be_asked_is_said_at_once():
    with school(EVE, calendar=dict(terms=[], holidays=[])): assert relief_() == [(LS.NO_CALENDAR, None)] and talks() == [] and rows("buttons") == []
    with school(EVE):
        with no_pub(): assert relief_() == [(WB.NO_PUB, None)] and talks() == []
        with stand_in(WB, "_staff", lambda pub: []): assert relief_() == [(f"{EVE} is not on the published timetable or the staff list.", None)] and talks() == [], "the app's own sentence"
        with stand_in(WB, "_staff", lambda pub: 1 / 0): assert relief_() == [(WENT_WRONG, None)] and talks() == []
        assert relief_() == [(HI, DAY_ROWS)]
    with school(HUGO):                                                                     # someone with no lessons at all
        say(HUGO, "/relief"); assert tap(HUGO, "Tomorrow, Tue 13 Oct") == [(NO_LESSONS, None), ("Hi Mr Hugo Ong. Which day are you away?", DAY_ROWS)]

@t
def an_unlinked_chat_cannot_ask():
    with school(EVE):
        hook(msg("/relief", 990)); assert sent(990) == [(990, NOT_LINKED)] and len(links.tries.fails["tg:990"]) == 1 and talks() == []
        for k in range(8): hook(msg("/relief", 990))
        assert len(sent(990)) == 5 and talks() == [] and rows("buttons") == [], "held back as any"
        with record(EVE, group="executive", extras=dict(relief=False, exams=None, admin=False)): assert relief_() == [(NOT_LINKED, None)] and talks() == [], "without the relief right"
        with record(EVE, off=True): assert relief_() == [(NOT_LINKED, None)]
        with broken_accounts(): links.tries.fails.clear(); assert relief_() == [(NOT_LINKED, None)]
        for kind in ("group", "supergroup", "channel"): n = len(tg.PRACTICE_LOG); hook(msg("/relief", CHATS[EVE], kind=kind)); assert len(tg.PRACTICE_LOG) == n
        links.tries.fails.clear()
        for text in ("/relief", "/RELIEF", " /relief ", "/relief@practice_bot", "/relief tomorrow please"): assert says(EVE, text) == [(HI, DAY_ROWS)], text
        assert len(talks()) == 1 and rows("links")[0]["name"] == EVE
    with school(EVE):                                                                      # a linked person over the limit: nothing at all, at any step
        to_work(); was = talks()
        for k in range(5): links.tries.fail(f"tg:{CHATS[EVE]}")
        u = tapping(EVE, "Later, in the app"); tg.PRACTICE_LOG.clear(); say(EVE, "p. 5"); say(EVE, "/cancel"); hook(a_doc(EVE)); hook(dict(update_id=next(_ids), edited_message=msg("x", CHATS[EVE])["message"])); hook(u)
        assert tg.PRACTICE_LOG == [] and talks() == was; say(EVE, "/help"); say(EVE, "/relief"); assert tg.PRACTICE_LOG == [] and mine() == []
    with school(EVE, SAM):                                                                 # another's press of my button, and mine in another chat
        to_work(); was = talks(); u = tapping(EVE, "Later, in the app", chat=CHATS[SAM]); assert answered(u) == (NOT_YOURS_BUTTON, True) and talks() == was
        u = tapping(EVE, "Later, in the app", chat=991); assert answered(u) == (NOT_LINKED, True) and talks() == was

@t
def other_asks_a_line_and_refuses_an_empty_one():
    with school(EVE, ROSA):
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day"); assert tap(EVE, "Other") == [(SAY_WHY, LINE)]
        was = {k: v for k, v in asking_of(EVE).items() if k != "question"}
        for text in ("", "   ", "\n\t ", "x" * 201, "é " * 150, None, 7, ["x"]): assert says(EVE, text) == [(SAY_WHY, LINE)] and {k: v for k, v in asking_of(EVE).items() if k != "question"} == was, text
        assert heard(EVE, lambda: hook(a_photo(EVE, caption="zebra"))) == [(SAY_WHY, LINE)] and heard(EVE, lambda: hook(_with(EVE, sticker=dict(file_id="s")))) == [(SAY_WHY, LINE)], "not a line: asked again"
        assert says(EVE, "  A parent\n meeting  at 10 ") == [(WHO_IS, LINE)]
        say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng"); text = tap(EVE, "Later for all the rest")[0][0]; assert "Reason: Other\n" in text and "parent" not in text
        sends(); r = only(); assert (r["reason"], r["reason_text"]) == ("Other", "A parent meeting at 10")
    for line in ("x" * 200, " " + "é" * 200 + " ", "No", "ok", "ABCD-EFGH", access.staff_code(EVE), "/ill", "7", "<b>x</b>"):       # what looks like a code or a command that is none is the line
        with school(EVE, ROSA):
            relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day", "Other"); assert says(EVE, line) == [(WHO_IS, LINE)] and asking_of(EVE)["why"] == line.strip() and deleted() == [] and not links.tries.fails.get(f"tg:{CHATS[EVE]}"), line
            say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng", "Later for all the rest", "Send"); assert only()["reason_text"] == line.strip()
    with school(EVE, ROSA):                                                                # the line belongs to Other alone
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day", "Other"); say(EVE, "zebra-reason"); say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng", "Later for all the rest", "Start again", "Tomorrow, Tue 13 Oct", "Whole day", "Course"); say(EVE, "rosa")
        tap(EVE, "Ms Rosa Ng", "Later for all the rest", "Send"); assert (only()["reason"], only()["reason_text"]) == ("Course", "")

@t
def the_last_officer_is_offered():
    with school(EVE, HUGO, SAM):
        absent(dates=["2026-10-16"], reporting_officer=SAM); at("09:01"); absent(teacher=SAM, dates=["2026-10-13"], reporting_officer=HUGO); at("09:02"); absent(by=HUGO, dates=["2026-10-14"], reporting_officer="")      # mine, another's, and one planned with none
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day"); assert tap(EVE, "Medical") == [("Your reporting officer is Mr Sam Tan. Right?", [["Yes", "Someone else"]])]
        assert tap(EVE, "Yes") == [(WORK_2, FIRST_ROWS)] and asking_of(EVE)["officer"] == SAM and edits()[-1][2].endswith("Right?\n\nYes")
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day", "Medical"); assert tap(EVE, "Someone else") == [(WHO_IS, LINE)] and says(EVE, "ROSA") == [(WHO_HIT, [["Ms Rosa Ng"]])]
    for officer in ("", EVE, "Mr Nobody Known", None, 7):                                  # none, themself, gone: the one before it
        with school(EVE):
            absent(dates=["2026-10-16"], reporting_officer=ROSA); at("09:01"); i = absent(dates=["2026-10-14"]); change_record(i, lambda r: r.update(reporting_officer=officer)); change_record(i, lambda r: r.update(cancelled=dict(at=clock.now, by=EVE, why="x")))
            relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day"); assert tap(EVE, "Medical") == [(RIGHT_ROSA, [["Yes", "Someone else"]])], officer
    with school(EVE):                                                                      # gone between the question and the press: refused, and the buttons stay
        absent(dates=["2026-10-16"]); relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day", "Medical"); was = talks(); u = tapping(EVE, "Yes"); real = WB._staff
        with stand_in(WB, "_staff", lambda pub: [p for p in real(pub) if p["name"] != ROSA]): assert answered(u) == (f"{ROSA} is not on the published timetable or the staff list.", True) and talks() == was
        assert tap(EVE, "Yes") == [(WORK_2, FIRST_ROWS)]
    # the search
    with school(EVE):
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day", "Medical")
        assert says(EVE, "zzz") == [(NOBODY_MATCHES, LINE)] and says(EVE, "evelyn") == [(NOBODY_MATCHES, LINE)], "never themself"
        assert says(EVE, "  ") == [(NOBODY_MATCHES, LINE)] and says(EVE, "lee MS") == [(WHO_HIT, [["Ms Maya Lee"]])], "every word, in any order and case"
        assert says(EVE, "mr") == [(WHO_HIT, [[p["name"]] for p in AP.listing(SCHOOL) if "Mr " in p["name"]])] and 2 < len(rows_now(EVE)) <= 8
        assert says(EVE, "rosa") == [(WHO_HIT, [["Ms Rosa Ng"]])] and says(EVE, "maya") == [(WHO_HIT, [["Ms Maya Lee"]])], "typed again: looked for again"
        u = callback(next(b["callback_data"] for m, p in tg.PRACTICE_LOG for row in (p.get("reply_markup") or {}).get("inline_keyboard", []) for b in row if b["text"] == "Ms Rosa Ng"), question(EVE, WHO_HIT)); assert answered(u) == (OLD_BUTTON, True), "of the search before"
        assert tap(EVE, "Ms Maya Lee") == [(WORK_2, FIRST_ROWS)] and asking_of(EVE)["officer"] == MAYA
    nine = RP.fake_pub([dict(name=EVE, dept="Science")] + [dict(name=f"Mx Made Up {k}", dept="Science") for k in range(9)], SCHOOL["model"]["lessons"][:2]); nine["model"].update(NP=12, school=SCHOOL["model"]["school"])
    with school(EVE), no_pub(nine):
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day", "Medical")
        assert says(EVE, "made") == [(WHO_HIT + "\n" + NOT_HERE, [[f"Mx Made Up {k}"] for k in range(8)])] and says(EVE, "made 8") == [(WHO_HIT, [["Mx Made Up 8"]])] and len(says(EVE, "up")[0][1]) == 8

@t
def a_shared_lesson_is_left_out():
    keys_ = lambda: [x["key"] for x in asking_of(EVE)["lessons"]]
    def on_page(dates="2026-10-13"):
        """the lessons the page's form would count as to cover"""
        return [x["key"] for x in call(EVE, "get", f"/api/relief/lessons?dates={dates}")["lessons"] if not x["others"] and not x["stopped"]]
    with school(EVE, BUSY):
        to_work(); assert keys_() == [K2, K5] == on_page(), "Busy is there for the third"
        absent(teacher=BUSY); to_work(); assert keys_() == [K2, K5, K8] == on_page(), "away too"
        tap(EVE, "Later for all the rest"); sends(); assert [(x["key"], x["needed"]) for x in only()["lessons"]] == [(K2, True), (K5, True), (K8, True)]
    with exam_school(EVE):                                                                 # an exam stops one: not asked of, and kept in the absence as the page keeps it
        e = exam("1C"); to_work(); assert keys_() == [K5] == on_page(); tap(EVE, "Later, in the app"); assert sends() == [(sent_text("1 lesson", "no work set yet", "Ms Rosa Ng is not on Telegram: please tell them yourself."), OPEN_MINE)]
        assert [(x["key"], x["needed"]) for x in only()["lessons"]] == [(K2, True), (K5, True), (K8, False)]; want = plain(only())
    with exam_school(EVE): exam("1C"); assert plain(by_page()) == want, "the same record"
    with exam_school(EVE, BUSY):                                                           # a co-teacher on a duty is not there
        exam("4A", duties=[(BUSY, 720, 750)]); to_work(); assert K8 in keys_() and keys_() == on_page()
    with exam_school(EVE):                                                                 # every lesson stopped: sent as the page's is, with none to set work for
        exam("1A", "1B", "1C", "5A"); got = to_work(); assert got == [(LIST_HEAD, LIST_ROWS)] and on_page() == []
        assert sends() == [(sent_text("0 lessons", "no work set yet", "Ms Rosa Ng is not on Telegram: please tell them yourself."), OPEN_MINE)] and [x["needed"] for x in only()["lessons"]] == [True, True, False]
    with exam_school(EVE):                                                                 # a shared lesson alone, and stopped: the page sends it, and so it goes on
        exam("5A"); relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Some periods", "P9 · 12:00"); assert tap(EVE, "P9 · 12:30") == [(REASON, REASON_ROWS)] and by_page(periods=[8, 8])["lessons"][0]["needed"] is False
    # no lesson that needs relief: the sentence, and the day asked again
    with school(EVE):
        relief_(); assert tap(EVE, "Today, Mon 12 Oct") == [(NO_LESSONS, None), (HI, DAY_ROWS)] and asking_of(EVE)["dates"] == [] and edits()[-1][2] == f"{HI}\n\nToday, Mon 12 Oct"
        assert tap(EVE, "Tomorrow, Tue 13 Oct") == [(SPAN, SPAN_ROWS)]
        tap(EVE, "Some periods", "P9 · 12:00"); assert tap(EVE, "P10 · 13:00") == [(NO_LESSONS, None), (SPAN, SPAN_ROWS)], "the shared one alone"
        tap(EVE, "Some periods", "P1 · 08:00"); assert tap(EVE, "P3 · 09:30") == [(REASON, REASON_ROWS)] and asking_of(EVE)["periods"] == [0, 2]
    with exam_school(EVE):                                                                 # a duty counts, as the page counts it: that day, at that time
        exam("5A", date="2026-10-15", duties=[(EVE, 540, 600)]); relief_(); tap(EVE, "Another day"); assert tap(EVE, "Thu 15 Oct") == [(SPAN, SPAN_ROWS)]
        tap(EVE, "Some periods", "P6 · 10:30"); assert tap(EVE, "P7 · 11:30") == [(NO_LESSONS, None), (SPAN, SPAN_ROWS)]
        tap(EVE, "Whole day", "Medical"); say(EVE, "rosa"); assert tap(EVE, "Ms Rosa Ng") == [("Relief for Thu 15 Oct · whole day\nReason: Medical\nReporting officer: Ms Rosa Ng", LIST_ROWS)] and sends()[0][0].startswith("✅ Sent to the relief team: 0 lessons, no work set yet.") and only()["lessons"] == []
    with exam_school(EVE):                                                                 # what the exams mean cannot be read: as on the page
        exam("1C")
        with unreadable(), quiet_app(): to_work(); assert keys_() == [K2, K5]
    # nothing to cover any more by the time the officer is known (Busy there after all): the sentence, and the day again
    with school(EVE, BUSY):
        absent(teacher=BUSY); relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Some periods", "P9 · 12:00", "P9 · 12:30", "Medical"); say(EVE, "rosa"); absences.cancel(mine(BUSY)[0]["id"], "x", BUSY)
        assert tap(EVE, "Ms Rosa Ng") == [(NO_LESSONS, None), (HI, DAY_ROWS)] and asking_of(EVE)["reason"] is None

@t
def an_overlap_is_refused_with_the_apps_sentence():
    with school(EVE, ROSA):
        i = absent(); to_list(); was, f, h = talks(), file_of(i), Since(); OVER = f"{EVE} has already sent an absence for {EVE} on Tue 13 Oct."
        n = len(edits()); u = tapping(EVE, "Send"); assert answered(u) == (OVER, True) and talks() == was and len(mine()) == 1 and file_of(i) == f and h.new() == [] and len(edits()) == n and not [x for x in said(EVE) if x.startswith("✅")]
        with stand_in(TE, "soon", lambda: 1 / 0), stand_in(WB, "_sync_exams", lambda pub: 1 / 0): assert answered(tapping(EVE, "Send")) == (OVER, True) and talks() == was, "pressed again: the same; nothing follows a refusal"
        absences.cancel(i, "x", EVE); assert sends() == [(sent_text("2 lessons", "no work set yet"), OPEN_MINE)] and len(mine()) == 2, "its buttons work still"
    with school(EVE):
        absent(); to_list(); assert answered(tapping(EVE, "Send"))[1] is True and tap(EVE, "Start again") == [(HI, DAY_ROWS)] and asking_of(EVE)["dates"] == [] and edits()[-1][2].endswith("\n\nStart again")
    with school(EVE):                                                                      # refused, and another talk was opened meanwhile (another copy of the app): that one stays
        def meanwhile(*a, **k):
            with tgdb.db() as c: c.execute("INSERT INTO talks(chat, kind, data, until) VALUES (?, 'change', '{}', 9e12)", (CHATS[EVE],))
            raise ValueError("Made up.")
        to_list()
        with stand_in(absences, "new", meanwhile): assert answered(tapping(EVE, "Send")) == ("Made up.", True)
        assert [x[1] for x in talks()] == ["change"]
    # refused, and the chat is not theirs any more (the page's unlink, another phone, another person): nothing is put back
    for f in (lambda: links.unlink(EVE), lambda: links.link(EVE, 995, None), lambda: links.link(MAYA, CHATS[EVE], None)):
        with school(EVE, ROSA, MAYA):
            absent(); to_list(reason="Other"); v, real_new = tapping(EVE, "Send"), absences.new; assert b"zebra-reason" in raw_store()
            with stand_in(absences, "new", lambda *a, **k: (f(), real_new(*a, **k))[1]): assert answered(v) == (f"{EVE} has already sent an absence for {EVE} on Tue 13 Oct.", True)
            assert rows("talks") == [] and b"zebra-reason" not in raw_store() and len(mine()) == 1
    # a lesson that is not there any more between the list and Send (a publish), or an officer who is not
    with school(EVE, ROSA):
        to_list(); was = talks(); less = json.loads(json.dumps(SCHOOL)); less["model"]["lessons"] = [L for L in less["model"]["lessons"] if L["p"] != 5]
        with no_pub(less): assert answered(tapping(EVE, "Send")) == (absences.CHANGED, True) and talks() == was and mine() == []; assert tap(EVE, "Start again") == [(HI, DAY_ROWS)]
        assert to_list()[0][0].count("•") == 2 and sends()[0][0].startswith("✅")
    with school(EVE):
        to_list(); real = AP.listing
        with stand_in(AP, "listing", lambda pub, data=None: [p for p in real(pub, data) if p["name"] != ROSA]): assert answered(tapping(EVE, "Send")) == ("Choose your reporting officer.", True) and mine() == [] and asking_of(EVE)
    with school(EVE):                                                                      # a day that has passed by then: the day's button, and Send
        at("23:50", 13); say(EVE, "/relief"); u = tapping(EVE, "Today, Tue 13 Oct"); at("00:01", 14); was = talks(); assert answered(u) == ("Choose up to 10 school days, today or later.", True) and talks() == was
        at("23:50", 13); to_list(day="Today, Tue 13 Oct"); at("00:05", 14); was = talks(); assert answered(tapping(EVE, "Send")) == ("Choose up to 10 school days, today or later.", True) and talks() == was and mine() == []
    with school(EVE):                                                                      # added meanwhile: in the absence, with no work
        to_list(); more = json.loads(json.dumps(SCHOOL)); more["model"]["lessons"].append(lesson(TUE, 10, 1, ["4A"], "Biology", [EVE]))
        with no_pub(more): assert sends()[0][0].startswith("✅ Sent to the relief team: 3 lessons, no work set yet.")

@t
def a_photo_and_a_document_are_attached():
    with school(EVE, ROSA):
        to_work(); got = []
        with stand_in(tg, "download", lambda fid, limit: got.append((fid, limit))): assert doc(EVE, "Work sheet (1).pdf", "F-doc", caption="Q1 to Q5\nthen hand in") == [(WORK_5, LAST_ROWS)] and photo(EVE, "F-pic") == [(f"{LIST_HEAD}\n{ON_2}{SET_BOTH}\n{ON_5}{SET_FILE}", LIST_ROWS)]
        assert got == [] and [m for m, p in tg.PRACTICE_LOG if m in ("download", "getFile")] == [], "nothing is downloaded before Send"
        assert json.dumps(asking_of(EVE)).count("F-pic") == 1 and "F-pic-s" not in json.dumps(asking_of(EVE)), "the largest size"
        fetched = []
        with stand_in(tg, "download", lambda fid, limit: (fetched.append((fid, limit, absences._LOCK.locked(), bot._pressing.locked(), len(mine()), len(talks()))), f"bytes of {fid}".encode())[1]):
            assert sends() == [(sent_text("2 lessons", "work set for 2"), OPEN_MINE)]
        assert fetched == [("F-doc", FI.MAX, False, False, 1, 0), ("F-pic", FI.MAX, False, False, 1, 0)], fetched
        r = only(); a, b = r["lessons"][0]["work"], r["lessons"][1]["work"]; assert (a["text"], a["link"], [f["name"] for f in a["files"]]) == ("Q1 to Q5\nthen hand in", "", ["Work sheet (1).pdf"]) and (b["text"], [f["name"] for f in b["files"]]) == ("", ["photo 1.jpg"])
        assert open(FI.path(r["id"], a["files"][0]["id"]), "rb").read() == b"bytes of F-doc" and open(FI.path(r["id"], b["files"][0]["id"]), "rb").read() == b"bytes of F-pic"; want = plain(r)
    with school(EVE, ROSA):
        assert plain(by_page(files=[(K2, "Work sheet (1).pdf", b"bytes of F-doc"), (K5, "photo 1.jpg", b"bytes of F-pic")], lessons=[dict(key=K2, work=dict(text="Q1 to Q5\nthen hand in"))])) == want, "as the page's form makes it"
    # a link alone is the link; with anything else it is text; line breaks kept
    for line, text, link in (("https://x.example.org/a?b=c#d", "", "https://x.example.org/a?b=c#d"), (" HTTP://X.example.org ", "", "HTTP://X.example.org"), ("see https://x.example.org", "see https://x.example.org", ""),
                             ("https://x.example.org\nhttps://y.example.org", "https://x.example.org\nhttps://y.example.org", ""), ("ftp://x.example.org", "ftp://x.example.org", ""), ("a\n\n b ", "a\n\n b", ""), ("ABCD-EFGH", "ABCD-EFGH", ""), ("/ill", "/ill", ""), ("No", "No", "")):
        with school(EVE, ROSA): to_work(); say(EVE, line); tap(EVE, "Later, in the app", "Send"); w = only()["lessons"][0]["work"]; assert (w["text"], w["link"]) == (text, link), line
    # Same as before: the last earlier lesson's text, link and files; only once there is one
    with school(EVE, ROSA):
        say(EVE, "/relief"); tap(EVE, "Several days", "Tue 13 Oct", "Wed 14 Oct", "Fri 16 Oct", "Done", "Whole day", "Medical"); say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng")
        assert tap(EVE, "Later, in the app")[0][1] == FIRST_ROWS, "no work before: nothing to repeat"
        assert doc(EVE, "a.pdf", "F-a", caption="Read")[0][1] == [["Same as before", "Later, in the app"], ["Later for all the rest"]]
        assert tap(EVE, "Same as before")[0][1] == LAST_ROWS and tap(EVE, "Same as before")[0][0].split("\n")[3:] == [f"{ON_2}{NONE_YET}", f"{ON_5}{SET_BOTH}", f"• 2A Science P2 on Wed 14 Oct: {SET_BOTH}", f"• 1A Art P1–P2 on Fri 16 Oct: {SET_BOTH}"]
        n = len(tg.PRACTICE_LOG); assert sends()[0][0] == sent_text("4 lessons", "work set for 3") and [p["file_id"] for m, p in tg.PRACTICE_LOG[n:] if m == "download"] == ["F-a"], "one file, downloaded once"
        assert [m for m, p in tg.PRACTICE_LOG[n:]] == ["answerCallbackQuery", "editMessageText", "download", "sendMessage"], "the press is answered before anything is fetched"
        works = {x["key"]: x["work"] for x in only()["lessons"]}; assert works[K2] == dict(text="", link="", files=[]) and works[K5] == works[KW] == works[KF] and works[KF]["text"] == "Read" and [f["name"] for f in works[KF]["files"]] == ["a.pdf"]
        assert len(os.listdir(os.path.join(FI.DIR, only()["id"]))) == 1
    with school(EVE, ROSA): to_work(); say(EVE, "https://x.example.org"); tap(EVE, "Same as before", "Send"); assert [x["work"]["link"] for x in only()["lessons"]] == ["https://x.example.org"] * 2 + [""]

@t
def too_big_or_wrong_kind_is_named():
    with school(EVE, ROSA):
        to_work(); was = {k: v for k, v in asking_of(EVE).items() if k != "question"}; again = lambda s: [(s, None), (WORK_2, FIRST_ROWS)]
        for name_, size, sentence in (("film.mp4", 5, FI.WRONG_KIND), ("archive.zip", 5, FI.WRONG_KIND), ("no extension", 5, FI.WRONG_KIND), (".pdf", 5, FI.WRONG_KIND), ("big.pdf", FI.MAX + 1, FI.TOO_BIG), ("empty.pdf", 0, FI.WRONG_KIND), ("x.PDF.exe", 5, FI.WRONG_KIND)):
            assert doc(EVE, name_, "F", size) == again(f"{name_}: {sentence}"), name_
        assert doc(EVE, "a" * 300 + ".zip", "F", 5) == again("a" * 96 + ".zip: " + FI.WRONG_KIND), "a name this long is cut"
        assert doc(EVE, "two\nlines.zip", "F", 5) == again(f"two lines.zip: {FI.WRONG_KIND}") and doc(EVE, None, "F", 5) == again(f"file: {FI.WRONG_KIND}")
        u = a_photo(EVE); [p.update(file_size=FI.MAX + 1) for p in u["message"]["photo"]]; assert heard(EVE, lambda: hook(u)) == again(f"photo 1.jpg: {FI.TOO_BIG}")
        assert says(EVE, "x" * 2001) == again("Keep the work under 2000 characters.") and says(EVE, "https://" + "x" * 500) == again("A link starts with http:// or https://.") and doc(EVE, caption="x" * 2001) == again("Keep the work under 2000 characters.")
        assert {k: v for k, v in asking_of(EVE).items() if k != "question"} == was and FI.MAX == 10 * 1024 * 1024, "nothing of these is kept"
        assert photo(EVE)[0][0] == WORK_5 and doc(EVE, "ten.PDF", "F", FI.MAX)[0][0].startswith("Relief for"), "just within"
    for kind in (dict(sticker=dict(file_id="s", emoji="x")), dict(voice=dict(file_id="v", duration=1)), dict(video=dict(file_id="v")), dict(video_note=dict(file_id="v")), dict(audio=dict(file_id="a")), dict(location=dict(latitude=1, longitude=1)),
                 dict(contact=dict(phone_number="1")), dict(document=7), dict(document={}), dict(document=dict(file_id=7, file_name="a.pdf")), dict(photo=[]), dict(photo=[7]), dict(photo=[dict(width=1)]), {}):
        with school(EVE, ROSA):
            to_work(); was = {k: v for k, v in asking_of(EVE).items() if k != "question"}; assert heard(EVE, lambda: hook(_with(EVE, **kind))) == [(SEND_ONE, None), (WORK_2, FIRST_ROWS)], kind
            assert {k: v for k, v in asking_of(EVE).items() if k != "question"} == was
    with school(EVE, ROSA):                                                                # a message changed after it was sent: here alone anything is said of it
        edit = lambda text: dict(update_id=next(_ids), edited_message=msg(text, CHATS[EVE])["message"])
        assert heard(EVE, lambda: hook(edit("/relief"))) == [] and heard(EVE, lambda: hook(edit(links.new_code(SAM)["code"]))) == [] and links.name_of(CHATS[EVE]) == EVE
        relief_(); assert heard(EVE, lambda: hook(edit("x"))) == [(PRESS_ONE, None), (HI, DAY_ROWS)] and heard(EVE, lambda: hook(edit("/cancel"))) == [(PRESS_ONE, None), (HI, DAY_ROWS)] and asking_of(EVE)
        to_work(); assert heard(EVE, lambda: hook(edit("p. 5"))) == [(SEND_ONE, None), (WORK_2, FIRST_ROWS)] and asking_of(EVE)["work"] == {}
        j = told_planned(dates=["2026-10-16"]); press(EVE, "cancel"); assert heard(EVE, lambda: hook(edit("The course is off"))) == [] and [x[1] for x in talks()] == ["cancel"]

@t
def an_edit_that_says_what_is_held_is_not_answered():
    def edit(**more): return heard(EVE, lambda: hook(dict(update_id=next(_ids), edited_message=_with(EVE, **more)["message"])))
    pdf = dict(document=dict(file_id="F", file_name="a.pdf", file_size=5))
    with school(EVE, ROSA):
        to_work(reason="Other"); asks_2 = [(SEND_ONE, None), (WORK_2, FIRST_ROWS)]; assert edit(text="https://x.example.org/a") == asks_2, "nothing of it is held yet"
        assert edit(text="zebra-reason") == edit(text="  zebra-reason\n") == [] and edit(text="zebra") == asks_2 and edit(text="") == asks_2, "the reason typed"
        say(EVE, "https://x.example.org/a"); asks_5 = [(SEND_ONE, None), (WORK_5, LAST_ROWS)]; was = asking_of(EVE); n = len(tg.PRACTICE_LOG)
        assert edit(text="https://x.example.org/a") == edit(text=" https://x.example.org/a ") == [] and tg.PRACTICE_LOG[n:] == [] and asking_of(EVE) == was, "a link's preview: not a word, and the question is where it was"
        assert edit(text="https://x.example.org/a?b") == asks_5 and edit(text="https://x.example.org/") == asks_5 and edit(text="p. 5") == asks_5
        doc(EVE, "a.pdf", "F", media_group_id="g", caption=" Page 1 "); doc(EVE, "b.pdf", "G", media_group_id="g", caption="and\n2"); the_list = [(PRESS_ONE, None), (board(EVE)[0], LIST_ROWS)]; assert the_list[1][0].endswith(f"{ON_5}work set (text, 2 files)")
        for caption in ("Page 1", "  Page 1 ", "and\n2", "Page 1\nand\n2"): assert edit(caption=caption, **pdf) == [], caption
        for caption in ("Page", "age 1", "2", "and", "Page 1 and", "", None): assert edit(caption=caption, **pdf) == the_list, caption
        assert edit(text="Page 1\nand\n2") == [] and edit(text="https://x.example.org/a") == [] and edit(sticker=dict(file_id="s")) == the_list and edit(**pdf) == the_list
        for odd in (7, ["zebra-reason"], {}): assert edit(text=odd) == the_list and edit(caption=odd) == the_list, odd
        assert sends()[0][0] == sent_text("2 lessons", "work set for 2") and [x["work"]["text"] for x in only()["lessons"]][:2] == ["", "Page 1\nand\n2"] and edit(text="https://x.example.org/a") == [], "and after it, as any edit"
    with school(EVE, ROSA):                                                                # the text typed, a line or more of it; another conversation holds nothing of it
        to_work(); say(EVE, "Read p. 5\nthen Q1"); assert edit(text="Read p. 5\nthen Q1 ") == [] and edit(text="Read p. 5") == [(SEND_ONE, None), (WORK_5, LAST_ROWS)] and edit(text="Read p. 5 then Q1") == [(SEND_ONE, None), (WORK_5, LAST_ROWS)]
        relief_(); assert edit(text="Read p. 5\nthen Q1") == [(PRESS_ONE, None), (HI, DAY_ROWS)]
    with school(EVE, ROSA):                                                                # no reason typed, no work: an empty text is not held
        relief_(); assert edit(text="") == edit(text="  ") == edit() == edit(caption=" ", **pdf) == [(PRESS_ONE, None), (HI, DAY_ROWS)]

@t
def the_list_says_what_is_set():
    for work_, want in ((dict(), NONE_YET), (dict(text="x"), "work set (text)"), (dict(link="x"), "work set (link)"), (dict(files=[1]), "work set (1 file)"), (dict(files=[1, 2]), "work set (2 files)"), (dict(link="x", files=[1, 2]), "work set (link, 2 files)"),
                        (dict(text="x", files=[1]), "work set (text, 1 file)"), (dict(text="x", link="y", files=[1, 2, 3, 4, 5]), "work set (text, link, 5 files)"), (dict(text="x", link="y"), "work set (text, link)")):
        assert AK._what(dict(dict(text="", link="", files=[]), **work_)) == want, work_
    with school(EVE, ROSA):                                                                # two files meant for one lesson and sent singly: it can be seen, and Start again is there
        to_work(); doc(EVE, "a.pdf", "F-a"); assert doc(EVE, "b.pdf", "F-b") == [(f"{LIST_HEAD}\n{ON_2}{SET_FILE}\n{ON_5}{SET_FILE}", LIST_ROWS)]
    with school(EVE, ROSA):
        to_work(); say(EVE, "quokka-work"); text = photo(EVE, "P", caption="lemur-work")[0][0]; assert text == f"{LIST_HEAD}\n{ON_2}{SET_}\n{ON_5}{SET_BOTH}" and "quokka" not in text and "lemur" not in text

@t
def a_file_outside_a_conversation_is_said_not_to_be_attached():
    said_so, hello, not_read = [(NOT_TAKEN, OPEN_MINE)], [(HELLO.format(name=EVE), None)], [(NOT_READ, None)]
    with school(EVE, SAM, ROSA):
        u = a_doc(EVE); assert talk_to(EVE, lambda: hook(u)) == [(NOT_TAKEN, dict(inline_keyboard=[[dict(text="Open in the app", url=BASE + "/relief#mine")]]))] and heard(EVE, lambda: hook(u)) == [], "an update is acted on once"
        for f in (lambda: photo(EVE), lambda: doc(EVE, "x.zip"), lambda: doc(EVE, caption="/stop"), lambda: photo(EVE, caption="ABCD-EFGH"), lambda: doc(EVE, caption="/relief")): assert f() == said_so
        assert links.name_of(CHATS[EVE]) == EVE and deleted() == [] and talks() == [] and not any(links.tries.fails.values()) and calls("getFile") == [] and calls("download") == []
        for kind in (dict(sticker=dict(file_id="s")), dict(voice=dict(file_id="v")), dict(video=dict(file_id="v")), dict(location={}), dict(document=7), dict(document={}), dict(photo=[]), {}): assert heard(EVE, lambda: hook(_with(EVE, **kind))) == not_read, kind
        assert says(EVE, "hello") == not_read and says(EVE, "/help") == hello
        # an album: once, however its files come; each chat's its own
        assert photo(EVE, "A1", media_group_id="g1") == said_so and photo(EVE, "A2", media_group_id="g1") == [] and doc(EVE, "a.pdf", "A3", media_group_id="g1") == []
        assert photo(EVE, "B1", media_group_id="g2") == said_so and photo(EVE, "A4", media_group_id="g1") == [] and photo(SAM, "A1", media_group_id="g1") == said_so
        for odd in (7, "", None, ["g3"], {}): assert photo(EVE, media_group_id=odd) == photo(EVE, media_group_id=odd) == said_so, odd
        ups = [a_photo(EVE, f"C{k}", media_group_id="g4") for k in range(6)]; n = len(said(EVE)); at_once(*[lambda u=u: hook(u) for u in ups]); assert said(EVE)[n:] == [NOT_TAKEN]
        for k in range(70): photo(EVE, f"D{k}", media_group_id=f"many{k}")
        assert len(tgdb.get_state("albums")) == AK.ALBUMS == 50 and photo(EVE, "D", media_group_id="many69") == [] and photo(EVE, "D", media_group_id="g1") == said_so, "the last fifty albums are known"
    with school(EVE, ROSA, base="http://localhost"): assert photo(EVE) == [(NOT_TAKEN, None)]
    # an album's file that comes after Send; or once the conversation has run out, or was cancelled
    with school(EVE, ROSA):
        to_work(); tap(EVE, "Later, in the app"); photo(EVE, "A1", media_group_id="g1"); sends(); was = file_of(only()["id"])
        assert photo(EVE, "A2", media_group_id="g1") == said_so and photo(EVE, "A3", media_group_id="g1") == [] and file_of(only()["id"]) == was and doc(EVE) == said_so
    for end in (lambda: at("09:30:01"), lambda: say(EVE, "/cancel"), lambda: say(EVE, "/help")):
        with school(EVE, ROSA): to_work(); end(); assert doc(EVE) == said_so and talks() == [] and mine() == []
    # a conversation that waits for something else answers it, as it did; so does a why
    with school(EVE, SAM, ROSA):
        relief_(); assert doc(EVE) == [(PRESS_ONE, None), (HI, DAY_ROWS)]; tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day", "Other"); assert doc(EVE) == [(SAY_WHY, LINE)]
        i, key = told_relief(); press(SAM, "change"); assert heard(SAM, lambda: hook(a_photo(SAM, caption="A meeting"))) == [(WHY_CHANGE, LINE)] and state_of(i) == "approved"
    # nobody there, over the limit, a group, an edit: as they were
    with school(EVE):
        for k in range(7): hook(dict(update_id=next(_ids), message=dict(a_doc(EVE)["message"], chat=dict(id=990, type="private"), **{"from": dict(id=990, is_bot=False)})))
        assert sent(990) == [(990, NOT_LINKED)] * 5 and len(links.tries.fails["tg:990"]) == 5
        with record(EVE, off=True): assert doc(EVE) == [(NOT_LINKED, None)]
        links.tries.fails.clear(); n = len(tg.PRACTICE_LOG)
        for kind in ("group", "supergroup", "channel"): hook(dict(update_id=next(_ids), message=dict(a_doc(EVE)["message"], chat=dict(id=CHATS[EVE], type=kind))))
        hook(dict(update_id=next(_ids), edited_message=a_doc(EVE)["message"])); assert tg.PRACTICE_LOG[n:] == []
        for k in range(5): links.tries.fail(f"tg:{CHATS[EVE]}")
        assert doc(EVE) == [] and photo(EVE) == [], "over the limit: nothing"

@t
def what_has_run_out_is_deleted_in_one_place_and_at_every_start():
    asked_for = []
    with school(EVE), stand_in(tgdb, "forget_talks", asked_for.append):
        bot.forget(); OB.prune(now=123.0); assert asked_for == [bot._clock(), 123.0], "the minute and the sender's start"
        bot.at_start(); assert asked_for[2:] == [bot._clock()], "with a token: what has run out"
        os.environ["TELEGRAM_BOT_TOKEN"] = ""
        try: bot.at_start(); assert asked_for[3] == float("inf"), "with none nobody can go on: all of it"
        finally: os.environ["TELEGRAM_BOT_TOKEN"] = "practice"
        for e in (RuntimeError("zebra"), sqlite3.OperationalError("zebra")):
            h = Grab(); KINDS.addHandler(h)
            try:
                def boom(now): raise e
                with stand_in(tgdb, "forget_talks", boom): assert bot.at_start() is None
            finally: KINDS.removeHandler(h)
            assert [type(e).__name__ in r.getMessage() and "zebra" not in r.getMessage() for r in h.records] == [True]
    def made(*talks_, text=None):
        """a data folder with a Telegram store in it (or a file that is none): talks_ (what is typed, seconds from now until it has run out)"""
        d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "relief")); p = os.path.join(d, "relief", "telegram.db")
        if text is not None: open(p, "wb").write(text); return d
        c = sqlite3.connect(p); c.executescript(tgdb.SCHEMA); c.executemany("INSERT INTO talks(chat, kind, data, until) VALUES (?, 'ask', ?, ?)", [(k + 1, json.dumps(dict(why=why)), time.time() + left) for k, (why, left) in enumerate(talks_)]); c.commit(); c.close(); return d
    def left(d):
        p = os.path.join(d, "relief", "telegram.db")
        if not os.path.exists(p): return None
        c = sqlite3.connect(p); got = [json.loads(r[0])["why"] for r in c.execute("SELECT data FROM talks ORDER BY chat")]; c.close(); return got
    two = ("zebra-old", -1), ("zebra-new", 900)
    runs = [(made(*two), "", "practice", ["zebra-new"]), (made(*two), "", "", []), (made(*two), "on", "", []), (tempfile.mkdtemp(), "", "", None), (tempfile.mkdtemp(), "", "practice", None), (made(text=b"this is no store " * 99), "", "", "odd")]
    ps = [subprocess.Popen([sys.executable, "-c", "import app; print('started')"], env=dict(os.environ, DATA_DIR=d, RELIEF_JOBS=jobs, TELEGRAM_BOT_TOKEN=token), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for d, jobs, token, want in runs]
    for p, (d, jobs, token, want) in zip(ps, runs):
        out, err = p.communicate(timeout=180); assert p.returncode == 0 and out.strip().endswith("started") and "zebra" not in out + err, (jobs, token, err[-300:])
        if want == "odd": continue
        assert left(d) == want, (jobs, token, left(d)); raw = b"".join(open(x, "rb").read() for x in glob.glob(os.path.join(d, "relief", "telegram.db*")))
        assert (b"zebra-old" not in raw) and (b"zebra-new" in raw) == (want == ["zebra-new"])
    with stand_in(tgdb, "PATH", os.path.join(tempfile.mkdtemp(), "relief", "telegram.db")):
        tgdb.forget_talks(9e12); assert not os.path.exists(os.path.dirname(tgdb.PATH)), "no store: none is made"

@t
def the_files_of_an_album_belong_to_one_lesson():
    with school(EVE, ROSA):
        to_work(); assert photo(EVE, "A1", media_group_id="g1", caption="Page 1") == [(WORK_5, LAST_ROWS)]; was = talks()[0][3]; at("09:05")
        n = len(tg.PRACTICE_LOG); assert photo(EVE, "A2", media_group_id="g1") == [] and doc(EVE, "a3.pdf", "A3", media_group_id="g1", caption="and 2") == [], "with no second question"
        assert tg.PRACTICE_LOG[n:] == [] and asking_of(EVE)["ask"] == WORK_5, "and the next lesson's is as it was"
        assert talks()[0][3] == was + 300 and all(r["until"] == was + 300 for r in rows("buttons")) and asking_of(EVE)["at"] == 1 and type(asking_of(EVE)["question"]) is int
        assert photo(EVE, "A2", media_group_id="g1") == [], "the same one twice"
        for k in (4, 5): assert photo(EVE, f"A{k}", media_group_id="g1") == []
        assert photo(EVE, "A6", media_group_id="g1") == [(f"photo 5.jpg: {TOO_MANY}", None)] and doc(EVE, "x.zip", "A7", media_group_id="g1") == [(f"x.zip: {FI.WRONG_KIND}", None)] and asking_of(EVE)["step"] == "work"
        assert photo(EVE, "B1", media_group_id="g2")[0][0].startswith("Relief for") and photo(EVE, "B2", media_group_id="g2") == [] and photo(EVE, "A9", media_group_id="g9") == [(PRESS_ONE, None), (board(EVE)[0], LIST_ROWS)], "after the last lesson too; another album is none's"
        assert sends()[0][0] == sent_text("2 lessons", "work set for 2"); a, b = [x["work"] for x in only()["lessons"][:2]]
        assert a["text"] == "Page 1\nand 2" and [f["name"] for f in a["files"]] == ["photo 1.jpg", "photo 2.jpg", "a3.pdf", "photo 3.jpg", "photo 4.jpg"] and [f["name"] for f in b["files"]] == ["photo 5.jpg", "photo 6.jpg"], (a, b)
    with school(EVE, ROSA):                                                                # for the last lesson: the list says it once the rest has come, in the same message
        say(EVE, "/relief"); tap(EVE, "Tomorrow, Tue 13 Oct", "Some periods", "P6 · 10:30", "P7 · 11:30", "Medical"); say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng")
        text = lambda what: f"Relief for Tue 13 Oct · P6–P7\nReason: Medical\nReporting officer: Ms Rosa Ng\n{ON_5}{what}"
        assert photo(EVE, "A1", media_group_id="g1") == [(text(SET_FILE), LIST_ROWS)]; q_, kb, n = asking_of(EVE)["question"], board(EVE)[1], len(tg.PRACTICE_LOG)
        assert photo(EVE, "A2", media_group_id="g1") == [] and photo(EVE, "A3", media_group_id="g1", caption="Page 3") == [] and doc(EVE, "x.zip", "A4", media_group_id="g1") == [(f"x.zip: {FI.WRONG_KIND}", None)]
        assert [(p["message_id"], p["text"]) for p in calls("editMessageText")[-2:]] == [(q_, text("work set (2 files)")), (q_, text("work set (text, 3 files)"))] and keyboard(calls("editMessageText")[-1]["reply_markup"]) == LIST_ROWS and board(EVE)[1] == kb and asking_of(EVE)["question"] == q_
        assert [m for m, p in tg.PRACTICE_LOG[n:]] == ["editMessageText", "editMessageText", "sendMessage"] and photo(EVE, "A2", media_group_id="g1") == [] and [m for m, p in tg.PRACTICE_LOG[n:]][3:] == [], "the same one twice: nothing to say"
        assert says(EVE, "hello") == [(PRESS_ONE, None), (text("work set (text, 3 files)"), LIST_ROWS)] and sends()[0][0] == sent_text("1 lesson", "work set for 1")
    with school(EVE, ROSA):                                                                # ... also while the list is on its way
        to_work(); tap(EVE, "Later, in the app"); real, nested = tg.call, []
        def on_its_way(method, params=None, **kw):
            if method == "sendMessage" and params["text"].startswith("Relief for") and not nested: nested.append(1); hook(a_photo(EVE, "A2", media_group_id="g1")); hook(a_photo(EVE, "A3", media_group_id="g1"))
            return real(method, params, **kw)
        with stand_in(tg, "call", on_its_way): assert photo(EVE, "A1", media_group_id="g1") == [(f"{LIST_HEAD}\n{ON_2}{NONE_YET}\n{ON_5}{SET_FILE}", LIST_ROWS)]
        p, = [p for p in calls("editMessageText") if p["text"].startswith("Relief for")]; assert (p["message_id"], p["text"]) == (asking_of(EVE)["question"], f"{LIST_HEAD}\n{ON_2}{NONE_YET}\n{ON_5}work set (3 files)") and keyboard(p["reply_markup"]) == LIST_ROWS
    with school(EVE, ROSA):                                                                # Same as before, and then the rest of that album
        to_work(); photo(EVE, "A1", media_group_id="g1"); tap(EVE, "Same as before"); photo(EVE, "A2", media_group_id="g1"); sends(); assert [[f["name"] for f in x["work"]["files"]] for x in only()["lessons"]] == [["photo 1.jpg", "photo 2.jpg"]] * 2 + [[]]
    with school(EVE, ROSA):                                                                # its first was refused: asked again, and the next is the answer
        to_work(); assert doc(EVE, "x.zip", "A1", media_group_id="g1") == [(f"x.zip: {FI.WRONG_KIND}", None), (WORK_2, FIRST_ROWS)] and doc(EVE, "y.pdf", "A2", media_group_id="g1") == [(WORK_5, LAST_ROWS)]
    for lock in (None, contextlib.nullcontext()) * 3:                                      # all at once, as Telegram posts them; in two copies of the app too
      with school(EVE, ROSA):
        to_work(); ups = [a_photo(EVE, f"A{k}", media_group_id="g1") for k in range(4)]
        with stand_in(bot, "_pressing", lock or bot._pressing): at_once(*[lambda u=u: hook(u) for u in ups])
        d = asking_of(EVE); assert d["at"] == 1 and [len(AK._work_of(d, k)["files"]) for k in (K2, K5)] == [4, 0] and sorted(f[0] for f in AK._work_of(d, K2)["files"]) == ["A0", "A1", "A2", "A3"] and type(d["question"]) is int, d
        assert says(EVE, "p. 5")[0][0].startswith("Relief for") and sends()[0][0].startswith("✅")
    with school(EVE, ROSA):                                                                # the question for the next lesson is on its way while the album goes on: its id is noted, and its answer taken
        to_work(); real, nested = tg.call, []
        def slow(method, params=None, **kw):
            if method == "sendMessage" and params["text"] == WORK_5 and not nested: nested.append(1); hook(a_photo(EVE, "A2", media_group_id="g1"))
            return real(method, params, **kw)
        with stand_in(tg, "call", slow): photo(EVE, "A1", media_group_id="g1")
        assert nested and type(asking_of(EVE)["question"]) is int and len(AK._work_of(asking_of(EVE), K2)["files"]) == 2 and says(EVE, "p. 5")[0][0].startswith("Relief for")
    for odd in (7, "", None, ["g1"], {}):                                                  # what is no album id is none
        with school(EVE, ROSA): to_work(); photo(EVE, "A1", media_group_id=odd); assert photo(EVE, "A2", media_group_id=odd)[0][0].startswith("Relief for"), odd

@t
def a_file_that_cannot_be_had_is_named_and_the_rest_goes():
    lost = lambda *names: "\n".join(f"{n} could not be attached: add it in the app." for n in names)
    with school(EVE, ROSA):
        to_work(); doc(EVE, "a.pdf", "F-a", media_group_id="g"); doc(EVE, "b.pdf", "F-b", media_group_id="g"); tap(EVE, "Same as before")
        with stand_in(tg, "download", lambda fid, limit: None if fid == "F-a" else b"b"): assert sends() == [(lost("a.pdf"), None), (sent_text("2 lessons", "work set for 2"), OPEN_MINE)], "named once"
        assert [[f["name"] for f in x["work"]["files"]] for x in only()["lessons"]] == [["b.pdf"], ["b.pdf"], []] and len(os.listdir(os.path.join(FI.DIR, only()["id"]))) == 1
    def boom(*a, **k): raise RuntimeError(f"{EVE} zebra-work F-a")
    for module, name in ((tg, "download"), (FI, "save"), (absences, "add_file")):           # whatever fails: the absence is sent, once, and said to be
        h = Grab(); KINDS.addHandler(h)
        try:
            with school(EVE, ROSA):
                to_work(); doc(EVE, "a.pdf", "F-a"); e = Since(); u = tapping(EVE, "Later, in the app"); hook(u)
                with stand_in(module, name, boom): assert sends() == [(lost("a.pdf"), None), (sent_text("2 lessons", "no work set yet"), OPEN_MINE)], name
                assert len(mine()) == 1 and [x[3] for x in e.new()] == ["asked"] and talks() == [] and only()["via"] == "telegram" and only()["lessons"][0]["work"]["files"] == []
                assert not os.path.isdir(os.path.join(FI.DIR, only()["id"])) or os.listdir(os.path.join(FI.DIR, only()["id"])) == [], "no file is left that no lesson lists"
        finally: KINDS.removeHandler(h)
        assert h.records and not any(w in r.getMessage() for r in h.records for w in (EVE, "zebra", "F-a", "a.pdf")), [r.getMessage() for r in h.records]
    with school(EVE, ROSA):                                                                # the answer of Telegram is larger than it said, or of no bytes
        to_work(); doc(EVE, "a.pdf", "F-a"); tap(EVE, "Later, in the app")
        with stand_in(tg, "download", lambda fid, limit: b""): assert sends()[0] == (lost("a.pdf"), None)
    with school(EVE, ROSA):                                                                # a lesson that is not in the absence any more when its file comes
        to_work(); doc(EVE, "a.pdf", "F-a"); doc(EVE, "b.pdf", "F-b")
        with stand_in(tg, "download", lambda fid, limit: (change_record(only()["id"], lambda r: r.update(lessons=[x for x in r["lessons"] if x["key"] != K2])), b"x")[1]): assert sends() == [(lost("a.pdf"), None), (sent_text("1 lesson", "work set for 1"), OPEN_MINE)]
        assert [[f["name"] for f in x["work"]["files"]] for x in only()["lessons"]] == [["b.pdf"], []] and len(os.listdir(os.path.join(FI.DIR, only()["id"]))) == 1
    with exam_school(EVE, ROSA):                                                           # one an exam stops meanwhile keeps its file (an exam takes no lesson out of one's own absence)
        to_work(); doc(EVE, "a.pdf", "F-a"); tap(EVE, "Later, in the app")
        with stand_in(tg, "download", lambda fid, limit: (exam("1C"), b"x")[1]): assert sends()[0][0].startswith("✅ Sent")
        assert [f["name"] for f in only()["lessons"][0]["work"]["files"]] == ["a.pdf"]
    with school(EVE, ROSA, TEAM):                                                          # cancelled on the page while its files come
        to_work(); doc(EVE, "a.pdf", "F-a"); tap(EVE, "Later, in the app")
        with stand_in(tg, "download", lambda fid, limit: (absences.cancel(only()["id"], "x", EVE), b"x")[1]): assert sends()[0] == (lost("a.pdf"), None)
        assert only()["cancelled"] and only()["lessons"][0]["work"]["files"] == [] and only()["lessons"][0]["work"]["text"] == ""
    with school(EVE, ROSA):                                                                # text set in the app meanwhile is kept, and so is a file added there
        to_work(); doc(EVE, "a.pdf", "F-a"); tap(EVE, "Later, in the app")
        def meanwhile(fid, limit):
            i = only()["id"]; f = FI.save(i, "mine.pdf", b"m"); absences.set_work(i, K2, dict(text="Typed there", link="https://x.example.org", files=[dict(id=f["id"], name=f["name"])], known=[]), EVE); return b"x"
        with stand_in(tg, "download", meanwhile): assert sends()[0][0] == sent_text("2 lessons", "work set for 1")
        w = only()["lessons"][0]["work"]; assert (w["text"], w["link"], [f["name"] for f in w["files"]]) == ("Typed there", "https://x.example.org", ["mine.pdf", "a.pdf"])
    for other in ("text", "link", "file", "unlocked"):                                     # what the app saves while the file waits for the lock is kept (its text, its link, its own file)
        with school(EVE, ROSA):
            to_work(); doc(EVE, "a.pdf", "F-a", caption="Typed here"); tap(EVE, "Later, in the app"); waits = []
            class Waiting:
                """the absences lock: once armed, the app saves just before the next one who wants it has it"""
                real = absences._LOCK
                def __enter__(s):
                    if waits: waits.pop()()
                    s.real.acquire()
                def __exit__(s, *a): s.real.release()
                def locked(s): return s.real.locked()
            def by_app():
                i = only()["id"]; w = only()["lessons"][0]["work"]
                f = [dict(id=FI.save(i, "mine.pdf", b"m")["id"], name="mine.pdf")] if other == "file" else []
                absences.set_work(i, K2, dict(text="Typed there" if other == "text" else w["text"], link="https://x.example.org" if other == "link" else w["link"], files=w["files"] + f, known=[]), EVE)
            def arrives(fid, limit):
                if other != "unlocked": waits.append(by_app)
                return b"x"
            with stand_in(absences, "_LOCK", Waiting()), stand_in(tg, "download", arrives): assert sends()[0][0].startswith("✅ Sent")
            w = only()["lessons"][0]["work"]; assert (w["text"], w["link"], [f["name"] for f in w["files"]]) == ("Typed there" if other == "text" else "Typed here", "https://x.example.org" if other == "link" else "", ["mine.pdf", "a.pdf"] if other == "file" else ["a.pdf"]) and waits == [], other
    with exam_school(EVE, ROSA):                                                           # a backup's own text and file are kept (the exams committee's absence moved into this one), and the new file comes after
        exam("5A", name=EXAM2, duties=[(EVE, 630, 690)]); RL.sync_all(SCHOOL, TERM, LS.today()); b, = [r["id"] for r in absences.all_records() if r.get("exams")]
        f = FI.save(b, "backup.pdf", b"theirs"); absences.set_work(b, K5, dict(text="Backup text", link="https://b.example.org", files=[dict(id=f["id"], name=f["name"])], known=[]), EVE)
        to_work(); tap(EVE, "Later, in the app"); doc(EVE, "a.pdf", "F-a"); assert sends() == [(sent_text("2 lessons", "work set for 1"), OPEN_MINE)]
        r, = [r for r in mine() if not r.get("exams")]; w = next(x for x in r["lessons"] if x["key"] == K5)["work"]; assert absences.load(b)["cancelled"] and (w["text"], w["link"], [f["name"] for f in w["files"]]) == ("Backup text", "https://b.example.org", ["backup.pdf", "a.pdf"])
        assert [open(FI.path(r["id"], f["id"]), "rb").read() for f in w["files"]] == [b"theirs", b"practice file"]
    with exam_school(EVE, ROSA):                                                           # ... and with five of its own there is no room: named, and nothing of it lost
        exam("5A", name=EXAM2, duties=[(EVE, 630, 690)]); RL.sync_all(SCHOOL, TERM, LS.today()); b, = [r["id"] for r in absences.all_records() if r.get("exams")]
        fs = [FI.save(b, f"b{k}.pdf", b"t") for k in range(5)]; absences.set_work(b, K5, dict(text="", link="", files=[dict(id=f["id"], name=f["name"]) for f in fs], known=[]), EVE)
        to_work(); tap(EVE, "Later, in the app"); doc(EVE, "a.pdf", "F-a"); assert sends() == [(lost("a.pdf"), None), (sent_text("2 lessons", "work set for 1"), OPEN_MINE)]
        r, = [r for r in mine() if not r.get("exams")]; assert [f["name"] for f in next(x for x in r["lessons"] if x["key"] == K5)["work"]["files"]] == [f"b{k}.pdf" for k in range(5)]
    with school(EVE, ROSA):                                                                # every file failing: one message
        to_work(); [doc(EVE, f"{k}.pdf", f"F{k}", media_group_id="g") for k in range(5)]; tap(EVE, "Later, in the app")
        with stand_in(tg, "download", lambda fid, limit: None): assert sends() == [(lost(*[f"{k}.pdf" for k in range(5)]), None), (sent_text("2 lessons", "no work set yet"), OPEN_MINE)]

@t
def the_app_failing_after_the_save_never_sends_it_twice():
    def boom(*a, **k): raise RuntimeError(f"{EVE} zebra-reason")
    with school(EVE, ROSA), quiet_app():                                                   # not marked: sent all the same
        to_list(); e = Since()
        with stand_in(absences, "set_via", boom): assert sends()[0][0].startswith("✅ Sent")
        assert len(mine()) == 1 and "via" not in only() and [x[3] for x in e.new()] == ["asked"] and talks() == []
    for module, name in ((WB, "_noted"), (WB, "_sync_exams"), (WB, "_soon"), (WB, "_tell_soon"), (links, "reachable"), (absences, "load")):
        with school(EVE, ROSA), quiet_app():
            to_list(); u = tapping(EVE, "Send"); again = tapping(EVE, "Send")
            with stand_in(module, name, boom): hook(u)
            assert len(mine()) == 1 and talks() == [] and [x for x in said(EVE) if x.startswith("✅ Sent")], name
            assert answered(again) == (OLD_BUTTON, True) and len(mine()) == 1, name
    class Dies(BaseException): pass
    def dies(*a, **k): raise Dies()
    for module, name in ((absences, "set_via"), (WB, "_noted"), (tg, "download"), (absences, "add_file")):       # the app stops there: one absence, and pressing again makes no other
        with school(EVE, ROSA):
            to_work(); doc(EVE, "a.pdf", "F-a"); tap(EVE, "Later, in the app"); again = tapping(EVE, "Send"); u = tapping(EVE, "Send")
            with stand_in(module, name, dies):
                try: handled(u)
                except Dies: pass
            assert len(mine()) == 1 and not bot._pressing.locked() and not absences._LOCK.locked(), name
            assert answered(again) == (OLD_BUTTON, True) and len(mine()) == 1, name
    with school(EVE, ROSA):                                                                # in the save itself: nothing is known of it, so the conversation is over
        to_list(); u, again = tapping(EVE, "Send"), tapping(EVE, "Send"); n = len(edits())
        with stand_in(absences, "new", boom): assert answered(u) == (WENT_WRONG, True)
        assert mine() == [] and talks() == [] and len(edits()) == n and answered(again) == (OLD_BUTTON, True), "one press is one try"
    with school(EVE, ROSA):                                                                # what follows happens in the page's order, with nothing held, before the press is answered
        to_list(); order, real = [], (WB._noted, WB._sync_exams, WB._soon, WB._tell_soon, tg.call); held = lambda: (absences._LOCK.locked(), bot._pressing.locked(), bot._counting.locked())
        with stand_in(WB, "_noted", lambda what, r, w, by=None: (order.append(("noted", what, w, by, "via" in absences.load(r["id"]), *held())), real[0](what, r, w, by=by))), stand_in(WB, "_sync_exams", lambda pub: (order.append(("sync", pub is SCHOOL, *held())), real[1](pub))), \
                stand_in(WB, "_soon", lambda **kw: (order.append(("soon", kw, *held())), real[2](**kw))[1]), stand_in(WB, "_tell_soon", lambda: (order.append(("tell", *held())), real[3]())), \
                stand_in(tg, "call", lambda m, p=None, **kw: (order.append((m, *held())), real[4](m, p, **kw))[1]): sends()
        F = (False, False, False); assert order == [("noted", "asked", "asked", (EVE, "telegram"), True, *F), ("sync", True, *F), ("soon", {}, *F), ("tell", *F), ("answerCallbackQuery", *F), ("editMessageText", *F), ("sendMessage", *F)], order
    with school(EVE, ROSA, SAM):                                                           # ... and the page's own, by the same function
        order = []
        with stand_in(WB, "_noted", lambda what, r, w, by=None: order.append(("noted", what, w, by))), stand_in(WB, "_sync_exams", lambda pub: order.append("sync")), stand_in(WB, "_soon", lambda **kw: order.append(("soon", kw))), stand_in(WB, "_tell_soon", lambda: order.append("tell")): by_page()
        assert order == [("noted", "asked", "asked", None), "sync", ("soon", {}), "tell"], order

@t
def two_presses_of_send_at_once_make_one_absence():
    for lock in (None, contextlib.nullcontext()):                                          # in one copy of the app, and (no lock between them) in two
        for _ in range(3):
            with school(EVE, ROSA):
                to_list(); ups, h = [tapping(EVE, "Send") for _ in range(6)], Since()
                with stand_in(bot, "_pressing", lock or bot._pressing): at_once(*[lambda u=u: hook(u) for u in ups])
                assert len(mine()) == 1 and len(h.new()) == 1 and sorted(answers()[-6:], key=str) == sorted([(None, None)] + [(OLD_BUTTON, True)] * 5, key=str), answers()[-6:]
                assert [x for x in said(EVE) if x.startswith("✅")] == [sent_text("2 lessons", "no work set yet")] and talks() == []
        with school(EVE, ROSA):                                                            # two buttons of one question at once: one of them
            relief_(); ups = [tapping(EVE, x) for x in ("Tomorrow, Tue 13 Oct", "Several days", "Another day")]
            with stand_in(bot, "_pressing", lock or bot._pressing): at_once(*[lambda u=u: hook(u) for u in ups])
            assert sorted(answers()[-3:], key=str) == sorted([(None, None)] + [(OLD_BUTTON, True)] * 2, key=str) and len(said(EVE)) == 2 and len(talks()) == 1
        with school(EVE, ROSA):                                                            # Send and Start again at once: one of them
            to_list(); ups = [tapping(EVE, x) for x in ("Send", "Start again")]
            with stand_in(bot, "_pressing", lock or bot._pressing): at_once(*[lambda u=u: hook(u) for u in ups])
            assert sorted(answers()[-2:], key=str) == sorted([(None, None), (OLD_BUTTON, True)], key=str) and len(mine()) + len(talks()) == 1
    with school(EVE, ROSA):                                                                # refused at once, again and again: the conversation stays, whole
        absent(); to_list(); was = talks(); ups = [tapping(EVE, "Send") for _ in range(4)]; at_once(*[lambda u=u: hook(u) for u in ups]); assert [a for a, _ in answers()[-4:]] == [f"{EVE} has already sent an absence for {EVE} on Tue 13 Oct."] * 4 and talks() == was
    with school(EVE, ROSA):                                                                # ticks at once are all kept, and the buttons shown last are as they are
        relief_(); tap(EVE, "Several days"); ups = [tapping(EVE, x) for x in ("Tue 13 Oct", "Wed 14 Oct", "Fri 16 Oct", "Tue 20 Oct")]; at_once(*[lambda u=u: hook(u) for u in ups])
        assert sorted(asking_of(EVE)["ticks"]) == ["2026-10-13", "2026-10-14", "2026-10-16", "2026-10-20"] and sorted(x for x in sum(rows_now(EVE), []) if x.startswith("✓")) == ["✓ Fri 16 Oct", "✓ Tue 13 Oct", "✓ Tue 20 Oct", "✓ Wed 14 Oct"]
    with school(EVE, ROSA):                                                                # a tick whose buttons reach Telegram after a later tick's: they are put right
        relief_(); tap(EVE, "Several days"); u, w, real, nested = tapping(EVE, "Tue 13 Oct"), tapping(EVE, "Wed 14 Oct"), tg.call, []
        def stale(method, params=None, **kw):
            if method == "editMessageReplyMarkup" and not nested: nested.append(1); hook(w)
            return real(method, params, **kw)
        with stand_in(tg, "call", stale): hook(u)
        assert [x for x in sum(rows_now(EVE), []) if x.startswith("✓")] == ["✓ Tue 13 Oct", "✓ Wed 14 Oct"] and len(calls("editMessageReplyMarkup")) == 3
    with school(EVE, ROSA):                                                                # lines at once: each answers one question at most, and is never taken twice
        to_work(); ups = [msg(f"Line {k}", CHATS[EVE]) for k in range(4)]; at_once(*[lambda u=u: hook(u) for u in ups]); d = asking_of(EVE)
        got = [AK._work_of(d, k)["text"] for k in (K2, K5)]; assert got[0].startswith("Line ") and len({x for x in got if x}) == len([x for x in got if x]), got

@t
def a_press_of_an_earlier_step_does_nothing():
    with school(EVE, ROSA, SAM):
        old = []
        def step(f): old.extend((tapping(EVE, x), x) for x in board(EVE)[1]); return f()
        relief_()
        for label in ("Several days", "Tue 13 Oct", "Done", "Some periods", "P1 · 08:00", "P7 · 11:30", "Medical"): step(lambda: tap(EVE, label))
        say(EVE, "ms"); step(lambda: tap(EVE, "Ms Rosa Ng")); step(lambda: says(EVE, "p. 1")); step(lambda: tap(EVE, "Same as before"))
        now_, was, n = set(board(EVE)[1].values()), talks(), len(said(EVE)); stale = [(u, x) for u, x in old if u["callback_query"]["data"] not in now_]; assert len(stale) > 30 and set(board(EVE)[1]) == {"Send", "Start again"}
        for u, x in stale: assert answered(u) == (OLD_BUTTON, True), x
        assert talks() == was and len(said(EVE)) == n and mine() == []
        assert all(re.fullmatch(r"b:[A-Za-z0-9_-]{16}", v) for v in now_) and {r["token"] for r in rows("buttons") if r["what"] == "ask"} == {v[2:] for v in now_}, "the ones that are over are not kept"
        assert all((r["name"], r["id"], r["ckey"], r["who"], r["extra"]) == (EVE, None, None, None, None) for r in rows("buttons") if r["what"] == "ask"), "a button holds nothing of what was said"
        sends(); assert len(mine()) == 1
        for u, x in old: assert answered(u) == (OLD_BUTTON, True), x
        assert len(mine()) == 1
    with school(EVE, ROSA, SAM):                                                           # two people at once: each conversation is its own
        relief_(); say(SAM, "/relief"); tap(EVE, "Tomorrow, Tue 13 Oct"); tap(SAM, "Several days"); assert tap(EVE, "Whole day") == [(REASON, REASON_ROWS)] and asking_of(SAM)["step"] == "days" and {r["name"] for r in rows("buttons")} == {EVE, SAM}
        say(SAM, "/cancel"); assert [x[0] for x in talks()] == [CHATS[EVE]] and tap(EVE, "Medical") == [(WHO_IS, LINE)]
    with school(EVE, ROSA):                                                                # /relief again: the one before it is over, with no word of it
        to_list(); u = tapping(EVE, "Send"); assert relief_() == [(HI, DAY_ROWS)] and answered(u) == (OLD_BUTTON, True) and mine() == [] and asking_of(EVE)["reason"] is None
        v = tapping(EVE, "Tomorrow, Tue 13 Oct"); tap(EVE, "Tomorrow, Tue 13 Oct"); was = talks(); assert answered(v) == (OLD_BUTTON, True) and talks() == was, "pressed twice"
    with school(EVE, ROSA):                                                                # a talk that had moved on meanwhile (another copy of the app): nothing is done
        relief_(); old_ = bot._talk(CHATS[EVE]); u, w = tapping(EVE, "Tomorrow, Tue 13 Oct"), tapping(EVE, "Several days"); hook(u); was = talks(); n = len(said(EVE))
        with stand_in(bot, "_talk", lambda chat: old_): assert answered(w) == (OLD_BUTTON, True) and says(EVE, "x") == [] and len(said(EVE)) == n
        assert talks() == was and [x[2]["step"] for x in talks()] == ["span"]
        to_work(); old_ = bot._talk(CHATS[EVE]); say(EVE, "p. 1"); was = [(c, k, dict(d, question=0), u_) for c, k, d, u_ in talks()]
        with stand_in(bot, "_talk", lambda chat: old_): n = len(tg.PRACTICE_LOG); say(EVE, "p. 2"); assert tg.PRACTICE_LOG[n:] == [], "the line that lost the race: nothing"
        assert [(c, k, dict(d, question=0), u_) for c, k, d, u_ in talks()] == was

@t
def text_where_a_button_is_needed_is_asked_again():
    with school(EVE, ROSA):
        relief_()
        for text, labels in ((HI, ["Several days"]), (WHICH_DAYS, ["Tue 13 Oct", "Done"]), (SPAN, ["Some periods"]), (FROM_P, ["P1 · 08:00"]), (TO_P, ["P7 · 11:30"]), (REASON, ["Medical"])):
            assert board(EVE)[0] == text; d, rows_, k = asking_of(EVE), rows_now(EVE), len(calls("editMessageReplyMarkup"))
            for line in ("hello", "Yes", "1", "Tue 13 Oct", "Send", "ABCD-EFGH", "", None): assert says(EVE, line) == [(PRESS_ONE, None), (text, rows_)], (text, line)
            e = asking_of(EVE); assert dict(e, question=0) == dict(d, question=0) and e["question"] > d["question"] and deleted() == [] and calls("editMessageReplyMarkup")[k] == dict(chat_id=CHATS[EVE], message_id=d["question"]), "the same question; the buttons of the one before are taken off"
            assert heard(EVE, lambda: hook(a_doc(EVE))) == [(PRESS_ONE, None), (text, rows_)] and heard(EVE, lambda: hook(_with(EVE, voice=dict(file_id="v")))) == [(PRESS_ONE, None), (text, rows_)]
            tap(EVE, *labels)
        say(EVE, "ms"); rows_ = rows_now(EVE); assert heard(EVE, lambda: hook(a_photo(EVE))) == [(PRESS_ONE, None), (WHO_HIT, rows_)], "names are offered: a button, or more of the name"
        say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng", "Later for all the rest"); assert says(EVE, "yes please") == [(PRESS_ONE, None), (board(EVE)[0], LIST_ROWS)] and mine() == [], "a line never sends"
    with school(EVE, ROSA):                                                                # a tick pressed on a copy whose buttons could not be taken off: that copy is changed
        relief_(); tap(EVE, "Several days"); u, q_ = tapping(EVE, "Tue 13 Oct"), asking_of(EVE)["question"]; say(EVE, "hello"); assert asking_of(EVE)["question"] != q_; hook(u)
        assert asking_of(EVE)["ticks"] == ["2026-10-13"] and calls("editMessageReplyMarkup")[-1]["message_id"] == q_
    with school(EVE, ROSA):                                                                # how long it lasts is not made longer by this
        relief_(); at("09:20"); say(EVE, "hello"); assert talks()[0][3] == secs("09:30")
    # a line, or a file, that replies to another message is not the answer (as for a why)
    with school(EVE, ROSA):
        to_work(); d = asking_of(EVE); assert heard(EVE, lambda: reply_to(EVE, d["question"] - 3, "p. 5")) == [(LAST_ONE, None), (WORK_2, FIRST_ROWS)] and asking_of(EVE)["work"] == {}
        assert heard(EVE, lambda: hook(a_doc(EVE, reply_to_message=dict(message_id=1)))) == [(LAST_ONE, None), (WORK_2, FIRST_ROWS)] and heard(EVE, lambda: say(EVE, "x", external_reply=dict(origin={}))) == [(LAST_ONE, None), (WORK_2, FIRST_ROWS)]
        assert heard(EVE, lambda: reply_to(EVE, asking_of(EVE)["question"], "p. 5"))[0][0] == WORK_5
        assert photo(EVE, "A1", media_group_id="g", reply_to_message=dict(message_id=asking_of(EVE)["question"]))[0][0].startswith("Relief for") and photo(EVE, "A2", media_group_id="g", reply_to_message=dict(message_id=3)) == [], "an album goes on whatever it replies to"

@t
def a_question_that_may_not_have_come_is_asked_again():
    """what is typed is never taken for the answer to a question the person may not have seen"""
    for kind in ("unsure", "network", "slow", "refused"):
        real = tg.call
        def failing_(method, params=None, **kw):
            r = real(method, params, **kw)
            return dict(ok=False, result=None, kind=kind, retry_after=5) if method == "sendMessage" else r
        with school(EVE, ROSA):
            relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day"); u = tapping(EVE, "Other")
            with stand_in(tg, "call", failing_): assert answered(u) == (None, None)
            assert asking_of(EVE)["step"] == "why" and says(EVE, "Hello?") == [(SAY_WHY, LINE)] and asking_of(EVE)["why"] == "" and says(EVE, "A meeting") == [(WHO_IS, LINE)], kind
            say(EVE, "rosa")
            with stand_in(tg, "call", failing_): hook(tapping(EVE, "Ms Rosa Ng"))
            assert says(EVE, "Hello?") == [(WORK_2, FIRST_ROWS)] and asking_of(EVE)["work"] == {}, kind
            with stand_in(tg, "call", failing_): say(EVE, "p. 5")
            assert heard(EVE, lambda: hook(a_doc(EVE))) == [(WORK_5, LAST_ROWS)] and tap(EVE, "Later, in the app")[0][0].startswith("Relief for")
            with stand_in(tg, "call", failing_): hook(tapping(EVE, "Send"))
            assert len(mine()) == 1 and mine()[0]["lessons"][0]["work"]["text"] == "p. 5" and talks() == [], "sent, whatever became of the message that says so"
        with school(EVE):                                                                  # its buttons work, should it have come after all
            relief_(); u = tapping(EVE, "Tomorrow, Tue 13 Oct")
            with stand_in(tg, "call", failing_): hook(u)
            assert tap(EVE, "Whole day") == [(REASON, REASON_ROWS)], kind
        with school(EVE):
            with stand_in(tg, "call", failing_): say(EVE, "/relief")
            assert says(EVE, "hello") == [(HI, DAY_ROWS)] and tap(EVE, "Tomorrow, Tue 13 Oct") == [(SPAN, SPAN_ROWS)], kind
    real = tg.call                                                                         # it came, and Telegram did not say its id: a line that replies to nothing is the answer
    for result in (None, True, {}, dict(message_id="7")):
        with school(EVE, ROSA), stand_in(tg, "call", lambda method, params=None, **kw: dict(real(method, params, **kw), **({"result": result} if method == "sendMessage" else {}))):
            relief_(); tap(EVE, "Tomorrow, Tue 13 Oct", "Whole day", "Other"); assert heard(EVE, lambda: reply_to(EVE, 7, "A meeting")) == [(LAST_ONE, None), (SAY_WHY, LINE)] and says(EVE, "A meeting") == [(WHO_IS, LINE)], result
            say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng"); assert says(EVE, "p. 5")[0][0] == WORK_5
    with school(EVE, ROSA):                                                                # answered before its id was noted: the id is not the next question's
        ids, nested = [], []
        def early(method, params=None, **kw):
            r = real(method, params, **kw)
            if method == "sendMessage": ids.append((params["text"], r["result"]["message_id"]))
            if method == "sendMessage" and params["text"] == SPAN and not nested: nested.append(1); hook(tapping(EVE, "Whole day"))
            return r
        relief_()
        with stand_in(tg, "call", early): tap(EVE, "Tomorrow, Tue 13 Oct")
        assert [x for x, n in ids] == [SPAN, REASON] and asking_of(EVE)["step"] == "reason" and asking_of(EVE)["question"] == ids[1][1], ids
    with school(EVE, ROSA):                                                                # a failing edit or answer changes nothing
        with stand_in(tg, "call", lambda method, params=None, **kw: dict(real(method, params, **kw), ok=method not in ("editMessageText", "editMessageReplyMarkup", "answerCallbackQuery"))):
            relief_(); tap(EVE, "Several days", "Tue 13 Oct"); assert asking_of(EVE)["ticks"] == ["2026-10-13"]; tap(EVE, "Done", "Whole day", "Medical"); say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng"); say(EVE, "p. 5"); tap(EVE, "Later, in the app", "Send"); assert len(mine()) == 1

@t
def a_talk_ends_after_thirty_minutes_and_on_cancel():
    with school(EVE, ROSA):
        relief_(); at("09:20"); tap(EVE, "Tomorrow, Tue 13 Oct"); assert talks()[0][3] == secs("09:50") and {r["until"] for r in rows("buttons")} == {secs("09:50")}, "30 minutes from the last step"
        at("09:50"); assert tap(EVE, "Whole day") == [(REASON, REASON_ROWS)], "in its last second"
        at("10:20:01"); u = tapping(EVE, "Medical"); assert answered(u) == (OLD_BUTTON, True) and says(EVE, "hello") == [(NOT_READ, None)] and rows("talks") == [] and mine() == []
        relief_(); at("10:55"); assert says(EVE, "ABCD-EFGH", message_id=41) == [(BAD_CODE, None)] and deleted() == [(CHATS[EVE], 41)], "a code is a code again"
        links.tries.fails.clear(); relief_(); tap(EVE, "Several days"); at("11:20"); tap(EVE, "Tue 13 Oct"); assert talks()[0][3] == secs("11:50") and {r["until"] for r in rows("buttons")} == {secs("11:50")}, "a tick is a step"
    for step in (0, 1, 2, 3):
        for text in ("/cancel", " /CANCEL ", "/cancel@practice_bot", "/cancel it was a mistake"):
            with school(EVE, ROSA):
                relief_(); [tap(EVE, x) for x in ("Tomorrow, Tue 13 Oct", "Whole day", "Medical")[:step]]; q_ = asking_of(EVE)["question"]
                assert says(EVE, text) == [(NOTHING_SENT, None)] and rows("talks") == [] and mine() == [], (step, text)
                assert calls("editMessageReplyMarkup")[-1:] == ([dict(chat_id=CHATS[EVE], message_id=q_)] if step < 3 else []), "the question loses its buttons"
                assert says(EVE, "/cancel") == [(NOT_READ, None)]
    with school(EVE, ROSA): to_list(); u = tapping(EVE, "Send"); assert says(EVE, "/cancel") == [(NOTHING_SENT, None)] and answered(u) == (OLD_BUTTON, True) and mine() == []
    # the other commands: told when a day was chosen
    for text, want in (("/help", [HELLO.format(name=EVE)]), ("/start", [HELLO.format(name=EVE)]), ("/start hello there", [HELLO.format(name=EVE)]), ("/stop", [STOPPED]), ("/start ABCD-EFGH", [BAD_CODE]), ("/HELP@practice_bot", [HELLO.format(name=EVE)])):
        with school(EVE, ROSA):
            relief_(); assert [x for x, b in says(EVE, text)] == want and rows("talks") == [], "no day chosen: nothing to tell"
        with school(EVE, ROSA):
            relief_(); tap(EVE, "Tomorrow, Tue 13 Oct"); u = tapping(EVE, "Whole day"); assert [x for x, b in says(EVE, text)] == [NOT_SENT] + want and rows("talks") == [] and mine() == [], text
            assert answered(u)[0] in (OLD_BUTTON, NOT_LINKED)
    with school(EVE, ROSA): relief_(); tap(EVE, "Several days", "Tue 13 Oct"); assert [x for x, b in says(EVE, "/help")][0] == NOT_SENT, "a day ticked is a day chosen"
    with school(EVE, ROSA): to_list(); assert relief_() == [(HI, DAY_ROWS)], "/relief starts anew without saying it"
    with school(EVE, ROSA): to_list(); tap(EVE, "Send"); assert [x for x, b in says(EVE, "/help")] == [HELLO.format(name=EVE)], "sent: nothing to tell"
    with school(EVE, HUGO):                                                                # linked to another by /start: said to whose it was, before
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct"); c = links.new_code(HUGO)["code"]; links.unlink(HUGO); assert [x for x, b in says(EVE, f"/start {c}")] == [NOT_SENT, TAKEN, HELLO.format(name=HUGO)] and rows("talks") == []
    with school(EVE):                                                                      # no right any more: NOT_LINKED alone
        relief_(); tap(EVE, "Tomorrow, Tue 13 Oct")
        with record(EVE, group="executive", extras=dict(relief=False, exams=None, admin=False)): assert says(EVE, "/help") == [(NOT_LINKED, None)] and rows("talks") == []
    # one nobody comes back to is deleted by the clock
    with school(EVE, SAM, ROSA):
        i, key = told_relief(); press(SAM, "change"); to_work(reason="Other"); at("09:15"); bot.forget(); assert sorted(x[1] for x in talks()) == ["ask", "change"]; at("09:15:01"); bot.forget(); assert [x[1] for x in talks()] == ["ask"]
        at("09:30"); bot.forget(); assert talks() and b"zebra-reason" in raw_store(); at("09:30:01"); bot.forget(); assert rows("talks") == [] and b"zebra-reason" not in raw_store()

@t
def another_question_in_its_place_says_it_was_not_sent():
    for what, question_ in (("change", WHY_CHANGE), ("cancel", WHY_CANCEL)):
        with school(EVE, SAM, TEAM):
            name = SAM if what == "change" else EVE
            if what == "change": i, key = told_relief()
            else: i = told_planned(dates=["2026-10-16"])
            was = file_of(i); say(name, "/relief"); assert [x for x, b in talk_to(name, lambda: press(name, what))] == [question_], "no day chosen: nothing to tell"
            say(name, "/relief"); tap(name, "Tomorrow, Tue 13 Oct"); u, q_ = tapping(name, "Whole day"), asking_of(name)["question"]
            assert [x for x, b in talk_to(name, lambda: press(name, what))] == [NOT_SENT, question_] and [x[1] for x in talks()] == [what], "told, before the question"
            assert answered(u) == (OLD_BUTTON, True) and [x[1] for x in talks()] == [what] and calls("editMessageReplyMarkup")[-1] == dict(chat_id=CHATS[name], message_id=q_)
            assert mine(name) == ([] if what == "change" else [absences.load(i)]) and file_of(i) == was
            assert says(name, "/relief")[0][1] == DAY_ROWS and [x[1] for x in talks()] == ["ask"], "and /relief ends that one, with no word"
    with school(SAM, EVE, TEAM):                                                           # acknowledging a relief leaves the conversation as it is
        i, key = told_relief(); say(SAM, "/relief"); tap(SAM, "Tomorrow, Tue 13 Oct"); was = talks(); assert press(SAM, "ack")[0].startswith("✅ Acknowledged") and talks() == was and tap(SAM, "Whole day") == [(REASON, REASON_ROWS)]
    with school(SAM, TEAM):                                                                # refused at the press (moved to another): no question, and the conversation goes on
        i, key = told_relief(); say(SAM, "/relief"); tap(SAM, "Tomorrow, Tue 13 Oct"); was = talks(); give(i, K5, MAYA); assert press(SAM, "change") == (CV.NOT_YOURS_COVER, True) and talks() == was and NOT_SENT not in said(SAM)

@t
def losing_the_right_or_the_link_mid_way():
    with school(EVE, ROSA, SAM):
        to_list(); was = talks(); u = lambda label="Send": tapping(EVE, label)
        with record(EVE, off=True): assert answered(u()) == (NOT_LINKED, True)
        with record(EVE, group="executive", extras=dict(relief=False, exams=None, admin=False)): assert answered(u()) == (NOT_YOURS_BUTTON, True)
        with broken_accounts(): links.tries.fails.clear(); assert answered(u()) == (NOT_LINKED, True)
        with no_pub(RP.fake_pub([dict(name=HUGO)])): links.tries.fails.clear(); assert answered(u()) == (NOT_LINKED, True), "gone from the timetable"
        links.tries.fails.clear(); assert talks() == was and mine() == [], "nothing is done, and given back it goes on"
        with record(EVE, off=True): assert says(EVE, "hello") == [(NOT_LINKED, None)]
        assert rows("talks") == [] and answered(u()) == (OLD_BUTTON, True) and mine() == [], "a line ends it"
    with school(EVE, ROSA, MAYA):
        to_list(); v = tapping(EVE, "Send"); links.unlink(EVE); assert rows("talks") == [] and answered(v) == (NOT_LINKED, True); links.link(EVE, CHATS[EVE], None); assert answered(v) == (OLD_BUTTON, True) and mine() == []
    with school(EVE, ROSA, MAYA):                                                          # moved to another phone: nobody there goes on with it
        to_list(); v = tapping(EVE, "Send"); links.link(EVE, 995, None); assert rows("talks") == [] and answered(callback(v["callback_query"]["data"], v["callback_query"]["message"], chat=995)) == (OLD_BUTTON, True) and mine() == []
    with school(EVE, ROSA, MAYA):                                                          # the chat is another's, and the talk was put back by hand: nothing of it is theirs
        to_list(); v = tapping(EVE, "Send"); kept_ = rows("talks")[0]; links.unlink(EVE); links.link(MAYA, CHATS[EVE], None)
        with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, ?, ?, ?)", (kept_["chat"], kept_["kind"], kept_["data"], kept_["until"]))
        assert answered(v) == (NOT_YOURS_BUTTON, True) and says(EVE, "x") == [(NOT_READ, None)] and mine() == mine(MAYA) == [] and rows("talks") == []
    for bad in ("{ not json", "[]", "null", "{}", '{"name": "Ms Evelyn Koh"}'):              # a conversation that cannot be read is none, or is one that went wrong: never anything done
        with school(EVE):
            with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, 'ask', ?, 9e12)", (CHATS[EVE], bad))
            got = says(EVE, "x"); assert got in ([(NOT_READ, None)], [(WENT_WRONG, None)]) and mine() == [] and says(EVE, "/cancel")[0][0] in (NOTHING_SENT, NOT_READ) and relief_() == [(HI, DAY_ROWS)], bad

@t
def a_publish_mid_way_never_loses_the_conversation():
    with school(EVE, ROSA):
        relief_(); was = talks()
        with no_pub(): assert answered(tapping(EVE, "Tomorrow, Tue 13 Oct")) == (WB.NO_PUB, True) and talks() == was
        tap(EVE, "Tomorrow, Tue 13 Oct")
        with no_pub(): assert tap(EVE, "Whole day") == [(REASON, REASON_ROWS)], "what needs no timetable goes on"
        with no_pub(): assert tap(EVE, "Medical") == [(WHO_IS, LINE)]
        was = talks()
        with no_pub(): assert says(EVE, "rosa") == [(WB.NO_PUB, None)] and [(c, k, d, u) for c, k, d, u in talks()] == was
        say(EVE, "rosa"); u = tapping(EVE, "Ms Rosa Ng")
        with no_pub(): assert answered(u) == (WB.NO_PUB, True)
        tap(EVE, "Ms Rosa Ng")
        with no_pub(): assert says(EVE, "p. 5") == [(WORK_5, LAST_ROWS)] and tap(EVE, "Same as before")[0][0].startswith("Relief for")
        was = talks()
        with no_pub(): assert answered(tapping(EVE, "Send")) == (WB.NO_PUB, True) and answered(tapping(EVE, "Start again")) == (WB.NO_PUB, True) and talks() == was and mine() == []
        assert sends()[0][0] == sent_text("2 lessons", "work set for 2")
    for cal, sentence in ((dict(terms=[], holidays=[]), LS.NO_CALENDAR), (dict(TERM, holidays=[dict(name="x", start="2026-10-13", end="2026-10-13")]), "Tue 13 Oct is not a school day in the calendar.")):
        with school(EVE, ROSA):                                                            # the calendar changed: the app's sentence, and the buttons stay
            relief_(); store.write_json(RS.PATH, dict(calendar=cal)); was = talks(); assert answered(tapping(EVE, "Tomorrow, Tue 13 Oct")) == (sentence, True) and talks() == was
        with school(EVE, ROSA): to_list(); store.write_json(RS.PATH, dict(calendar=cal)); was = talks(); assert answered(tapping(EVE, "Send")) == (sentence, True) and talks() == was and mine() == []

@t
def an_officer_who_is_not_on_telegram_is_said_to_be():
    NOT_ON = "Ms Rosa Ng is not on Telegram: please tell them yourself."
    with school(EVE): to_list(); assert sends() == [(sent_text("2 lessons", "no work set yet", NOT_ON), OPEN_MINE)]
    with school(EVE, ROSA):
        to_list()
        with record(ROSA, group="executive", extras=dict(relief=False, exams=None, admin=False)): assert sends()[0][0].endswith(NOT_ON), "linked, and without relief: not reached"
    for base in ("http://localhost", "", None):                                            # Telegram takes https buttons alone
        with school(EVE, ROSA, base=base): to_list(); assert sends() == [(sent_text("2 lessons", "no work set yet"), None)], base

@t
def a_very_long_list_is_cut():
    days_ = [d for d in DAYS]
    def busy_school(classes):
        pub = RP.fake_pub([dict(name=EVE, dept="Science"), dict(name=ROSA, dept="English")], [lesson(d, p, 1, classes, "Science with a long name", [EVE], group=f"Group {p}") for d in days_ for p in range(8)])
        pub["model"]["school"].update(start_time="08:00", period_minutes=30); pub["model"]["NP"] = 12; pub["model"]["setup"]["rules"] = []
        return pub
    for classes, least in ((["1A"], 30), ([f"Sec {k} Integrity" for k in range(12)], 5)):
        with school(EVE, ROSA), no_pub(busy_school(classes)):
            relief_(); tap(EVE, "Several days"); [tap(EVE, x) for x in list(board(EVE)[1]) if x != "Done"]; tap(EVE, "Done", "Whole day", "Medical"); say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng"); assert len(asking_of(EVE)["lessons"]) == 80
            assert says(EVE, "x" * 2000)[0][1] == [["Same as before", "Later, in the app"], ["Later for all the rest"]]
            text, rows_ = tap(EVE, "Later for all the rest")[0]; lines = text.split("\n"); shown = [x for x in lines if x.startswith("•")]
            assert rows_ == LIST_ROWS and len(text) <= 4096 and lines[-1] == f"and {80 - len(shown)} more" and least <= len(shown) <= 30 and (least != 30 or len(shown) == 30), (len(text), len(shown))
            assert sends()[0][0] == sent_text("80 lessons", "work set for 1") and len(only()["lessons"]) == 80
            for m, p in tg.PRACTICE_LOG:
                assert len(p.get("text") or "") <= 4096 and all(len(b.get("callback_data", "").encode()) <= 64 and 1 <= len(b["text"]) <= 64 for row in (p.get("reply_markup") or {}).get("inline_keyboard", []) for b in row), (m, p)
    for classes, least in ((["1A"], 30), ([f"Sec {k} Integrity" for k in range(12)], 5)):   # ... with the longest of what is set, for every lesson
        with school(EVE, ROSA), no_pub(busy_school(classes)):
            relief_(); tap(EVE, "Several days"); [tap(EVE, x) for x in list(board(EVE)[1]) if x != "Done"]; tap(EVE, "Done", "Whole day", "Medical"); say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng")
            [hook(a_photo(EVE, f"A{k}", media_group_id="g", **({} if k else dict(caption="x" * 1000)))) for k in range(5)]; [tap(EVE, "Same as before") for _ in range(79)]
            text = board(EVE)[0]; shown = [x for x in text.split("\n") if x.startswith("•")]; assert len(text) <= 4096 and all(x.endswith(": work set (text, 5 files)") for x in shown) and text.endswith(f"\nand {80 - len(shown)} more") and least <= len(shown) <= 30 and "xx" not in text, (len(text), len(shown))
    thirty = RP.fake_pub([dict(name=EVE, dept="Science"), dict(name=ROSA, dept="English")], [lesson(d, p, 1, ["1A"], "Art", [EVE]) for d in days_[5:8] for p in range(10)]); thirty["model"].update(NP=12); thirty["model"]["school"].update(start_time="08:00", period_minutes=30)
    with school(EVE, ROSA), no_pub(thirty):
        relief_(); tap(EVE, "Several days", "Mon 12 Oct", "Tue 13 Oct", "Wed 14 Oct", "Done", "Whole day", "Medical"); say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng"); text = tap(EVE, "Later for all the rest")[0][0]; assert text.count("•") == 30 and "more" not in text
    with school(EVE, ROSA):                                                                # a school whose periods have no times
        bare = json.loads(json.dumps(SCHOOL)); bare["model"]["school"].pop("start_time"); bare["model"].pop("times", None)
        with no_pub(bare):
            relief_(); tap(EVE, "Tomorrow, Tue 13 Oct"); assert tap(EVE, "Some periods") == [(FROM_P, [["P1", "P2", "P3"], ["P4", "P5", "P6"], ["P7", "P8", "P9"], ["P10", "P11", "P12"]])] and tap(EVE, "P3")[0][1][0] == ["P3", "P4", "P5"]
            tap(EVE, "P12", "Medical"); say(EVE, "rosa"); assert tap(EVE, "Ms Rosa Ng")[0][0] == WORK_2.replace(" (09:00)", "")

@t
def the_typed_reason_is_nowhere_but_in_the_absence():
    h, root = Grab(), logging.getLogger(); old = root.level; root.addHandler(h); KINDS.addHandler(h); root.setLevel(logging.DEBUG); real = tg.call
    def boom(*a, **k): raise LookupError(f"{EVE} zebra-reason quokka-work 987654")
    clear = lambda: b"zebra" not in raw_store() and b"quokka" not in raw_store()
    try:
        with school(EVE, ROSA, TEAM, SAM):
            to_work(reason="Other"); say(EVE, "quokka-work"); assert b"zebra-reason" in raw_store(), "kept while it is going"
            shown_ = "".join(x for x in said(EVE)); assert "zebra" not in shown_ and "quokka" not in shown_, "never said back"
            tap(EVE, "Later, in the app"); sends(); i = only()["id"]; assert only()["reason_text"] == "zebra-reason" and clear(), "sent: gone from the store"
            give(i, K5, SAM); swept(); send(); everyone = "".join(x for c, x in sent() if c != CHATS[EVE]); assert "Other" in "".join(said(ROSA)) and "zebra" not in everyone and "zebra" not in "".join(x for c, x in sent(CHATS[EVE]))
            absences.cancel(i, "x", EVE)
            for end in (lambda: say(EVE, "/cancel"), lambda: say(EVE, "/help"), lambda: say(EVE, "/relief"), lambda: tap(EVE, "Later for all the rest", "Start again"), lambda: links.unlink(EVE)):
                if EVE not in links.linked(): links.link(EVE, CHATS[EVE], None)
                to_work(reason="Other"); end(); assert clear(), "however it ends"
            links.link(EVE, CHATS[EVE], None); to_work(reason="Other"); tap(EVE, "Later for all the rest")
            with stand_in(absences, "new", boom): answered(tapping(EVE, "Send"))
            assert clear() and talks() == []; to_work(reason="Other"); u = tapping(EVE, "Later, in the app"); at("12:00"); answered(u); say(EVE, "hello"); assert clear(), "run out, and met"
            for module, name in ((store, "published"), (tgdb, "db"), (absences, "all_records"), (RS, "load")):
                at("09:00"); to_work(reason="Other"); u = tapping(EVE, "Later, in the app"); v = tapping(EVE, "Later for all the rest")
                with stand_in(module, name, boom), quiet_app(): handled(u); handled(msg("zebra-line", CHATS[EVE])); handled(a_doc(EVE, "quokka.pdf")); handled(v); handled(msg("/relief", CHATS[EVE])); handled(msg("/cancel", CHATS[EVE]))
                say(EVE, "/cancel")
            with stand_in(tg, "call", lambda m, p=None, **kw: tg._fail("refused")): to_fail = [handled(msg(x, CHATS[EVE])) for x in ("/relief", "zebra-line", "/cancel")]
        raw = "".join(open(os.path.join(history.DIR, f), encoding="utf-8").read() for f in os.listdir(history.DIR)); assert "zebra-reason" not in raw and "quokka" not in raw
        mine_ = "\n".join(r.getMessage() for r in h.records if r.name.startswith("relief")); assert "LookupError" in mine_ and "refused" in mine_, mine_
        everything = "\n".join(r.getMessage() + str(r.exc_info or "") + str(r.args or "") for r in h.records if r.name.startswith("relief"))
        for bad in [EVE, ROSA, "zebra", "quokka", "987654", K5, *(str(c) for c in CHATS.values())]: assert bad not in everything, bad
        assert real is tg.call
    finally: root.removeHandler(h); KINDS.removeHandler(h); root.setLevel(old)

@t
def nothing_is_held_while_anything_is_said():
    real, seen = tg.call, []
    def spy(method, params=None, **kw): seen.append((method, absences._LOCK.locked(), bot._pressing.locked(), bot._counting.locked())); return real(method, params, **kw)
    with school(EVE, ROSA), stand_in(tg, "call", spy):
        relief_(); tap(EVE, "Several days", "Tue 13 Oct", "Done", "Some periods", "P1 · 08:00", "P7 · 11:30", "Other"); say(EVE, ""); say(EVE, "x"); say(EVE, "zzz"); say(EVE, "rosa"); tap(EVE, "Ms Rosa Ng"); doc(EVE, "x.zip"); doc(EVE); say(EVE, "x" * 2001); tap(EVE, "Same as before", "Send")
        relief_(); say(EVE, "x"); say(EVE, "/cancel")
    assert len(seen) > 40 and not any(any(x[1:]) for x in seen), [x for x in seen if any(x[1:])]
    with school(EVE, ROSA):                                                                # no model call, and no thread
        with stand_in(PK, "CALL", lambda data: 1 / 0): n = threading.active_count(); to_list(); sends(); assert threading.active_count() == n and len(mine()) == 1
    # an update is acted on once; a press from another kind of chat, or by another, on nothing
    with school(EVE, ROSA):
        to_list(); u = tapping(EVE, "Send"); [hook(u) for _ in range(3)]; assert len(mine()) == 1 and len([x for x in said(EVE) if x.startswith("✅")]) == 1
        for bad in (dict(data="b:" + "x" * 16), dict(data=None), dict(data="ask:send")): v = dict(tapping(EVE, "Send")["callback_query"]); v.update(bad); assert answered(dict(update_id=next(_ids), callback_query=v)) == (OLD_BUTTON, True)
    for first in ("asking", "bot"):                                                        # either can be imported first
        p = subprocess.run([sys.executable, "-c", f"import relief.{first}"], cwd=ROOT, env=dict(os.environ, DATA_DIR=tempfile.mkdtemp()), capture_output=True, text=True); assert p.returncode == 0, p.stderr[-400:]

# ---- an outage of Telegram (the final review) ----
REVOKED, WRONG_TOKEN = (401, dict(ok=False)), (404, dict(ok=False))

@contextlib.contextmanager
def clockwork(*down, how=NEVER_LEFT):
    """the school's bot under a made-up token and a clock of its own, from 09:00 on Mon 12 Oct: Telegram is down (how: what it does then) from one second
    to another, as often as down says -> v: v.t the second now; v.run(to): the sender every five seconds and the sweep every minute, until then; v.went:
    [(second, chat, text)]; v.asked: the seconds of getMe; v.tried: how many messages were tried; v.lines: what was logged"""
    began, h = datetime.datetime.fromisoformat("2026-10-12T09:00:00+08:00"), Grab()
    v = types.SimpleNamespace(t=0, went=[], asked=[], tried=0, lines=lambda: [r.getMessage() for r in h.records])
    def now(): return began + datetime.timedelta(seconds=v.t)
    def out(url, data, headers, timeout):
        method, p = url.rsplit("/", 1)[1], parts(data, headers)[0]
        if method == "getMe": v.asked.append(v.t)
        if method == "sendMessage": v.tried += 1
        if any(a <= v.t < b for a, b in down):
            if isinstance(how, BaseException): raise how
            return how[0], json.dumps(how[1]).encode()
        if method == "sendMessage": v.went.append((v.t, p["chat_id"], p["text"]))
        return 200, json.dumps(dict(ok=True, result=dict(message_id=1000 + v.tried))).encode()
    def run(to):
        while v.t < to:
            clock.now = now().isoformat(timespec="seconds")
            if v.t % 60 == 0: TE.sweep()
            OB.send_due()
            v.t += 5
        clock.now = now().isoformat(timespec="seconds")
    v.run, v.told = run, lambda name: [x for t_, c, x in v.went if c == CHATS[name]]
    os.environ["TELEGRAM_BOT_TOKEN"] = "made-up-" + secrets.token_hex(10)
    tgdb.set_state("bot", dict(tgdb.get_state("bot"), username="ctss_made_up_bot", key=digest(tg.hook_secret())))
    KINDS.addHandler(h)
    try:
        with stand_in(tg, "_send", out), stand_in(OB, "_clock", lambda: now().timestamp()): yield v
    finally: KINDS.removeHandler(h)

def once(v):
    """nobody got any message twice, and every message there is has gone"""
    assert len(set((c, x) for t_, c, x in v.went)) == len(v.went) and {(r["state"], r["tries"]) for r in outs()} == {("sent", 0)}, [(r["kind"], r["name"], r["state"], r["tries"]) for r in outs()]

def a_busy_morning():
    """a relief planned, its messages of five kinds to make now -> the two absences' ids"""
    i = absent(by=HUGO); give(i, K2, MAYA); CV.ask_change(i, K2, "A parent meeting", MAYA); new_pick(i, K2, RUTH); give(i, K5, SAM)
    j = absent(dates=["2026-10-16"]); absences.cancel(j, "Better", EVE); return i, j

@t
def an_outage_costs_no_more_than_the_outage():
    """the final review's table: however long it was, what waited goes within half a minute of its end, in its order, once, and no try is counted"""
    for minutes, hows in ((3, (NEVER_LEFT, DOWN, REVOKED, WRONG_TOKEN)), (13, (NEVER_LEFT, REVOKED)), (20, (DOWN,)), (45, (NEVER_LEFT,)), (120, (DOWN,))):
        for how in hows:
            end = minutes * 60
            with school(EVE, SAM, MAYA, ROSA, TEAM, LEE), clockwork((0, end), how=how) as v:
                a_busy_morning(); v.run(end); assert v.went == [] and v.tried == 1 and {(r["state"], r["tries"], r["next_at"]) for r in outs()} == {("queued", 0, 0)}, (minutes, how)
                assert len(v.asked) <= end / 20 + 1 and all(b - a >= 20 for a, b in zip(v.asked, v.asked[1:])) and v.lines() == ["network"], (minutes, how, v.lines())
                v.run(end + 30); once(v); assert len(v.went) == len(outs()) == 7 and all(end <= t_ < end + 30 for t_, c, x in v.went), (minutes, how, v.went)
                with tgdb.db(read=True) as c: assert [x for t_, c_, x in v.went] == [r["text"] for r in c.execute("SELECT text FROM outbox ORDER BY rowid")], "in their order"
                assert {r["kind"] for r in outs()} == {"planned", "officer", "relief", "ask", "cancelled"} and v.lines() == ["network", "Telegram answers again (network)"], v.lines()
                n, asked_ = len(v.went), len(v.asked); v.run(end + 600); assert len(v.went) == n and len(v.asked) == asked_, "and nothing more"
    # a connection that times out: the one message that may have gone is marked so, the rest as above
    with school(EVE, SAM, MAYA, ROSA, TEAM, LEE), clockwork((0, 1200), how=MAY_HAVE) as v:
        a_busy_morning(); v.run(1200); assert v.tried == 1; v.run(1230); assert collections.Counter(r["state"] for r in outs()) == {"unsure": 1, "sent": 6} and {r["tries"] for r in outs()} == {0} and len(v.went) == 6
    # one blip, between two runs: told at the next
    with school(SAM), clockwork((0, 4)) as v: i = absent(); give(i, K5, SAM); v.run(15); assert [(t_, x) for t_, c, x in v.went] == [(5, RELIEF_K5)]
    # up and down all morning: each goes as soon as it is up, for half a minute
    with school(EVE, SAM, MAYA, ROSA, TEAM, LEE), clockwork(*[(a, a + 60) for a in range(0, 5400, 90)]) as v:
        for k, (ckey, who_) in enumerate(((K2, MAYA), (K5, SAM))): v.run(600 * k); i = absent(by=HUGO, periods=[2, 4] if ckey == K2 else [5, 6]); give(i, ckey, who_)
        v.run(5400); once(v); assert all(t_ % 90 >= 60 for t_, c, x in v.went) and max(t_ for t_, c, x in v.went) < 720

@t
def a_move_during_an_outage_is_told_when_it_ends():
    with school(SAM, MAYA, TEAM), clockwork((600, 4200)) as v:
        i = absent(by=HUGO); give(i, K5, SAM); v.run(1200); assert v.told(SAM) == [RELIEF_K5]
        give(i, K5, MAYA); v.run(4200); assert len(v.went) == 1 and [(r["kind"], r["name"], r["state"], r["tries"]) for r in outs()][1:] == [("moved", SAM, "queued", 0), ("relief", MAYA, "queued", 0)]
        v.run(4230); once(v); assert [(c, x) for t_, c, x in v.went[1:]] == [(CHATS[SAM], MOVED_K5), (CHATS[MAYA], RELIEF_K5)] and all(4200 <= t_ < 4230 for t_, c, x in v.went[1:])
        v.run(8400); assert len(v.went) == 3
    # what is not true any more by then is not said: moved twice, moved and back, cancelled
    with school(SAM, MAYA, HUGO, TEAM), clockwork((600, 4200)) as v:
        i = absent(by=HUGO); give(i, K5, SAM); v.run(1200); give(i, K5, MAYA); v.run(1800); give(i, K5, HUGO); v.run(4230)
        assert v.told(SAM) == [RELIEF_K5, MOVED_K5] and v.told(MAYA) == [] and v.told(HUGO) == [RELIEF_K5] and [r["state"] for r in outs("relief", MAYA)] == ["dropped"]
    with school(SAM, MAYA, TEAM), clockwork((600, 4200)) as v:
        i = absent(by=HUGO); give(i, K5, SAM); v.run(1200); give(i, K5, MAYA); v.run(1800); give(i, K5, SAM); v.run(4230); assert v.told(MAYA) == [] and v.told(SAM) == [RELIEF_K5] * 2 and state(outs("moved")[0]["key"]) == "dropped"
    with school(SAM, MAYA, TEAM), clockwork((600, 4200)) as v:
        i = absent(by=HUGO); give(i, K5, SAM); v.run(1200); give(i, K5, MAYA); v.run(1800); absences.cancel(i, "Better", EVE); v.run(4290); assert v.told(MAYA) == [] and v.told(SAM) == [RELIEF_K5, MOVED_K5] and v.told(TEAM) == [CANCELLED_EVE.format(EVE)]

@t
def in_doubt_getme_is_asked_every_twenty_seconds():
    assert (OB.ME_EVERY, OB.ME_TIMEOUT) == (20, 5)
    for first in (NEVER_LEFT, DOWN, REVOKED, WRONG_TOKEN, MAY_HAVE):
        with made_up():
            links.link(TIA, 501, None); now, at_, checked = [1000], [], []
            def go(t_, f): now[0] = t_; return with_send(f, lambda: OB.send_due(now=t_))
            for k in "ab": q(k, text=k)
            f, seen = tele(first, me=NEVER_LEFT, before=lambda m, p, up: at_.append((now[0], m))); assert go(1000, f)["sent"] == 0 and at_ == [(1000, "sendMessage")]
            go(1001, f); was = rows("outbox"); q("c", text="c")
            with valid(lambda it: checked.append(it)):                                      # a run every second (woken by each save): nothing but the question
                for t_ in range(1002, 1101): assert go(t_, f)["sent"] == 0
            assert at_[1:] == [(t_, "getMe") for t_ in range(1001, 1101, 20)] and checked == [] and rows("outbox")[:2] == was, (first, at_)
            f, seen = tele(); assert go(1100, f)["sent"] == 0 and seen == []; assert go(1101, f)["sent"] == (2 if first is MAY_HAVE else 3) and [m for m, p, up in seen][0] == "getMe"
            assert texts(seen) == ["a", "b", "c"][first is MAY_HAVE:] and {r["tries"] for r in rows("outbox")} == {0}, "oldest first, and no try counted"
            # the next doubt is another: it asks at its first run, however lately the last one did; a clock put back asks too
            q("d", text="d"); f, seen = tele(NEVER_LEFT); go(1102, f); assert go(1107, f)["sent"] == 1 and [m for m, p, up in seen] == ["sendMessage", "getMe", "sendMessage"]
            q("e", text="e"); f, seen = tele(NEVER_LEFT, me=DOWN); go(5000, f); go(5001, f); go(5002, f); go(4000, f); assert [m for m, p, up in seen] == ["sendMessage", "getMe", "getMe"]

@t
def a_try_that_met_an_outage_is_not_counted():
    """Telegram does not answer getMe after it: it was not the message. When it answers, it was, the sixth time for good"""
    with made_up():
        links.link(TIA, 501, None); go = lambda at_: with_send(f, lambda: OB.send_due(now=at_)); has = lambda k: (state(k), item(k)["tries"], item(k)["next_at"])
        for n in range(6):
            counted = ("queued", n + 1, 1000 + OB.WAITS[n]) if n < 5 else ("failed", 6, 0)
            for how, me in ((NEVER_LEFT, DOWN), (DOWN, MAY_HAVE), (REVOKED, REVOKED), (DOWN, SLOW(1))):
                k = f"k{len(rows('outbox'))}"; q(k); put(k, tries=n); f, seen = tele(how, me=me); go(1000); assert has(k) == counted, (n, how)
                go(1001); assert has(k) == ("queued", n, 0) and [m for m, p, up in seen] == ["sendMessage", "getMe"], (n, how)
                f, seen = tele(); go(1030); assert has(k)[:2] == ("sent", n), "at once, however long it would have waited"; OB._hold[0] = 0.0
            k = f"k{len(rows('outbox'))}"; q(k); put(k, tries=n); f, seen = tele(NEVER_LEFT); go(1000); go(1001); assert has(k) == counted and [m for m, p, up in seen] == ["sendMessage", "getMe"], "answered: counted"
            put(k, state="sent")
        # what became of it meanwhile stays (another copy of the app tried it, it was dropped, its person blocked the bot)
        for changes in (dict(tries=4), dict(state="dropped"), dict(state="sending"), dict(state="sent"), dict(state="unsure")):
            q("x"); f, seen = tele(NEVER_LEFT, me=DOWN); go(1000); put("x", **changes); was = item("x"); go(1001); assert item("x") == was, changes
            put("x", state="dropped"); OB._doubt.clear()
        # only the one it began with, and once
        q("y"); q("z"); put("z", tries=3, next_at=9e9); f, seen = tele(NEVER_LEFT, me=DOWN); go(1000); go(1001); put("y", tries=1); go(1021); assert has("y") == ("queued", 1, 0) and has("z") == ("queued", 3, 9e9) and len(seen) == 3

@t
def a_message_that_fails_by_itself_holds_the_others_one_run():
    """a fault of the app's own (one that cannot be sent) is told from an outage by getMe: six tries and it is failed, and the rest go in the next run"""
    def fault(m, p, up):
        if m == "sendMessage" and p["text"] == "bad": raise ValueError("made up")
    with made_up():
        links.link(TIA, 501, None); f, seen = tele(before=fault); t_ = [1000]; q("bad", text="bad"); n = 0
        def run(): got = with_send(f, lambda: OB.send_due(now=t_[0])); t_[0] += 5; return got
        for k in "abc": q(k, text=k)
        assert run() == dict(sent=0, waiting=4) and texts(seen) == ["bad"]
        assert run()["sent"] == 3 and texts(seen) == ["bad", "bad", "a", "b", "c"], "due again, and the oldest: tried, and the rest go all the same"
        while state("bad") == "queued":                                                     # the sender, every five seconds, with a message a minute
            if t_[0] % 60 == 0: n += 1; q(f"m{n}", text=f"m{n}")
            run()
            if t_[0] % 60 == 10: assert state(f"m{n}") == "sent", (n, t_[0])                 # in the run it was queued for, or the one after
        assert texts(seen).count("bad") == 6 and n > 40 and {state(f"m{k}") for k in range(1, n)} == {"sent"} and sum(OB.WAITS) <= t_[0] - 1000 < sum(OB.WAITS) + 60, "its own ladder, no longer"
        run(); assert [x for x in texts(seen) if x != "bad"] == ["a", "b", "c"] + [f"m{k}" for k in range(1, n + 1)] and state("bad") == "failed", "each once"
    with made_up():                                                                         # several of them, among good ones
        links.link(TIA, 501, None); f, seen = tele(before=fault); t_ = 1000
        for k in range(12): q(f"k{k}", text="bad" if k % 2 == 0 else f"good {k}")
        for _ in range(12): with_send(f, lambda: OB.send_due(now=t_)); t_ += 5
        assert sorted(x for x in texts(seen) if x != "bad") == sorted(f"good {k}" for k in range(1, 12, 2)), "within the minute"

@t
def a_token_that_is_not_taken_gives_nothing_up():
    for how in (REVOKED, WRONG_TOKEN):
        with made_up():
            links.link(TIA, 501, None); links.link(HUGO, 502, None); [q(f"k{i}", TIA if i % 2 else HUGO, f"k{i}") for i in range(6)]
            f, seen = tele(rest=how, me=how)
            for t_ in range(1000, 1000 + 2 * 3600, 5): with_send(f, lambda: OB.send_due(now=t_))
            assert len(texts(seen)) == 1 and len(seen) <= 1 + 2 * 180 and {(r["state"], r["tries"]) for r in rows("outbox")} == {("queued", 0)} and links.chat_of(TIA) == 501 and links.chat_of(HUGO) == 502, how
            f, seen = tele(); assert with_send(f, lambda: OB.send_due(now=1030 + 2 * 3600))["sent"] == 6 and texts(seen) == [f"k{i}" for i in range(6)]
            with work("a.pdf") as fs: f, seen = tele(OK_, how, how, how); q("f", files=fs); with_send(f, lambda: OB.send_due(now=99_000)); assert [m for m, p, up in seen] == ["sendMessage"] + ["sendDocument"] * 3 and OB.told("f")["files_failed"] == 1

@t
def the_sender_asks_before_anything_goes_when_it_starts():
    """a start in an outage spends no message: none is marked as one that may have gone, and no try is counted"""
    def started(f, until):
        th = OB.start(every=0.01)
        try:
            for _ in range(300):
                if until(): return
                time.sleep(0.01)
            raise AssertionError("not within three seconds")
        finally: OB._stop.set(); OB.wake(); th.join(5)
    with made_up():
        links.link(TIA, 501, None); q("a", text="a"); q("b", text="b")
        for how in (MAY_HAVE, NEVER_LEFT, REVOKED):                                         # started three times in it
            f, seen = tele(rest=how, me=how); runs = []; real = OB.send_due
            with stand_in(OB, "send_due", lambda: (real(), runs.append(1))): with_send(f, lambda: started(f, lambda: len(runs) > 10))
            assert [m for m, p, up in seen] == ["getMe"] and [(r["state"], r["tries"]) for r in rows("outbox")] == [("queued", 0)] * 2 and OB._doubt.is_set(), "at once, and not again within twenty seconds"
        f, seen = tele(); with_send(f, lambda: started(f, lambda: state("b") == "sent")); assert [m for m, p, up in seen] == ["getMe", "sendMessage", "sendMessage"] and texts(seen) == ["a", "b"] and not OB._doubt.is_set(), "asked at once, however lately before the start"
        f, seen = tele(); b = tgdb.get_state("bot"); tgdb.set_state("bot", None); n = []; real = OB.send_due; q("c", text="c")
        with stand_in(OB, "send_due", lambda: (real(), n.append(1))): with_send(f, lambda: started(f, lambda: len(n) > 3))
        assert seen == []; tgdb.set_state("bot", b); assert with_send(f, OB.send_due)["sent"] == 1 and [m for m, p, up in seen] == ["getMe", "sendMessage"], "not connected: asked once it is"

@t
def a_doubt_is_two_lines_and_a_store_that_fails_one():
    h = Grab(); KINDS.addHandler(h); lines = lambda: [r.getMessage() for r in h.records]
    go = lambda f, at_: with_send(f, lambda: OB.send_due(now=at_))
    try:
        for first, kind in ((NEVER_LEFT, "network"), (REVOKED, "network"), (LATE, "unsure")):
            with made_up():
                links.link(TIA, 501, None); q("a"); q("b"); h.records.clear(); f, seen = tele(first, me=NEVER_LEFT)
                for t_ in range(1000, 2800, 5): go(f, t_)
                assert lines() == [kind] and len(seen) == 91, (first, lines()[:5], len(seen))
                go(tele(me=LATE)[0], 2800); f, seen = tele(me=SLOW(30)); go(f, 2820); assert len(seen) == 1 and lines() == [kind], "another way of not answering is not another line"
                f, seen = tele(); go(f, 2850); assert lines() == [kind, f"Telegram answers again ({kind})"] and {r["state"] for r in rows("outbox")} <= {"sent", "unsure"}, lines()
                # what fails outside a doubt is logged as ever, and so is the next doubt
                q("d"); go(tele(REFUSED)[0], 2860); q("e"); go(tele(NEVER_LEFT)[0], 2865); go(tele()[0], 2880); assert lines()[2:] == ["refused", "network", "Telegram answers again (network)"], lines()
                with_send(tele(me=NEVER_LEFT)[0], lambda: tg.call("getMe")); assert lines()[-1] == "network" and len(lines()) == 6, "another's question is logged"
        with made_up():                                                                     # a start: a line when Telegram does not answer, none when it does
            links.link(TIA, 501, None); q("a")
            for me, want in ((NEVER_LEFT, ["network"]), (LATE, ["unsure"]), (OK_, [])):
                OB._doubts(); h.records.clear(); f, seen = tele(me=me); [go(f, t_) for t_ in range(1000, 1100, 5)]; assert lines() == want, (me, lines())
        # another thread's calls are logged meanwhile
        with made_up():
            links.link(TIA, 501, None); q("a"); go(tele(NEVER_LEFT)[0], 1000); h.records.clear(); other = []
            def elsewhere(m, p, up):
                if not other: other.append(1); th = threading.Thread(target=lambda: tg.call("sendMessage", dict(chat_id=1))); th.start(); th.join(5)
            go(tele(rest=REFUSED, me=NEVER_LEFT, before=elsewhere)[0], 1001); assert other and lines() == ["refused"], lines()
        # the sender's own failure: when it is another kind than the last, not at each run; and again once it had worked
        with telegram():
            real = OB.send_due
            def loop(*raises):
                left = list(raises)
                def due():
                    e = left.pop(0)
                    if not left: OB._stop.set()
                    if e: raise e(f"{TIA} made up")
                    return real()
                h.records.clear(); OB._stop.clear()
                with stand_in(OB, "send_due", due), stand_in(OB, "_wake", types.SimpleNamespace(wait=lambda s: None, clear=lambda: None)): OB._loop(0)
                return lines()
            D, O, failed = sqlite3.DatabaseError, sqlite3.OperationalError, "the message sender failed ({})".format
            assert loop(*[D] * 6) == [failed("DatabaseError")] and loop(None) == [] and loop(D, D, O, O, D) == [failed("DatabaseError"), failed("OperationalError"), failed("DatabaseError")] and loop(None) == []
            assert loop(D, None, D, D, None, None, D) == [failed("DatabaseError")] * 3 and loop(D, D) == [], "worked meanwhile: again"; loop(None)
            with stand_in(OB, "recover", lambda: (_ for _ in ()).throw(D("made up"))):
                n = [0]
                def wait(s): n[0] += 1; OB._stop.set() if n[0] == 5 else None
                h.records.clear(); OB._stop.clear()
                with stand_in(OB, "_wake", types.SimpleNamespace(wait=wait, clear=lambda: None)): OB._loop(0)
                assert lines() == [failed("DatabaseError")], "a store that is damaged when the app starts"
            loop(None)
        # a store that can be read and not written (a full disk): the same, at each run
        with telegram():
            links.link(TIA, 501, None); real_db = tgdb.db
            def locked(read=False):
                if not read: raise sqlite3.OperationalError("made up")
                return real_db(read)
            for k in range(2):
                q(f"a{k}"); q(f"b{k}"); h.records.clear()
                with stand_in(tgdb, "db", locked): [OB.send_due() for _ in range(6)]
                assert lines() == ["a message could not be sent (OperationalError)"] and OB.send_due()["sent"] == 2, lines()
            q("c"); h.records.clear(); b = tgdb.get_state("bot")
            with stand_in(tgdb, "db", locked): OB.send_due()
            tgdb.set_state("bot", None); OB.send_due(); tgdb.set_state("bot", b)
            with stand_in(tgdb, "db", locked): OB.send_due(); OB.send_due()
            assert len(lines()) == 2, "off meanwhile: it is said again"
            assert OB.send_due()["sent"] == 1
    finally: KINDS.removeHandler(h)

# ---- Answers, Task 1: the form and the reporting officer ----
NOT_TOLD_ROSA = "Ms Rosa Ng is not on Telegram: please tell them yourself."
ASKED = dict(dates=["2026-10-13"], periods=None, reason="Medical", reason_text="", reporting_officer=ROSA, lessons=[])

@t
def the_form_says_when_the_officer_is_not_on_telegram():
    with school(EVE):
        assert call(EVE, "post", "/api/relief/absences", ASKED)["officer_not_told"] == NOT_TOLD_ROSA
        assert AK.NOT_TOLD is TE.NOT_TOLD
    with school(EVE, ROSA): assert "officer_not_told" not in call(EVE, "post", "/api/relief/absences", ASKED), "she will be told"
    with school(EVE):
        tgdb.set_state("bot", None); assert "officer_not_told" not in call(EVE, "post", "/api/relief/absences", ASKED), "no bot: nothing is said of it"
    with school(EVE):
        assert "officer_not_told" not in call(HUGO, "post", "/api/relief/absences", dict(ASKED, teacher=EVE, reporting_officer="")), "no officer named"
        assert "officer_not_told" not in call(HUGO, "post", "/api/relief/absences", dict(ASKED, teacher=EVE, dates=["2026-10-14"], reporting_officer=HUGO)), "the officer sent it"
    with school(EVE):
        def boom(*a, **k): raise RuntimeError("made up")
        with stand_in(links, "reachable", boom): r = call(EVE, "post", "/api/relief/absences", ASKED)
        assert "officer_not_told" not in r and len(mine()) == 1, "never the save's failure"

# ---- Answers, Task 2: unlinked because the bot was blocked ----
def status_of(name): return who(name).get("/api/relief/telegram").get_json()

@t
def the_blocked_line_is_theirs_alone_and_goes_when_they_link():
    with made_up():
        links.link(TIA, 501, None); links.link(HUGO, 502, None); f, seen = tele(BLOCKED)
        with now_is("2026-10-13T07:10:00+08:00"): q("a"); with_send(f, OB.send_due)
        assert links.blocked(TIA) == "2026-10-13T07:10:00+08:00" and status_of(TIA)["blocked"] == "2026-10-13T07:10:00+08:00" and status_of(TIA)["linked"] is False
        assert links.blocked(HUGO) is None and status_of(HUGO)["blocked"] is None, "nobody else's"
        links.link(TIA, 601, None); assert links.blocked(TIA) is None and status_of(TIA)["blocked"] is None, "linked again"
        links.unlink(TIA); links.note_blocked(TIA); c = links.new_code(TIA)["code"]; assert links.use(c, 601, None) == TIA and links.blocked(TIA) is None, "by a code too"
        assert links.note_blocked(TIA) is False and links.blocked(TIA) is None, "never while they are linked"
        assert [r["k"] for r in rows("state") if r["k"].startswith("blocked:")] == []

@t
def only_a_blocked_bot_makes_the_line():
    with made_up():
        links.link(TIA, 501, None); links.unlink(TIA); assert links.blocked(TIA) is None, "Unlink, /stop or the team"
        links.link(TIA, 501, None); tgweb_unlink = who(TEAM).post("/api/relief/telegram/unlink", json=dict(name=TIA)); assert tgweb_unlink.status_code == 200 and links.blocked(TIA) is None
        links.link(TIA, 501, None); f, seen = tele(BLOCKED, before=lambda *a: tgdb.set_state("bot", None)); q("a"); with_send(f, OB.send_due)
        assert links.blocked(TIA) is None, "the bot disconnected meanwhile: nobody unlinked, no line"
        bot_on("ctss_made_up_bot"); real = links.unlink
        def late(name, *a): links.link(TIA, 601, None); return real(name, *a)
        with stand_in(links, "unlink", late): f, seen = tele(BLOCKED); q("b"); with_send(f, OB.send_due)
        assert links.chat_of(TIA) == 601 and links.blocked(TIA) is None, "linked again on another phone between: no line"
        links.unlink(TIA); links.link(TIA, 501, None); f, seen = tele(BLOCKED, before=lambda *a: links.unlink(TIA)); q("c"); with_send(f, OB.send_due)
        assert links.blocked(TIA) is None, "unlinked by hand between: the bot was not what unlinked them"
        links.link(TIA, 501, None); tgdb.set_state("blocked:" + TIA, "2026-10-13T07:10:00+08:00"); assert status_of(TIA)["blocked"] is None, "a note left behind is not shown while linked"

assert REAL == [], "a test reached the network"
print(f"{COUNT} relief telegram tests passed")

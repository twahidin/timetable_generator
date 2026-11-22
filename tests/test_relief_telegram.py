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
from relief import bot, links, outbox as OB, people as RP, tgweb, web as WB  # noqa: E402

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
    tg.PRACTICE_LOG.clear(); links.tries.fails.clear(); OB._doubt.clear()

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
    old = root.level; root.addHandler(h); root.setLevel(logging.DEBUG)
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
    finally: root.removeHandler(h); root.setLevel(old)

# ---- Task 3: the message queue and its sender ----
import subprocess  # noqa: E402
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
def q(key="k", name=TIA, text="A made-up message", **more): return OB.queue(key, name, text, kind=more.pop("kind", "relief"), **more)

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
            (TIA, 501, "relief", "Line é 1\nLine 2 ", "queued", "2026-10-13T07:20:00+08:00", None, None, 0), r
        assert json.loads(r["ref"]) == ref and json.loads(r["files"]) == files and json.loads(r["buttons"]) == buttons
        assert tg.PRACTICE_LOG == [] and rows("buttons") == [], "queueing sends nothing"
        for s in ("queued", "sending", "sent", "failed", "unsure"):
            put("k", state=s); assert q(text="Another") is False and item("k")["text"] == "Line é 1\nLine 2 ", s
        put("k", state="dropped", tries=4, slows=3, next_at=9e9, files_failed=1)
        assert q(text="Again") is True, "a dropped key is as if it were not there"
        r = item("k"); assert (r["text"], r["state"], r["tries"], r["slows"], r["files_failed"], r["buttons"]) == ("Again", "queued", 0, 0, 0, "[]") and len(rows("outbox")) == 1, r
        assert q() is False
        for bad in ([["x"]], [[dict(what="ack")]], [5]):          # a button that cannot be shown is the caller's mistake, said at once
            try: q("bad", buttons=bad)
            except (TypeError, ValueError, KeyError, AttributeError): pass
            else: raise AssertionError(bad)
        assert state("bad") is None
        assert q("flat", buttons=[dict(text="One", what="ack")]) is True and json.loads(item("flat")["buttons"]) == [[dict(text="One", what="ack")]], "a button alone is its own row"

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
                mid = state("k"); OB.recover(); OB._doubt.clear()                 # the app starts again, and everything works
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
        # slow: as long as Telegram says, an hour at most, and no try is counted
        f, seen = tele(SLOW(12), NEVER_LEFT, SLOW(7200), SLOW(0)); q("s", text="Slow one"); now = 2_000_000
        go(now); r = item("s"); assert (r["state"], r["tries"], r["slows"], r["next_at"]) == ("queued", 0, 1, now + 12), r
        go(now + 11); assert len(seen) == 1
        go(now + 12); r = item("s"); assert (r["tries"], r["slows"], r["next_at"]) == (1, 1, now + 12 + 5), r
        go(now + 17); r = item("s"); assert (r["tries"], r["slows"], r["next_at"]) == (1, 2, now + 17 + 3600), r
        go(now + 17 + 3600); r = item("s"); assert r["slows"] == 3 and r["next_at"] >= now + 17 + 3601, r
        assert go(now + 9999)["sent"] == 1 and texts(seen) == ["Slow one"] * 5 and state("s") == "sent"
        # ... 20 times in all
        f, seen = tele(rest=SLOW(1)); q("t")
        for i in range(1, 21): go(1000 * i); assert (state("t"), item("t")["slows"], len(seen)) == ("queued", i, i)
        go(21_000); assert state("t") == "failed" and len(seen) == 21
        f, seen = tele(SLOW(5), NEVER_LEFT); real = OB._clock                       # the real clock, when none is given
        OB._clock = lambda: 5_000_000.5
        try: q("u"); with_send(f, OB.send_due); assert item("u")["next_at"] == 5_000_005.5
        finally: OB._clock = real

@t
def a_flood_answer_stops_the_run():
    """Telegram asked for a pause: nothing more goes in this run, and nothing else before it (or a minute) is over"""
    with made_up():
        links.link(TIA, 501, None); links.link(HUGO, 502, None)
        for i in range(6): q(f"k{i}", HUGO if i else TIA, str(i))
        f, seen = tele(SLOW(30)); go = lambda at: with_send(f, lambda: OB.send_due(now=at))
        assert go(1000) == dict(sent=0, waiting=6) and len(seen) == 1
        for at in (1001, 1005, 1029): assert go(at) == dict(sent=0, waiting=6) and len(seen) == 1, at
        assert go(1030) == dict(sent=6, waiting=0) and texts(seen) == list("001" + "2345"), texts(seen)
        for i in range(6): q(f"m{i}", HUGO if i else TIA, str(i))
        f, seen = tele(SLOW(3600)); go(2000)
        assert go(2059)["sent"] == 0 and go(2060) == dict(sent=5, waiting=1) and item("m0")["next_at"] == 5600, "one person's hour is not everybody's"
        assert go(5600)["sent"] == 1

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
        for me in (MAY_HAVE, NEVER_LEFT, DOWN, LATE, REFUSED, SLOW(3), BLOCKED, (200, dict(ok=False))):
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
        # the bot disconnected meanwhile (somebody else's token says 403 to everybody): nobody is unlinked
        wipe(); bot_on("ctss_made_up_bot"); links.link(TIA, 501, None)
        def off(*a):
            with tgdb.db() as c: c.execute("DELETE FROM state WHERE k='bot'")
        f, seen = tele(BLOCKED, before=off); q("a"); with_send(f, OB.send_due)
        assert links.chat_of(TIA) == 501 and item("a") is None

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
        # it raises, or answers nothing: the message goes (VALID is asked last thing, each time it is tried)
        def boom(it): raise ValueError(TIA)
        for i, f in enumerate((boom, lambda it: None, lambda it: 0)):
            q(f"v{i}")
            with valid(f): assert OB.send_due()["sent"] == 1 and state(f"v{i}") == "sent", i
    with made_up():
        links.link(TIA, 501, None); f, seen = tele(NEVER_LEFT); q("r"); with_send(f, lambda: OB.send_due(now=1000))
        with valid(lambda it: False): with_send(f, lambda: OB.send_due(now=2000))
        assert state("r") == "dropped" and len(seen) == 1, "asked again before another try"

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
        links.link(TIA, 501, None); f, seen = tele(); extra = dict(absent="Mdm Very Long Name " * 9, n=[1])
        q(buttons=[[dict(text="✅ Acknowledge", what="ack", id="abc", ckey="Mon|3|S1|" + "x" * 90, who=TIA, extra=extra), dict(text="↩ Request to change", what="change", id="abc", ckey="c")],
                   [dict(text="Open in the app", url="https://ct.example.org/relief"), dict(text="Open here", url="http://localhost:8000/relief")],
                   [dict(text="Not secure", url="http://example.org"), dict(text="Odd", url="javascript:alert(1)"), dict(text="None", url=None)]])
        with_send(f, lambda: OB.send_due(now=5000))
        kb = seen[0][1]["reply_markup"]["inline_keyboard"]
        assert [[b["text"] for b in row] for row in kb] == [["✅ Acknowledge", "↩ Request to change"], ["Open in the app"]], kb
        assert kb[1][0] == dict(text="Open in the app", url="https://ct.example.org/relief") and [sorted(b) for b in kb[0]] == [["callback_data", "text"]] * 2
        data = [b["callback_data"] for b in kb[0]]
        assert all(re.fullmatch(r"b:[A-Za-z0-9_-]{16}", d) and len(d.encode()) < 64 for d in data) and data[0] != data[1], data
        got = {r["token"]: r for r in rows("buttons")}
        assert set(got) == {d[2:] for d in data}
        a, b = got[data[0][2:]], got[data[1][2:]]
        assert (a["name"], a["what"], a["id"], a["ckey"], a["who"], json.loads(a["extra"]), a["until"]) == (TIA, "ack", "abc", "Mon|3|S1|" + "x" * 90, TIA, extra, 5000 + 30 * 86400), a
        assert (b["name"], b["what"], b["id"], b["ckey"], b["who"], json.loads(b["extra"])) == (TIA, "change", "abc", "c", None, None), b
        f, seen = tele(); q("none", buttons=[[dict(text="x", url="http://localhost/relief")]]); q("no"); with_send(f, OB.send_due)
        assert all("reply_markup" not in p for m, p, up in seen) and len(seen) == 2 and len(rows("buttons")) == 2
    with telegram():                                                                       # practice: the same keyboard
        links.link(TIA, 501, None); q(buttons=[[dict(text="Here", url="http://localhost/relief"), dict(text="A", what="ack")]]); OB.send_due()
        assert [b["text"] for b in tg.PRACTICE_LOG[0][1]["reply_markup"]["inline_keyboard"][0]] == ["A"]

@t
def a_retry_keeps_its_tokens():
    with made_up():
        links.link(TIA, 501, None); f, seen = tele(NEVER_LEFT, SLOW(3), DOWN); q(buttons=[[dict(text="A", what="ack"), dict(text="B", what="change")]])
        for at in (1000, 2000, 3000, 4000): with_send(f, lambda: OB.send_due(now=at))
        kbs = [p["reply_markup"]["inline_keyboard"] for m, p, up in seen]
        assert len(kbs) == 4 and all(k == kbs[0] for k in kbs) and state("k") == "sent", kbs
        got = rows("buttons"); assert len(got) == 2 and {r["until"] for r in got} == {4000 + 30 * 86400}, "kept 30 days from the try that went"
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

@contextlib.contextmanager
def work(*names):
    """made-up work files -> their rows for queue"""
    got = [FI.save("abc123", n, f"made-up {n}".encode()) for n in names]
    try: yield [dict(id="abc123", file=x["id"], name=n) for x, n in zip(got, names)]
    finally:
        for x in got: FI.delete("abc123", x["id"])

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
        for answers, calls, failed, naps in (((SLOW(3),), 2, 0, 1), ((SLOW(3), NEVER_LEFT), 3, 0, 2), ((DOWN, DOWN, DOWN), 3, 1, 2), ((SLOW(9999), SLOW(1)), 3, 0, 2),
                                             ((MAY_HAVE,), 1, 1, 0), ((LATE,), 1, 1, 0), ((BLOCKED,), 1, 1, 0), ((REFUSED,), 1, 1, 0), ((NEVER_LEFT, MAY_HAVE), 2, 1, 1)):
            NAPS.clear(); f, seen = tele(OK_, *answers); key = f"f{len(rows('outbox'))}"; q(key, files=fs[:1]); with_send(f, OB.send_due)
            assert (len(seen) - 1, OB.told(key)["files_failed"], len(NAPS), state(key)) == (calls, failed, naps, "sent"), (answers, seen, NAPS)
            assert all(0 < n <= 20 for n in NAPS), NAPS
        assert links.chat_of(TIA) == 501, "a file refused unlinks nobody"
        # missing, odd or unreadable: noted, the others go
        for bad in (dict(id="abc123", file="0" * 12, name="x.pdf"), dict(id="../x", file="y", name="z"), dict(name="x.pdf"), dict(id="abc123", file=fs[0]["file"])):
            f, seen = tele(); key = f"f{len(rows('outbox'))}"; q(key, files=[bad, fs[1]]); with_send(f, OB.send_due)
            assert len(seen) == 2 and seen[1][2][1] == "b.docx" and OB.told(key)["files_failed"] == 1 and state(key) == "sent", (bad, seen)
        # a message that did not go takes no file with it
        for answer_ in (REFUSED, MAY_HAVE, LATE, NEVER_LEFT, SLOW(4), BLOCKED):
            OB._doubt.clear(); f, seen = tele(answer_); key = f"f{len(rows('outbox'))}"; q(key, files=fs); with_send(f, lambda: OB.send_due(now=1000)); assert len(seen) == 1, answer_
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
    import datetime
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
    h, root = Grab(), logging.getLogger(); old = root.level; root.addHandler(h); root.setLevel(logging.DEBUG)
    try:
        with made_up(), work("secret-name.pdf") as fs:
            tok = os.environ["TELEGRAM_BOT_TOKEN"]; links.link(TIA, 987650077, None); real = tgdb.db
            for i, a in enumerate((OK_, BLOCKED, REFUSED, DOWN, SLOW(3), NEVER_LEFT, MAY_HAVE, ValueError(f"{TIA} {tok}"))):
                links.link(TIA, 987650077, None); f, seen = tele(a, MAY_HAVE)
                q(f"relief:{TIA}:{i}", text="a private line", files=fs + [dict(name="secret-name.pdf")], buttons=[[dict(text="private label", what="ack", extra=dict(p="private extra"))]])
                def boom(it): raise RuntimeError(f"{TIA} a private line {tok}")
                with valid(boom): with_send(f, lambda: OB.send_due(now=1000))
            q(f"relief:{TIA}:x")
            def no_store(read=False): raise sqlite3.OperationalError(f"{TIA} a private line") if read is False else None
            tgdb.db = lambda read=False: real(read) if read else no_store()
            try: with_send(tele()[0], lambda: OB.send_due(now=9e12))
            finally: tgdb.db = real
        mine = "\n".join(r.getMessage() for r in h.records if r.name.startswith("relief"))
        for want in ("RuntimeError", "OperationalError", "network", "unsure", "blocked", "slow", "refused"): assert want in mine, (want, mine)
        everything = "\n".join(r.getMessage() + str(r.exc_info or "") + str(r.args or "") for r in h.records)
        for bad in ("private", TIA, "Tia", "98765", tok, "secret-name", "relief:", tg.hook_secret() or "x" * 64): assert bad not in everything, bad
    finally: root.removeHandler(h); root.setLevel(old)

assert REAL == [], "a test reached the network"
print(f"{COUNT} relief telegram tests passed")

"""The Telegram Bot API client: standard library only, and one function, _send, that touches the network.

token: the env TELEGRAM_BOT_TOKEN, stripped ("" when unset). on: a token is set. practice: the token is the word "practice":
nothing leaves the server, every call is kept in PRACTICE_LOG as (method, params) and getMe answers practice_bot.
hook_secret: hex HMAC-SHA256 of "telegram-hook:" + token under SECRET_KEY, what Telegram sends back with each update
("" when there is no SECRET_KEY). call: one Bot API method, never raising: dict(ok, result, kind, retry_after), kind None
when ok, else "blocked" (403), "slow" (429, wait retry_after), "refused" (other 4xx, no token, an answer that is not ok or not
JSON), "network" (an outage: 5xx other than 500 and 504, or never connected; and 401 and 404, a token that is revoked or wrong,
whatever was sent) and "unsure" (the request went out and no answer came, a read timeout or a reset, or it was 500 or 504, which
may come after it was taken: the message may have arrived). files: (field, filename, bytes) sent as multipart. download: a file by
its id, None when over the limit or failed.
The bot's address holds the token: no address, exception text or answer body is ever logged or raised; a failure is logged by
its kind alone to "relief.telegram", but for this thread's within quiet. Tests replace _send, which is the only way out."""
import contextlib, hashlib, ssl, hmac, itertools, json, logging, os, secrets, socket, threading, urllib.error, urllib.request
import http.client

API = "https://api.telegram.org"
PRACTICE_LOG = []                    # (method, params) of every call made in practice mode, for tests
_log = logging.getLogger("relief.telegram")
_counter = itertools.count(1)
_plock = threading.Lock()
_here = threading.local()            # quiet: this thread's failures are not logged
PRACTICE_FILE = b"practice file"


def token(): return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
def on(): return token() != ""
def practice(): return token() == "practice"


def hook_secret():
    key = os.environ.get("SECRET_KEY") or ""
    if not key: return ""
    return hmac.new(key.encode(), ("telegram-hook:" + token()).encode(), hashlib.sha256).hexdigest()


def _send(url, data, headers, timeout):
    """the one place that touches the network: (status, body bytes). An HTTP error status is an answer, not a failure."""
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        try: body = e.read()
        except Exception: body = b""
        return e.code, body


@contextlib.contextmanager
def quiet():
    """what this thread calls meanwhile is not logged when it fails (a question asked again and again, its first failure logged)"""
    _here.quiet = True
    try: yield
    finally: _here.quiet = False


def _fail(kind, retry_after=None):
    if not getattr(_here, "quiet", False): _log.warning(kind)
    return dict(ok=False, result=None, kind=kind, retry_after=retry_after)


def _multipart(params, files):
    boundary = "tt" + secrets.token_hex(16)
    out = []
    for k, v in (params or {}).items():
        if not isinstance(v, (str, int, float)): v = json.dumps(v)
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for field, filename, content in files:
        safe = str(filename).replace('"', "'").replace("\r", " ").replace("\n", " ")
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{safe}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
        out.append(bytes(content)); out.append(b"\r\n")
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def _body(raw):
    try:
        d = json.loads(raw.decode("utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return None


def _kind_of(exc):
    """'network' when nothing can have gone out, 'unsure' when the request may have: never retried by itself"""
    if isinstance(exc, urllib.error.URLError):
        exc = exc.reason
    if isinstance(exc, (socket.gaierror, ConnectionRefusedError, ssl.SSLCertVerificationError)): return "network"
    if isinstance(exc, (ConnectionError, TimeoutError, socket.timeout, http.client.HTTPException, OSError)): return "unsure"
    return "network"


def _classify(status, raw):
    d = _body(raw)
    if status == 200:
        if d is None or not d.get("ok"): return _fail("refused")
        return dict(ok=True, result=d.get("result"), kind=None, retry_after=None)
    if status == 403: return _fail("blocked")
    if status == 429:
        ra = ((d or {}).get("parameters") or {}).get("retry_after")
        return _fail("slow", ra if isinstance(ra, (int, float)) and not isinstance(ra, bool) else 5)
    if status in (401, 404): return _fail("network")
    if 400 <= status < 500: return _fail("refused")
    return _fail("unsure" if status in (500, 504) else "network")


def call(method, params=None, files=None, timeout=15):
    """one Bot API method; never raises"""
    try:
        if not on(): return _fail("refused")
        if practice():
            with _plock:
                PRACTICE_LOG.append((method, dict(params or {})))
                n = next(_counter)
            result = dict(username="practice_bot", first_name="Practice") if method == "getMe" else dict(message_id=n)
            return dict(ok=True, result=result, kind=None, retry_after=None)
        url = f"{API}/bot{token()}/{method}"
        if files:
            data, ctype = _multipart(params, files)
        else:
            data, ctype = json.dumps(params or {}).encode(), "application/json"
        try:
            status, raw = _send(url, data, {"Content-Type": ctype}, timeout)
        except urllib.error.HTTPError as e:
            try: raw = e.read()
            except Exception: raw = b""
            status = e.code
        return _classify(status, raw)
    except Exception as e:
        return _fail(_kind_of(e))


def download(file_id, limit):
    """the bytes of a file Telegram holds, or None when it is larger than limit or anything fails"""
    try:
        if not on(): return None
        if practice():
            with _plock: PRACTICE_LOG.append(("download", dict(file_id=file_id)))
            return PRACTICE_FILE if len(PRACTICE_FILE) <= limit else None
        r = call("getFile", dict(file_id=file_id))          # a failure here is already logged, by kind
        if not r["ok"]: return None
        if not isinstance(r["result"], dict): _log.warning("refused"); return None
        path, size = r["result"].get("file_path"), r["result"].get("file_size")
        if not path or (isinstance(size, int) and size > limit): _log.warning("refused"); return None
        status, raw = _send(f"{API}/file/bot{token()}/{path}", None, {}, 30)
        if status != 200:
            _classify(status, raw); return None             # logs its kind
        if len(raw) > limit: _log.warning("refused"); return None
        return raw
    except Exception as e:
        _log.warning(_kind_of(e))
        return None

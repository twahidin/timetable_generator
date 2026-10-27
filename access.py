"""Access codes. Three shared codes come from Railway variables (COMMITTEE_CODE, TEACHER_CODE, STUDENT_CODE); each
student on the Students sheet also gets a personal code made from their Student ID and SECRET_KEY, so the codes stay
the same until SECRET_KEY changes. Codes are compared ignoring case, spaces and dashes."""
import collections, hashlib, hmac, os, threading, time

ROLES = (("committee", "COMMITTEE_CODE"), ("teacher", "TEACHER_CODE"), ("student", "STUDENT_CODE"))
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"          # no 0/O, 1/I/L: easy to read off a slip

def norm(code):
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum())

def secret():
    return (os.environ.get("SECRET_KEY") or "").encode()

def personal_code(student_id):
    d = hmac.new(secret(), ("timetable-personal:" + str(student_id)).encode(), hashlib.sha256).digest()
    n = int.from_bytes(d[:8], "big"); out = ""
    for _ in range(8): out += ALPHABET[n % len(ALPHABET)]; n //= len(ALPHABET)
    return out[:4] + "-" + out[4:]

def configured():
    """which general codes are set, and problems to show the committee"""
    have = {role: bool(norm(os.environ.get(var))) for role, var in ROLES}
    probs = [f"{var} is not set in Railway variables." for role, var in ROLES if not have[role]]
    if not os.environ.get("SECRET_KEY"): probs.append("SECRET_KEY is not set: sign-ins and personal student codes need it.")
    vals = [norm(os.environ.get(var)) for _, var in ROLES if norm(os.environ.get(var))]
    if len(vals) != len(set(vals)): probs.append("Two of the general codes are the same; make them different.")
    short = [var for _, var in ROLES if 0 < len(norm(os.environ.get(var))) < 6]
    if short: probs.append(f"{', '.join(short)} should be at least 6 letters or digits.")
    return have, probs

def match(code, personal):
    """-> (role, student_id) or (None, None). personal: {normalised code: student id}"""
    c = norm(code)
    if not c: return None, None
    for role, var in ROLES:
        v = norm(os.environ.get(var))
        if v and hmac.compare_digest(v, c): return role, None
    sid = personal.get(c)
    return ("personal", sid) if sid is not None else (None, None)

class Limiter:
    """at most `n` wrong codes per `window` seconds from one address"""
    def __init__(self, n=10, window=600):
        self.n, self.window, self.fails, self.lock = n, window, collections.defaultdict(collections.deque), threading.Lock()
    def blocked(self, who):
        with self.lock:
            q = self.fails[who]; now = time.time()
            while q and now - q[0] > self.window: q.popleft()
            return len(q) >= self.n
    def fail(self, who):
        with self.lock: self.fails[who].append(time.time())

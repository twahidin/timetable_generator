"""Password rules, hashing, one-time passwords and the sign-in lockout."""
import collections, secrets, threading, time
from werkzeug.security import check_password_hash, generate_password_hash
import access

COMMON = frozenset({
    '0000000000', '0123456789', '0987654321', '1111111111', '1122334455',
    '11223344556', '1212121212', '123123123123', '1234512345', '123456123456',
    '1234567890', '123456789012', '1234567891', '12345678910', '1q2w3e4r5t',
    '1q2w3e4r5t6y', '1qaz2wsx3e', '1qaz2wsx3edc', '2222222222', '9876543210',
    'abc1234567', 'abc123456789', 'abcd123456', 'abcd1234567', 'abcdefghij',
    'abcdefghijk', 'admin12345', 'admin123456', 'administrator', 'administrator1',
    'asdfghjkl1', 'asdfghjkl123', 'asdfghjklqwe', 'baseball123', 'basketball1',
    'batman12345', 'changeme12', 'changeme123', 'changeme1234', 'chocolate1',
    'ctss123456', 'ctss1234567', 'dragon12345', 'football123', 'football1234',
    'google12345', 'ilovemyself', 'iloveyou12', 'iloveyou123', 'iloveyou123!',
    'iloveyou1234', 'jennifer123', 'jordan2345', 'letmein123', 'letmein1234',
    'letmein12345', 'master12345', 'michael123', 'minecraft1', 'minecraft12',
    'monkey12345', 'p@ssw0rd123', 'p@ssword123', 'passw0rd123', 'password1!',
    'password12', 'password123', 'password1234', 'password12345', 'password123456',
    'password1234567', 'pokemon123', 'princess123', 'princess1234', 'qwerty1234',
    'qwerty12345', 'qwerty123456', 'qwertyuiop', 'qwertyuiop1', 'qwertyuiop123',
    'school12345', 'schooldays1', 'shadow12345', 'singapore1', 'singapore12',
    'singapore123', 'singapore2024', 'singapore2025', 'singapore2026', 'starwars123',
    'sunshine123', 'sunshine1234', 'superman123', 'teacher1234', 'teacher12345',
    'timetable1', 'timetable12', 'timetable123', 'timetable1234', 'timetable2026',
    'trustno1234', 'welcome123', 'welcome1234', 'welcome12345', 'welcome2023',
    'welcome2024', 'welcome2025', 'welcome2026', 'zaq12wsxcde', 'zxcvbnm123',
    'zxcvbnm1234',
})

def _flat(s):
    return "".join(ch for ch in str(s or "").lower() if ch not in " .")

def problem(pw, username="", name=""):
    """-> the sentence to show, or None when the password is acceptable"""
    pw = str(pw or "")
    if len(pw) < 10: return "Use at least 10 characters."
    f = _flat(pw)
    if any(x and f == x for x in (_flat(username), _flat(name))): return "Don't use your username or your name."
    if pw.lower() in COMMON: return "That password is too common. Choose another."
    return None

def hash_pw(pw):
    return generate_password_hash(pw)

_DUMMY = generate_password_hash(secrets.token_hex(16))

def check_pw(hashed, pw):
    """with no stored hash it still does the same work, so timing does not show who has an account"""
    try: ok = check_password_hash(hashed if isinstance(hashed, str) and hashed else _DUMMY, str(pw or ""))
    except ValueError: return False
    return bool(ok and hashed)

def one_time():
    s = "".join(secrets.choice(access.ALPHABET) for _ in range(12))
    return "-".join(s[i:i + 4] for i in range(0, 12, 4))

class Lockout:
    """`n` wrong passwords within `window` seconds blocks that key until they age out; in memory"""
    def __init__(self, n=5, window=900):
        self.n, self.window, self.fails, self.lock = n, window, collections.defaultdict(collections.deque), threading.Lock()
    def _trim(self, key):
        q, now = self.fails[key], time.time()
        while q and now - q[0] > self.window: q.popleft()
        if not q: self.fails.pop(key, None)
        return q
    def blocked(self, key):
        with self.lock: return len(self._trim(key)) >= self.n
    def fail(self, key):
        with self.lock: self._trim(key); self.fails[key].append(time.time())
    def clear(self, key):
        with self.lock: self.fails.pop(key, None)

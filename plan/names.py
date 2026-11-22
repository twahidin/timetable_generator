"""Names to codes: what may be sent to the AI, and the names put back in what it says.

A teacher goes as a code ("T07"), several people who fit as "T03 or T11", a student as "a student", the school's name as "the
school". Words are compared in any case, with wide and joined letters as plain ones, no accents, every dash a hyphen and without
the characters nobody sees; letters and digits glued together are read apart, but a word of the timetable ("3A", "T02") stays whole.

FIRST, over the whole text, the whole stored names: every word of a name, in any order, with or without its title, across white
space, tabs and bars, lines, one hyphen, apostrophe, dot or underscore, brackets, quotes or asterisks, a footnote's digit or mark,
and one comma or semicolon. Of all ways to pick ones that do not overlap: the one that covers the most words, then the most that are
not protected, then the fewest names, then the leftmost. Nothing later undoes one in a list or in the app's words, whatever
number, date, subject or room is beside it: with a student Goh Jun "Mon 3 Jun Goh 8.00" is "Mon 3 a student 8.00", with a Mr Art Koh
"Sec 3 Art Koh" is "Sec 3 T05", and the row is asked about. A name with a comma in it gives way to names without one that hide
more, or as much (two matches, one on each side), unless it is a teacher's with one word on one side.

THEN, in the words left, from left to right and the longest first, where the text is from decides:
- everywhere: a title (TITLES) and words of one teacher's name, on one line and in one cell (a title is a teacher's: it is never part
  of a student's name); two or more words of one name side by side, in any order; a student's ID; a stored name of one word, as it
  is written or in capitals;
- "typed" (a person's own words): also the short name exactly as it is written, and one word that starts with a capital letter
  and is in a teacher's name (not one in capitals with a digit: "WA2");
- "app" (the app's own sentences and records): also the short name exactly as it is written;
- "list" (the agreed list): nothing more. Its single words and short names are left alone.
Any other place counts as "typed", which hides the most.

Never a code: a protected word on its own (a day or month, or a word of a level, class, subject, short subject, setup code or
room of the published timetable), or several that all are; a link of names (bin, s/o, and) or one letter on its own; small words
in small letters ("do an"); one letter glued to a digit (P3, T01); a unit after a number that is a length ("90 min"), not a level's
(Sec 3) or a paper's (P1). The words after the unit are, when it makes a whole name of three or more of them ("90 min Jun Tan"), and so
is the unit itself after the number of a line or cell, 1 to 45, when a whole name starts with it ("4 Min Thu").
No title: "teacher" and "sir" unless a word with a capital follows; "MISS" before a subject in capitals ("WILL MISS ART"); a
subject's code as it is written ("DR") unless a word follows that a teacher has and the timetable has not. Else a title makes a
person of a protected word ("Ms May").

PART of a name, in a list and in the app's words, never has a month or weekday bound to a day's number ("May 3"), and protected words
are cut from its ends: what is left must be two words, or have a title. So "Sec 3 Art Koh" and "on 3 May Lim" stay when the stored
names have more words. In typed words a protected word, or a small word in small letters, at either end of a match, of a whole
name too, stays out of it when it reads as something else and the rest is still a match: a verb ("Mdm Lim may be away"), a date ("Mdm
Lim May 3", "on 3 May Lim is away"), the next line or cell, a subject or room ("Mr Koh Art Room").

Who is meant when several fit: whoever has the title that is written ("Mr Tan"), then whoever has those words and no more, else
all of them; a teacher before a student. A student's ID is matched in any case: of six or more characters with letters and digits,
anywhere, glued or not; a shorter one on its own or glued to a name; with no letter and fewer than five digits only after "student",
"pupil" or "ID" (it could be a date, a time or a count); with no digit as it is written; never one that is a class, room or other
word of the timetable. A school's name of fewer than four letters is not hidden (the lead's ruling: it is too likely to be an
ordinary word). A name the app does not know (a misspelling, a visitor, given names run together, initials) goes as it is."""
import bisect, functools, re, unicodedata

from relief.pick import HONORIFICS
from ttgen.report import short_subject

TITLES = HONORIFICS + ("madam", "mister", "cikgu", "encik", "puan", "ustaz", "ustazah", "sir", "teacher", "prof", "professor")
STUDENT, SCHOOL = "a student", "the school"
_ALIKE = {"madam": "mdm", "mister": "mr", "professor": "prof"}          # one title, two ways to write it
_WORDS_TOO = ("teacher", "sir")                         # ordinary words too: a title only before a name word with a capital
_TITLES = frozenset(TITLES)
_DAYS = "monday tuesday wednesday thursday friday saturday sunday".split()
_MONTHS = "january february march april may june july august september october november december".split()
_DATES = frozenset(w for d in _DAYS + _MONTHS for w in (d, d[:3]))
_UNITS = frozenset("min mins hr hrs h sec secs".split())
_JOINERS = frozenset("bin binte binti bte bt s/o d/o a/l a/p and of the".split())        # in many names, and never a name
_SMALL = frozenset(("a an and are as at be but by can do for from go had has have he her him his i if in is it me my no not of "
                    "on or our she so that the them then they this to up us was we were will with you your").split())

_RUN = re.compile(r"(?<![^\W_])(?:[sd]/o|a/[lp])(?![^\W_])|[^\W_]+", re.I)
_PIECE = re.compile(r"\d+|[A-Za-z\u00c0-\u024f]+|[^\W\d_A-Za-z\u00c0-\u024f]+")          # digits, Latin letters, other letters
_DAY = re.compile(r"(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?|(?:19|20)\d\d")
_NTH = re.compile(r"\d{1,2}(?:st|nd|rd|th)", re.I)
_CODE = re.compile(r"(?<![^\W_])T\d{2,}(?![^\W_])")
_EDGE = re.compile(r"[|\t\n\r\v\f\x1c-\x1e\x85\u2028\u2029]|\s{3}")                     # between two cells or lines
_AFTER_ID = re.compile(r"[\s.:#]*")                     # between "student no" and the number
_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1b\x7f]")
_NONE, _SOFT, _CELL, _LINE, _COMMA = range(5)           # between two words: nothing that joins; a space or a mark; a tab or a wide space; a line break; a comma
_LINES = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"
_TIGHT = "-'\u2018\u2019`._"                            # with no space beside it: Wei-Ling, Nur'Aisyah, tan.wei.ling, tan_wei_ling
_APOSTROPHES = ("'", "\u2019")
_LIKE_ONE = "\u02b9\u02bb\u02bc\u02bd\u2032"            # signs written for an apostrophe
_COMMAS = "\u3001\u060c\uff64"
_MARKS = dict.fromkeys(map(ord, "()[]{}\"'*_^\u2018\u2019\u201c\u201d\u2020\u2021\u00a7\u00b6"))      # round a word of a name
_ROUND = re.compile("[][(){}\"'*_\u2018\u2019\u201c\u201d]")
_DASHES = "\u2043\u2212\u02d7"                          # dashes that Unicode does not call dashes
_BLANK = "\u115f\u1160\u2800"                           # letters and signs nobody sees


@functools.lru_cache(maxsize=4096)
def _form(c):
    """one character as it is compared: "" for an accent (it belongs to the letter before it), None for one nobody sees"""
    kind = unicodedata.category(c)
    if kind == "Cf" or kind == "Cc" and not c.isspace(): return None
    if kind == "Pd" or c in _DASHES: return "-"
    if c in _LIKE_ONE: return "'"
    if c in _COMMAS: return ","
    if unicodedata.decomposition(c).startswith(("<super>", "<sub>", "<circle>")): return "^"      # a footnote's mark
    out = "".join(x for x in unicodedata.normalize("NFKD", c) if unicodedata.category(x)[0] != "M")
    if out and all(x in _BLANK for x in out): return None
    return out if len(out) < 5 else "|"


def _fold(text):
    """(the text as it is compared, where each of its characters starts in the text, where each ends, the places of hidden
    characters): wide and joined forms as plain letters, no accents, every dash a "-", and nothing that nobody sees"""
    if text.isascii() and not _CONTROL.search(text): return text, None, None, ()
    out, first, last, hidden = [], [], [], []
    for i, c in enumerate(text):
        got = c if " " <= c < "\x7f" else _form(c)
        if got is None:
            if not hidden or hidden[-1] != len(out): hidden.append(len(out))
        elif got:
            for x in got: out.append(x); first.append(i); last.append(i + 1)
        elif last: last[-1] = i + 1
    return "".join(out), first, last, hidden


def _words_of(text):
    """the runs of letters and digits of a text, as they are compared"""
    return [w.casefold() for w in _RUN.findall(_fold(text)[0])]


def _space(g):
    if any(c in _LINES for c in g): return _LINE
    return _CELL if "\t" in g or len(g) > 2 else _SOFT


def _gap(g, before):
    """what the text g between two words is; before: the word before it"""
    if not g or len(g) == 1 and g in _TIGHT: return _SOFT
    if g.isspace(): return _space(g)
    if g[0] == "-" and g[1:].isspace() and _space(g[1:]) == _LINE: return _LINE          # Wei-Ling, cut at the hyphen
    rest = g.translate(_MARKS).replace("|", "\t")                                        # "(Alicia) Ng", "Ms *Tan*"; a bar is the edge of a cell
    if rest[:1] == "." and (before in _TITLES or len(before) == 1 and before.isalpha()): rest = rest[1:]      # "Ms. Tan", "S. Kumar"
    if not rest: return _SOFT
    if rest.isspace(): return _space(rest)
    return _COMMA if rest.strip() in (",", ";") else _NONE


class _Text:
    """a text's words (raw: as compared but in their own case; key: in small letters), where they are, and what is between them.
    A run of letters and digits is cut where one turns into the other, so that a digit glued to a name hides nothing, but a word
    of the timetable ("3A", "T02") stays whole, and a long ID is one word, with no key. A word with hidden characters in it can be
    read in two ways (Names._cut)"""

    def __init__(self, text, names, reading=0):
        self.text, self.levels = text, names._levels
        self.norm, self._first, self._last, hidden = _fold(text)
        self.hidden = len(hidden)
        self.raw, self.key, self.a, self.b = [], [], [], []
        at = 0
        for x, y in (*names._long_ids(self.norm), (len(self.norm), None)):
            for m in _RUN.finditer(self.norm, at, x):
                w = m.group()
                for a, b in [m.span()] if w.isascii() and (w.isalpha() or w.isdigit()) or "/" in w else names._pieces(w, m.start()):
                    inner = [h - a for h in hidden[bisect.bisect_right(hidden, a):bisect.bisect_left(hidden, b)]] if hidden else ()
                    was = a
                    for end in names._cut(self.norm[a:b], inner, reading) if inner else (b - a,):
                        self._add(was, a + end, self.norm[was:a + end].casefold())
                        was = a + end
            if y is not None: self._add(x, y, "")
            at = y
        self.n = n = len(self.raw)
        self.taken, self.counted = [False] * n, None      # the words in a whole name; the numbers after "student"
        self.gap = [_NONE] + [_gap(self.norm[self.b[j - 1]:self.a[j]], self.key[j - 1]) for j in range(1, n)]
        self.digit = digit = [r.isdecimal() for r in self.raw]
        self.off, self.unit, self.line = [False] * n, [False] * n, [False] * n
        for j in range(n):
            if self.key[j] in _UNITS and j and digit[j - 1] and self.near(j) and not self.level(j - 1) and not (j > 1 and self.glued(j - 1) and not self.unit[j - 2]):
                self.unit[j] = True              # a unit after a number, but not after a level's (Sec 3) or a paper's (P1)
                self.line[j] = len(self.raw[j - 1]) < 3 and 0 < int(self.raw[j - 1]) < 46 and (j == 1 or bool(_EDGE.search(self.norm[self.b[j - 2]:self.a[j - 1]])))      # the number of a line
            elif len(self.key[j]) == 1:          # one letter glued to a digit (P3, T01) is no word of a name
                self.off[j] = any(0 <= k < n and digit[k] and self.glued(max(j, k)) for k in (j - 1, j + 1))

    def _add(self, a, b, key): self.raw.append(self.norm[a:b]); self.key.append(key); self.a.append(a); self.b.append(b)

    def glued(self, j): return 0 < j < self.n and self.a[j] == self.b[j - 1]

    def start(self, j): return self._first[self.a[j]] if self._first is not None else self.a[j]

    def end(self, j): return self._last[self.b[j] - 1] if self._last is not None else self.b[j]

    def between(self, j): return " ".join(self.norm[self.b[j - 1]:self.a[j]].split())

    def small(self, j): return self.raw[j].islower()

    def sign(self, j):
        """is word j capitals with a digit glued after it: a paper ("WA2"), not a name alone"""
        return self.raw[j].isupper() and self.glued(j + 1) and self.digit[j + 1]

    def after(self, j):
        """(the next word, what is between them) after word j; digits glued to the end of j or to the next word are a footnote's, and
        are passed over, unless they are a date's or a length's"""
        k = j + 1
        if k + 1 < self.n and self.digit[k] and (self.glued(k) or self.glued(k + 1) and not self.dated(k + 1, -1) and not self.unit[k + 1]): return k + 1, self.gap[k + 1 if self.glued(k) else k]
        return k, self.gap[k] if k < self.n else _NONE

    def owns(self, j):
        """is word j the s of "Ms Tan's": no word of a name"""
        return self.key[j] == "s" and self.between(j)[-1:] in _APOSTROPHES

    def near(self, j):
        """is word j right after the word before it: glued, or with a space or hyphen between them, and no other mark"""
        return self.gap[j] == _SOFT and self.between(j) in ("", "-")

    def level(self, k):
        """is word k the number of a level: the 3 of "Sec 3" """
        return k > 0 and self.near(k) and (self.key[k - 1], self.key[k]) in self.levels

    def dated(self, j, step):
        """is word j a day or month with a day's number (or a year) right after it (step 1) or before it (-1), on the same line;
        the number of a level ("Sec 3") is not one"""
        k = j + step
        if self.key[j] not in _DATES or not 0 <= k < self.n or not self.near(max(j, k)) or not _DAY.fullmatch(self.key[k]): return False
        return step > 0 or not self.level(k)


def _list(x): return list(x) if hasattr(x, "__iter__") and not isinstance(x, (str, bytes, dict)) else []


def _dicts(x): return [d for d in _list(x) if isinstance(d, dict)]


def _dict(x): return x if isinstance(x, dict) else {}


def _model(pub): return _dict(_dict(pub).get("model"))


def _levels(pub):
    m = _model(pub)
    out = _list(m.get("levels")) + _list(_dict(_dict(m.get("setup")).get("school")).get("levels"))
    out += [x.get("level") for k in ("classes", "lessons") for x in _dicts(m.get(k))]
    return out + [c.get("level") for c in _dicts(_dict(m.get("setup")).get("classes"))]


def _subjects(pub):
    """the subjects of the published timetable: full, short and setup code, as they are written"""
    m = _model(pub)
    out, names = [], {str(x.get("subject") or "") for x in _dicts(m.get("lessons")) + _dicts(_dict(m.get("setup")).get("subjects"))}
    for s, v in _dict(m.get("subjects")).items(): names.add(str(s or "")); out.append(_dict(v).get("short"))
    for s in _dicts(_dict(m.get("setup")).get("subjects")): out.append(s.get("code"))
    for s in names: out += [s, short_subject(s)]
    return [str(x) for x in out if x not in (None, "")]


def _strings(pub):
    """the levels, classes, subjects and rooms of the published timetable, as they are written"""
    m = _model(pub)
    setup, out = _dict(m.get("setup")), _levels(pub) + _subjects(pub)
    for c in _dicts(m.get("classes")): out += [c.get("name"), c.get("home")]
    for c in _dicts(setup.get("classes")): out += [c.get("class"), c.get("home_room")]
    for x in _dicts(m.get("lessons")): out += [x.get("room"), x.get("rain"), *_list(x.get("classes"))]
    for r in _dicts(m.get("rooms")): out += [r.get("name"), *_list(r.get("parts"))]
    for r, parts in _dict(m.get("room_parts")).items(): out += [r, *_list(parts)]
    for v in _dicts(setup.get("venues")): out.append(v.get("room"))
    return [str(x) for x in out if x not in (None, "")]


def protected(pub):
    """the words that are never made a code on their own, casefolded: the days and months and their three letters, and every
    word of the published timetable's levels, classes, subjects, short subjects, setup codes and rooms. A title is not one,
    whatever a room is called: "Mdm Lim" stays a person"""
    strings = _strings(pub)
    return frozenset(w for s in strings for w in _words_of(s) + [x.casefold() for x in _RUN.findall(s)]) - _TITLES | _DATES


def _bits(mask):
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def _tidy(text, at, start, end):
    """where a match from start to end starts and ends, with the bracket, quote or asterisk that goes with one inside it"""
    inner = text[start:end]
    if not _ROUND.search(inner): return start, end
    for a, b in ("()", "[]", "{}", "\u201c\u201d"):
        if inner.count(b) > inner.count(a) and start > at and text[start - 1] == a: start -= 1
        if inner.count(a) > inner.count(b) and text[end:end + 1] == b: end += 1
    for q in "\"*_":
        k = inner.count(q)
        while k and start > at and text[start - 1] == q: start -= 1; k -= 1
        while k and text[end:end + 1] == q: end += 1; k -= 1
    for a, b in ("''", "\u2018\u2019"):
        if b + " " in inner and start > at and text[start - 1] == a: start -= 1
        if " " + a in inner and text[end:end + 1] == b: end += 1
    return start, end


class Names:
    """the codes of one talk. pub: the published timetable (or None); people: accounts.people.listing(pub); students:
    model["students"]. Codes are T01, T02, ... in order of the names, less a number that is a word of the timetable, a group,
    a short name or an ID. Everything is worked out here, so out is one pass over the text"""

    def __init__(self, pub, people, students):
        strings, model, setup = _strings(pub), _model(pub), _dict(_model(pub).get("setup"))
        self._prot = frozenset(x for w in protected(pub) for x in _words_of(w))
        self._widest = max((len(w) for w in self._prot), default=0)
        self._levels = {tuple(_words_of(str(s))) for s in _levels(pub) if len(_words_of(str(s))) == 2}
        self._signs = {_fold(str(s.get("code")))[0].strip() for s in _dicts(setup.get("subjects")) if s.get("code")}       # subject codes, as they are written
        self._subjects = {w for x in _subjects(pub) for w in _words_of(x)}
        self._known, self._heads, self._deep = None, set(), {}      # every word of a name; what an ID may start with before its first digit; the long IDs, by their first six characters
        short = {}
        for p in _dicts(people):
            name = str(p.get("name") or "").strip()
            if name: short.setdefault(name, str(p.get("short") or "").strip())
        kids = [(str(x.get("id") if x.get("id") is not None else "").strip(), str(x.get("name") or "").strip()) for x in _dicts(students)]
        self._people = sorted(short, key=lambda n: (n.casefold(), n))
        groups = [str(x.get(k) or "") for x in _dicts(model.get("lessons")) for k in ("group", "block")]
        taken = self._prot.union(w for s in groups + list(short.values()) + [i for i, _ in kids] for w in _words_of(s))
        self._codes, n = [], 0
        for _ in self._people:
            n += 1
            while f"t{n:02d}" in taken: n += 1
            self._codes.append(f"T{n:02d}")
        self._code = dict(zip(self._people, self._codes))
        self._who_is = dict(zip(self._codes, self._people))
        self._place = {" ".join(n.split()): i for i, n in enumerate(self._people)}

        # every person is one bit, the teachers first; a mask is a set of people
        self._teachers = (1 << len(self._people)) - 1
        self._all = (1 << (len(self._people) + len(kids))) - 1
        self._has = {}           # (word, 1st, 2nd ... of it in the name) -> who has it
        self._order = {}         # person -> the words of the name in order
        self._long = {}          # number of words -> whose whole name is that many
        self._titled = {"": 0}   # title -> who has it ("": who has none in front)
        self._ones = {}          # a name of one word -> [(as written, person's mask)]
        self._tree = {}          # the full names as stored, word by word: word -> (next, marks between); None -> mask
        self._schools = {}       # the same, for the school's names
        for i, name in enumerate(self._people + [n for _, n in kids]): self._learn(i, name)
        self._known = {k for k, _ in self._has} | _TITLES

        wholes = {" ".join(_fold(s)[0].split()).casefold() for s in strings}
        self._shorts, self._longest = {}, 0
        self._ids, self._bare, self._written = set(), set(), set()      # IDs: in any case; that could be a date; with no digit, as they are written
        for i, name in enumerate(self._people):
            t = _Text(short[name], self)
            if not t.n or short[name] == name or all(w in self._prot for w in t.key): continue
            if t.n == 1 and (len(t.key[0]) == 1 or t.key[0] in _SMALL and not t.raw[0].isupper()): continue       # "S", "On"
            s = self._cell(t, 0, t.n)
            self._shorts[s] = self._shorts.get(s, 0) | 1 << i
            self._longest = max(self._longest, t.n)
        deep = set()
        for sid, _ in kids:
            t = _Text(sid, self)
            if not t.n: continue
            s = self._cell(t, 0, t.n)
            digits, letters = sum(c.isdecimal() for c in s), any(c.isalpha() for c in s)
            if s.casefold() in wholes or t.n == 1 and (t.key[0] in self._prot or not digits and self._plain(t.key[0])): continue
            if not digits: self._written.add(s)
            elif digits < 5 and not letters: self._bare.add(s)
            elif letters and len(s) > 5: deep.add(s.lower()); continue
            else: self._ids.add(s.casefold()); self._heads.add(re.match(r"\D*", s.casefold()).group())
            self._longest = max(self._longest, t.n)
        for s in (_dict(_dict(pub).get("meta")).get("school"), _dict(model.get("school")).get("name")):
            s = str(s or "").strip()
            if sum(c.isalpha() for c in s) >= 4 and s.casefold() != "school":        # "School" is what a setup with no name has
                self._plant(self._schools, _Text(s, self), 0, 1)
        self._firsts = {_Text(s, self).key[0] for s in (*self._shorts, *self._ids, *self._bare, *self._written)}       # the first words of short names and IDs
        for s in sorted(deep, key=len, reverse=True): self._deep.setdefault(s[:6], []).append(s)

    # ------------------------------------------------------------------------------------------------ the tables
    @staticmethod
    def _cell(t, i, e): return " ".join(t.norm[t.a[i]:t.b[e - 1]].split())

    @staticmethod
    def _plant(tree, t, first, mask):
        if first >= t.n: return
        node = tree
        for j in range(first, t.n):
            step = node.setdefault(t.key[j], ({}, set()))
            if j > first: step[1].add(t.between(j))
            node = step[0]
        node[None] = node.get(None, 0) | mask

    def _learn(self, i, name):
        t, me, first = _Text(name, self), 1 << i, 0
        for k in t.key:
            if k in _TITLES: self._titled[_ALIKE.get(k, k)] = self._titled.get(_ALIKE.get(k, k), 0) | me
        while first < t.n and t.key[first] in _TITLES: first += 1
        if not first: self._titled[""] |= me
        body = range(first, t.n)
        words = [t.key[j] for j in body if t.key[j] not in _TITLES and not any(c.isdigit() for c in t.key[j])]
        self._order[i] = words
        if not words: return                                             # no letters, or a title alone: nobody's name
        if len(body) == 1: self._ones.setdefault(words[0], []).append((t.raw[first], me))
        elif len(words) < len(body) or any(t.gap[j] == _NONE for j in body[1:]): self._plant(self._tree, t, first, me)        # what a run of words cannot find
        if all(t.key[j] in _TITLES or t.key[j] in words for j in body): self._long[len(words)] = self._long.get(len(words), 0) | me
        for j, k in enumerate(words):
            at = (k, words[:j + 1].count(k))
            self._has[at] = self._has.get(at, 0) | me

    def _long_ids(self, norm):
        """[(start, end)] of the IDs of six or more characters, letters and digits, wherever they are, glued or not"""
        out, at = [], 0
        low = "".join(c.lower() if len(c.lower()) == 1 else c for c in norm) if self._deep else ""
        while at < len(low) - 5:
            got = next((len(s) for s in self._deep.get(low[at:at + 6], ()) if low.startswith(s, at)), 0)
            if got: out.append((at, at + got))
            at += got or 1
        return out

    def _pieces(self, w, at):
        """[(start, end)] of the pieces of a run of letters and digits w, at a place in the text: whole when it is a word of the
        timetable or "3rd", else cut where letters turn into digits; what is left of it may be such a word ("Tan3A"), and the last
        letters before digits may be the start of an ID after a name ("NgS101")"""
        out, a, n = [], 0, len(w)
        while a < n:
            if n - a <= self._widest and (w[a:].casefold() in self._prot or _NTH.fullmatch(w, a)): out.append((at + a, at + n)); break
            b = _PIECE.match(w, a).end()
            if self._known and b < n and w[b].isdecimal() and w[a:b].casefold() not in self._known:
                b = next((b - k for k in (1, 2, 3) if b - k - a > 1 and w[a:b - k].casefold() in self._known and w[b - k:b].casefold() in self._heads), b)
            out.append((at + a, at + b)); a = b
        return out

    def _cut(self, word, inner, reading):
        """where to cut a word with hidden characters at inner. Reading 0: into the fewest words of names (itself, when it is one), else
        nowhere; 1: into the most words of names, else at all of them"""
        low, at = word.casefold(), [0, *inner, len(word)]
        if self._known is None: return (len(word),)
        best = [()] + [None] * (len(at) - 1)
        for j in range(1, len(at) if len(at) < 20 and len(low) == len(word) else 0):
            ways = [best[i] + (at[j],) for i in range(j) if best[i] is not None and low[at[i]:at[j]] in self._known]
            best[j] = max(ways[::-1], key=len, default=None) if reading else min(ways, key=len, default=None)
        return best[-1] or (tuple(at[1:]) if reading else (len(word),))

    # ------------------------------------------------------------------------------------------------ what a word can be
    def _plain(self, word): return word in self._prot or word in _SMALL or len(word) == 1

    def _verb(self, t, j, beside):
        """is word j an ordinary word in small letters beside a word that is not: "Lim may be away", "Ask Kumar a question" """
        return t.small(j) and not t.small(beside) and self._plain(t.key[j])

    def _apart(self, t, s, j):
        """is word s no part of a name that goes on at word j: "may Lim come", "on 3 May long papers are" """
        return self._verb(t, s, j) or t.dated(s, -1) and t.small(j) and not t.small(s)

    def _title(self, t, i):
        """(the word after the titles at word i, them), or (i, None). A title is on the line and in the cell of its name. "MISS" is
        not one before a word of a subject in capitals; a subject's code, as it is written ("DR"), only before a word that a teacher
        has and the timetable has not; "teacher" and "sir" only before a word with a capital"""
        s, got = i, []
        while len(got) < 3 and s + 1 < t.n and t.key[s] in _TITLES and t.gap[s + 1] == _SOFT:
            raw, word = t.raw[s], t.key[s + 1]
            if raw == "MISS" and t.raw[s + 1].isupper() and word in self._subjects: break
            if raw in self._signs and word in self._prot: break
            if t.key[s] in _WORDS_TOO and (not t.raw[s + 1][:1].isupper() or t.between(s + 1) not in ("", ".")): break
            got.append(t.key[s]); s += 1
            if got[-1] in _WORDS_TOO: break
        return (s, got) if got else (i, None)

    def _by_title(self, mask, title):
        same = 0
        for k in title: same |= self._titled.get(_ALIKE.get(k, k), 0)
        return mask & same or mask

    def _loose_end(self, t, words, mask):
        """in typed words: may the last word of a match be something else: in another cell or line, a date, a verb, or (when it
        does not follow the word before it in any of the names the match fits) the start of a subject or room"""
        j, before = words[-1], words[-2] if len(words) > 1 else words[0] - 1
        if t.key[j] not in self._prot and not (t.small(j) and self._plain(t.key[j])): return False
        if t.gap[j] != _SOFT or t.dated(j, 1) or self._verb(t, j, before): return True
        if not t.small(j) and not (j + 1 < t.n and t.gap[j + 1] == _SOFT and t.key[j + 1] in self._prot - _SMALL): return False
        return not any(pair == (t.key[before], t.key[j]) for i in _bits(mask) for pair in zip(self._order[i], self._order[i][1:]))

    def _loose_start(self, t, words):
        """the same of the first word, with no title"""
        s, j = words[0], words[1]
        return t.key[s] in self._prot and (t.gap[j] != _SOFT or t.dated(s, -1)) or self._verb(t, s, j)

    def _who(self, t, words, mask, title, where):
        """the people (of mask, who have all these words in their name) the words stand for after the title, or 0; of two or more
        words, of one after a title, or of one that is enough on its own. A title is a teacher's"""
        keys, teachers, k = [t.key[j] for j in words], mask & self._teachers, len(words)
        if title:
            s = words[0]
            verb, word = title == ["miss"] and t.small(s - 1), title[-1] in _WORDS_TOO                      # "they will miss Art"
            if all(self._plain(w) for w in keys) and (verb or self._verb(t, s, s - 1) or word and self._loose_end(t, words, mask)): return 0      # or "Miss a lesson"
            pool = self._by_title(teachers, title)
            return pool & self._long.get(k, 0) or pool
        if self._nobody(t, words): return 0
        if k > 1: return mask
        raw, one = t.raw[words[0]], 0
        if t.sign(words[0]): return 0
        for written, person in self._ones.get(keys[0], ()):
            if raw == written or raw.isupper() and len(raw) > 1: one |= person
        pool = teachers if one & self._teachers or where == "typed" and raw[:1].isupper() else 0
        return pool & one & self._titled[""] or pool or one

    def _nobody(self, t, words):
        """with no title: all the words are protected, or links of names, or one letter, or small words in small letters ("do an")"""
        keys = [t.key[j] for j in words]
        return (all(w in self._prot for w in keys) or all(w in _JOINERS or len(w) == 1 for w in keys)
                or all(self._plain(w) for w in keys) and all(t.small(j) for j in words))

    # ------------------------------------------------------------------------------------------------ whole names, over the whole text
    def _whole(self, t, s, title, where):
        """[(where it starts, its end, how many words, what it weighs, who)] of the whole stored names of two or more words from word
        s, in any order. From a unit after a number: the words after it, when the unit makes a name of three or more of them; with
        the unit when the number is a line's and the name starts with it as it is stored. In typed words, without the first or last
        word when it reads as something else. A name weighs its words; one with a comma in it less than nothing, unless it is a
        teacher's with one word on one side; one word that is left of it nothing: it is kept for later"""
        out, words, mask, seen, j, comma = [], [], self._all, {}, s, 0
        while j < t.n and not t.off[j]:
            k = t.key[j]
            seen[k] = seen.get(k, 0) + 1
            mask &= self._has.get((k, seen[k]), 0)
            if not mask: break
            words.append(j)
            n = len(words)
            full = mask & self._long.get(n, 0) if n > 1 else 0
            if full and t.unit[s]:
                same = sum(1 << i for i in _bits(full) if self._order[i] == [t.key[w] for w in words]) if t.line[s] else 0
                if same: out.append((s, j + 1, n, n, same))
                if n > 2: out.append((words[1], j + 1, n - 1, n - 1, full))
            elif full:
                heavy = full & self._teachers and (comma == 1 and not title and not self._past(t, s - 1, s, where) or n - comma == 1 and not self._past(t, j, j + 1, where))
                rest, who = self._stands(t, words, mask, full, title, where)
                if who: out.append((rest[0], rest[-1] + 1, n, 0 if len(rest) == 1 else n if heavy or not comma else -1, who))
            j, g = t.after(j)
            if j >= t.n or t.owns(j) or g == _NONE or g != _SOFT and t.unit[s] or g == _COMMA and comma: break
            if g == _COMMA: comma = n
        return out

    def _past(self, t, s, e, where):
        """does part of a name start at word s and go past word e"""
        got = self._part(t, s, None, where, False) if s >= 0 else None
        return bool(got) and got[0] > e

    def _stands(self, t, words, mask, full, title, where):
        """(the words of a whole name that are taken as it, who it is: 0 when it is not taken): nobody's, and a student's after a
        teacher's title, are not; in typed words what reads as something else is left out when the rest is a match"""
        who = full & self._teachers or mask & self._teachers                     # part of a teacher's name goes before a student's whole one
        if not title and self._nobody(t, words): return words, 0
        if title and (not who or any(t.gap[j] in (_CELL, _LINE) for j in words[1:])):
            got = self._part(t, words[0], title, where, False)                   # a title and its name are in one cell: what is in another must be more than a month
            if got and (not who or all(t.key[j] in self._prot for j in words if j >= got[0])): return words, 0
        rest = words
        if where == "typed":
            while len(rest) > 1 and self._loose_end(t, rest, mask): rest = rest[:-1]
            if len(rest) > 1 and not title and self._loose_start(t, rest): rest = rest[1:]
        if rest != words:
            got = self._who(t, rest, self._those(t, rest), title, where)
            if got: return rest, got
        if not who: return words, full
        return words, who if title else who & self._titled[""] or who            # the title is seen to in _pass

    def _those(self, t, words):
        """who has all these words"""
        mask, seen = self._all, {}
        for j in words:
            seen[t.key[j]] = seen.get(t.key[j], 0) + 1
            mask &= self._has.get((t.key[j], seen[t.key[j]]), 0)
        return mask

    def _walk(self, tree, t, s):
        """[(end, mask)] of the names in tree from word s, as they are stored, with their own marks"""
        node, j, out = tree, s, []
        while j < t.n:
            step = node.get(t.key[j])
            if step is None or j > s and t.gap[j] in (_NONE, _COMMA) and t.between(j) not in step[1]: break
            node = step[0]; j += 1
            if None in node: out.append((j, node[None]))
        return out

    def _wholes(self, t, where, titles):
        """{word: (end, who)} of the whole names in the text (who is None: the school's): of all ways to pick ones that do not
        overlap, the one that covers the most words, then the most that are not protected, then the fewest names, then the leftmost.
        A name with a comma in it gives way to parts of names that cover more, or (unless it is a teacher's, with one word on one
        side) as much"""
        found, plain, commas = [[] for _ in range(t.n)], [False] * t.n, False       # (end, how many words, what they weigh, who); in a whole name with no comma
        for s in range(t.n):
            title = titles.get(s)
            here = self._whole(t, s, title, where) if (t.key[s], 1) in self._has else []
            for e, mask in self._walk(self._tree, t, s) if not t.unit[s] else ():
                who = mask & self._teachers
                if not title and all(w in self._prot for w in t.key[s:e]) or title and not who and self._part(t, s, title, where, False): continue
                here.append((s, e, e - s, e - s, who if title else who & self._titled[""] or who))
            here += [(s, e, e - s, e - s, None) for e, _ in self._walk(self._schools, t, s)]
            for at, e, n, weight, who in here:
                found[at].append((e, n, weight, who))
                if any(t.gap[j] == _COMMA for j in range(at + 1, e)): commas = True
                else: plain[at:e] = [True] * (e - at)
        for s in range(t.n) if commas else ():
            got = self._part(t, s, titles.get(s), where, False)
            if got and not any(plain[s:got[0]]): found[s].append((got[0], got[0] - s, 0, 0))
        best, take = [(0, 0, 0, 0)] * (t.n + 1), [None] * t.n
        for s in range(t.n - 1, -1, -1):
            best[s] = best[s + 1]
            for e, n, weight, who in found[s]:
                v = (best[e][0] + n, best[e][1] + sum(k not in self._prot for k in t.key[s:e]), best[e][2] + weight, best[e][3] - 1)
                if v >= best[s]: best[s], take[s] = v, (e, weight, who)
        out, s = {}, 0
        while s < t.n:
            e, weight, who = take[s] or (s + 1, 0, 0)
            if weight:
                out[s] = e, who
                t.taken[s:e] = [True] * (e - s)
            s = e
        return out

    # ------------------------------------------------------------------------------------------------ what is left
    def _part(self, t, s, title, where, commas=True):
        """(end, who) of the longest run of words of one name at word s, or None; after a title, of a teacher's. In a list and in the
        app's words a day or month bound to a day's number after it is not in it, and protected words are cut from its ends"""
        words, masks, mask, seen, j, comma = [], [], self._teachers if title else self._all, {}, s, 0
        while j < t.n and not (t.off[j] or t.unit[j] or t.taken[j]):
            k = t.key[j]
            if where != "typed" and t.dated(j, 1) and not (title and j == s and self._by_title(self._long.get(1, 0), title) & self._has.get((k, 1), 0)): break
            seen[k] = seen.get(k, 0) + 1
            mask &= self._has.get((k, seen[k]), 0)
            if not mask: break
            words.append(j); masks.append(mask)
            n, g = t.after(j)
            if n >= t.n or not title and len(words) == 1 and self._apart(t, s, n) or t.owns(n): break
            if g == _COMMA:
                if comma or not commas: break
                comma = len(words)
            elif g == _NONE or title and g != _SOFT: break
            elif g != _SOFT and (t.key[j] in self._prot or t.key[n] in self._prot): break          # a month in another cell or line
            j = n
        if not words: return None
        while len(words) > 1 and self._verb(t, words[-1], words[-2]): words.pop(); masks.pop()          # "Lim may be away"
        if where != "typed":
            if not title and t.key[s] in self._prot and len(words) > 1: return None
            while len(words) > 1 and t.key[words[-1]] in self._prot: words.pop(); masks.pop()
        who = self._who(t, words, masks[-1], title, where)
        if where == "typed":
            while who and len(words) > 1 and self._loose_end(t, words, masks[-1]):
                rest = self._who(t, words[:-1], masks[-2], title, where)
                if not rest: break
                words.pop(); masks.pop(); who = rest
            if who and not title and len(words) > 1 and self._loose_start(t, words) and self._part(t, words[1], None, where): return None
        if who and comma and len(words) > comma:                                 # a match on each side of the comma
            before = self._part(t, s, title, where, False)
            if before and self._part(t, words[comma], None, where, False): return before
        return (words[-1] + 1, who) if who else None

    def _exact(self, t, i, where):
        """[(end, order on a tie, who)] of the short names and the shorter IDs at word i. A short name is a run of letters and digits
        of its own; an ID may be followed at once by letters, not by a digit"""
        out = []
        for e in range(min(i + self._longest, t.n), i, -1):
            if t.taken[e - 1]: continue
            s = self._cell(t, i, e)
            if where != "list" and s in self._shorts and not t.glued(e) and not t.off[i] and not t.unit[i] and not (s in ("AM", "PM") and i and t.digit[i - 1]): out.append((e, 3, self._shorts[s]))
            if s.casefold() in self._ids or s in self._written: ok = not (t.glued(e) and t.digit[e]) and (not t.glued(i) or t.digit[i - 1] or len(t.key[i - 1]) != 1 and (t.key[i - 1] in self._known or not t.key[i - 1]))
            else: ok = s in self._bare and self._counted(t)[i]
            if ok: out.append((e, 1, 0))
        return out

    def _counted(self, t):
        """which numbers come after "student", "pupil" or "ID", or after another one that does: "student no.: 12", "students 12 and 14" """
        if t.counted is None:
            t.counted = out = [False] * t.n
            for j in range(1, t.n):
                if not t.digit[j]: continue
                k, mark = j - 1, t.norm[t.b[j - 1]:t.a[j]]
                if t.key[k] in ("and", "or") and k: out[j] = out[k - 1]
                elif t.digit[k]: out[j] = out[k] and mark.strip() in (",", ";", "&", "/", "+")
                else:
                    if t.key[k] in ("no", "nos", "number", "numbers") and k and t.gap[k] == _SOFT: k -= 1
                    out[j] = t.key[k] in ("student", "students", "pupil", "pupils", "id", "ids") and bool(_AFTER_ID.fullmatch(mark))
        return t.counted

    def _match(self, t, i, s, title, where):
        """(end, who: 0 is a student) of the longest match at word i, where the words after its titles start at word s, or None"""
        found = self._exact(t, i, where) if t.key[i] in self._firsts else []          # (end, order on a tie, who)
        got = self._part(t, s, title, where) if title or (t.key[i], 1) in self._has else None
        if got: found.append((got[0], 2, got[1]))
        if not found: return None
        e, _, who = max(found, key=lambda x: x[:2])
        return e, who

    def _label(self, who, raw):
        who &= self._teachers
        if not who: return STUDENT
        me = self._place.get(" ".join(raw.split()), -1)                         # two names with the same words: as it is stored
        if me >= 0 and who >> me & 1: return self._codes[me]
        return " or ".join(self._codes[i] for i in _bits(who))

    # ------------------------------------------------------------------------------------------------ what is called
    def out(self, text, where):
        """text with every known name made a code, "a student" or "the school"; where is "typed", "list" or "app" (see the top
        of the file). Anything that is not a string is given back as it is"""
        if not isinstance(text, str): return text
        if where not in ("list", "app"): where = "typed"
        t = _Text(text, self)
        got = self._pass(t, where)
        if not t.hidden: return got
        got = self._pass(_Text(got, self, 1), where)                 # a hidden character is inside a word, or between two: in either order
        if t.hidden > 99: return got
        return min(got, self._pass(_Text(self._pass(_Text(text, self, 1), where), self), where), key=self._left)

    def _left(self, text):
        """(how many words of names, how many words) are left in a text with hidden characters, however they are read"""
        text, n, words = _CODE.sub(" ", text.replace(STUDENT, " ").replace(SCHOOL, " ")), 0, 0
        for t in (_Text(text, self), _Text(text, self, 1)):
            n += sum(k in self._known and k not in _TITLES and not self._plain(k) for k in t.key)
            words += t.n
        return n, words

    def _pass(self, t, where):
        """t's text with the names in it replaced"""
        heads, titles = {}, {}                   # a title -> (the word after it and the titles that follow it, them); that word -> them
        for i in range(t.n):
            if t.key[i] in _TITLES:
                s, title = self._title(t, i)
                if title: heads[i] = s, title; titles.setdefault(s, title)
        wholes = self._wholes(t, where, titles)
        text, parts, at, i = t.text, [], 0, 0
        while i < t.n:
            s, title = heads.get(i, (i, None))
            got = None
            if i + 1 in wholes and t.gap[i + 1] == _SOFT and t.key[i] in _TITLES and not title: s, title = i + 1, [t.key[i]]       # "MISS ART KOH": only the title as it is stored
            if s in wholes:
                e, who = wholes[s]
                if not title: got = e, who
                elif who and who & self._teachers and (i in heads or who & self._titled.get(_ALIKE.get(title[0], title[0]), 0)): got = e, self._by_title(who & self._teachers, title)
            elif t.key[i] == "the" and i + 1 in wholes and wholes[i + 1][1] is None and t.gap[i + 1] in (_SOFT, _LINE): got = wholes[i + 1]
            elif not t.key[i]: got = i + 1, 0
            else: got = self._match(t, i, s, title, where)
            if not got: i += 1; continue
            e, who = got
            start, end = _tidy(text, at, t.start(i), t.end(e - 1))
            label = SCHOOL if who is None else self._label(who, text[start:end])
            before = text[at:start] or (parts[-1] if parts else "")
            parts += [text[at:start], " " if before[-1:].isalnum() else "", label, " " if text[end:end + 1].isalnum() else ""]
            at, i = end, e
        return "".join(parts) + text[at:]

    def back(self, text):
        """text with every code made the name as it is stored; a code nobody has, or one beside a letter or digit, is left"""
        return _CODE.sub(lambda m: self._who_is.get(m.group(), m.group()), text) if isinstance(text, str) else text

    def scrub(self, obj, where="app"):
        """a copy of obj with out on every string in it: dict values (keys are never changed, so never use a name as a key),
        lists and tuples, to any depth. Numbers, True, False and None pass; anything else is refused, so that nothing goes out
        unread"""
        if isinstance(obj, str): return self.out(obj, where)
        if obj is None or isinstance(obj, (bool, int, float)): return obj
        if isinstance(obj, dict): return {k: self.scrub(v, where) for k, v in obj.items()}
        if isinstance(obj, list): return [self.scrub(v, where) for v in obj]
        if isinstance(obj, tuple): return tuple(self.scrub(v, where) for v in obj)
        raise TypeError(f"cannot be sent: {type(obj).__name__}")

    def code(self, name):
        """the code of a person on the listing, by the name as it is stored; KeyError for anyone else"""
        return self._code[name]

    def known_codes(self):
        """every code that stands for somebody"""
        return frozenset(self._who_is)

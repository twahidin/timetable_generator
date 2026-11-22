"""Names to codes: what may be sent to the AI, and the names put back in what it says.

A teacher goes as a code ("T07"), several people who fit as "T03 or T11", a student as "a student", the school's name as "the
school". A text is read from left to right; at each word the longest match is taken, and matches never overlap. Words are
compared in any case, with wide and joined letters as plain ones, no accents, every dash a hyphen and without the characters
nobody sees; letters and digits glued together are read apart, but a word of the timetable ("3A", "T02") stays whole. What is a
match depends on where the text is from:
- everywhere: a WHOLE stored name, every word of it, in any order, with or without its title; a title (TITLES) and one or more
  words of one teacher's name, on one line and in one cell; two or more words of one teacher's or one student's name side by
  side, in any order; a student's ID; a stored name of one word, as it is written or in capitals; the school's name;
- "typed" (a person's own words): also the short name exactly as it is written, and one word that starts with a capital letter
  and is in a teacher's name (not one in capitals with a digit: "WA2");
- "app" (the app's own sentences and records): also the short name exactly as it is written;
- "list" (the agreed list): nothing more. Its single words and short names are left alone.
Any other place counts as "typed", which hides the most. Words are side by side across white space, with one hyphen, apostrophe,
dot or underscore between them, with brackets, quotes or asterisks round them, with a footnote's digit or mark glued on, and
across one comma (but not when the words on each side of it are a match of their own, unless they make one teacher's whole name).

Never a code: a protected word on its own (a day or month, or a word of a level, class, subject, short subject, setup code or
room of the published timetable), or several that all are; a link of names (bin, s/o, and) or one letter on its own; small words
in small letters ("do an"); one letter glued to a digit (P3, T01); a unit after a number ("90 min"), unless it is in a whole name
of three or more words ("1 Min Jun Tan" in a numbered class list). No title: "teacher" and "sir" unless a word with a capital
follows; a subject's code as it is written ("DR"); one in capitals before a protected word in capitals ("WILL MISS ART"). A title
makes a person of a protected word ("Ms May").

In a list and in the app's words a month or weekday bound to a day's number ("Mon 3 Jun", "May 3") never joins PART of a name, and
protected words are cut from the ends of part of a name: what is left must be two words, or have a title. So "Sec 3 Art Koh" and
"on 3 May Lim" stay when the stored names have more words. A WHOLE stored name always goes, across wide spaces, tabs, lines and
one comma too, and wins over a date or a subject: with a Mr Art Koh, "Sec 3 Art Koh" is "Sec 3 T05", and the row is asked about.
KNOWN LIMIT: a student's whole name of exactly two words, one of them a month or weekday, straight after a day's number ("Mon 3 Jun
Goh 8.00" for a student Goh Jun) reads as a date and a surname, and stays.
In typed words a protected word, or a small word in small letters, at either end of a match stays out of it when it reads as
something else and the rest is still a match: a verb ("Mdm Lim may be away"), a date ("Mdm Lim May 3", "on 3 May Lim is away"), the
next line or cell, a subject or room ("Mr Koh Art Room"). Whatever is left beside a code is never a word that only a name has.

Who is meant when several fit: whoever has the title that is written ("Mr Tan"), then whoever has those words and no more, else
all of them; a teacher before a student. A student's ID is matched in any case; one with no letter and fewer than five digits
could be a date, a time or a count, so it is one only right after "student", "pupil" or "ID" (with "no." or "#" or not); one with
no digit is matched as it is written; one that is a class, room or other word of the timetable is not matched. A school's name of
fewer than four letters is not hidden (the lead's ruling: it is too likely to be an ordinary word). A name the app does not know
(a misspelling, a visitor, given names run together, initials) goes as it is."""
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
    rest = g.translate(_MARKS)                                                           # "(Alicia) Ng", "Ms *Tan*"
    if rest[:1] == "." and (before in _TITLES or len(before) == 1): rest = rest[1:]      # "Ms. Tan", "S. Kumar"
    if not rest: return _SOFT
    if rest.isspace(): return _space(rest)
    return _COMMA if rest.strip() == "," else _NONE


class _Text:
    """a text's words (raw: as compared but in their own case; key: in small letters), where they are, and what is between them.
    A run of letters and digits is cut where one turns into the other, so that a digit glued to a name hides nothing, but a word
    of the timetable ("3A", "T02") stays whole. A word with hidden characters in it can be read in two ways (Names._cut)"""

    def __init__(self, text, names, reading=0):
        self.text, self.levels = text, names._levels
        self.norm, self._first, self._last, hidden = _fold(text)
        self.hidden = len(hidden)
        self.raw, self.key, self.a, self.b = [], [], [], []
        for m in _RUN.finditer(self.norm):
            w = m.group()
            for a, b in [m.span()] if w.isascii() and (w.isalpha() or w.isdigit()) or "/" in w else names._pieces(w, m.start()):
                inner = [h - a for h in hidden[bisect.bisect_right(hidden, a):bisect.bisect_left(hidden, b)]] if hidden else ()
                was = a
                for end in names._cut(self.norm[a:b], inner, reading) if inner else (b - a,):
                    self.raw.append(self.norm[was:a + end]); self.key.append(self.raw[-1].casefold()); self.a.append(was); self.b.append(a + end)
                    was = a + end
        self.n = len(self.raw)
        self.gap = [_NONE] + [_gap(self.norm[self.b[j - 1]:self.a[j]], self.key[j - 1]) for j in range(1, self.n)]
        digit = [r.isdecimal() for r in self.raw]
        self.digit = digit
        self.off, self.unit = [False] * self.n, [False] * self.n      # one letter glued to a digit (P3, T01) is never a word of a name; a unit after a number only of a whole one
        for j in range(self.n):
            near = [k for k in (j - 1, j + 1) if 0 <= k < self.n and digit[k] and self.glued(max(j, k))]
            self.off[j] = len(self.key[j]) == 1 and bool(near)
            self.unit[j] = not self.off[j] and self.key[j] in _UNITS and j > 0 and digit[j - 1] and self.near(j) and not self.level(j - 1)

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

    def cut_line(self, j, s):
        """a line break before word j, in a match that starts at word s, with a date on one side of it"""
        return self.gap[j] == _LINE and (self.dated(j, 1) or j == s + 1 and self.dated(s, -1))


def _list(x): return list(x) if hasattr(x, "__iter__") and not isinstance(x, (str, bytes, dict)) else []


def _dicts(x): return [d for d in _list(x) if isinstance(d, dict)]


def _dict(x): return x if isinstance(x, dict) else {}


def _model(pub): return _dict(_dict(pub).get("model"))


def _levels(pub):
    m = _model(pub)
    out = _list(m.get("levels")) + _list(_dict(_dict(m.get("setup")).get("school")).get("levels"))
    out += [x.get("level") for k in ("classes", "lessons") for x in _dicts(m.get(k))]
    return out + [c.get("level") for c in _dicts(_dict(m.get("setup")).get("classes"))]


def _strings(pub):
    """the levels, classes, subjects (full, short and setup code) and rooms of the published timetable, as they are written"""
    m = _model(pub)
    setup, subjects, out = _dict(m.get("setup")), set(), _levels(pub)
    for c in _dicts(m.get("classes")): out += [c.get("name"), c.get("home")]
    for c in _dicts(setup.get("classes")): out += [c.get("class"), c.get("home_room")]
    for x in _dicts(m.get("lessons")):
        out += [x.get("room"), x.get("rain"), *_list(x.get("classes"))]
        subjects.add(str(x.get("subject") or ""))
    for s, v in _dict(m.get("subjects")).items(): subjects.add(str(s or "")); out.append(_dict(v).get("short"))
    for s in _dicts(setup.get("subjects")): subjects.add(str(s.get("subject") or "")); out.append(s.get("code"))
    for r in _dicts(m.get("rooms")): out += [r.get("name"), *_list(r.get("parts"))]
    for r, parts in _dict(m.get("room_parts")).items(): out += [r, *_list(parts)]
    for v in _dicts(setup.get("venues")): out.append(v.get("room"))
    for s in subjects: out += [s, short_subject(s)]
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
        self._known, self._heads = None, set()      # every word of a name; what an ID may start with before its first digit
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
        for sid, _ in kids:
            t = _Text(sid, self)
            if not t.n: continue
            s = self._cell(t, 0, t.n)
            digits, letters = sum(c.isdecimal() for c in s), any(c.isalpha() for c in s)
            if s.casefold() in wholes or t.n == 1 and (t.key[0] in self._prot or not digits and self._plain(t.key[0])): continue
            if not digits: self._written.add(s)
            elif digits < 5 and not letters: self._bare.add(s)
            else: self._ids.add(s.casefold()); self._heads.add(re.match(r"\D*", s.casefold()).group())
            self._longest = max(self._longest, t.n)
        for s in (_dict(_dict(pub).get("meta")).get("school"), _dict(model.get("school")).get("name")):
            s = str(s or "").strip()
            if sum(c.isalpha() for c in s) >= 4 and s.casefold() != "school":        # "School" is what a setup with no name has
                self._plant(self._schools, _Text(s, self), 0, 1)
        self._firsts = {_Text(s, self).key[0] for s in (*self._shorts, *self._ids, *self._bare, *self._written)}       # the first words of short names and IDs
        self._starts = {k for k, _ in self._has}.union(_TITLES, self._tree, self._schools, ("the",))       # and of everything else

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
            best[j] = (max if reading else min)(ways, key=len, default=None)
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
        """(the word after the titles at word i, them), or (i, None). A title is on the line and in the cell of its name. A word
        that is a subject's code, as it is written ("DR"), is not one, nor one in capitals before a protected word in capitals
        ("WILL MISS ART"); "teacher" and "sir" only before a word with a capital"""
        s, got = i, []
        while len(got) < 3 and s + 1 < t.n and t.key[s] in _TITLES and t.gap[s + 1] == _SOFT and t.raw[s] not in self._signs:
            if t.raw[s].isupper() and t.raw[s + 1].isupper() and t.key[s + 1] in self._prot: break
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

    def _loose_start(self, t, words, commas):
        """in typed words: may the first word of a match be something else, as the last one may, while a match that starts at the
        next word hides the rest"""
        s, j = words[0], words[1]
        if not (t.key[s] in self._prot and (t.gap[j] != _SOFT or t.dated(s, -1)) or self._verb(t, s, j)): return False
        rest = self._name(t, j, None, "typed", commas)
        return bool(rest) and not any(k >= rest[0] and t.key[k] not in self._prot for k in words)

    def _who(self, t, words, mask, title, where):
        """the people (of mask, who have all these words in their name) the words stand for after the title, or 0; of two or more
        words, of one after a title, or of one that is enough on its own"""
        keys, teachers, k = [t.key[j] for j in words], mask & self._teachers, len(words)
        plain = all(self._plain(w) for w in keys)
        if title:
            s = words[0]
            verb, word = title == ["miss"] and t.small(s - 1), title[-1] in _WORDS_TOO                      # "they will miss Art"
            if plain and (verb or self._verb(t, s, s - 1) or word and self._loose_end(t, words, mask)): return 0      # or "Miss a lesson"
            if teachers:
                pool = self._by_title(teachers, title)
                return pool & self._long.get(k, 0) or pool
            return mask if k > 1 and not verb and not word else 0
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

    # ------------------------------------------------------------------------------------------------ one match
    def _whole(self, t, s, title, where, commas, on=False):
        """(end, who) of the longest whole stored name of two or more words at word s, in any order, or None; of three or more when a
        unit after a number is one of them ("1 Min Jun Tan"). on: a title before it is not on its line"""
        words, masks, mask, seen, j, comma, best = [], [], self._all, {}, s, 0, None
        while j < t.n and not t.off[j]:
            k = t.key[j]
            seen[k] = seen.get(k, 0) + 1
            mask &= self._has.get((k, seen[k]), 0)
            if not mask: break
            words.append(j); masks.append(mask)
            full = mask & self._long.get(len(words), 0)
            if full and len(words) > (2 if any(t.unit[w] for w in words) else 1) and (title or not self._nobody(t, words)):
                date = not full & self._teachers and len(words) == 2 and not title and t.dated(s, -1)      # "3 Jun Goh": see the top
                if not date: best = (len(words), full)
            n, g = t.after(j)
            if n >= t.n or t.owns(n): break
            if g == _COMMA:
                if comma or not commas: break
                comma = len(words)
            elif g == _NONE or title and g != _SOFT: break
            j = n
        if not best: return None
        k, full = best
        words = words[:k]
        if comma and k > comma:
            split = self._split(t, words, comma, title, where)
            if split > k - comma or split and not (full & self._teachers and (comma == 1 and not title or split == 1)): return self._whole(t, s, title, where, False)
        if title:
            who = self._who(t, words, masks[k - 1], title, where)
        else:
            tt = full & self._teachers
            who = tt & self._titled[""] or tt or full
        if not who: return None
        if where == "typed":
            while len(words) > 1 and self._loose_end(t, words, masks[len(words) - 1]):
                rest = self._who(t, words[:-1], masks[len(words) - 2], title, where)
                if not rest: break
                words, who = words[:-1], rest
            if not title and not on and len(words) > 1 and self._loose_start(t, words, commas): return None
        return words[-1] + 1, who

    def _part(self, t, s, title, where, commas):
        """(end, who) of the longest run of words of one name at word s, or None. In a list and in the app's words a day or month
        bound to a day's number is never in it, and protected words are cut from its ends"""
        words, masks, mask, seen, j, comma = [], [], self._all, {}, s, 0
        while j < t.n and not t.off[j] and not t.unit[j]:
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
            elif g == _NONE or title and g != _SOFT or t.cut_line(n, s): break
            elif g == _CELL and (t.key[j] in self._prot or t.key[n] in self._prot): break
            j = n
        if not words: return None
        while len(words) > 1 and self._verb(t, words[-1], words[-2]): words.pop(); masks.pop()          # "Lim may be away"
        if where != "typed":
            if not title and t.key[s] in self._prot and len(words) > 1: return None
            while len(words) > 1 and t.key[words[-1]] in self._prot: words.pop(); masks.pop()
            who = self._who(t, words, masks[-1], title, where)
        else:
            who = self._who(t, words, masks[-1], title, where)
            while who and len(words) > 1 and self._loose_end(t, words, masks[-1]):
                rest = self._who(t, words[:-1], masks[-2], title, where)
                if not rest: break
                words.pop(); masks.pop(); who = rest
            if who and not title and len(words) > 1 and self._loose_start(t, words, commas): return None
        if who and comma and len(words) > comma and self._split(t, words, comma, title, where): return self._part(t, s, title, where, False)
        return (words[-1] + 1, who) if who else None

    def _split(self, t, words, c, title, where):
        """when the words before a comma (the first c) and those after it are matches of their own, and leave no word that only a
        name has: how many words the second match has; else 0"""
        before = self._name(t, words[0], title, where, False)
        if not before or any(j >= before[0] and t.key[j] not in self._prot for j in words[:c]): return 0
        after = self._name(t, words[c], None, where, False)
        if not after or any(j >= after[0] and t.key[j] not in self._prot for j in words[c:]): return 0
        return after[0] - words[c]

    def _walk(self, tree, t, s):
        """(end, mask) of the longest name in tree from word s, as it is stored, with its own marks, or None"""
        node, j, got = tree, s, None
        while j < t.n:
            step = node.get(t.key[j])
            if step is None or j > s and t.gap[j] in (_NONE, _COMMA) and t.between(j) not in step[1]: break
            node = step[0]; j += 1
            if None in node: got = (j, node[None])
        return got

    def _name(self, t, s, title, where, commas=True):
        """(end, who) of the longest match of a person at word s, after the title, or None; of the same length, a teacher before a
        student and a whole name before part of one"""
        if s >= t.n or t.off[s]: return None
        whole, part = self._whole(t, s, title, where, commas), self._part(t, s, title, where, commas)
        best = max((x for x in (whole, part) if x), key=lambda x: (x[0], bool(x[1] & self._teachers)), default=None)
        if title and best:                       # a whole name that goes on in another cell or line, with a word only a name has
            more = self._whole(t, s, None, where, commas, True)
            rest = range(best[0], more[0]) if more else ()
            if any(t.gap[j] in (_CELL, _LINE) for j in rest) and any(t.key[j] not in self._prot for j in rest): best = more
        got = self._walk(self._tree, t, s)
        if got and got[0] > (best[0] if best else s + (2 if t.unit[s] else 1)) and (title or not all(w in self._prot for w in t.key[s:got[0]])):
            teachers = got[1] & self._teachers
            if teachers: return got[0], self._by_title(teachers, title or [""])
            if not title or title[-1] not in _WORDS_TOO and not (title == ["miss"] and t.small(s - 1)): return got
        n = t.after(s)[0]
        if best and not title and n < best[0] and (t.key[s] in self._prot or self._verb(t, s, n)):       # a match that starts after it and goes further hides more
            more = self._name(t, n, None, where, commas)
            if more and more[0] > best[0]: return None
        return best

    def _exact(self, t, i, where):
        """[(end, order on a tie, who)] of the short names and IDs at word i. A short name is a run of letters and digits of its
        own; an ID may be followed at once by letters, not by a digit"""
        out = []
        for e in range(min(i + self._longest, t.n), i, -1):
            s = self._cell(t, i, e)
            if where != "list" and s in self._shorts and not t.glued(e) and not t.off[i] and not t.unit[i] and not (s in ("AM", "PM") and i and t.digit[i - 1]): out.append((e, 3, self._shorts[s]))
            if s.casefold() in self._ids or s in self._written: ok = not (t.glued(e) and t.digit[e]) and (not t.glued(i) or t.digit[i - 1] or len(t.key[i - 1]) > 1 and t.key[i - 1] in self._known)
            else: ok = s in self._bare and self._numbered(t, i)
            if ok: out.append((e, 1, 0))
        return out

    def _numbered(self, t, i):
        """does word i, a number, come after "student", "pupil" or "ID": "student 12", "student no. 12", "ID: 12", "student #12" """
        k = i - 1
        if k > 0 and t.key[k] in ("no", "number") and t.between(i) in ("", ".") and t.gap[k] == _SOFT: k, gap = k - 1, _SOFT
        else: gap = t.gap[i] if i else _NONE
        return k >= 0 and t.key[k] in ("student", "pupil", "id") and (gap == _SOFT or t.between(i) in (":", "#", ":#"))

    def _match(self, t, i, where, at):
        """the longest match at word i, after the character at: (first character, the one after the last, the next word, what goes
        instead), or None"""
        found = self._exact(t, i, where) if t.key[i] in self._firsts else []          # (end, order on a tie, who: 0 is a student)
        if t.key[i] in self._starts:
            s, title = self._title(t, i)
            got = self._name(t, s, title, where)
            if not title and t.key[i] in _TITLES and i + 1 < t.n and t.gap[i + 1] == _SOFT:        # "MR ART KOH": the title as it is stored, and the whole name
                more = self._whole(t, i + 1, None, where, True)
                if more and more[1] & self._titled.get(_ALIKE.get(t.key[i], t.key[i]), 0): got = (more[0], self._by_title(more[1], [t.key[i]]))
            if got: found.append((got[0], 2, got[1]))
            for j in (i, i + 1) if t.key[i] == "the" and i + 1 < t.n and t.gap[i + 1] in (_SOFT, _LINE) else (i,):
                school = self._walk(self._schools, t, j)
                if school: found.append((school[0], 4, None))
        if not found: return None
        e, order, who = max(found, key=lambda x: x[:2])
        start, end = t.start(i), t.end(e - 1)
        if order == 4: return start, end, e, SCHOOL
        start, end = _tidy(t.text, at, start, end)
        return start, end, e, self._label(who, t.text[start:end])

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
        text, parts, at, i = t.text, [], 0, 0
        while i < t.n:
            got = self._match(t, i, where, at)
            if got is None: i += 1; continue
            start, end, i, label = got
            before = text[at:start] or (parts[-1] if parts else "")
            parts += [text[at:start], " " if before[-1:].isalnum() else "", label, " " if text[end:end + 1].isalnum() else ""]
            at = end
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

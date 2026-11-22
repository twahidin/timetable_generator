"""Names to codes: what may be sent to the AI, and the names put back in what it says.

A teacher goes as a code ("T07"), several people who fit as "T03 or T11", a student as "a student", the school's name as "the
school". A text is cut into words once and read from left to right; at each word the longest match is taken, and matches never
overlap. What is a match depends on where the text is from:
- everywhere: the stored full name with or without its title; a title (TITLES) and one or more words of one teacher's name; two
  or more words of one teacher's or one student's name side by side, in any order; a student's ID; all of these in any case. A
  stored name of one word, as it is written or in capitals. The school's name in any case, when it has four letters or more;
- "typed" (a person's own words): also the short name exactly as it is written, and one word that starts with a capital letter
  and is in a teacher's name;
- "app" (the app's own sentences and records): also the short name exactly as it is written;
- "list" (the agreed list): nothing more. Its single words and short names are left alone.
Any other place counts as "typed", which hides the most. Words are side by side across white space (a line break and a tab too),
or with one hyphen, apostrophe, dot or underscore between them; a full name also with the marks it is stored with, and in "list"
and "app" with a comma ("Tan, Wei Ling"; in "typed" the two sides are matched on their own).

Never a code: one protected word (see protected) on its own, or several that all are; a word that is only a link in names (bin,
s/o, and), or one letter, on its own; small words in small letters ("do an"). A word that is protected, or small and in small
letters, stays out of a match when it reads as something else: a verb beside a name ("Mdm Lim may be away"), or, as long as the
rest is still a match, a date ("Mdm Lim May 3"), the next line, a subject or room ("Mr Koh Art Room"). A protected word is never
joined to another cell of a row. So what stays beside a code is never a word that only a name has.

Who is meant when several fit: whoever has the title that is written ("Mr Tan"), then whoever has those words and no more, else
all of them; a teacher before a student. A student's ID is matched in any case; one with no letter and fewer than five digits
could be a date, a time or a count, so it is one only right after "student", "pupil" or "ID"; one with no digit is matched as it
is written; one that is a class, room or other word of the timetable is not matched. A name the app does not know (a misspelling,
a visitor) goes as it is."""
import re, unicodedata

from relief.pick import HONORIFICS
from ttgen.report import short_subject

TITLES = HONORIFICS + ("madam", "cikgu", "encik", "puan", "ustaz", "ustazah", "sir", "teacher", "prof", "professor")
STUDENT, SCHOOL = "a student", "the school"
_ALIKE = {"madam": "mdm", "professor": "prof"}          # one title, two ways to write it
_WORDS_TOO = ("teacher", "sir")                         # ordinary words too: a title only before a name word with a capital, on the same line
_TITLES = frozenset(TITLES)
_DAYS = "monday tuesday wednesday thursday friday saturday sunday".split()
_MONTHS = "january february march april may june july august september october november december".split()
_DATES = frozenset(w for d in _DAYS + _MONTHS for w in (d, d[:3]))
_JOINERS = frozenset("bin binte binti bte bt s/o d/o a/l a/p and of the".split())        # in many names, and never a name
_SMALL = frozenset(("a an and are as at be but by can do for from go had has have he her him his i if in is it me my no not of "
                    "on or our she so that the them then they this to up us was we were will with you your").split())

_MARK = "[\u0300-\u036f\u1ab0-\u1aff\u00ad\u200b-\u200d\u2060\ufeff]"                  # accents on their own, and marks nobody sees
_WORD = re.compile(rf"[sd]/o(?![^\W_])|a/[lp](?![^\W_])|(?:[^\W_]{_MARK}*)+", re.I)
_HIDDEN = re.compile(_MARK)
_NUMBER = re.compile(r"\d{1,2}(?:st|nd|rd|th)?|(?:19|20)\d\d")
_CODE = re.compile(r"(?<!\w)T\d{2,}(?!\w)")
_NONE, _SOFT, _CELL, _LINE, _COMMA = range(5)           # between two words: nothing that joins; a space or a mark; a tab or a wide space; a line break; a comma
_TIGHT = "-\u2010\u2011'\u2018\u2019\u02bc`._"          # with no space beside it: Wei-Ling, Nur'Aisyah, tan.wei.ling, tan_wei_ling
_APOSTROPHES = tuple("'\u2019\u02bc")               # "Ms Tan's": the s is no word of a name
_LINES = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"


def _key(word):
    """a word as it is compared: any case, with no accents, in any form of the same letters"""
    if word.isascii(): return word.casefold()
    return "".join(c for c in unicodedata.normalize("NFKD", _HIDDEN.sub("", word)) if not unicodedata.combining(c)).casefold()


def _space(g):
    if any(c in _LINES for c in g): return _LINE
    return _CELL if "\t" in g or len(g) > 2 else _SOFT


def _gap(g, before):
    """what the text g between two words is; before: the word before it"""
    if not g.isascii(): g = _HIDDEN.sub("", g)
    if g.isspace(): return _space(g)
    if len(g) == 1 and g in _TIGHT: return _SOFT
    if g[0:1] in _TIGHT[:3] and g[1:].isspace() and _space(g[1:]) == _LINE: return _LINE                    # Wei-Ling, cut at the hyphen
    if before in _WORDS_TOO or len(before) == 1: rest = g[1:] if g[:1] == "." else g                        # "teacher. Grace", "S. Kumar"
    else: rest = g.strip(".()[]*_\"'\u201c\u201d\u2018\u2019") if before in _TITLES else g                                          # "Ms. Tan", "(Ms) Tan", "Ms *Tan*"
    if rest != g and (not rest or rest.isspace()): return _space(rest) if rest else _SOFT
    return _COMMA if g.strip() == "," else _NONE


class _Text:
    """a text's words (as written and as compared), where they are, and what is between them"""

    def __init__(self, text):
        found = list(_WORD.finditer(text))
        self.text, self.n = text, len(found)
        self.raw = [m.group() for m in found]
        self.key = [_key(r) for r in self.raw]
        self.start, self.end = [m.start() for m in found], [m.end() for m in found]
        self.gap = [_NONE] + [_gap(text[self.end[j - 1]:self.start[j]], self.key[j - 1]) for j in range(1, self.n)]

    def between(self, j): return " ".join(self.text[self.end[j - 1]:self.start[j]].split())

    def small(self, j): return self.raw[j].islower()

    def dated(self, j, step):
        """is word j a day or month with a number right after it (step 1) or before it (-1), on the same line"""
        k = j + step
        return self.key[j] in _DATES and 0 <= k < self.n and self.gap[max(j, k)] == _SOFT and bool(_NUMBER.fullmatch(self.key[k]))


def _strings(pub):
    """the levels, classes, subjects (full, short and setup code) and rooms of the published timetable, as they are written"""
    m = (pub or {}).get("model") or {}
    setup, out, subjects = m.get("setup") or {}, [], set()
    out += m.get("levels") or []
    out += (setup.get("school") or {}).get("levels") or []
    for c in m.get("classes") or []: out += [c.get("name"), c.get("level"), c.get("home")]
    for c in setup.get("classes") or []: out += [c.get("class"), c.get("level"), c.get("home_room")]
    for x in m.get("lessons") or []:
        out += [x.get("level"), x.get("room"), x.get("rain"), *(x.get("classes") or [])]
        subjects.add(x.get("subject"))
    for s, v in (m.get("subjects") or {}).items():
        subjects.add(s); out.append((v or {}).get("short"))
    for s in setup.get("subjects") or []:
        subjects.add(s.get("subject")); out.append(s.get("code"))
    for r in m.get("rooms") or []: out += [r.get("name"), *(r.get("parts") or [])]
    for r, parts in (m.get("room_parts") or {}).items(): out += [r, *(parts or [])]
    for v in setup.get("venues") or []: out.append(v.get("room"))
    for s in subjects: out += [s, short_subject(str(s or ""))]
    return [str(x) for x in out if x not in (None, "")]


def protected(pub):
    """the words that are never made a code on their own, casefolded: the days and months and their three letters, and every
    word of the published timetable's levels, classes, subjects, short subjects, setup codes and rooms. A title is not one,
    whatever a room is called: "Mdm Lim" stays a person"""
    return frozenset(w.casefold() for s in _strings(pub) for w in _WORD.findall(s)) - _TITLES | _DATES


def _bits(mask):
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


class Names:
    """the codes of one talk. pub: the published timetable (or None); people: accounts.people.listing(pub); students:
    model["students"]. Codes are T01, T02, ... in order of the names, less a number that is a word of the timetable, a group,
    a short name or an ID. Everything is worked out here, so out is one pass over the text"""

    def __init__(self, pub, people, students):
        strings = _strings(pub)
        self._prot = frozenset(_key(w) for w in protected(pub))
        short = {}
        for p in people or ():
            name = str(p.get("name") or "").strip()
            if name: short.setdefault(name, str(p.get("short") or "").strip())
        kids = [(str(x.get("id") if x.get("id") is not None else "").strip(), str(x.get("name") or "").strip()) for x in students or ()]
        self._people = sorted(short, key=lambda n: (n.casefold(), n))
        model = (pub or {}).get("model") or {}
        groups = [str(x.get(k) or "") for x in model.get("lessons") or [] for k in ("group", "block")]
        taken = self._prot.union(_key(w) for s in groups + list(short.values()) + [i for i, _ in kids] for w in _WORD.findall(s))
        self._codes, n = [], 0
        for _ in self._people:
            n += 1
            while f"t{n:02d}" in taken: n += 1
            self._codes.append(f"T{n:02d}")
        self._code = dict(zip(self._people, self._codes))
        self._name = dict(zip(self._codes, self._people))

        # every person is one bit, the teachers first; a mask is a set of people
        self._teachers = (1 << len(self._people)) - 1
        self._all = (1 << (len(self._people) + len(kids))) - 1
        self._has = {}           # (word, 1st, 2nd ... of it in the name) -> who has it
        self._order = {}         # person -> the words of the name in order
        self._long = {}          # number of words -> who has that many
        self._titled = {"": 0}   # title -> who has it ("": who has none in front)
        self._ones = {}          # a name of one word -> [(as written, person's mask)]
        self._whole_names = {}   # a tree of the full names, word by word: word -> (next, marks between); None -> [mask, {what follows it in the name}]
        self._schools = {}       # the same, for the school's names
        for i, name in enumerate(self._people + [n for _, n in kids]): self._learn(i, name)

        wholes = {" ".join(s.split()).casefold() for s in strings}
        self._shorts, self._longest = {}, 0
        self._ids, self._bare, self._written = set(), set(), set()      # IDs: in any case; that could be a date; with no digit, as they are written
        for i, name in enumerate(self._people):
            words = _WORD.findall(short[name])
            if not words or short[name] == name or all(_key(w) in self._prot for w in words): continue
            if len(words) == 1 and (len(words[0]) == 1 or _key(words[0]) in _SMALL and not words[0].isupper()): continue       # "S", "On"
            s = self._trim(short[name])
            self._shorts[s] = self._shorts.get(s, 0) | 1 << i
            self._longest = max(self._longest, len(words))
        for sid, _ in kids:
            words = _WORD.findall(sid)
            if not words: continue
            s, digits = self._trim(sid), sum(c.isdigit() for c in sid)
            if s.casefold() in wholes or len(words) == 1 and (_key(words[0]) in self._prot or not digits and self._plain(_key(words[0]))): continue
            if not digits: self._written.add(s)
            elif digits < 5 and not any(c.isalpha() for c in s): self._bare.add(s)
            else: self._ids.add(s.casefold())
            self._longest = max(self._longest, len(words))
        meta = (pub or {}).get("meta") or {}
        for s in (meta.get("school"), (model.get("school") or {}).get("name")):
            s = str(s or "").strip()
            if sum(c.isalpha() for c in s) >= 4 and _key(s) != "school":        # "School" is what a setup with no name has
                self._plant(self._schools, s, list(_WORD.finditer(s)), 1)

    # ------------------------------------------------------------------------------------------------ the tables
    @staticmethod
    def _trim(s):
        found = list(_WORD.finditer(s))
        return " ".join(s[found[0].start():found[-1].end()].split())

    @staticmethod
    def _plant(tree, name, found, mask):
        node = tree
        for j, m in enumerate(found):
            step = node.setdefault(_key(m.group()), ({}, set()))
            if j: step[1].add(" ".join(name[found[j - 1].end():m.start()].split()))
            node = step[0]
        leaf = node.setdefault(None, [0, set()])
        leaf[0] |= mask
        leaf[1].add(name[found[-1].end():])

    def _learn_whole(self, i, name):
        """the full name of person i less the titles in front; returns the words it is made of"""
        found = list(_WORD.finditer(name))
        while found and _key(found[0].group()) in _TITLES: found.pop(0)
        if not any(c.isalpha() for m in found for c in m.group()): return []
        if len(found) == 1: self._ones.setdefault(_key(found[0].group()), []).append((found[0].group(), 1 << i))
        else: self._plant(self._whole_names, name, found, 1 << i)
        return [_key(m.group()) for m in found]

    def _learn(self, i, name):
        keys = [_key(w) for w in _WORD.findall(name)]
        for k in keys:
            if k in _TITLES: self._titled[_ALIKE.get(k, k)] = self._titled.get(_ALIKE.get(k, k), 0) | 1 << i
        if not keys or keys[0] not in _TITLES: self._titled[""] |= 1 << i
        words = [k for k in self._learn_whole(i, name) if k not in _TITLES and not k[0].isdigit()]      # "3A" or "01" in a name is no word of it
        self._order[i] = words
        self._long[len(words)] = self._long.get(len(words), 0) | 1 << i
        for j, k in enumerate(words):
            at = (k, words[:j + 1].count(k))
            self._has[at] = self._has.get(at, 0) | 1 << i

    # ------------------------------------------------------------------------------------------------ one match
    def _plain(self, word): return word in self._prot or word in _SMALL or len(word) == 1

    def _verb(self, t, j, beside):
        """is word j an ordinary word in small letters beside a word that is not: "Lim may be away", "Ask Kumar a question" """
        return t.small(j) and not t.small(beside) and self._plain(t.key[j])

    def _joined(self, t, j, s, titled):
        """is word j side by side with the word before it, in a match that starts at word s (after a title: titled). A protected
        word is never joined to another cell, nor a date to another line"""
        g = t.gap[j]
        if g == _SOFT: return True
        if g == _CELL: return t.key[j] not in self._prot and t.key[j - 1] not in self._prot
        return g == _LINE and not t.dated(j, 1) and (titled or j != s + 1 or not t.dated(s, -1))

    def _title(self, t, i):
        """(the word after the titles at word i, them), or (i, None): titles in a row ("Dr Mrs"), or "teacher" or "sir" before
        a word with a capital on the same line"""
        s, got = i, []
        while s + 1 < t.n and t.key[s] in _TITLES and self._joined(t, s + 1, i, True):
            if t.key[s] in _WORDS_TOO and (t.gap[s + 1] != _SOFT or not t.raw[s + 1][:1].isupper()): break
            got.append(t.key[s]); s += 1
            if got[-1] in _WORDS_TOO: break
        return (s, got) if got else (i, None)

    def _by_title(self, mask, title):
        same = 0
        for k in title: same |= self._titled.get(_ALIKE.get(k, k), 0)
        return mask & same or mask

    def _apart(self, t, s):
        """is word s, with no title before it, no part of a name that goes on: "may Lim come", "on 3 May long papers are" """
        return self._verb(t, s, s + 1) or t.dated(s, -1) and t.small(s + 1) and not t.small(s)

    def _loose_end(self, t, j, mask):
        """may the last word j of a match be something else: on the next line, a date, or (when it does not follow the word
        before it in any of the names the match fits) a verb, or the start of a subject or room"""
        if t.key[j] not in self._prot and not (t.small(j) and self._plain(t.key[j])): return False
        if t.gap[j] == _LINE or t.dated(j, 1): return True
        if not t.small(j) and not (j + 1 < t.n and t.gap[j + 1] == _SOFT and t.key[j + 1] in self._prot - _SMALL): return False
        return not any(pair == (t.key[j - 1], t.key[j]) for i in _bits(mask) for pair in zip(self._order[i], self._order[i][1:]))

    def _loose_start(self, t, j): return t.key[j] in self._prot and (t.gap[j + 1] == _LINE or t.dated(j, -1))

    def _who(self, t, s, e, mask, title, where):
        """the people (of mask, who have all the words s to e in their name) these words stand for after the title, or 0"""
        keys, teachers = t.key[s:e], mask & self._teachers
        plain = all(self._plain(w) for w in keys)
        if title:
            verb = title == ["miss"] and t.small(s - 1)                         # "they will miss Art"
            word = title[-1] in _WORDS_TOO
            if plain and (verb or self._verb(t, s, s - 1) or word and self._loose_end(t, e - 1, mask)): return 0      # or "Miss a lesson"
            if teachers:
                pool = self._by_title(teachers, title)
                return pool & self._long.get(e - s, 0) or pool
            return mask if e - s > 1 and not verb and not word else 0
        if all(w in self._prot for w in keys) or all(w in _JOINERS or len(w) == 1 for w in keys): return 0
        if plain and all(t.small(j) for j in range(s, e)): return 0             # "do an", "go on"
        if e - s > 1:
            full = teachers & self._long.get(e - s, 0)
            return full & self._titled[""] or full or teachers or mask
        raw, one = t.raw[s], 0
        for written, person in self._ones.get(keys[0], ()):
            if raw == written or raw.isupper() and len(raw) > 1: one |= person
        pool = teachers if one & self._teachers or where == "typed" and raw[:1].isupper() else 0
        return pool & one & self._titled[""] or pool or one

    def _words(self, t, s, title, where):
        """(how far the words of one name go from word s, the end of the match, who it stands for); who is 0: no match"""
        masks, mask, seen, j = [], self._all, {}, s
        while j < t.n and (j == s or self._joined(t, j, s, bool(title))):
            k = t.key[j]
            if j > s and (self._verb(t, j, j - 1) or not title and j == s + 1 and self._apart(t, s) or k == "s" and t.between(j) in _APOSTROPHES): break
            seen[k] = seen.get(k, 0) + 1
            mask &= self._has.get((k, seen[k]), 0)
            if not mask: break
            masks.append(mask); j += 1
        e = s + len(masks)
        who = self._who(t, s, e, masks[-1], title, where) if masks else 0
        while who and e - s > 1 and self._loose_end(t, e - 1, masks[e - s - 1]):
            rest = self._who(t, s, e - 1, masks[e - s - 2], title, where)
            if not rest: break
            e, who = e - 1, rest
        if who and not title and e - s > 1 and self._loose_start(t, s) and self._words(t, s + 1, None, where)[2]: who = 0
        return s + len(masks), e, who

    def _walk(self, tree, t, s, titled, comma):
        """(the end, mask, what follows it) of the longest full name in tree from word s, or None: with the marks the name is
        stored with, and with a comma when comma is True and no protected word is beside it"""
        node, j, got = tree, s, None
        while j < t.n:
            step = node.get(t.key[j])
            if step is None: break
            if j > s and not self._joined(t, j, s, titled):
                if t.gap[j] in (_CELL, _LINE): break
                if t.between(j) not in step[1] and not (comma and t.gap[j] == _COMMA and not self._plain(t.key[j - 1]) and not self._plain(t.key[j])): break
            node = step[0]; j += 1
            if None in node: got = (j, *node[None])
        return got

    def _exact(self, t, i, where):
        """[(end, order on a tie, who)] of the longest short name and the longest ID at word i"""
        out = []
        for e in range(min(i + self._longest, t.n), i, -1):
            s = " ".join(t.text[t.start[i]:t.end[e - 1]].split())
            if where != "list" and s in self._shorts and not (s in ("AM", "PM") and i and t.key[i - 1].isdigit()): out.append((e, 3, self._shorts[s]))
            if (s.casefold() in self._ids or s in self._written
                    or s in self._bare and i and t.key[i - 1] in ("student", "pupil", "id") and (t.gap[i] == _SOFT or t.between(i) == ":")): out.append((e, 1, 0))
        return out

    def _match(self, t, i, where):
        """the longest match at word i: (first character, the one after the last, the next word, what goes instead), or None"""
        s, title = self._title(t, i)
        reach, e, who = self._words(t, s, title, where)
        found = [(e, 2, who)] if who else []                                    # (end, order on a tie, who: 0 is a student)
        end_of, mask, tails = self._walk(self._whole_names, t, s, bool(title), where != "typed") or (0, 0, ())
        if end_of > reach and (title or not (all(w in self._prot for w in t.key[s:end_of]) or self._apart(t, s) or self._verb(t, end_of - 1, end_of - 2))):
            teachers = mask & self._teachers
            if teachers: found.append((end_of, 2, self._by_title(teachers, title or [""])))
            elif not title or title[-1] not in _WORDS_TOO: found.append((end_of, 2, mask))
        if self._longest: found += self._exact(t, i, where)
        for j in (i, i + 1) if t.key[i] == "the" and i + 1 < t.n and t.gap[i + 1] in (_SOFT, _LINE) else (i,):
            school = self._walk(self._schools, t, j, False, False)
            if school: found.append((school[0], 4, None))
        if not found: return None
        e, order, who = max(found, key=lambda x: x[:2])
        start, end = t.start[i], t.end[e - 1]
        if order == 4: return start, end, e, SCHOOL
        if e == end_of > reach: end += max((len(x) for x in tails if t.text.startswith(x, end)), default=0)      # "Ho Mei (Mrs Wong)": the last mark
        if title and start and t.text[start - 1] == "(" and t.text[t.end[i]:t.end[i] + 1] == ")": start -= 1        # "(Ms) Tan"
        return start, end, e, self._label(who, t.text[start:end])

    def _label(self, who, raw):
        if not who & self._teachers: return STUDENT
        found = list(_bits(who & self._teachers))
        if len(found) > 1:                                                      # two names with the same words: as it is stored
            raw = " ".join(raw.split())
            found = [i for i in found if " ".join(self._people[i].split()) == raw] or found
        return " or ".join(self._codes[i] for i in found)

    # ------------------------------------------------------------------------------------------------ what is called
    def out(self, text, where):
        """text with every known name made a code, "a student" or "the school"; where is "typed", "list" or "app" (see the top
        of the file). Anything that is not a string is given back as it is"""
        if not isinstance(text, str): return text
        if where not in ("list", "app"): where = "typed"
        t, parts, at, i = _Text(text), [], 0, 0
        while i < t.n:
            got = self._match(t, i, where)
            if got is None: i += 1; continue
            start, end, i, label = got
            parts += [text[at:start], label]; at = end
        return "".join(parts) + text[at:]

    def back(self, text):
        """text with every code made the name as it is stored; a code nobody has, or one inside a longer word, is left"""
        return _CODE.sub(lambda m: self._name.get(m.group(), m.group()), text) if isinstance(text, str) else text

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
        return frozenset(self._name)

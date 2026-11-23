"""The school's agreed list of exam papers, without AI: the text out of an Excel or Word file (or the app's own layout read
as it is), the text cut into pieces for a reader, and the rows a reader gives matched against the published timetable. No
Flask here and nothing of app.py; nothing here calls an AI. Rows come from an untrusted reader: nothing but Refused leaves."""
import datetime
import io
import re
import warnings
import zipfile
import xml.etree.ElementTree as ET

from exams import papers as _papers
from plan.steps import Refused, LONGEST, MAX_PAPERS, WRONG, _date, _fold, _short, _time

BAD_FILE = "Give an Excel or Word file, or paste the list."
LONG_LIST = "Keep the list under 20,000 characters."
MOST_BYTES, MOST_CHARS = 5 * 1024 * 1024, 20000
MOST_DOC, MOST_BOOK = 20 * 1024 * 1024, 50 * 1024 * 1024      # unpacked: word/document.xml, and all of an Excel file
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# ---------------------------------------------------------------- the text of a file
def _kind(filename, data) -> str:
    """".xlsx" or ".docx" when the file may be opened, else Refused"""
    kind = str(filename or "").strip().lower()[-5:]
    if kind not in (".xlsx", ".docx") or not isinstance(data, (bytes, bytearray)) or len(data) > MOST_BYTES:
        raise Refused(BAD_FILE)
    return kind


def _zip(data, kind) -> zipfile.ZipFile:
    """the file as a zip, refused before anything is unpacked when it would unpack too big (a zip bomb)"""
    try:
        z = zipfile.ZipFile(io.BytesIO(bytes(data)))
        infos = z.infolist()
    except Exception:
        raise Refused(BAD_FILE) from None
    if kind == ".xlsx" and sum(i.file_size for i in infos) > MOST_BOOK:
        raise Refused(BAD_FILE)
    if kind == ".docx" and next((i.file_size for i in infos if i.filename == "word/document.xml"), MOST_DOC + 1) > MOST_DOC:
        raise Refused(BAD_FILE)
    return z


def _value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        return v.date().isoformat() if v.time() == datetime.time() else v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, datetime.time):
        return v.strftime("%H:%M")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return " ".join(str(v).split())


def _book(data) -> list:
    import openpyxl
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(io.BytesIO(bytes(data)), read_only=True, data_only=True)
        try:
            out = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    cells = [_value(v) for v in row]
                    while cells and not cells[-1]:
                        cells.pop()
                    if cells:
                        out.append("\t".join(cells))
            return out
        finally:
            wb.close()


def _para(p) -> str:
    """the words of a Word paragraph: its text, a tab as a tab, a line break as a space"""
    out = []
    for e in p.iter():
        if e.tag == W + "t":
            out.append(e.text or "")
        elif e.tag == W + "tab":
            out.append("\t")
        elif e.tag in (W + "br", W + "cr"):
            out.append(" ")
    return "".join(out).strip()


def _doc(z) -> list:
    xml = z.open("word/document.xml").read(MOST_DOC + 1)
    if len(xml) > MOST_DOC or b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise Refused(BAD_FILE)
    out = []

    def walk(e):
        if e.tag == W + "p":
            out.append(_para(e))
        elif e.tag == W + "tbl":
            for tr in e.iter(W + "tr"):
                cells = [" ".join(t for t in (_para(p) for p in tc.iter(W + "p")) if t) for tc in tr.iter(W + "tc")]
                out.append("\t".join(cells).rstrip("\t"))
        else:
            for c in e:
                walk(c)
    walk(ET.fromstring(xml))
    return [x for x in out if x.strip()]


def text_of(filename, data) -> str:
    """the text of an Excel file (cells joined by tabs, rows by newlines) or a Word file (paragraphs, and table rows as
    cells joined by tabs), blank rows left out. Anything else, too big or damaged: Refused(BAD_FILE); a text over 20,000
    characters: Refused(LONG_LIST)"""
    kind = _kind(filename, data)
    z = _zip(data, kind)
    try:
        lines = _book(data) if kind == ".xlsx" else _doc(z)
    except Refused:
        raise
    except Exception:
        raise Refused(BAD_FILE) from None
    text = "\n".join(lines)
    if len(text) > MOST_CHARS:
        raise Refused(LONG_LIST)
    return text


def own_layout(filename, data):
    """the rows of a list in the app's own layout (papers.HEADER), read without AI; None when the file is not in it. A file
    in the layout with a wrong row: Refused with papers' sentence for that row"""
    if str(filename or "").strip().lower()[-5:] != ".xlsx":
        return None
    _zip(data, _kind(filename, data))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            got = _papers.read_paper_list(bytes(data))
            import openpyxl
            ws = openpyxl.load_workbook(io.BytesIO(bytes(data)), data_only=True).worksheets[0]
            lines = [n for n, row in enumerate(ws.iter_rows(values_only=True), start=1)
                     if n > 1 and any(_papers._cell(v) for v in (list(row) + [None] * 8)[:8])]
    except ValueError as e:
        if str(e) == _papers.BAD_HEADER:
            return None
        raise Refused(str(e)) from None
    except Exception:
        raise Refused(BAD_FILE) from None
    return [dict(line=n, level=p["level"], subject=p["subject"], paper=p["paper"], minutes=p["minutes"], date=p["date"],
                 start=p["start"], all=p["who"] == "level", subjects=[], together=p["together"]) for n, p in zip(lines, got)]


def pieces(text, lines=40) -> list:
    """the text in pieces of at most `lines` lines each, in order, every line kept (piece k starts at line k * lines + 1),
    trailing spaces off; [] for a blank text"""
    if not isinstance(text, str) or not isinstance(lines, int) or isinstance(lines, bool) or lines < 1:
        raise Refused(WRONG)
    if not text.strip():
        return []
    rows = [r.rstrip() for r in text.strip("\n").split("\n")]
    return ["\n".join(rows[i:i + lines]) for i in range(0, len(rows), lines)]


# ---------------------------------------------------------------- the rows a reader gives, against the timetable
def _key(t) -> str:
    """the words compared: no case, spaces or brackets, "&" and "and" left out"""
    t = re.sub(r"[()\[\]{}]", " ", str(t)).replace("&", " and ").casefold()
    return "".join(w for w in t.split() if w != "and")


def _subjects(model, lv) -> dict:
    """{subject as the timetable writes it: its keys} of the subjects with lessons at the level lv"""
    d = lambda x: x if isinstance(x, dict) else {}
    l = lambda x: x if isinstance(x, list) else []
    names = sorted({x["subject"] for x in l(model.get("lessons")) if isinstance(x, dict) and x.get("level") == lv
                    and isinstance(x.get("subject"), str) and x["subject"].strip()})
    codes = [x for x in l(d(model.get("setup")).get("subjects")) if isinstance(x, dict)]
    out = {}
    for s in names:
        words = [s, d(d(model.get("subjects")).get(s)).get("short")] + [x.get("code") for x in codes if x.get("subject") == s]
        out[s] = {_key(w) for w in words if isinstance(w, str) and _key(w)}
    return out


def _plain(written, subjects):
    """the one subject whose name, short name or code the words are; None when none, or more than one, is"""
    k = _key(written)
    full = [s for s in subjects if _key(s) == k]
    if len(full) == 1:
        return full[0]
    some = [s for s, keys in subjects.items() if k in keys]
    return some[0] if len(some) == 1 else None


class _Odd(Exception):
    """a row that cannot be read"""


def _text(v, blank_ok=False) -> str:
    if v is None and blank_ok:
        return ""
    if not isinstance(v, str) or len(v.strip()) > LONGEST or not (v.strip() or blank_ok):
        raise _Odd
    return v.strip()


def _minutes(v, n):
    if v is None or v == "":
        return None, f"Row {n} has no length."
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise _Odd
    m = v.strip() if isinstance(v, str) else v
    if isinstance(m, str) and re.fullmatch(r"\d{1,4}", m):
        m = int(m)
    if isinstance(m, float) and m.is_integer():
        m = int(m)
    if not isinstance(m, int) or m < 1:
        return None, f"Row {n}: {_short(v)} is not a length in minutes."
    return m, ""


def _when(v, read, what, n):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None, ""
    if not isinstance(v, str):
        raise _Odd
    try:
        return read(v), ""
    except Refused:
        return None, f"Row {n}: {_short(v.strip())} is not a {what}."


def _row(r, at, model, levels):
    """(entries, "plain" or "other") of a row whose level, subject and paper are texts already, or (None, why); _Odd when a
    field is not of its kind"""
    bare = lambda t: "".join(_fold(t).split())
    level = next((x for x in levels if isinstance(x, str) and bare(x) == bare(r["level"])), None)
    if level is None:
        return None, f"{r['level']} is not a level of this exam."
    subjects = _subjects(model, level)
    meant = r.get("subjects")
    if meant is not None and (not isinstance(meant, list) or not all(isinstance(x, str) for x in meant) or len(meant) > 20):
        raise _Odd
    plain = _plain(r["subject"], subjects)
    if plain:
        read_as = [plain]
    else:
        by_fold = {_fold(s): s for s in subjects}
        read_as = list(dict.fromkeys(by_fold.get(_fold(x)) for x in meant or []))
        if not read_as or None in read_as:
            return None, f"{level} has no subject called {r['subject']}."
    minutes, why = _minutes(r.get("minutes"), at)
    date, why = (None, why) if why else _when(r.get("date"), _date, "date", at)
    start, why = (None, why) if why else _when(r.get("start"), _time, "time", at)
    if not why and start and not date:
        why = f"Row {at} has no date."
    if why:
        return None, why
    all_ = r.get("all", False)
    if not isinstance(all_, bool) and all_ is not None:
        raise _Odd
    together = _text(r.get("together"), blank_ok=True)
    if len(read_as) > 1:
        together = together or _text(f"{level} {r['subject']}"[:LONGEST])
    return [dict(line=at, written=r["subject"], level=level, subject=s, paper=r["paper"], minutes=minutes, date=date, start=start,
                 who="level" if all_ else "groups", together=together) for s in read_as], "plain" if plain else "other"


def match(rows, model, levels) -> dict:
    """rows (dicts of line, level, subject, paper, minutes, date, start, all, subjects and, from the app's own layout, together)
    -> dict(plain, other, unmatched): plain and other are entries for to_papers, each with the line and the words as written;
    unmatched are dict(line, level, subject, paper, why). At most MAX_PAPERS papers go in; a row past them is unmatched"""
    if not isinstance(rows, list) or not isinstance(levels, list):
        raise Refused(WRONG)
    model = model if isinstance(model, dict) else {}
    out, count = dict(plain=[], other=[], unmatched=[]), 0
    for i, r in enumerate(rows, start=1):
        line = r.get("line") if isinstance(r, dict) else None
        good = isinstance(line, int) and not isinstance(line, bool) and line >= 1
        at = line if good else i
        try:
            if not isinstance(r, dict) or not good:
                raise _Odd
            r = dict(r, level=_text(r.get("level")), subject=_text(r.get("subject")), paper=_text(r.get("paper"), blank_ok=True))
            got, how = _row(r, at, model, levels)
        except _Odd:
            got, how = None, f"Row {at} could not be read."
        if got and count + len(got) > MAX_PAPERS:
            got, how = None, f"Row {at} is over {MAX_PAPERS} papers."
        if got:
            count += len(got)
            out[how] += got
            continue
        words = {k: (r.get(k) if isinstance(r, dict) and isinstance(r.get(k), str) else "") for k in ("level", "subject", "paper")}
        out["unmatched"].append(dict(line=at, **{k: v[:LONGEST] for k, v in words.items()}, why=how))
    return out


PUT = ("level", "subject", "paper", "minutes", "date", "start", "who", "together")


def to_papers(entries) -> list:
    """the rows steps' put_list takes, from entries of match's plain and other"""
    if not isinstance(entries, list):
        raise Refused(WRONG)
    out = []
    for e in entries:
        if not isinstance(e, dict) or any(k not in e for k in PUT) or e["who"] not in ("level", "groups"):
            raise Refused(WRONG)
        out.append({k: e[k] for k in PUT})
    return out

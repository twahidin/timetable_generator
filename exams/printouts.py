"""Printouts (A4 PDFs) and the Excel download for a made exam schedule. Reads the schedule and the published model; writes nothing."""
import collections
import io
import re

from exams import days as _days
from exams import make as _make
from exams import papers as _papers
from exams import seating as _seat
from relief.codes import _cell

WHATS = ("seating", "doors", "attendance", "classes", "roster-day", "roster-teacher", "timetable")
LISTS = dict(none="No relief needed", backup="Backup needed", runs="Runs as usual")


def _made(sched):
    return sched.get("made") or {}


def _names(pub):
    return {s["id"]: s for s in pub["model"].get("students") or []}


def _seat_key(seat):
    m = re.match(r"([A-Za-z]*)(\d*)$", str(seat))
    return (len(m.group(1)), m.group(1), int(m.group(2) or 0)) if m else (0, str(seat), 0)


def _span(p):
    a = _days.minutes(p["start"])
    return "%s to %s" % (_days.hhmm(a), _days.hhmm(a + p["minutes"]))


def _where(sched):
    """-> [(sitting, room, [[sid, seat]] in seat order)] for every room of every made sitting"""
    seats = _made(sched).get("seats") or {}
    out = []
    for sit in _seat.sittings(sched):
        for room, rows in (seats.get(sit["key"]) or {}).items():
            out.append((sit, room, sorted(rows, key=lambda r: _seat_key(r[1]))))
    return out


class _Doc:
    def __init__(self, pub, sched, what, out):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from ttgen.export import _fonts
        self.R, self.B = _fonts()
        self.W, self.H = A4
        self.M = 36
        self.head = "%s · %s · %s" % (pub["model"]["school"]["name"], sched.get("name"), what)
        self.c = canvas.Canvas(out, pagesize=A4)
        self.c.setTitle(self.head)
        self.page()

    def page(self):
        from ttgen.export import MUTED, _hex
        self.c.setFont(self.B, 9)
        self.c.setFillColor(_hex(MUTED))
        self.c.drawString(self.M, self.H - self.M + 8, self.head)
        self.y = self.H - self.M - 10

    def need(self, h):
        if self.y - h < self.M:
            self.c.showPage()
            self.page()

    def line(self, text, bold=False, size=9.5, x=0, gap=4, muted=False, width=None):
        from ttgen.export import INK, MUTED, _fit, _hex
        self.need(size + gap)
        t, s = _fit(str(text), self.B if bold else self.R, size, (width or self.W - 2 * self.M - x), 5)
        self.c.setFont(self.B if bold else self.R, s)
        self.c.setFillColor(_hex(MUTED if muted else INK))
        self.y -= size
        self.c.drawString(self.M + x, self.y, t)
        self.y -= gap

    def title(self, text):
        self.need(60)
        self.y -= 8
        self.line(text, bold=True, size=13, gap=6)

    def row(self, cells, widths, bold=False, size=9, gap=5):
        from ttgen.export import INK, _fit, _hex
        self.need(size + gap)
        self.y -= size
        x = self.M
        self.c.setFillColor(_hex(INK))
        for text, w in zip(cells, widths):
            t, s = _fit(str(text), self.B if bold else self.R, size, w - 6, 5)
            self.c.setFont(self.B if bold else self.R, s)
            self.c.drawString(x, self.y, t)
            x += w
        self.y -= gap

    def rule(self, x1=None, x2=None):
        from ttgen.export import LINE, _hex
        self.c.setStrokeColor(_hex(LINE))
        self.c.line(x1 or self.M, self.y, x2 or self.W - self.M, self.y)
        self.y -= 4

    def grid(self, room, rows, names, xset):
        """the seat grid: columns A, B, ... across, row numbers down; each seat 'class id' with the name in small type"""
        from ttgen.export import LINE, MUTED, _fit, _hex
        geo = (xset.get("rooms") or {}).get(room) or {}
        by = {str(seat): sid for sid, seat in rows}
        cols = sorted({re.match(r"[A-Za-z]*", s).group(0) for s in by if re.match(r"[A-Za-z]+\d", s)}, key=lambda s: (len(s), s))
        if cols:
            nrows = max([geo.get("rows") or 0] + [int(re.sub(r"\D", "", s) or 0) for s in by])
            cells = [[(c + str(r)) for c in cols] for r in range(1, nrows + 1)]
        else:
            n = 6
            ks = sorted(by, key=_seat_key)
            cells = [ks[i:i + n] for i in range(0, len(ks), n)]
        ncol = max((len(r) for r in cells), default=1)
        w = min(110, (self.W - 2 * self.M) / ncol)
        h = 26
        for r in cells:
            self.need(h + 2)
            top = self.y
            for i, seat in enumerate(r):
                x = self.M + i * w
                self.c.setStrokeColor(_hex(LINE))
                self.c.rect(x, top - h, w - 3, h)
                sid = by.get(seat)
                self.c.setFillColor(_hex(MUTED))
                self.c.setFont(self.R, 6)
                self.c.drawString(x + 3, top - 7, seat)
                if sid:
                    st = names.get(sid) or {}
                    t, s = _fit("%s %s" % (st.get("cls") or "", sid), self.B, 8, w - 8, 5)
                    self.c.setFont(self.B, s)
                    self.c.setFillColor(_hex("1B2330"))
                    self.c.drawString(x + 3, top - 16, t)
                    t, s = _fit(st.get("name") or "", self.R, 6, w - 8, 4)
                    self.c.setFont(self.R, s)
                    self.c.setFillColor(_hex(MUTED))
                    self.c.drawString(x + 3, top - 23, t)
            self.y -= h + 2


def _sitting_title(sit, room):
    return "%s %s · %s" % (sit["date"], _days.hhmm(sit["start"]), room)


def _per_room(d, pub, sched, xset, what):
    names = _names(pub)
    for sit, room, rows in _where(sched):
        d.title(_sitting_title(sit, room))
        if what == "seating":
            d.grid(room, rows, names, xset)
        elif what == "doors":
            by = collections.OrderedDict()
            for sid, _ in sorted(rows, key=lambda r: ((names.get(r[0]) or {}).get("cls") or "", r[0])):
                by.setdefault((names.get(sid) or {}).get("cls") or "", []).append(sid)
            for cls, sids in by.items():
                d.line("%s  (%d)   %s" % (cls, len(sids), ", ".join(sids)), size=10)
        else:
            w = [60, 70, 190, 60, 150]
            d.row(["Seat", "ID", "Name", "Class", "Signature"], w, bold=True)
            for sid, seat in rows:
                st = names.get(sid) or {}
                d.row([seat, sid, st.get("name"), st.get("cls"), ""], w, size=9, gap=9)
                d.rule(d.M + sum(w[:4]), d.M + sum(w) - 6)


def _classes(d, pub, sched):
    model = pub["model"]
    names = _names(pub)
    at = {}
    for sit, room, rows in _where(sched):
        for sid, seat in rows:
            at[(sit["key"], sid)] = (room, seat)
    keys = {p["id"]: "%s %s" % (p["date"], _days.hhmm(_days.minutes(p["start"]))) for p in sched.get("papers") or [] if p.get("date") and p.get("start")}
    mine = collections.defaultdict(list)
    for p in sorted((p for p in sched.get("papers") or [] if p["id"] in keys), key=lambda p: (p["date"], _days.minutes(p["start"]))):
        for sid in _papers.who_sits(p, model):
            mine[sid].append(p)
    for cls in sorted({s.get("cls") for sid, s in names.items() if sid in mine}):
        d.title("Class " + str(cls))
        w = [150, 80, 90, 90, 70]
        for sid in sorted(i for i, s in names.items() if s.get("cls") == cls and i in mine):
            d.line("%s  %s" % (sid, names[sid].get("name")), bold=True, size=9.5, gap=2)
            for p in mine[sid]:
                room, seat = at.get((keys[p["id"]], sid), ("not seated", ""))
                d.row([_papers.label(p), p["date"], _span(p), room, seat], w, size=8.5, gap=3)


def _roster(d, sched, by_teacher):
    duties = _made(sched).get("duties") or []
    w = [110, 90, 110, 200]
    if by_teacher:
        mine = collections.defaultdict(list)
        for x in duties:
            for n in x["names"]:
                mine[n].append(x)
        for n in sorted(mine):
            d.title(n)
            for x in sorted(mine[n], key=lambda x: (x["date"], x["start"])):
                d.row([x["date"], "%s to %s" % (_days.hhmm(x["start"]), _days.hhmm(x["end"])), x["room"], "chief" if x.get("chief") == n else ""], w)
    else:
        for date in sorted({x["date"] for x in duties}):
            d.title(date)
            d.row(["Time", "Room", "Chief", "Invigilators"], [110, 90, 110, 200], bold=True)
            for x in sorted((x for x in duties if x["date"] == date), key=lambda x: (x["start"], x["room"])):
                d.row(["%s to %s" % (_days.hhmm(x["start"]), _days.hhmm(x["end"])), x["room"], x.get("chief") or "", ", ".join(x["names"])], [110, 90, 110, 200])


def _timetable(d, sched):
    by = collections.defaultdict(list)
    for p in sched.get("papers") or []:
        if p.get("date") and p.get("start"):
            by[p.get("level") or ""].append(p)
    for lv in sorted(by):
        d.title(lv)
        w = [90, 110, 250]
        for p in sorted(by[lv], key=lambda p: (p["date"], _days.minutes(p["start"]))):
            d.row([p["date"], _span(p), _papers.label(p)], w)


def pdf(what, pub, cal, sched, xset, out) -> None:
    if what not in WHATS:
        raise ValueError(what)
    d = _Doc(pub, sched, what, out)
    if what in ("seating", "doors", "attendance"):
        _per_room(d, pub, sched, xset, what)
    elif what == "classes":
        _classes(d, pub, sched)
    elif what == "timetable":
        _timetable(d, sched)
    else:
        _roster(d, sched, what == "roster-teacher")
    d.c.showPage()
    d.c.save()


def xlsx(pub, cal, sched, xset) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Papers"
    src = openpyxl.load_workbook(io.BytesIO(_papers.paper_list_xlsx(sched))).active
    for r in src.iter_rows(values_only=True):
        ws.append([_cell(v) if isinstance(v, str) else v for v in r])
    names, by_id = _names(pub), {p["id"]: p for p in sched.get("papers") or []}
    seats = wb.create_sheet("Seats")
    seats.append(["Date", "Start", "Room", "Seat", "Student ID", "Name", "Class", "Paper"])
    for sit in _seat.sittings(sched):
        taking = _seat.sitting_students(sit, sched, pub["model"])
        for room, rows in sorted(((_made(sched).get("seats") or {}).get(sit["key"]) or {}).items()):
            for sid, seat in sorted(rows, key=lambda r: _seat_key(r[1])):
                st = names.get(sid) or {}
                labels = ", ".join(_papers.label(by_id[i]) for i in (taking.get(sid) or {}).get("papers", []) if i in by_id)
                seats.append([_cell(v) for v in (sit["date"], _days.hhmm(sit["start"]), room, seat, sid, st.get("name") or "", st.get("cls") or "", labels)])
    duties = wb.create_sheet("Duties")
    duties.append(["Date", "From", "To", "Room", "Paper(s)", "Invigilators", "Chief", "Needs backup"])
    sits = {s["key"]: s for s in _seat.sittings(sched)}
    for x in _made(sched).get("duties") or []:
        labels = ", ".join(_papers.label(by_id[i]) for i in (sits.get(x["key"]) or {}).get("papers", []) if i in by_id)
        duties.append([_cell(v) for v in (x["date"], _days.hhmm(x["start"]), _days.hhmm(x["end"]), x["room"], labels,
                                          ", ".join(x["names"]), x.get("chief") or "", ", ".join(x.get("backup") or {}))])
    lessons = wb.create_sheet("Lessons")
    lessons.append(["List", "Date", "From", "To", "Classes", "Subject", "Teachers", "Room", "Note"])
    got = _make.lesson_lists(pub, cal, sched)
    for k, name in LISTS.items():
        for i in got.get(k) or []:
            lessons.append([_cell(v) for v in (name, i["date"], i["start"], i["end"], ", ".join(i["classes"]), i["subject"],
                                               ", ".join(i["teachers"]), i["room"], i["note"])])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()

"""The committee's personal staff codes: a CSV and printable slips, as the personal student codes have."""
import collections, csv, io

import access
from relief.settings import FORMULA


def _cell(v):
    """a CSV cell a spreadsheet will not read as a formula (relief.settings refuses such names too; this is the second guard)"""
    v = str(v)
    return "'" + v if v[:1] in FORMULA else v


def codes_csv(people) -> str:
    """Name, Department, Personal code: one row a person, in the order of people (BOM first, for Excel)"""
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["Name", "Department", "Personal code"])
    for p in people: w.writerow([_cell(p["name"]), _cell(", ".join(p["depts"])), _cell(access.staff_code(p["name"]))])
    return "\ufeff" + buf.getvalue()


def slips_pdf(school: str, people, url: str, out):
    """slips to cut (10 to an A4 page, a new page per first department) with each person's code, drawn as
    ttgen.export.code_slips_pdf draws the student slips"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from ttgen.export import INK, MUTED, SUB, _fit, _fonts, _hex
    R, B = _fonts(); W, H = A4; c = canvas.Canvas(out, pagesize=A4); c.setTitle(f"{school} relief codes")
    by = collections.OrderedDict()
    for p in people: by.setdefault(p["depts"][0] if p["depts"] else "", []).append(p)
    M, cols, rows = 28, 2, 5; sw, sh = (W - 2 * M) / cols, (H - 2 * M - 16) / rows
    for dept, ps in by.items():
        for k in range(0, len(ps), cols * rows):
            c.setFont(B, 9); c.setFillColor(_hex(MUTED)); c.drawString(M, H - M + 6, f"{school} · relief codes · {dept or 'No department'} · cut along the dashed lines")
            for i, p in enumerate(ps[k:k + cols * rows]):
                x = M + (i % cols) * sw; y = H - M - 16 - (i // cols + 1) * sh
                c.setDash(3, 3); c.setStrokeColor(_hex("B8BEC6")); c.setLineWidth(0.6); c.rect(x + 4, y + 4, sw - 8, sh - 8); c.setDash()
                c.setFillColor(_hex(MUTED)); c.setFont(R, 8.5); c.drawString(x + 16, y + sh - 24, f"{school} · your relief code")
                t, ts = _fit(p["name"], B, 13, sw - 40, 9)
                c.setFillColor(_hex(INK)); c.setFont(B, ts); c.drawString(x + 16, y + sh - 44, t)
                t, ts = _fit(", ".join(p["depts"]), R, 9.5, sw - 40, 6)
                c.setFillColor(_hex(SUB)); c.setFont(R, ts); c.drawString(x + 16, y + sh - 59, t)
                c.setFillColor(_hex(INK)); c.setFont("Courier-Bold", 24); c.drawString(x + 16, y + sh - 98, access.staff_code(p["name"]))
                c.setFillColor(_hex(SUB)); t, ts = _fit(f"Go to {url}", B, 8.5, sw - 36, 6); c.setFont(B, ts); c.drawString(x + 16, y + 42, t)
                c.setFont(R, 8.2); c.drawString(x + 16, y + 30, "choose Relief and enter this code.")
                c.drawString(x + 16, y + 18, "Keep it to yourself: anyone with it can act as you.")
            c.showPage()
    c.save()
    return out

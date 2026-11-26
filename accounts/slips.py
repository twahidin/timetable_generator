"""Sign-in slips for staff: a username made from a name, a PDF of slips to cut and a CSV of the same rows."""
import collections, csv, io, re, unicodedata

from relief.settings import FORMULA

TITLES = frozenset({"mr", "mrs", "ms", "mdm", "miss", "dr", "mx"})
LONGEST = 40


def make_username(name: str, depts, taken) -> str:
    """a username of 3 to 40 of [a-z0-9._-] from a name: a leading title dropped, accents folded, only letters and digits
    kept; too short a name is filled from its department, then "staff"; a clash gets 2, 3 ... (`taken` holds lower case)"""
    words = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower().split()
    if len(words) > 1 and words[0].rstrip(".") in TITLES: words = words[1:]
    base = re.sub(r"[^a-z0-9]", "", "".join(words))
    if len(base) < 3 and depts:
        base += re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(depts[0])).encode("ascii", "ignore").decode().lower())
        base = base[:3] if len(base) >= 3 else base
    if len(base) < 3: base += "staff"
    base = base[:LONGEST]
    u, k = base, 1
    while u in taken:
        k += 1; s = str(k); u = base[:LONGEST - len(s)] + s
    return u


def _cell(v):
    v = str(v)
    return "'" + v if v[:1] in FORMULA else v


def slips_csv(rows) -> str:
    """Name, Department, Username, Temporary password: one row a person, in the order of rows (BOM first, for Excel)"""
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["Name", "Department", "Username", "Temporary password"])
    for r in rows: w.writerow([_cell(r["name"]), _cell(", ".join(r["depts"])), _cell(r["username"]), _cell(r["password"])])
    return "﻿" + buf.getvalue()


def slips_pdf(school: str, rows, url: str, out):
    """slips to cut (10 to an A4 page, a new page per first department), laid out as relief.codes.slips_pdf does"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from ttgen.export import INK, MUTED, SUB, _fit, _fonts, _hex
    R, B = _fonts(); W, H = A4; c = canvas.Canvas(out, pagesize=A4); c.setTitle(f"{school} sign-in slips")
    by = collections.OrderedDict()
    for p in rows: by.setdefault(p["depts"][0] if p["depts"] else "", []).append(p)
    M, cols, nrows = 28, 2, 5; sw, sh = (W - 2 * M) / cols, (H - 2 * M - 16) / nrows
    for dept, ps in by.items():
        for k in range(0, len(ps), cols * nrows):
            c.setFont(B, 9); c.setFillColor(_hex(MUTED)); c.drawString(M, H - M + 6, f"{school} · sign-in slips · {dept or 'No department'} · cut along the dashed lines")
            for i, p in enumerate(ps[k:k + cols * nrows]):
                x = M + (i % cols) * sw; y = H - M - 16 - (i // cols + 1) * sh
                c.setDash(3, 3); c.setStrokeColor(_hex("B8BEC6")); c.setLineWidth(0.6); c.rect(x + 4, y + 4, sw - 8, sh - 8); c.setDash()
                c.setFillColor(_hex(MUTED)); c.setFont(R, 8.5); c.drawString(x + 16, y + sh - 20, _fit(f"{school} · your sign-in", R, 8.5, sw - 36, 6)[0])
                t, ts = _fit(p["name"], B, 13, sw - 40, 9)
                c.setFillColor(_hex(INK)); c.setFont(B, ts); c.drawString(x + 16, y + sh - 38, t)
                t, ts = _fit(", ".join(p["depts"]), R, 9.5, sw - 40, 6)
                c.setFillColor(_hex(SUB)); c.setFont(R, ts); c.drawString(x + 16, y + sh - 52, t)
                c.setFont(R, 8.5); c.setFillColor(_hex(MUTED)); c.drawString(x + 16, y + sh - 69, "Username")
                t, ts = _fit(p["username"], "Courier-Bold", 14, sw - 40, 8)
                c.setFillColor(_hex(INK)); c.setFont("Courier-Bold", ts); c.drawString(x + 16, y + sh - 84, t)
                c.setFont(R, 8.5); c.setFillColor(_hex(MUTED)); c.drawString(x + 16, y + sh - 100, "Temporary password")
                c.setFillColor(_hex(INK)); c.setFont("Courier-Bold", 16); c.drawString(x + 16, y + sh - 117, p["password"])
                c.setFillColor(_hex(SUB)); t, ts = _fit(f"Go to {url}, sign in, then choose your own password.", B, 8.2, sw - 36, 5); c.setFont(B, ts); c.drawString(x + 16, y + 30, t)
                c.setFont(R, 8.2); c.drawString(x + 16, y + 18, "Keep this slip to yourself until you have.")
            c.showPage()
    c.save()
    return out

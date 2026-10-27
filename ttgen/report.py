"""Write the solved timetable to a workbook (class, teacher and room grids, lesson list, teacher load) and check it."""
import collections, datetime, re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
from openpyxl.comments import Comment

NAVY = "1F4E78"
F = lambda **k: Font(name="Arial", size=k.pop("size", 8), **k)
HDR = PatternFill("solid", fgColor=NAVY); BRK = PatternFill("solid", fgColor="D9D9D9"); EXTF = "FFF2CC"
WRAP = Alignment(wrap_text=True, vertical="center", horizontal="center")
BOX = Border(*(Side(style="thin", color="B7B7B7"),) * 4)
PAL = ["DCE9F7", "FCE4CC", "D9F0DA", "F8D7DA", "F3EBC9", "E4DDF4", "D4EFEF", "EADCF0", "E9E1D6", "DDE3F0", "EDEDED", "F6E3C6"]
BREAK = {"F": "Assembly", "R": "Recess", "U": "Lunch"}

def short_subject(s):
    s = re.sub(r"English Language", "EL", s); s = re.sub(r"Mathematics", "Math", s); s = re.sub(r"Physical Education", "PE", s)
    s = re.sub(r"Character and Citizenship Education", "CCE", s); s = re.sub(r"Combined Science", "Sci", s); s = re.sub(r"Additional Mathematics", "AMath", s)
    s = re.sub(r"Principles of Accounts", "POA", s); s = re.sub(r"Literature in English", "Lit", s); s = re.sub(r"Design & Technology", "D&T", s)
    s = re.sub(r"Food and Consumer Education", "FCE", s); s = re.sub(r"Food and Nutrition", "F&N", s); s = re.sub(r"Social Studies", "SS", s)
    s = re.sub(r"Programme for Active Learning", "PAL", s); s = re.sub(r"Applied Learning Programme", "ALP", s)
    s = re.sub(r"\(Standard\)", "Std", s); s = re.sub(r"\(Foundation\)", "Fdn", s); s = re.sub(r" Language", "", s)
    return s

def clock(sc, p):
    h, m = map(int, str(sc["start_time"]).split(":")[:2]); t = h * 60 + m + p * int(sc["period_minutes"])
    return f"{(t // 60 - 1) % 12 + 1}.{t % 60:02d}"

def assign_rooms(res):
    P = res["problem"]; NP = P.NP
    rooms = collections.defaultdict(list); cap = {}
    for v in P.spec["venues"]: rooms[v.get("kind") or "classroom"].append(v["room"]); cap[v["room"]] = 1
    for r in P.spec.get("rules", []):
        if r.get("rule") == "At most N at once" and r.get("scope") == "Room" and r.get("target") in cap and r.get("number"): cap[r["target"]] = int(r["number"])
    occ = collections.defaultdict(collections.Counter)
    for r in P.spec.get("rules", []):
        if r.get("rule") == "Not available" and r.get("scope") == "Room" and r.get("target") in cap:
            S, _ = P.rule_positions(r)
            for q in S: occ[r["target"]][q] = 99
    home = {c["class"]: c.get("home_room") for c in P.spec["classes"]}
    def free(x, pos): return all(occ[x][q] < cap.get(x, 1) for q in pos)
    lessons = res["lessons"]
    for L in lessons: L["rooms"] = {}; L["pos"] = list(range(L["start"], L["start"] + L["ln"]))
    for L in lessons:
        if L["unit"]["kind"] == "class" and not L["part"][0]["room_kind"]:
            h = home.get(L["unit"]["classes"][0])
            if h: L["rooms"][id(L["part"][0])] = h; [occ[h].update({q: 1}) for q in L["pos"]]
    used = {}
    for L in sorted(lessons, key=lambda L: (L["start"], -L["ln"])):
        for r in L["part"]:
            if id(r) in L["rooms"]: continue
            k = r["room_kind"] or "classroom"; key = (r["code"], tuple(r["classes"]), r["subject"])
            pref = ([used[key]] if key in used else []) + ([home.get(c) for c in L["unit"]["classes"]] if k == "classroom" else []) + rooms.get(k, [])
            if k == "classroom": pref += rooms.get("classroom", [])
            x = next((x for x in pref if x and x in cap and x in rooms.get(k, []) + ([h for h in home.values()] if k == "classroom" else []) and free(x, L["pos"])), None)
            L["rooms"][id(r)] = x or "TBC"
            if x:
                for q in L["pos"]: occ[x][q] += 1
                used.setdefault(key, x)

def check(res):
    """independent checks on the result; returns (problems, stats)"""
    P = res["problem"]; NP = P.NP; probs = []; L = res["lessons"]
    got = collections.Counter()
    for x in L:
        for r in x["part"]: got[(id(r), x["unit"]["classes"][0] if x["unit"]["kind"] == "class" else "*")] += x["ln"]
    for u in P.units:
        for r in u["rows"]:
            k = (id(r), u["classes"][0] if u["kind"] == "class" else "*")
            if got[k] != r["periods"]: probs.append(f"{r['subject']} {r['code']} {'/'.join(u['classes'])}: {got[k]} periods placed, {r['periods']} planned.")
    tb = collections.defaultdict(list)
    for x in L:
        for t in {t for r in x["part"] for t in r["teachers"]}:
            for q in x["pos"]: tb[(t, q)].append(x)
    probs += [f"Teacher clash: {t} at {P.days[q // NP]} period {q % NP}." for (t, q), v in tb.items() if len(v) > 1]
    cap = {v["room"]: 1 for v in P.spec["venues"]}
    for r in P.spec.get("rules", []):
        if r.get("rule") == "At most N at once" and r.get("scope") == "Room" and r.get("target") in cap and r.get("number"): cap[r["target"]] = int(r["number"])
    rb = collections.Counter((room, q) for x in L for room in x["rooms"].values() for q in x["pos"])
    probs += [f"Room over capacity: {room} at {P.days[q // NP]} period {q % NP}." for (room, q), n in rb.items() if room != "TBC" and n > cap.get(room, 1)]
    occ = collections.defaultdict(list)
    for x in L:
        for c in x["unit"]["classes"]:
            for q in x["pos"]: occ[(c, q)].append(x)
    side = 0
    for (c, q), xs in occ.items():
        if len(xs) > 1:
            if any(x["unit"]["kind"] == "class" for x in xs): probs.append(f"Class clash: {c} at {P.days[q // NP]} period {q % NP}.")
            else: side += 1
    for x in L:
        lv = x["unit"]["level"]
        for q in x["pos"]:
            if P.grid[lv][q // NP][q % NP] not in "LA": probs.append(f"{x['unit']['name']} sits in a break at {P.days[q // NP]} period {q % NP}.")
    for r in P.spec.get("rules", []):
        if r.get("rule") == "Not available" and r.get("scope") == "Teacher" and str(r.get("strength") or "Must") == "Must":
            S, _ = P.rule_positions(r)
            if any(q in S for x in L if r["target"] in {t for rr in x["part"] for t in rr["teachers"]} for q in x["pos"]):
                probs.append(f"{r['target']} has a lesson in a blocked time.")
    # students listed on the Students sheet
    code_l = collections.defaultdict(set)
    for x in L:
        for r in x["part"]: code_l[r["code"]] |= set(x["pos"])
    ecp = collections.defaultdict(set)
    for x in L:
        if x["unit"]["kind"] == "class": ecp[x["unit"]["classes"][0]] |= set(x["pos"])
    sclash = 0
    for s in P.spec.get("students", []):
        seen = collections.Counter()
        for q in ecp.get(s.get("class"), ()): seen[q] += 1
        for g in s.get("groups") or []:
            for q in code_l.get(g, ()): seen[q] += 1
        if any(n > 1 for n in seen.values()): sclash += 1
    if sclash: probs.append(f"{sclash} students on the Students sheet have two lessons at once.")
    # rules checked after solving
    post = []
    tpos = collections.defaultdict(set)
    for x in L:
        for t in {t for r in x["part"] for t in r["teachers"]}: tpos[t] |= set(x["pos"])
    for r in P.spec.get("rules", []):
        if r.get("rule") == "Max periods in a row" and r.get("number"):
            N = int(r["number"]); who = [r["target"]] if r["scope"] == "Teacher" else list(tpos)
            bad = [t for t in who if _longest_run(tpos[t], NP) > N]
            post.append(f"Max periods in a row ({N}): " + (f"{len(bad)} teachers go over: {', '.join(bad[:8])}" if bad else "kept by everyone."))
        if r.get("rule") == "At least one recess a day":
            who = [r["target"]] if r["scope"] == "Teacher" else list(tpos)
            bad = []
            for t in who:
                for d in range(P.ND):
                    rec = set()
                    for lv in P.levels:
                        rec |= {d * NP + p for p, ch in enumerate(P.grid[lv][d]) if ch == "R"}
                    groups = _runs_set(rec, NP)
                    if tpos[t] & {q for q in range(d * NP, d * NP + NP)} and groups and all(g & tpos[t] for g in groups): bad.append(f"{t} ({P.days[d]})")
            post.append("At least one recess a day: " + (f"missed on {len(bad)} teacher-days: {', '.join(bad[:6])}" if bad else "kept by everyone."))
    stats = dict(lessons=len(L), after_school=sum(1 for x in L if x["ext"]), side_by_side=side, students_checked=len(P.spec.get("students", [])))
    return probs, stats, post

def _longest_run(pos, NP):
    best = cur = 0; prev = None
    for q in sorted(pos):
        cur = cur + 1 if prev is not None and q == prev + 1 and q // NP == prev // NP else 1; best = max(best, cur); prev = q
    return best
def _runs_set(s, NP):
    out, cur = [], set(); prev = None
    for q in sorted(s):
        if prev is not None and (q != prev + 1): out.append(cur); cur = set()
        cur.add(q); prev = q
    if cur: out.append(cur)
    return out

def write_timetable(res, path):
    P = res["problem"]; sc = P.spec["school"]; NP, ND = P.NP, P.ND
    if res["lessons"]: assign_rooms(res)
    probs, stats, post = check(res) if res["lessons"] else (["No timetable."], {}, [])
    L = res["lessons"]; wb = openpyxl.Workbook(); wb.remove(wb.active)
    fam_col = {}
    def colour(subj):
        k = re.sub(r"\s*\(.*|\s+G[123]$", "", subj); fam_col.setdefault(k, PAL[len(fam_col) % len(PAL)]); return fam_col[k]
    short = {t["name"]: (t.get("short") or t["name"]) for t in P.spec["teachers"]}
    # read me
    ws = wb.create_sheet("Read me")
    lines = [(f"{sc['name']} · {sc['timetable']} timetable", "t"),
             (f"{len(P.spec['classes'])} classes, {len(P.spec['teachers'])} teachers, {stats.get('lessons', 0)} lessons placed. Solver status: {res['status']}.", ""),
             ("Checks", "h")]
    lines += [("No problems found: no teacher, room or class is double-booked; every lesson has its planned periods; nothing sits in a break.", "")] if not probs else [(p, "") for p in probs[:40]]
    if stats.get("side_by_side"): lines.append((f"{stats['side_by_side']} class-periods have two bands running side by side for different students (e.g. extra periods for one level).", ""))
    ext = [x for x in L if x["ext"]]
    lines.append(("After-school lessons", "h"))
    lines += [("None.", "")] if not ext else [(f"{x['unit']['name']}: {P.days[x['start'] // NP]} {clock(sc, x['start'] % NP)}-{clock(sc, x['start'] % NP + x['ln'])}", "") for x in ext]
    if post: lines += [("Rules checked after solving", "h")] + [(p, "") for p in post]
    if res.get("notes"): lines += [("Notes", "h")] + [(n, "") for n in res["notes"]]
    lines += [("How to read", "h"), ("Classes, Teachers and Rooms sheets show one grid per class, teacher or room: days down the side, periods across (clock times in the header). "
               "Banded lessons show the subjects running; hover a cell to see every group, teacher and room. 'only' means just those groups have a lesson. Yellow = after-school slot.", "")]
    for i, (t, k) in enumerate(lines, start=1):
        c = ws.cell(i, 1, t); c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(name="Arial", size=14, bold=True, color=NAVY) if k == "t" else Font(name="Arial", size=11, bold=True, color=NAVY) if k == "h" else Font(name="Arial", size=10)
    ws.column_dimensions["A"].width = 130
    def grid(ws, keys, cells_of, level_of, title_of):
        ws.column_dimensions["A"].width = 11
        for p in range(NP): ws.column_dimensions[CL(p + 2)].width = 6.2
        r0 = 1
        for k in keys:
            ws.cell(r0, 1, title_of(k)).font = F(bold=True, size=11)
            ws.cell(r0 + 1, 1, "Day").font = F(bold=True, color="FFFFFF"); ws.cell(r0 + 1, 1).fill = HDR
            for p in range(NP):
                c = ws.cell(r0 + 1, p + 2, f"{p}\n{clock(sc, p)}"); c.font = F(bold=True, color="FFFFFF", size=7); c.fill = HDR; c.alignment = WRAP
            ws.row_dimensions[r0 + 1].height = 24
            cells = cells_of(k); lv = level_of(k)
            for d in range(ND):
                rr = r0 + 2 + d; ws.row_dimensions[rr].height = 36; ws.cell(rr, 1, P.days[d]).font = F(bold=True)
                p = 0
                while p < NP:
                    pos = d * NP + p
                    if pos in cells:
                        text, com, fill = cells[pos]; q = p
                        while q + 1 < NP and cells.get(pos + q + 1 - p, (None,))[0] == text and q - p < 5: q += 1
                        c = ws.cell(rr, p + 2, text); c.font = F(); c.alignment = WRAP; c.border = BOX
                        if fill: c.fill = PatternFill("solid", fgColor=fill)
                        if com: c.comment = Comment(com, "Timetable"); c.comment.width = 320; c.comment.height = 140
                        if q > p: ws.merge_cells(start_row=rr, start_column=p + 2, end_row=rr, end_column=q + 2)
                        p = q + 1; continue
                    if lv:
                        ch = P.grid[lv][d][p]
                        if ch in BREAK: c = ws.cell(rr, p + 2, BREAK[ch]); c.fill = BRK; c.font = F(size=7, color="595959"); c.alignment = WRAP
                    p += 1
            r0 += ND + 3
        ws.freeze_panes = "B1"; ws.page_setup.orientation = "landscape"; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    def class_cells(c):
        by = collections.defaultdict(list)
        for x in L:
            if c in x["unit"]["classes"]:
                for q in x["pos"]: by[q].append(x)
        cells = {}
        for q, xs in by.items():
            texts, coms = [], []
            for x in xs:
                if x["unit"]["kind"] == "class":
                    r = x["part"][0]; texts.append(f"{short_subject(r['subject'])}\n{', '.join(short.get(t, t) for t in r['teachers'])} {x['rooms'].get(id(r), '')}")
                else:
                    subs = list(dict.fromkeys(short_subject(re.sub(r'\s+G[123]$', '', r['subject'])) for r in x["part"]))
                    lab = " / ".join(subs[:3]) + (f" +{len(subs) - 3}" if len(subs) > 3 else "")
                    if len(x["part"]) < len(x["unit"]["rows"]): lab += " only"
                    texts.append(lab if len(xs) > 1 else lab + f"\n{len(x['part'])} groups")
                    coms += [f"{r['code']}: {r['subject']} - {', '.join(r['teachers'])} - {x['rooms'].get(id(r), '')}" for r in x["part"]]
            fill = EXTF if any(x["ext"] for x in xs) else colour(xs[0]["part"][0]["subject"])
            cells[q] = ("\n+ ".join(texts), "\n".join(coms) or None, fill)
        return cells
    ws = wb.create_sheet("Classes")
    grid(ws, [c["class"] for c in P.spec["classes"]], class_cells, lambda c: P.level_of[c],
         lambda c: f"Class {c} ({P.level_of[c]}, {P.cls[c].get('size') or ''} students, home room {P.cls[c].get('home_room') or '-'})")
    tl = collections.defaultdict(list)
    for x in L:
        for r in x["part"]:
            for t in r["teachers"]: tl[t].append((x, r))
    def teacher_cells(t):
        cells = {}
        for x, r in tl[t]:
            who = r["code"] if r["code"] != "Entire Class" else x["unit"]["classes"][0]
            for q in x["pos"]:
                cells[q] = (f"{short_subject(r['subject'])} {who}\n{x['rooms'].get(id(r), '')}", f"{r['subject']} | {who} | classes {', '.join(r['classes'])}", EXTF if x["ext"] else colour(r["subject"]))
        return cells
    ws = wb.create_sheet("Teachers")
    tper = {t: sum(x["ln"] for x, _ in v) for t, v in tl.items()}
    grid(ws, sorted(tl, key=str.lower), teacher_cells, lambda t: None, lambda t: f"{t} ({tper[t]} periods a cycle)")
    rl = collections.defaultdict(list)
    for x in L:
        for r in x["part"]: rl[x["rooms"].get(id(r), "TBC")].append((x, r))
    def room_cells(rm):
        cells = {}
        for x, r in rl[rm]:
            who = r["code"] if r["code"] != "Entire Class" else x["unit"]["classes"][0]
            for q in x["pos"]:
                prev = cells.get(q); txt = f"{short_subject(r['subject'])} {who}"
                cells[q] = ((prev[0] + " + " + txt) if prev else txt, None, colour(r["subject"]))
        return cells
    ws = wb.create_sheet("Rooms")
    grid(ws, [v["room"] for v in P.spec["venues"] if v["room"] in rl] + (["TBC"] if "TBC" in rl else []), room_cells, lambda r: None, lambda r: f"Room {r}")
    ws = wb.create_sheet("Lessons")
    hdr = ["Day", "Start period", "Starts", "End period", "Periods", "Level", "Classes", "Subject", "Group", "Teachers", "Room", "After school"]
    ws.append(hdr)
    for x in sorted(L, key=lambda x: (x["start"], x["unit"]["level"])):
        for r in x["part"]:
            p = x["start"] % NP
            ws.append([P.days[x["start"] // NP], p, clock(sc, p), p + x["ln"] - 1, x["ln"], r["level"], ", ".join(x["unit"]["classes"] if x["unit"]["kind"] == "class" else r["classes"]),
                       r["subject"], r["code"], ", ".join(r["teachers"]), x["rooms"].get(id(r), ""), "yes" if x["ext"] else ""])
    for c in ws[1]: c.font = Font(name="Arial", bold=True, color="FFFFFF", size=10); c.fill = HDR
    for col, w in zip("ABCDEFGHIJKL", (11, 7, 8, 7, 7, 7, 22, 34, 10, 34, 14, 8)): ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    ws = wb.create_sheet("Teacher load")
    ws.append(["Teacher", "Department", "Allowance", "Periods timetabled", "Most periods in a day", "Days teaching", "Longest run (periods)", "After-school periods"])
    for t in P.spec["teachers"]:
        n = t["name"]; perday = collections.Counter(); pos = set(); ex = 0
        for x, r in tl.get(n, []):
            perday[x["start"] // NP] += x["ln"]; pos |= set(x["pos"]); ex += x["ln"] if x["ext"] else 0
        ws.append([n, t.get("dept"), t.get("allowance"), tper.get(n, 0), max(perday.values()) if perday else 0, len(perday), _longest_run(pos, NP), ex])
    for c in ws[1]: c.font = Font(name="Arial", bold=True, color="FFFFFF", size=10); c.fill = HDR
    for col, w in zip("ABCDEFGH", (30, 11, 10, 12, 12, 10, 12, 12)): ws.column_dimensions[col].width = w
    wb.save(path)
    return probs, stats, post

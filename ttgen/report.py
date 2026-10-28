"""Write the solved timetable to a workbook (class, teacher and room grids, lesson list, teacher load) and check it."""
import collections, datetime, re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
from openpyxl.comments import Comment
from .spec import no_free_periods

NAVY = "1F4E78"
F = lambda **k: Font(name="Arial", size=k.pop("size", 8), **k)
HDR = PatternFill("solid", fgColor=NAVY); BRK = PatternFill("solid", fgColor="D9D9D9"); EXTF = "FFF2CC"
WRAP = Alignment(wrap_text=True, vertical="center", horizontal="center")
BOX = Border(*(Side(style="thin", color="B7B7B7"),) * 4)
PAL = ["DCE9F7", "FCE4CC", "D9F0DA", "F8D7DA", "F3EBC9", "E4DDF4", "D4EFEF", "EADCF0", "E9E1D6", "DDE3F0", "EDEDED", "F6E3C6"]
BREAK = {"F": "Assembly", "R": "Recess", "U": "Lunch"}
# the Lessons sheet is the hand-over format: one row per group per lesson; rows that meet together share a Lesson ID
LESSON_HEADERS = ["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group",
                  "Teachers", "Room", "After school"]

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
        lv = x["unit"]["level"]; d = P.days[x["pos"][0] // NP]; keep = P.keep.get(d)
        if keep is not None and x["pos"][-1] % NP >= keep:   # Settings 'Lessons end by': the lesson runs past the time for its day
            probs.append(f"{x['unit']['name']} ends after {clock(P.spec['school'], keep)} on {d} (Settings: Lessons end by)."); continue
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
    nf = no_free_periods(P.spec["school"])
    if nf in ("Yes", "Prefer") and P.spec.get("students"):   # Settings 'Students have no free periods': counted here, not enforced
        free = []
        for s in P.spec["students"]:
            lv = P.level_of.get(s.get("class"))
            if lv not in P.grid: continue
            pos = set(ecp.get(s["class"], ())) | {q for g in s.get("groups") or [] for q in code_l.get(g, ())}
            n = 0
            for d in range(P.ND):
                qs = [q for q in pos if q // NP == d]
                if qs: n += sum(1 for q in range(min(qs), max(qs) + 1) if q not in pos and P.grid[lv][d][q % NP] == "L")
            free.append(n)
        if free: post.append(f"Students have no free periods ({nf}): counted, not enforced by this solver. Free periods a cycle: {sum(free) / len(free):.1f} on average, "
                             f"{max(free)} at most; {sum(1 for f in free if f == 0)} of {len(free)} students have none.")
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

def write_timetable(res, path, return_model=False):
    """assign rooms, check, and write the combined workbook (export.write_excel: Read me, Classes, Teachers, Rooms,
    Students, Lessons, Teacher load). Returns (problems, stats, post-solve rule checks[, model])."""
    from .export import model_from_result, write_excel
    if not res["lessons"]:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Read me"
        ws["A1"] = f"No timetable found. Solver status: {res['status']}."
        for i, n in enumerate(res.get("notes", []), start=3): ws.cell(i, 1, n)
        wb.save(path); out = (["No timetable found."], {}, [])
        return out + (None,) if return_model else out
    assign_rooms(res)
    probs, stats, post = check(res)
    m = model_from_result(res); m["notes"] = post + m["notes"]
    extra = [p for p in probs if "blocked time" in p]
    if extra: m["checks"]["problems"] += extra; m["checks"]["ok"] = False
    write_excel(m, path)
    return (probs, stats, post, m) if return_model else (probs, stats, post)

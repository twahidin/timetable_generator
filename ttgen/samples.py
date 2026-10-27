"""Fictional Singapore sample schools (secondary and primary) used to show how the template is filled.
All names are invented. Periods and day shapes are typical values, not MOE requirements."""
import collections, itertools, re
from .spec import defaults, day_names

FIRST = ["Adeline", "Benjamin", "Charmaine", "Darren", "Evelyn", "Farhan", "Grace", "Harish", "Irene", "Jasper", "Kavitha", "Leonard", "Michelle",
         "Nadia", "Oliver", "Priya", "Qistina", "Raymond", "Sabrina", "Terence", "Umairah", "Vincent", "Wen Hui", "Xavier", "Yasmin", "Zachary",
         "Amanda", "Bryan", "Cheryl", "Desmond", "Elaine", "Faizal", "Gwen", "Hakim", "Ivy", "Joel", "Karen", "Lionel", "Melissa", "Nicholas"]
LAST = ["Tan", "Lim", "Ng", "Wong", "Goh", "Chua", "Koh", "Teo", "Ong", "Lee", "Rahman", "Kumar", "Ismail", "Nair", "Yeo", "Ho", "Low", "Chan", "Sim", "Pillai"]
def _names():
    seen = set()
    for i in itertools.count():
        n = f"{FIRST[i % len(FIRST)]} {LAST[(i * 7 + i // len(FIRST)) % len(LAST)]}"
        if n not in seen:
            seen.add(n); yield n

class Staffing:
    """greedy, load-balanced teacher assignment for the sample lessons"""
    def __init__(self, allowance, school):
        self.allow, self.school, self.names = allowance, school, _names()
        self.t = []      # dicts: name, dept, load, subjects{subject: set(levels)}, classes set
    def new(self, dept):
        n = next(self.names); x = dict(name=n, short=n.split()[0] + " " + n.split()[-1][0], dept=dept, load=0, subjects={}, classes=set())
        self.t.append(x); return x
    def pick(self, dept, subj, level, periods, classes, avoid=(), prefer_class=True, any_dept=False):
        pool = [x for x in self.t if (any_dept or x["dept"] == dept) and x["name"] not in avoid and x["load"] + periods <= self.allow]
        def score(x):
            same_sub = subj in x["subjects"]; same_cls = bool(x["classes"] & set(classes))
            return (same_cls if prefer_class else 0, same_sub, -x["load"])
        pool.sort(key=score, reverse=True)
        x = pool[0] if pool and (any_dept or pool[0]["subjects"] or True) else None
        if x is None or (not any_dept and subj not in x["subjects"] and len(x["subjects"]) >= 3):
            x = self.new(dept) if not any_dept else (pool[0] if pool else self.new(dept))
        x["load"] += periods; x["subjects"].setdefault(subj, set()).add(level); x["classes"] |= set(classes)
        return x["name"]
    def teachers(self):
        bands = self.school["bands"]; out = []
        for x in self.t:
            ct = []
            for s, lv in x["subjects"].items():
                lv = sorted(lv)
                if len(lv) == 1: sc = lv[0]
                elif len({bands[v] for v in lv}) == 1 and len(lv) == 2: sc = bands[lv[0]]
                else: sc = "All"
                ct.append(dict(subject=s, levels=sc))
            out.append(dict(name=x["name"], short=x["short"], dept=x["dept"], allowance=self.allow, provisional="No", can_teach=ct[:8]))
        return out

SFIRST = ["Aiden", "Alicia", "Amirul", "Anya", "Arjun", "Bella", "Brandon", "Caleb", "Chloe", "Daniel", "Dhruv", "Elijah", "Emma", "Ethan", "Faris",
          "Gabriel", "Hannah", "Haziq", "Isaac", "Isabelle", "Jayden", "Jia Hui", "Jun Jie", "Kai", "Kayla", "Lucas", "Lydia", "Marcus", "Megan",
          "Natalie", "Nathan", "Nur Aisyah", "Nurul", "Owen", "Rachel", "Rayan", "Rui En", "Ryan", "Sarah", "Sean", "Shermaine", "Siti", "Sophia",
          "Tanisha", "Timothy", "Valerie", "Vikram", "Wei Jie", "Xin Yi", "Yi Xuan", "Yu Xuan", "Zara", "Zhi Hao", "Zoe", "Adam", "Aaliyah",
          "Jun Wei", "Kavin", "Li Ting", "Matthew"]
SLAST = ["Tan", "Lim", "Lee", "Ng", "Ong", "Wong", "Goh", "Chua", "Chan", "Koh", "Teo", "Ang", "Yeo", "Tay", "Ho", "Low", "Toh", "Sim", "Chong",
         "Chia", "Rahman", "Ismail", "Hassan", "Abdullah", "Kumar", "Nair", "Pillai", "Singh", "Fernandez", "De Souza"]

def _student_names():
    import random
    combos = [f"{a} {b}" for a in SFIRST for b in SLAST]; random.Random(2027).shuffle(combos)
    yield from combos

def _add_students(spec):
    """fictional students, each placed in one group of every block of their level, matching the group sizes on 6 Lessons:
    students in a lower level tag (G1, G2, Foundation) take that tag's groups where the block has them"""
    from .reader import derive
    from .spec import family as _family
    derive(spec)
    sc = spec["school"]; order = [t for t, _ in sc["tags"]]; names = _student_names(); out = []
    for lv in sc["levels"]:
        cls = [c for c in spec["classes"] if c["level"] == lv]
        if not cls: continue
        roster = {c["class"]: [dict(id=f"{c['class']}-{i:02d}", name=next(names), level=lv, groups=[], **{"class": c["class"]}) for i in range(1, int(c["size"]) + 1)] for c in cls}
        by_class = [s for c in cls for s in roster[c["class"]]]
        spread = [s for k in range(max(len(v) for v in roster.values())) for c in cls for s in roster[c["class"]][k:k + 1]]
        blocks = collections.OrderedDict()
        for x in spec["lessons"]:
            if x.get("block") and x["level"] == lv and x.get("code"): blocks.setdefault(x["block"], []).append(x)
        track, top, lower = {}, None, []
        tagged = [rs for rs in blocks.values() if len({r["tag"] for r in rs} - {"-"}) >= 2]
        if tagged:
            rs = max(tagged, key=lambda rs: (len({r["tag"] for r in rs}), -len({_family(r["subject"]) for r in rs})))
            cnt = collections.Counter()
            for r in rs: cnt[r["tag"]] += int(r.get("students") or 0)
            top = min(cnt, key=lambda t: order.index(t) if t in order else 99)
            lower = sorted((t for t in cnt if t != top), key=cnt.get)
            it = iter(spread)
            for t in lower:
                for _ in range(cnt[t]):
                    s = next(it, None)
                    if s: track[id(s)] = t
            for s in spread: track.setdefault(id(s), top)
        for name, rs in blocks.items():
            rem = {id(r): int(r.get("students") or 0) for r in rs}; done = set()
            def fill(r, pool):
                for s in pool:
                    if rem[id(r)] <= 0: break
                    if id(s) in done: continue
                    s["groups"].append(r["code"]); done.add(id(s)); rem[id(r)] -= 1
            low_rows = [r for r in rs if r["tag"] in lower]
            for r in low_rows: fill(r, [s for s in by_class if track.get(id(s)) == r["tag"]])
            low_fam = {_family(r["subject"]) for r in low_rows}; low_ids = {id(r) for r in low_rows}
            rest = sorted((r for r in rs if id(r) not in low_ids), key=lambda r: _family(r["subject"]) in low_fam)
            for r in rest:
                pool = [s for s in by_class if id(s) not in done]
                if low_rows: pool.sort(key=lambda s: track.get(id(s)) == top)
                fill(r, pool)
            for s in by_class:
                if id(s) not in done:
                    r = next((r for r in rs if r["tag"] == track.get(id(s))), rs[-1]); s["groups"].append(r["code"]); done.add(id(s))
        out += by_class
    spec["students"] = out
    return spec

def _split(n, k):
    return [n // k + (1 if i < n % k else 0) for i in range(k)]

def _build(school, day_structure, venues, classes, subjects, plan, rules, allowance, combinations=None):
    """plan: list of ('block', level, block name, classes, [(subject, groups, students)]) or ('class', level, subject, dept)"""
    dept = {s["subject"]: s["dept"] for s in subjects}
    per = {(s["subject"], lv): p for s in subjects for lv, p in s["periods"].items()}
    st = Staffing(allowance, school); blocks, lessons = [], []
    for item in plan:
        if item[0] == "block":
            _, lv, name, cls, groups = item
            blocks.append(dict(block=name, level=lv, classes=cls)); used = []
            for subj, k, n in groups:
                for size in _split(n, k):
                    t = st.pick(dept[subj], subj, lv, per[(subj, lv)], cls, avoid=used, prefer_class=False)
                    used.append(t)
                    lessons.append(dict(level=lv, subject=subj, block=name, classes=cls, teachers=[t], students=size))
    used_lv = collections.defaultdict(list)
    for item in plan:
        if item[0] == "class":
            _, lv, subj, cls_list = item
            for c in cls_list:
                any_d = dept[subj] in ("CCE", "PAL", "ALP")
                avoid = used_lv[(lv, subj)] if any_d else ()
                t = st.pick(dept[subj], subj, lv, per[(subj, lv)], [c], avoid=avoid, prefer_class=True, any_dept=any_d)
                used_lv[(lv, subj)].append(t)
                lessons.append(dict(level=lv, subject=subj, block=None, classes=[c], teachers=[t],
                                    students=next(x["size"] for x in classes if x["class"] == c)))
    teachers = st.teachers()
    # a part-time example: the teacher whose subjects have the fewest lessons a cycle
    def lessons_of(t):
        out = 0
        for l in lessons:
            if t in l["teachers"]:
                s = next(x for x in subjects if x["subject"] == l["subject"]); p_ = s["periods"][l["level"]]; L_ = s.get("lesson_length") or school["lesson_length"]
                out = max(out, -(-p_ // L_))
        return out
    part = min(teachers, key=lambda t: (lessons_of(t["name"]), -len(t["can_teach"])))["name"]
    return dict(school=school, day_structure=day_structure, venues=venues, classes=classes, subjects=subjects, teachers=teachers,
                blocks=blocks, lessons=lessons, rules=rules(teachers, part), students=[], combinations=combinations or [])

def _code(s):
    return {"English Language": "EL", "Mathematics": "MA", "Science": "SC", "Chinese": "CL", "Higher Chinese": "HC", "Malay": "ML", "Tamil": "TL",
            "Literature in English": "LE", "Geography": "GE", "History": "HI", "Art": "AR", "Music": "MU", "Physical Education": "PE",
            "Character and Citizenship Education": "CC", "Design & Technology": "DT", "Food and Consumer Education": "FC", "Applied Learning Programme": "AL",
            "Combined Science (Phy/Chem)": "PC", "Combined Science (Chem/Bio)": "CB", "Additional Mathematics": "AM", "Principles of Accounts": "PA",
            "Computing": "CO", "Food and Nutrition": "FN", "Humanities (Geography)": "HG", "Humanities (History)": "HH", "Social Studies": "SS",
            "Chinese Language": "CL", "Higher Chinese Language": "HC", "Malay Language": "ML", "Tamil Language": "TL",
            "Programme for Active Learning": "PL"}.get(re.sub(r"\s*\((Standard|Foundation)\)$|\s+G[123]$", "", s), s[:2].upper())

# ----------------------------------------------------------------- secondary
def secondary():
    sc = defaults("secondary"); days = day_names(sc["weeks"])
    lower = {"Mon": "F" + "L" * 6 + "RR" + "L" * 9 + "UU" + "LLL" + "AAA", "Thu": "F" + "L" * 6 + "RR" + "L" * 9 + "UU" + "AAA" + "...",
             "Fri": "F" + "L" * 6 + "RR" + "L" * 6 + "." * 11}
    upper = {"Mon": "F" + "LLL" + "RR" + "L" * 9 + "UU" + "L" * 6 + "AAA", "Thu": "F" + "LLL" + "RR" + "L" * 9 + "UU" + "LLL" + "AAA" + "...",
             "Fri": "F" + "LLL" + "RR" + "L" * 9 + "." * 11}
    def shape(tbl): return {d: tbl.get(d.split()[-1], tbl["Mon"]) for d in days}
    ds = {lv: shape(lower if lv in ("Sec 1", "Sec 2") else upper) for lv in sc["levels"]}
    venues = []
    for L in range(1, 5):
        for k in range(1, 5): venues.append(dict(room=f"A{L}-0{k}", kind="classroom", capacity=40, building="Block A", floor=L))
    for k in range(1, 13): venues.append(dict(room=f"B{(k - 1) // 4 + 1}-0{(k - 1) % 4 + 1}", kind="classroom", capacity=40, building="Block B", floor=(k - 1) // 4 + 1))
    for n, kd, cap in (("Science Lab 1", "lab", 40), ("Science Lab 2", "lab", 40), ("Science Lab 3", "lab", 40), ("Science Lab 4", "lab", 40), ("Computer Lab 1", "computer lab", 40),
                       ("Computer Lab 2", "computer lab", 40), ("Art Room 1", "art room", 40), ("Art Room 2", "art room", 40), ("D&T Studio 1", "d&t studio", 40),
                       ("D&T Studio 2", "d&t studio", 40), ("Food Lab 1", "food lab", 40), ("Food Lab 2", "food lab", 40), ("Music Room", "music room", 40),
                       ("Field", "pe venue", 80), ("Hall", "pe venue", 80), ("ISH", "pe venue", 40), ("Basketball Court", "pe venue", 40)):
        venues.append(dict(room=n, kind=kd, capacity=cap, building="Block C", floor=1))
    sizes = {"1": [38, 38, 37, 39], "2": [37, 38, 38, 36], "3": [38, 37, 38, 38], "4": [36, 38, 37, 38]}
    classes = [dict(class_=None)] and []
    for L in "1234":
        for k, ch in enumerate("ABCD"):
            classes.append(dict(**{"class": f"{L}{ch}"}, level=f"Sec {L}", size=sizes[L][k], home_room=f"A{L}-0{k + 1}"))
    S = []
    def subj(name, tag, dept, kind=None, length=None, **per):
        S.append(dict(subject=name, code=_code(name), tag=tag, dept=dept, room_kind=kind, lesson_length=length, periods={f"Sec {k[1]}": v for k, v in per.items()}))
    for g, p12, p34 in (("G3", 24, 18), ("G2", 24, 21), ("G1", 24, None)): subj(f"English Language {g}", g, "EL", s1=p12, s2=p12, **({"s3": p34, "s4": p34} if p34 else {}))
    for g, p12, p34 in (("G3", 20, 18), ("G2", 20, 21), ("G1", 28, None)): subj(f"Mathematics {g}", g, "MA", s1=p12, s2=p12, **({"s3": p34, "s4": p34} if p34 else {}))
    for g in ("G3", "G2", "G1"): subj(f"Science {g}", g, "SC", s1=20, s2=20)
    subj("Chinese G3", "G3", "MT", s1=20, s2=20, s3=18, s4=18); subj("Chinese G2", "G2", "MT", s1=20, s2=20); subj("Chinese G1", "G1", "MT", s1=14, s2=14)
    subj("Higher Chinese G3", "G3", "MT", s1=22, s2=22, s3=18, s4=18); subj("Malay G3", "G3", "MT", s1=20, s2=20, s3=18, s4=18); subj("Tamil G3", "G3", "MT", s1=20, s2=20, s3=18, s4=18)
    for n in ("Literature in English", "Geography", "History"): subj(n, "-", "EL" if n.startswith("Lit") else "HU", s1=6, s2=6)
    subj("Art", "-", "AE", "art room", s1=6, s2=6); subj("Music", "-", "AE", "music room", s1=6, s2=6)
    subj("Design & Technology", "-", "CT", "d&t studio", s1=12); subj("Food and Consumer Education", "-", "CT", "food lab", s2=12)
    subj("Applied Learning Programme", "-", "ALP", "computer lab", s1=3)
    subj("Combined Science (Phy/Chem) G3", "G3", "SC", "lab", s3=18, s4=18); subj("Combined Science (Chem/Bio) G3", "G3", "SC", "lab", s3=18, s4=18)
    subj("Combined Science (Phy/Chem) G2", "G2", "SC", "lab", s3=21, s4=21)
    subj("Additional Mathematics G3", "G3", "MA", s3=18, s4=18); subj("Principles of Accounts G3", "G3", "MA", s3=18, s4=18)
    subj("Literature in English G3", "G3", "EL", s3=18, s4=18)
    subj("Computing G3", "G3", "IT", "computer lab", s3=18, s4=18); subj("Design & Technology G3", "G3", "CT", "d&t studio", s3=18, s4=18)
    subj("Food and Nutrition G3", "G3", "CT", "food lab", s3=18, s4=18); subj("Art G3", "G3", "AE", "art room", s3=18, s4=18)
    subj("Humanities (Geography) G3", "G3", "HU", s3=9, s4=9); subj("Humanities (History) G3", "G3", "HU", s3=9, s4=9); subj("Social Studies", "-", "HU", s3=9, s4=9)
    subj("Physical Education", "-", "PE", "pe venue", s1=12, s2=12, s3=12, s4=12)
    subj("Character and Citizenship Education", "-", "CCE", s1=12, s2=12, s3=6, s4=6)
    plan = []
    for L in "12":
        lv, cls = f"Sec {L}", [f"{L}{c}" for c in "ABCD"]; n = sum(x["size"] for x in classes if x["level"] == lv)
        g1, g2 = 27, 35; g3 = n - g1 - g2
        plan.append(("block", lv, f"{lv} English", cls, [("English Language G3", 3, g3), ("English Language G2", 1, g2), ("English Language G1", 1, g1)]))
        plan.append(("block", lv, f"{lv} Mathematics", cls, [("Mathematics G3", 3, g3), ("Mathematics G2", 1, g2), ("Mathematics G1", 1, g1)]))
        plan.append(("block", lv, f"{lv} Science", cls, [("Science G3", 3, g3), ("Science G2", 1, g2), ("Science G1", 1, g1)]))
        plan.append(("block", lv, f"{lv} Mother Tongue", cls, [("Chinese G3", 2, 60), ("Higher Chinese G3", 1, 28), ("Chinese G2", 1, 22), ("Chinese G1", 1, 10),
                                                               ("Malay G3", 1, n - 60 - 28 - 22 - 10 - 12), ("Tamil G3", 1, 12)]))
        whole = ["Literature in English", "Geography", "History", "Art", "Music", "Physical Education", "Character and Citizenship Education"]
        whole += ["Design & Technology", "Applied Learning Programme"] if L == "1" else ["Food and Consumer Education"]
        for s in whole: plan.append(("class", lv, s, cls))
    for L in "34":
        lv, cls = f"Sec {L}", [f"{L}{c}" for c in "ABCD"]; n = sum(x["size"] for x in classes if x["level"] == lv); g2 = 34; g3 = n - g2
        plan.append(("block", lv, f"{lv} English", cls, [("English Language G3", 3, g3), ("English Language G2", 1, g2)]))
        plan.append(("block", lv, f"{lv} Mathematics", cls, [("Mathematics G3", 3, g3), ("Mathematics G2", 1, g2)]))
        plan.append(("block", lv, f"{lv} Mother Tongue", cls, [("Chinese G3", 2, 70), ("Higher Chinese G3", 1, 30), ("Malay G3", 1, n - 70 - 30 - 14), ("Tamil G3", 1, 14)]))
        plan.append(("block", lv, f"{lv} Science", cls, [("Combined Science (Phy/Chem) G3", 2, 80), ("Combined Science (Chem/Bio) G3", 1, g3 - 80), ("Combined Science (Phy/Chem) G2", 1, g2)]))
        plan.append(("block", lv, f"{lv} Option X", cls, [("Additional Mathematics G3", 2, 70), ("Principles of Accounts G3", 1, 40), ("Literature in English G3", 1, n - 110)]))
        plan.append(("block", lv, f"{lv} Option Y", cls, [("Computing G3", 1, 38), ("Design & Technology G3", 1, 38), ("Food and Nutrition G3", 1, 38), ("Art G3", 1, n - 114)]))
        plan.append(("block", lv, f"{lv} Humanities elective", cls, [("Humanities (Geography) G3", 2, 76), ("Humanities (History) G3", 2, n - 76)]))
        for s in ("Social Studies", "Physical Education", "Character and Citizenship Education"): plan.append(("class", lv, s, cls))
    def rules(teachers, part):
        return [dict(scope="School", target="Whole school", rule="Once a day per group", strength="Must", note="sample rule"),
                dict(scope="School", target="Whole school", rule="Avoid after-school slots", strength="Prefer", note="sample rule"),
                dict(scope="Subject", target="Physical Education", rule="At most N at once", number=4, strength="Must", note="sample rule"),
                dict(scope="Room", target="Field", rule="At most N at once", number=2, strength="Must", note="Field holds two classes"),
                dict(scope="Room", target="Hall", rule="At most N at once", number=2, strength="Must", note="Hall holds two classes"),
                dict(scope="Room", target="Hall", rule="Not available", week="Both", day="Mon", **{"from": 0, "to": 3}, strength="Must", note="Monday assembly"),
                dict(scope="Teacher", target=part, rule="Not available", week="Both", day="Fri", **{"from": 0, "to": 14}, strength="Must", note="part-time: not in on Fridays"),
                dict(scope="Level", target="Sec 3", subject="Character and Citizenship Education", rule="Same time across classes", strength="Must", note="level talks"),
                dict(scope="Department", target="MT", rule="Keep free together", week="Both", day="Wed", **{"from": 20, "to": 22}, strength="Prefer", note="MT department meeting"),
                dict(scope="Level", target="Sec 1", subject="Physical Education", rule="Not in periods", week="Both", day="All", **{"from": 20, "to": 22}, strength="Prefer", note="no PE in the last hour"),
                dict(scope="School", target="Whole school", rule="Max periods a day", number=15, strength="Prefer", note="teachers: at most 5 hours of lessons a day")]
    combos = [dict(level="Sec 3", code="S1", subjects=["Combined Science (Phy/Chem) G3", "Additional Mathematics G3", "Computing G3"], places=30),
              dict(level="Sec 3", code="S2", subjects=["Combined Science (Chem/Bio) G3", "Principles of Accounts G3", "Food and Nutrition G3"], places=30),
              dict(level="Sec 3", code="S3", subjects=["Combined Science (Phy/Chem) G2", "Literature in English G3", "Design & Technology G3"], places=30)]
    return _add_students(_build(sc, ds, venues, classes, S, plan, rules, allowance=64, combinations=combos))

# ----------------------------------------------------------------- primary
def primary():
    sc = defaults("primary"); days = day_names(sc["weeks"])
    shape = {"P1": "F" + "LLL" + "R" + "L" * 6 + "...", "P3": "F" + "LLLL" + "R" + "L" * 6 + "..", "P5": "F" + "LLLLL" + "R" + "L" * 5 + "AA"}
    key = {"P1": "P1", "P2": "P1", "P3": "P3", "P4": "P3", "P5": "P5", "P6": "P5"}
    ds = {lv: {d: shape[key[lv]] for d in days} for lv in sc["levels"]}
    venues = [dict(room=f"{L}-0{k}", kind="classroom", capacity=40, building="Block A", floor=(L + 1) // 2) for L in range(1, 7) for k in range(1, 4)]
    venues += [dict(room=f"R-0{k}", kind="classroom", capacity=40, building="Block B", floor=1) for k in range(1, 7)]
    venues += [dict(room=n, kind=kd, capacity=c, building="Block C", floor=1) for n, kd, c in
               (("Science Room 1", "science room", 40), ("Science Room 2", "science room", 40), ("Computer Lab", "computer lab", 40), ("Art Room", "art room", 40),
                ("Music Room", "music room", 40), ("Hall", "pe venue", 80), ("Field", "pe venue", 80), ("ISH", "pe venue", 40))]
    classes = []
    for L in range(1, 7):
        for k, ch in enumerate("ABC"):
            classes.append(dict(**{"class": f"{L}{ch}"}, level=f"P{L}", size=30 if L <= 2 else 38 - k, home_room=f"{L}-0{k + 1}"))
    S = []
    def subj(name, tag, dept, kind=None, length=None, **per):
        S.append(dict(subject=name, code=_code(name), tag=tag, dept=dept, room_kind=kind, lesson_length=length, periods={f"P{k[1]}": v for k, v in per.items()}))
    subj("English Language", "-", "EL", p1=13, p2=13, p3=12, p4=12)
    subj("English Language (Standard)", "Std", "EL", p5=12, p6=12); subj("English Language (Foundation)", "Fdn", "EL", p5=12, p6=12)
    subj("Mathematics", "-", "MA", p1=9, p2=9, p3=10, p4=10)
    subj("Mathematics (Standard)", "Std", "MA", p5=11, p6=11); subj("Mathematics (Foundation)", "Fdn", "MA", p5=11, p6=11)
    subj("Science", "-", "SC", "science room", p3=4, p4=5)
    subj("Science (Standard)", "Std", "SC", p5=6, p6=6); subj("Science (Foundation)", "Fdn", "SC", p5=6, p6=6)
    for n in ("Chinese Language", "Malay Language", "Tamil Language"): subj(n, "-", "MT", **{f"p{i}": 8 for i in range(1, 7)})
    subj("Higher Chinese Language", "Higher", "MT", **{f"p{i}": 9 for i in range(3, 7)})
    subj("Social Studies", "-", "SS", None, 1, p3=2, p4=2, p5=2, p6=2)
    subj("Art", "-", "AE", "art room", **{f"p{i}": 2 for i in range(1, 7)}); subj("Music", "-", "AE", "music room", 1, **{f"p{i}": 2 for i in range(1, 7)})
    subj("Physical Education", "-", "PE", "pe venue", p1=3, p2=3, p3=3, p4=3, p5=3, p6=2)
    subj("Character and Citizenship Education", "-", "CCE", None, 1, **{f"p{i}": 2 for i in range(1, 7)})
    subj("Programme for Active Learning", "-", "PAL", p1=3, p2=3)
    plan = []
    for L in range(1, 7):
        lv, cls = f"P{L}", [f"{L}{c}" for c in "ABC"]; n = sum(x["size"] for x in classes if x["level"] == lv)
        mt = [("Chinese Language", 2, n - 18 - 12 - (16 if L >= 3 else 0)), ("Malay Language", 1, 18), ("Tamil Language", 1, 12)]
        if L >= 3: mt.append(("Higher Chinese Language", 1, 16))
        plan.append(("block", lv, f"{lv} Mother Tongue", cls, mt))
        if L >= 5:
            for base in ("English Language", "Mathematics", "Science"):
                plan.append(("block", lv, f"{lv} {base}", cls, [(f"{base} (Standard)", 2, n - 22), (f"{base} (Foundation)", 1, 22)]))
            whole = ["Social Studies", "Art", "Music", "Physical Education", "Character and Citizenship Education"]
        else:
            whole = ["English Language", "Mathematics", "Art", "Music", "Physical Education", "Character and Citizenship Education"]
            whole += ["Science", "Social Studies"] if L >= 3 else ["Programme for Active Learning"]
        for s in whole: plan.append(("class", lv, s, cls))
    def rules(teachers, part):
        return [dict(scope="School", target="Whole school", rule="Once a day per group", strength="Prefer", note="sample rule (English and Maths may need two lessons on some days)"),
                dict(scope="School", target="Whole school", rule="Avoid after-school slots", strength="Prefer", note="P5-P6 supplementary slot only if needed"),
                dict(scope="Subject", target="Physical Education", rule="At most N at once", number=4, strength="Must", note="sample rule"),
                dict(scope="Room", target="Hall", rule="At most N at once", number=2, strength="Must", note="Hall holds two classes"),
                dict(scope="Room", target="Field", rule="At most N at once", number=2, strength="Must", note="Field holds two classes"),
                dict(scope="Room", target="Hall", rule="Not available", week="Both", day="Mon", **{"from": 0, "to": 1}, strength="Must", note="Monday assembly"),
                dict(scope="Teacher", target=part, rule="Not available", week="Both", day="Wed", **{"from": 0, "to": 13}, strength="Must", note="part-time: not in on Wednesdays"),
                dict(scope="Department", target="MT", rule="Keep free together", week="Both", day="Thu", **{"from": 11, "to": 12}, strength="Prefer", note="MT department meeting"),
                dict(scope="Level", target="P1", subject="Physical Education", rule="Not in periods", week="Both", day="All", **{"from": 9, "to": 10}, strength="Prefer", note="no PE in the last hour for P1")]
    return _add_students(_build(sc, ds, venues, classes, S, plan, rules, allowance=36))

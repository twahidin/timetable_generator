"""Plain-assert tests for sync.py: run with .venv/bin/python tests/test_sync.py"""
import copy
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sync  # noqa: E402


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def norm(x, top=True):
    """Compare form: no nulls, no `_` keys (except `_id`), rows ordered by _id."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if v is None or (k.startswith("_") and k != "_id"):
                continue
            if top and k in sync.LISTS and isinstance(v, list):
                v = sorted(v, key=lambda r: r.get("_id", ""))
            out[k] = norm(v, False)
        return out
    if isinstance(x, list):
        return [norm(v, False) for v in x]
    return x


def same(a, b):
    return canon(norm(a)) == canon(norm(b))


with open(os.path.join(HERE, "sync_cases.json"), encoding="utf-8") as f:
    CASES = json.load(f)

passed = 0
for case in CASES:
    name, base = case["name"], case["base"]
    if "ops" in case:
        got = sync.diff(base, case["cur"])
        assert canon(got) == canon(case["ops"]), (name, "diff", canon(got))
        spec = copy.deepcopy(base)
        assert sync.apply(spec, case["ops"]) == 0, (name, "skipped")
        assert same(spec, case["cur"]), (name, "apply", canon(norm(spec)))
    else:
        spec = copy.deepcopy(base)
        sync.apply(spec, case["theirs"])
        sync.apply(spec, case["mine"])
        assert same(spec, case["merged"]), (name, "merge", canon(norm(spec)))
    passed += 1

# constants and ids
assert sync.MERGE == {"teachers": ("can_teach",), "students": ("groups",)}
assert sync.LISTS == ("venues", "classes", "subjects", "teachers", "blocks", "lessons",
                      "rules", "students", "combinations", "roles", "choices")
i = sync.new_id()
assert len(i) == 10 and all(c in "abcdefghijklmnopqrstuvwxyz0123456789" for c in i)
assert sync.new_id() != sync.new_id()

# ensure_ids
spec = {"school": {"name": "A"}, "classes": [{"class": "1A"}, {"_id": "keep", "class": "1B"}],
        "teachers": [{"name": "Tan"}]}
assert sync.ensure_ids(spec) is True
assert spec["classes"][1]["_id"] == "keep"
ids = [spec["classes"][0]["_id"], spec["teachers"][0]["_id"]]
assert all(len(x) == 10 for x in ids) and ids[0] != ids[1]
before = copy.deepcopy(spec)
assert sync.ensure_ids(spec) is False and spec == before
assert sync.ensure_ids({"school": {}}) is False
passed += 1

# skips and edge behaviour
spec = {"classes": [{"_id": "c1", "size": 1}]}
assert sync.apply(spec, [["set", "classes", "zz", "size", 2], ["del", "classes", "zz"],
                         ["add", "classes", {"_id": "c1"}, ""],
                         ["merge", "classes", "zz", "x", [], []],
                         ["bogus"], ["top", "classes", []]]) == 6
assert spec == {"classes": [{"_id": "c1", "size": 1}]}
assert sync.apply(spec, [["add", "classes", {"_id": "c0"}, ""],
                         ["add", "classes", {"_id": "c9"}, "nope"],
                         ["set", "classes", "c1", "size", None],
                         ["top", "extra_sheets", {"a": 1}]]) == 0
assert [r["_id"] for r in spec["classes"]] == ["c0", "c1", "c9"]
assert spec["classes"][1] == {"_id": "c1"} and spec["extra_sheets"] == {"a": 1}
passed += 1

# malformed merge lists are skipped, never half-applied or raised
for bad in ("x", {"a": 1}, None, 5):
    for pos in (4, 5):
        op = ["merge", "teachers", "t1", "can_teach", [], []]
        op[pos] = bad
        spec = {"teachers": [{"_id": "t1", "can_teach": [1]}]}
        assert sync.apply(spec, [op]) == 1, ("merge", bad, pos)
        assert spec == {"teachers": [{"_id": "t1", "can_teach": [1]}]}
passed += 1

# non-dict school / day_structure / level are replaced, not raised on
spec = {"school": None, "day_structure": None}
assert sync.apply(spec, [["school", "name", "B"], ["day", "Sec 1", "Mon", "FL"]]) == 0
assert spec == {"school": {"name": "B"}, "day_structure": {"Sec 1": {"Mon": "FL"}}}
spec = {"day_structure": {"Sec 1": None, "Sec 2": "x"}}
assert sync.apply(spec, [["day", "Sec 1", "Mon", "FL"], ["day", "Sec 2", "Mon", None]]) == 0
assert spec["day_structure"]["Sec 1"] == {"Mon": "FL"}
spec = {"school": "oops"}
assert sync.apply(spec, [["school", "name", None]]) == 0 and spec["school"] == {}
passed += 1

# what a head of department may change
spec = {"teachers": [{"_id": "t1", "provisional": "No"}, {"_id": "t2", "provisional": "Yes"}, {"_id": "t3"}], "classes": [{"_id": "c1"}]}
for ok in ([["set", "lessons", "l1", "students", 12]], [["add", "blocks", {"_id": "b9"}, ""]], [["del", "lessons", "l1"]],
           [["add", "teachers", {"_id": "t9", "provisional": "No"}, ""]],
           [["set", "teachers", "t2", "name", "X"]], [["set", "teachers", "t2", "dept", "SC"]], [["del", "teachers", "t2"]], []):
    assert sync.head_may(spec, ok) is None, ok
for bad in ([["set", "classes", "c1", "size", 9]], [["school", "name", "X"]], [["day", "Sec 1", "Mon", "FL"]], [["top", "k", 1]],
            [["set", "teachers", "t1", "name", "X"]], [["set", "teachers", "t3", "name", "X"]], [["del", "teachers", "t1"]],
            [["merge", "teachers", "t1", "can_teach", [], []]], [["set", "teachers", "t2", "dept2", "SC"]],
            [["set", "teachers", "t2", "provisional", "No"]], [["add", "classes", {"_id": "c2"}, ""]],
            [["set", "lessons", "l1", "students", 1], ["set", "classes", "c1", "size", 9]], ["x"], [[]], [["set"]]):
    why = sync.head_may(spec, bad)
    assert isinstance(why, str) and why.endswith("."), bad
assert "classes" in sync.head_may(spec, [["set", "classes", "c1", "size", 9]])
assert sync.head_may(spec, [["set", "teachers", "t2", "dept2", "SC"]]) == "Only the committee gives a teacher a second department."
assert sync.head_may(spec, [["merge", "teachers", "t1", "can_teach", [], []]]) == "Department heads can only add a teacher, or edit a provisional teacher."
passed += 1

# a head's batch is split: what they may make is applied, the rest is refused with a reason (index in the batch)
spec = {"teachers": [{"_id": "t1", "provisional": "No"}], "classes": [{"_id": "c1"}]}
batch = [["set", "lessons", "l1", "students", 12], ["set", "classes", "c1", "size", 9],
         ["add", "teachers", {"_id": "t9", "name": "N"}, ""], ["set", "teachers", "t9", "short", "NN"],
         ["set", "teachers", "t1", "name", "X"]]
ok, refused = sync.head_split(spec, batch)
assert ok == [batch[0], batch[2], batch[3]], ok
assert [i for i, _ in refused] == [1, 4], refused
assert refused[0][1] == sync.head_may(spec, [batch[1]]) and "classes" in refused[0][1]
assert "provisional" in refused[1][1] and all(w.endswith(".") for _, w in refused)
assert sync.head_split(spec, []) == ([], [])
assert sync.head_may(spec, batch) == refused[0][1]
assert sync.head_split(spec, ["x", [["set"]]])[1][0] == (0, "Department heads cannot send that change.")
passed += 1

# choices are a list; ensure_ids links each to its rule by the rule's _id, and a head cannot touch them
spec = {"rules": [{"rule": "In words"}], "choices": [{"kind": "rule", "rule": 0}, {"kind": "rule", "rule": 7}]}
assert "choices" in sync.LISTS
assert sync.ensure_ids(spec) is True
a, b = spec["choices"]
assert a["_id"] and b["_id"] and a["rule_id"] == spec["rules"][0]["_id"] and b["rule_id"] is None, spec
assert "rule" not in a and "rule" not in b, spec
assert sync.ensure_ids(spec) is False
why = sync.head_split(spec, [["add", "choices", {"kind": "rule"}, ""]])[1][0][1]
assert "choices" in why, why
passed += 1

# a list section that is null or not a list: add starts it as a list, del / set / merge skip (same as sync.js)
for bad in (None, "x", {"a": 1}):
    spec = {"roles": bad}
    assert sync.apply(spec, [["add", "roles", {"_id": "r1", "role": "EO"}, ""]]) == 0, bad
    assert spec == {"roles": [{"_id": "r1", "role": "EO"}]}, spec
    spec = {"roles": bad}
    assert sync.apply(spec, [["del", "roles", "r1"], ["set", "roles", "r1", "role", "X"],
                             ["merge", "roles", "r1", "x", [1], []]]) == 3, bad
    assert spec == {"roles": bad}
passed += 1

# a head may not touch the lessons the Class Parents take: the staffed rows' teachers, mark, subject, block, code, classes,
# level, nor delete one, nor make a row staffed that was not (an add, or a set that leaves it staffed)
SUBJ = "Form Period"
def staffed_setup():
    return {"school": {"parents_subjects": [SUBJ]}, "subjects": [{"_id": "s1", "subject": SUBJ}, {"_id": "s2", "subject": "Maths"}],
            "classes": [{"_id": "c1", "class": "1A", "level": "Sec 1", "parents": ["Lim", "Tan"]}, {"_id": "c2", "class": "1B", "level": "Sec 1"}],
            "lessons": [dict(_id="L1", level="Sec 1", subject=SUBJ, block=None, classes=["1A"], teachers=["Lim", "Tan"]),
                        dict(_id="L2", level="Sec 1", subject="Maths", block=None, classes=["1A"], teachers=["Ong"]),
                        dict(_id="L3", level="Sec 1", subject=SUBJ, block="Band A", classes=["1A"], teachers=["Ong"])]}
sp = staffed_setup()
WHY = "Only the committee can change these lessons: their teachers are the class's form teachers."
for op in (["set", "lessons", "L1", "teachers", ["Koh"]], ["set", "lessons", "L1", "by_hand", True], ["del", "lessons", "L1"],
           ["set", "lessons", "L1", "subject", "Maths"], ["set", "lessons", "L1", "block", "Band A"], ["set", "lessons", "L1", "classes", ["1B"]],
           ["set", "lessons", "L1", "level", "Sec 2"], ["set", "lessons", "L1", "code_override", "X"],
           ["set", "lessons", "L2", "subject", SUBJ],                    # the ordinary row would become staffed
           ["set", "lessons", "L3", "block", None],                      # so would a block row with its block cleared
           ["add", "lessons", dict(_id="n1", level="Sec 1", subject=SUBJ, block=None, classes=["1B"], teachers=[]), ""]):
    assert sync.head_may(sp, [op]) == WHY, op
for op in (["set", "lessons", "L2", "teachers", ["Koh"]], ["set", "lessons", "L1", "note", "x"], ["set", "lessons", "L1", "students", 9],
           ["set", "lessons", "L3", "teachers", ["Koh"]],                # a block row of the named subject is not staffed
           ["add", "lessons", dict(_id="n2", level="Sec 1", subject=SUBJ, block="Band A", classes=["1B"], teachers=[]), ""],
           ["add", "lessons", dict(_id="n3", level="Sec 1", subject="Maths", block=None, classes=["1B"], teachers=[]), ""], ["del", "lessons", "L2"]):
    assert sync.head_may(sp, [op]) is None, op
assert sync.head_split(sp, [["set", "lessons", "L2", "students", 1], ["del", "lessons", "L1"]]) == ([["set", "lessons", "L2", "students", 1]], [(1, WHY)])
# one batch cannot get round it: each op is judged on the setup as the allowed ones before it leave it
for first, then in ((dict(_id="n8", level="Sec 1", subject="Maths", block=None, classes=["1A"], teachers=["Typed T"]), ["set", "lessons", "n8", "subject", SUBJ]),
                    (dict(_id="n8", level="Sec 1", subject=SUBJ, block="Band A", classes=["1B"], teachers=[]), ["set", "lessons", "n8", "block", None])):
    ok, refused = sync.head_split(sp, [["add", "lessons", first, ""], then])
    assert ok == [["add", "lessons", first, ""]] and refused == [(1, WHY)], (ok, refused)
    assert [r["_id"] for r in sp["lessons"]] == ["L1", "L2", "L3"]       # the setup judged on is not changed
# a malformed lessons op from a head is refused with the usual sentence and never raises; a merge on a lesson is refused whatever the field
SEND = "Department heads cannot send that change."
for op in (["set", "lessons", "L1"], ["set", "lessons", "L1", "note"], ["set", "lessons", "L2", "students", 1, 2], ["set", "lessons"], ["del", "lessons"], ["add", "lessons"],
           ["merge", "lessons", "L2", "classes"], ["merge", "lessons", "L2", "classes", "x", []], ["set", "lessons", 5, "note", "x"], ["set", "lessons", "L2", 7, "x"]):
    assert sync.head_may(sp, [op]) == SEND, op
assert sync.head_split(sp, [["set", "lessons", "L2"], ["set", "lessons", "L2", "students", 1]]) == ([["set", "lessons", "L2", "students", 1]], [(0, SEND)])
assert sync.head_may(sp, [["merge", "lessons", "L3", "block", [], []]]) == WHY     # a group row would become a staffed row
assert sync.head_may(sp, [["merge", "lessons", "L1", "classes", [], []]]) == WHY   # a staffed row
assert sync.head_may(sp, [["merge", "lessons", "L2", "classes", ["1B"], []]]) == SEND
assert sync.head_may(sp, [["merge", "lessons", "L2", "block", [], []]]) == SEND
passed += 1

# ---- a head signed in as a person changes only their own departments' rows (depts given; None = the shared heads' code, as above)
from ttgen import samples  # noqa: E402

OTHER = "This row is another department's: only its head or the committee can change it."
NOSUB = "Choose a subject of your department for this row first."
BOTHERS = "This band holds another department's groups: only the committee can rename or delete it."
BNOT = "This band holds none of your department's groups."
TDEPT = "You can put a new teacher only in your own department."
assert (sync.OTHER_DEPT, sync.NO_SUBJECT, sync.BAND_OTHERS, sync.BAND_NOT_YOURS, sync.TEACHER_DEPT) == (OTHER, NOSUB, BOTHERS, BNOT, TDEPT)


def sample():
    s = samples.secondary()
    sync.ensure_ids(s)
    return s


def sent(base, edit):
    """The ops the page sends for an edit on step 5: the edit is made on the setup, the page gives new rows ids
    (Sync.ensureIds) and sends Sync.diff of the setup before and after, which sync.diff mirrors."""
    cur = copy.deepcopy(base)
    edit(cur)
    sync.ensure_ids(cur)
    return sync.diff(base, cur)


def size_of(s, c):
    return next((int(x.get("size") or 0) or None for x in s["classes"] if x.get("class") == c), None)


# the Add bars and band edits, made as static/app.js, static/groups.js and static/map.js make them
def whole_bar(level, subject, pattern=None):          # app.js addFromBar "whole" (Add a whole-class subject): one row per class
    def edit(s):
        for c in [c for c in s["classes"] if c.get("level") == level]:
            row = dict(level=level, subject=subject, block=None, classes=[c["class"]], teachers=[], students=c.get("size"))
            if pattern:
                row["pattern"] = list(pattern)
            s["lessons"].append(row)
    return edit


def one_per_class(level, subject, classes):           # groups.js addOnePerClass ("gfeach"): a whole-class row for each class lacking one
    def edit(s):
        for c in classes:
            if any(x.get("subject") == subject and not x.get("block") and not x.get("code_override") and c in (x.get("classes") or []) for x in s["lessons"]):
                continue
            s["lessons"].append(dict(level=level, subject=subject, block=None, classes=[c], teachers=[], students=size_of(s, c)))
    return edit


def new_group(level, subject, block=None, classes=None, students=None, keep=None):   # groups.js newGroup ("gfadd"); keep: pullOutCode's code
    def edit(s):
        band = next((b for b in s["blocks"] if b.get("block") == block), None) if block else None
        row = dict(level=level, subject=subject, block=block or None, classes=list(classes or (band or {}).get("classes") or []),
                   teachers=[], students=students or None)
        if keep:
            row["code_override"] = keep
        s["lessons"].append(row)
    return edit


def band_groups(block, subject, n, students=None):    # app.js addFromBar "groups": n teaching groups in a band
    def edit(s):
        b = next(b for b in s["blocks"] if b.get("block") == block)
        for _ in range(n):
            s["lessons"].append(dict(level=b["level"], subject=subject, block=b["block"], classes=list(b.get("classes") or []), teachers=[], students=students))
    return edit


def table_lesson(level):                              # app.js the Table view's "+ Add" teaching group: a blank row
    return lambda s: s["lessons"].append(dict(level=level, subject=None, block=None, classes=[], teachers=[], students=None))


def new_band(block, level, classes, everyone=None):   # groups.js newBand ("bfadd")
    def edit(s):
        b = dict(block=block, level=level, classes=list(classes))
        if everyone is not None:
            b["everyone"] = everyone
        s["blocks"].append(b)
    return edit


def table_band(level):                                # app.js the Table view's "+ Add band": a blank band
    return lambda s: s["blocks"].append(dict(block="", level=level, classes=[]))


def rename_band(block, to):                           # groups.js renameBand: the band, its groups and the step 6 rules naming it
    def edit(s):
        for x in s["lessons"]:
            if x.get("block") == block:
                x["block"] = to
        for r in s["rules"]:
            if r.get("scope") == "Block" and r.get("target") == block:
                r["target"] = to
        next(b for b in s["blocks"] if b.get("block") == block)["block"] = to
    return edit


def drop_band(block, keep):                           # groups.js dropBand: its groups deleted with it, or kept as single groups
    def edit(s):
        band = next(b for b in s["blocks"] if b.get("block") == block)
        if keep:
            for n, x in enumerate(x for x in s["lessons"] if x.get("block") == block):
                x["block"] = None                      # fromBand
                if not x.get("code_override") and (x.get("students") or 0) < sum(size_of(s, c) or 0 for c in x.get("classes") or []):
                    x["code_override"] = f"9KC{n + 1}"   # a pull-out group keeps a code of its own (the code's text is the page's)
        else:
            s["lessons"] = [x for x in s["lessons"] if x.get("block") != block]
        s["blocks"].remove(band)
    return edit


def new_teacher(name, dept, role=""):                 # map.js newTeacher (+ New teacher on the department map), as a head's page makes it
    return lambda s: s["teachers"].append(dict(name=name, short=name.split(" ")[0], dept=dept, role=role, allowance=None, provisional="Yes"))


def teachers_bar(names, dept):                        # app.js addFromBar "teachers" (step 4), as a head's page makes it
    return lambda s: s["teachers"].extend(dict(name=n, short=n.split(" ")[0], dept=dept, allowance=None, provisional="Yes") for n in names)


def split(spec, ops, depts):
    before = copy.deepcopy(spec)
    out = sync.head_split(spec, ops, depts)
    assert spec == before, "the setup judged on is not changed"
    return out


base = sample()
L = base["lessons"]
sc = next(x for x in L if sync.lesson_dept(base, x) == "SC")
ma = next(x for x in L if sync.lesson_dept(base, x) == "MA")
sci_band = next(b for b in base["blocks"] if b["block"] == "Sec 1 Science")
opt_x = next(b for b in base["blocks"] if b["block"] == "Sec 3 Option X")
assert {sync.lesson_dept(base, x) for x in sync.band_lessons(base, sci_band)} == {"SC"}
assert {sync.lesson_dept(base, x) for x in sync.band_lessons(base, opt_x)} == {"MA", "EL"}

# band_lessons: the lessons whose block is the band's name and level its level
got = sync.band_lessons(base, sci_band)
assert got and all(x["block"] == "Sec 1 Science" and x["level"] == "Sec 1" for x in got)
assert len(got) == sum(1 for x in L if x.get("block") == "Sec 1 Science" and x.get("level") == "Sec 1")
assert sync.band_lessons(base, dict(sci_band, level="Sec 2")) == []
assert sync.band_lessons(base, {"block": "", "level": "Sec 1"}) == [] and sync.band_lessons(base, None) == []
passed += 1

# a lesson row: their own changed, allowed; another department's, refused; moved into another department, refused
own = sent(base, lambda s: next(x for x in s["lessons"] if x["_id"] == sc["_id"]).update(teachers=["Typed Teacher"]))
assert own and split(base, own, ["SC"]) == (own, [])
assert split(base, own, ["MA"]) == ([], [(0, OTHER)])
assert split(base, own, ["MA", "SC"]) == (own, [])
assert split(base, own, (" SC ",)) == (own, [])                    # trimmed, any sequence
assert split(base, own, []) == ([], [(0, OTHER)])                   # a head with no departments changes no row
moved = sent(base, lambda s: next(x for x in s["lessons"] if x["_id"] == sc["_id"]).update(subject="Mathematics G3"))
assert split(base, moved, ["SC"]) == ([], [(0, OTHER)])             # out of their department
assert split(base, moved, ["MA"]) == ([], [(0, OTHER)])             # nor into it
assert split(base, moved, ["SC", "MA"]) == (moved, [])
dele = [["del", "lessons", ma["_id"]]]
assert split(base, dele, ["SC"]) == ([], [(0, OTHER)]) and split(base, dele, ["MA"]) == (dele, [])
assert sync.head_may(base, own, ["MA"]) == OTHER and sync.head_may(base, own, ["SC"]) is None
assert sync.head_may(base, own) is None and sync.head_split(base, own) == (own, [])       # the shared heads' code: as today
passed += 1

# every Add bar on step 5, as the page sends it: a subject of their department, allowed; an empty one or one with no
# department, NO_SUBJECT; another department's, OTHER_DEPT
nodept = copy.deepcopy(base)
nodept["subjects"].append({"_id": "nsubj00001", "subject": "Study Skills"})
bars = {
    "whole-class subject": lambda subj: whole_bar("Sec 1", subj),
    "whole-class subject with lessons": lambda subj: whole_bar("Sec 2", subj, pattern=[3, 3, 2]),
    "one per class": lambda subj: one_per_class("Sec 1", subj, ["1A", "1B"]),
    "teaching group in a band": lambda subj: new_group("Sec 1", subj, block="Sec 1 Science", students=30),
    "teaching group of its own": lambda subj: new_group("Sec 1", subj, classes=["1A"], students=12, keep="1XX9"),
    "groups in a band": lambda subj: band_groups("Sec 3 Option X", subj, 2, students=20),
}
for label, bar in bars.items():
    ops = sent(base, bar("Science G3"))
    assert ops and all(o[0] == "add" and o[1] == "lessons" for o in ops), (label, ops)
    assert split(base, ops, ["SC"]) == (ops, []), label
    assert split(base, ops, ["MA"]) == ([], [(i, OTHER) for i in range(len(ops))]), label
    ops = sent(base, bar(""))
    assert split(base, ops, ["SC"]) == ([], [(i, NOSUB) for i in range(len(ops))]), label
    ops = sent(nodept, bar("Study Skills"))
    assert split(nodept, ops, ["SC"]) == ([], [(i, NOSUB) for i in range(len(ops))]), label
    assert sync.head_split(nodept, ops) == (ops, []), label                   # the shared heads' code: as today
ops = sent(base, table_lesson("Sec 1"))
assert len(ops) == 1 and "subject" not in ops[0][2]
assert split(base, ops, ["SC"]) == ([], [(0, NOSUB)])
# a band: anyone may add one (it holds no groups yet), from the Groups bar or the Table view
for ops in (sent(base, new_band("Sec 1 Science Plus", "Sec 1", ["1A", "1B"])), sent(base, new_band("Sec 1 Option Z", "Sec 1", ["1A"], everyone=False)),
            sent(base, table_band("Sec 2"))):
    assert len(ops) == 1 and ops[0][:2] == ["add", "blocks"], ops
    assert split(base, ops, ["SC"]) == (ops, []) and split(base, ops, []) == (ops, [])
passed += 1

# a new band added and its classes set in one batch: allowed (the set is judged on the batch's band)
mid = copy.deepcopy(base)
new_band("Sec 1 Science Plus", "Sec 1", ["1A"])(mid)
sync.ensure_ids(mid)
first = sync.diff(base, mid)
later = sent(mid, lambda s: next(b for b in s["blocks"] if b["block"] == "Sec 1 Science Plus").update(classes=["1A", "1B"]))
batch = first + later
assert [o[0] for o in batch] == ["add", "set"]
assert split(base, batch, ["SC"]) == (batch, [])
spec = copy.deepcopy(base)
assert sync.apply(spec, batch) == 0 and next(b for b in spec["blocks"] if b["block"] == "Sec 1 Science Plus")["classes"] == ["1A", "1B"]
# ...and renamed in the same batch (it holds none of anyone's groups)
batch2 = batch + sent(mid, rename_band("Sec 1 Science Plus", "Sec 1 Science Extra"))
assert split(base, batch2, ["MA"]) == (batch2, [])
passed += 1

# any other change to a band: allowed when it holds one of their groups (or none at all), else BAND_NOT_YOURS
classes_x = sent(base, lambda s: next(b for b in s["blocks"] if b["_id"] == opt_x["_id"]).update(classes=["3A", "3B"]))
note_x = sent(base, lambda s: next(b for b in s["blocks"] if b["_id"] == opt_x["_id"]).update(note="Typed note"))
for ops in (classes_x, note_x, [["merge", "blocks", opt_x["_id"], "classes", ["3E"], []]]):
    assert split(base, ops, ["MA"]) == (ops, []) and split(base, ops, ["EL"]) == (ops, []), ops    # a shared band: each head with a group in it
    assert split(base, ops, ["SC"]) == ([], [(0, BNOT)]), ops
    assert sync.head_split(base, ops) == (ops, [])
empty = copy.deepcopy(base)
new_band("Sec 2 Empty", "Sec 2", ["2A"])(empty)
sync.ensure_ids(empty)
eb = next(b for b in empty["blocks"] if b["block"] == "Sec 2 Empty")
ops = [["set", "blocks", eb["_id"], "classes", ["2B"]]]
assert split(empty, ops, ["SC"]) == (ops, [])
passed += 1

# renaming a band: with its groups' block, judged as one. Only their own groups in it: all allowed
ren = sent(base, rename_band("Sec 1 Science", "Sec 1 Sciences"))
assert ren[0] == ["set", "blocks", sci_band["_id"], "block", "Sec 1 Sciences"]
assert len(ren) == 1 + len(sync.band_lessons(base, sci_band)) and all(o[:1] + o[3:] == ["set", "block", "Sec 1 Sciences"] for o in ren[1:])
assert split(base, ren, ["SC"]) == (ren, [])
assert split(base, ren, ["MA"]) == ([], [(i, BOTHERS) for i in range(len(ren))])     # none of theirs in it: the committee's
assert sync.head_split(base, ren) == (ren, [])
# a band shared with another department: all of it refused, nothing applied
ren = sent(base, rename_band("Sec 3 Option X", "Sec 3 Option W"))
assert len(ren) == 1 + len(sync.band_lessons(base, opt_x))
ok, refused = split(base, ren, ["MA"])
assert ok == [] and refused == [(i, BOTHERS) for i in range(len(ren))], (ok, refused)
spec = copy.deepcopy(base)
assert sync.apply(spec, ok) == 0 and spec == base
assert split(base, ren, ["MA", "EL"]) == (ren, [])                 # a head of both: all of it
# leaving out the other department's group does not get round it: the band is judged on every group in it
mine_only = [o for o in ren if o[1] == "blocks" or sync.lesson_dept(base, sync._find(base, "lessons", o[2])) == "MA"]
assert len(mine_only) < len(ren)
assert split(base, mine_only, ["MA"]) == ([], [(i, BOTHERS) for i in range(len(mine_only))])
# nor does sending the other department's group's move alone: that is a change to their row
el = next(o for o in ren if o[1] == "lessons" and sync.lesson_dept(base, sync._find(base, "lessons", o[2])) == "EL")
assert split(base, [el], ["MA"]) == ([], [(0, OTHER)])
# their own group in the shared band moved out of it, alone, is theirs to move
mo = next(o for o in ren if o[1] == "lessons" and sync.lesson_dept(base, sync._find(base, "lessons", o[2])) == "MA")
assert split(base, [mo], ["MA"]) == ([mo], [])
# the band's name or level typed in the Table view (the band row alone) is a rename too
for op in (["set", "blocks", opt_x["_id"], "block", "Sec 3 Option W"], ["set", "blocks", opt_x["_id"], "level", "Sec 4"],
           ["merge", "blocks", opt_x["_id"], "block", [], []], ["merge", "blocks", opt_x["_id"], "level", [], []]):
    assert split(base, [op], ["MA"]) == ([], [(0, BOTHERS)]), op
    assert sync.head_split(base, [op]) == ([op], [])
for op in (["set", "blocks", sci_band["_id"], "block", "Sec 1 Sciences"], ["set", "blocks", sci_band["_id"], "level", "Sec 2"]):
    assert split(base, [op], ["SC"]) == ([op], []), op
passed += 1

# deleting a band: with its groups (deleted, or kept as single groups), judged as one
for keep in (False, True):
    ops = sent(base, drop_band("Sec 1 Science", keep))
    assert ops[0] == ["del", "blocks", sci_band["_id"]] and len(ops) > 1, ops
    assert split(base, ops, ["SC"]) == (ops, []), keep
    assert split(base, ops, ["MA"]) == ([], [(i, BOTHERS) for i in range(len(ops))]), keep
    ops = sent(base, drop_band("Sec 3 Option X", keep))
    if keep:
        assert any(o[3] == "code_override" for o in ops if o[0] == "set"), ops
    ok, refused = split(base, ops, ["MA"])
    assert ok == [] and refused == [(i, BOTHERS) for i in range(len(ops))], (keep, ok, refused)
    spec = copy.deepcopy(base)
    assert sync.apply(spec, ok) == 0 and spec == base
    assert split(base, ops, ["EL", "MA"]) == (ops, [])
    assert sync.head_split(base, ops) == (ops, [])
assert split(base, [["del", "blocks", opt_x["_id"]]], ["MA"]) == ([], [(0, BOTHERS)])      # the band row alone (the Table view's delete)
assert split(base, [["del", "blocks", sci_band["_id"]]], ["SC"]) == ([["del", "blocks", sci_band["_id"]]], [])
passed += 1

# the rest of a batch is still judged one operation at a time around a refused band change
batch = own + sent(base, rename_band("Sec 3 Option X", "Sec 3 Option W"))
ok, refused = split(base, batch, ["SC", "MA"])
assert ok == own and [i for i, _ in refused] == list(range(1, len(batch))) and {w for _, w in refused} == {BOTHERS}
passed += 1

# the Class Parents' lessons first, as today; and a band change part of which today's rules refuse is refused whole
cp = copy.deepcopy(base)
cp["school"]["parents_subjects"] = ["Science G1"]
g1 = [x for x in sync.band_lessons(cp, sci_band) if x["subject"] == "Science G1"]
assert g1
ops = sent(cp, drop_band("Sec 1 Science", True))
ok, refused = split(cp, ops, ["SC"])
assert ok == [] and len(refused) == len(ops) and {w for _, w in refused} == {WHY}, (ok, refused)
today = sync.head_split(cp, ops)[1]                                 # the shared heads' code: one at a time, as today
assert today and all(w == WHY for _, w in today) and len(today) < len(ops)
cpw = copy.deepcopy(base)
cpw["school"]["parents_subjects"] = ["Science G3"]
cpw["lessons"].append(dict(_id="cpwhole001", level="Sec 1", subject="Science G3", block=None, classes=["1A"], teachers=["Typed T"]))
assert split(cpw, [["set", "lessons", "cpwhole001", "teachers", ["Other T"]]], ["SC"]) == ([], [(0, WHY)])
assert split(cpw, [["set", "lessons", "cpwhole001", "teachers", ["Other T"]]], ["MA"]) == ([], [(0, WHY)])
passed += 1

# teachers: a new teacher only in their department; head_prepare does to a head's teacher add what the app did
prov = copy.deepcopy(base)
prov["teachers"].append({"_id": "provt00001", "name": "Typed Prov", "dept": "SC", "provisional": "Yes"})
assert split(prov, [["set", "teachers", "provt00001", "dept", "MA"]], ["SC"]) == ([], [(0, TDEPT)])
assert split(prov, [["set", "teachers", "provt00001", "dept", None]], ["SC"]) == ([], [(0, TDEPT)])
assert split(prov, [["set", "teachers", "provt00001", "dept", "SC"]], ["SC"]) == ([["set", "teachers", "provt00001", "dept", "SC"]], [])
assert split(prov, [["set", "teachers", "provt00001", "name", "Typed Two"]], ["SC"]) == ([["set", "teachers", "provt00001", "name", "Typed Two"]], [])
assert sync.head_split(prov, [["set", "teachers", "provt00001", "dept", "MA"]]) == ([["set", "teachers", "provt00001", "dept", "MA"]], [])
t1 = base["teachers"][0]
assert t1.get("provisional") == "No"
assert split(base, [["set", "teachers", t1["_id"], "dept", "MA"]], ["SC"])[1] == [(0, "Department heads can change a teacher's details only while the teacher is provisional.")]
assert split(prov, [["set", "teachers", "provt00001", "dept2", "SC"]], ["SC"])[1] == [(0, "Only the committee gives a teacher a second department.")]
for make in (new_teacher("Typed New", "MA"), teachers_bar(["Typed One", "Typed Two"], "MA"), new_teacher("Typed Blank", "")):
    ops = sent(base, make)
    assert ops and all(o[:2] == ["add", "teachers"] for o in ops)
    for o in ops:
        o[2]["provisional"], o[2]["dept2"] = "No", "EL"              # what a page could send
    assert split(base, ops, ["SC"])[1] == [(i, TDEPT) for i in range(len(ops))]      # judged as sent, before head_prepare
    plain = copy.deepcopy(ops)
    sync.head_prepare(plain)                                          # the shared heads' code: as the app did
    assert all(o[2]["provisional"] == "Yes" and "dept2" not in o[2] and o[2]["dept"] == ops[0][2]["dept"] for o in plain), plain
    sync.head_prepare(ops, ["SC", "MA2"])
    assert all(o[2]["dept"] == "SC" and o[2]["provisional"] == "Yes" and "dept2" not in o[2] for o in ops), ops
    assert split(base, ops, ["SC", "MA2"]) == (ops, [])
ops = sent(base, new_teacher("Typed Mine", "MA"))
sync.head_prepare(ops, ["SC", "MA"])
assert ops[0][2]["dept"] == "MA"                                    # one of theirs already: kept
ops = sent(base, new_teacher("Typed None", "MA"))
sync.head_prepare(ops, [])                                          # no departments: nothing to put it in, and it is refused
assert ops[0][2]["dept"] == "MA" and ops[0][2]["provisional"] == "Yes"
assert split(base, ops, []) == ([], [(0, TDEPT)])
for junk in ([], ["x"], [["add", "teachers"]], [["add", "teachers", "row", ""]], [["add", "lessons", {"subject": "X"}, ""]]):
    before_j = copy.deepcopy(junk)
    sync.head_prepare(junk, ["SC"])
    assert junk == before_j, junk
sync.head_prepare(None, ["SC"])
passed += 1

# malformed or odd operations with departments given never raise, and are refused or skipped as today
for op in (["x"], [], ["set"], ["set", "blocks"], ["set", "blocks", opt_x["_id"]], ["set", "blocks", 5, "block", "X"], ["merge", "blocks", opt_x["_id"], "classes", "x", []],
           ["del", "blocks"], ["add", "blocks"], ["add", "blocks", "row", ""], ["add", "lessons", "row", ""], ["add", "lessons", None, ""], ["set", "lessons", "nope", "subject", "X"],
           ["del", "lessons", "nope"], ["set", "blocks", "nope", "block", "X"], ["del", "blocks", "nope"], ["set", "teachers", "nope", "dept", "SC"],
           ["add", "teachers", {"name": "T", "dept": 5}, ""], ["set", "lessons", sc["_id"], "subject", ["Science G3"]], "op", None, 7):
    for depts in (["SC"], [], None):
        sync.head_split(base, [op, op], depts)
        sync.head_may(base, [op], depts)
odd = copy.deepcopy(base)
next(x for x in odd["lessons"] if x.get("block") == "Sec 1 Science")["_id"] = ["not", "a", "name"]      # a damaged row
assert split(odd, [["del", "blocks", sci_band["_id"]]], ["SC"]) == ([["del", "blocks", sci_band["_id"]]], [])
assert split(base, [["set", "lessons", "nope", "subject", "X"]], ["SC"]) == ([["set", "lessons", "nope", "subject", "X"]], [])   # no such row: apply skips it
assert split(base, [["add", "lessons", "row", ""]], ["SC"]) == ([], [(0, NOSUB)])
passed += 1

# R9: a head's band may not take the name of another band at its level (the page reads the first band of a name, the
# solver the last), judged on the batch as the ops before leave it; the shared heads' code as today
TAKEN = "Another band already has that name."
assert sync.BAND_NAME_TAKEN == TAKEN
add_taken = sent(base, new_band("Sec 3 Option X", "Sec 3", ["3A"]))         # the page's own check bypassed
assert split(base, add_taken, ["MA"]) == ([], [(0, TAKEN)]) and split(base, add_taken, ["SC"]) == ([], [(0, TAKEN)])
assert sync.head_split(base, add_taken) == (add_taken, [])
ren_taken = sent(base, rename_band("Sec 1 Science", "Sec 1 Mathematics"))   # an own-only band onto another's name: all of it refused
assert len(ren_taken) > 1 and split(base, ren_taken, ["SC"]) == ([], [(i, TAKEN) for i in range(len(ren_taken))])
assert sync.head_split(base, ren_taken) == (ren_taken, [])
lvl = copy.deepcopy(base)
lvl["blocks"].append({"_id": "lvlband001", "block": "Sec 1 Science", "level": "Sec 2", "classes": ["2A"]})
assert split(lvl, [["set", "blocks", sci_band["_id"], "level", "Sec 2"]], ["SC"]) == ([], [(0, TAKEN)])   # onto that name at that level
assert split(base, [["set", "blocks", sci_band["_id"], "level", "Sec 2"]], ["SC"])[1] == []
for ops in (sent(base, new_band("Sec 3 Option Q", "Sec 3", ["3A"])), sent(base, new_band("Sec 3 Option X", "Sec 4", ["4A"])),
            sent(base, rename_band("Sec 1 Science", "Sec 1 Sciences"))):    # a fresh name, or the name at another level
    assert split(base, ops, ["SC"]) == (ops, []), ops
freed = copy.deepcopy(base)
rename_band("Sec 1 Science", "Sec 1 Sciences")(freed)
batch = sync.diff(base, freed) + sent(freed, new_band("Sec 1 Science", "Sec 1", ["1A"]))      # the name freed earlier in the batch
assert split(base, batch, ["SC"]) == (batch, [])
blank2 = copy.deepcopy(base)
table_band("Sec 2")(blank2)
sync.ensure_ids(blank2)
batch = sync.diff(base, blank2) + sent(blank2, table_band("Sec 2"))         # two blank bands: no name to take
assert split(base, batch, ["SC"]) == (batch, [])
passed += 1

# R10: another department's provisional teacher is its head's or the committee's (their departments before and after)
OTEACH = "This teacher is another department's: only its head or the committee can change them."
assert sync.OTHER_TEACHER == OTEACH
prov2 = copy.deepcopy(prov)
prov2["teachers"] += [{"_id": "provt00002", "name": "Typed Other", "dept": "MA", "provisional": "Yes"},
                      {"_id": "provt00003", "name": "Typed Both", "dept": "SC", "dept2": "MA", "provisional": "Yes"}]
for op in (["set", "teachers", "provt00002", "name", "Typed X"], ["del", "teachers", "provt00002"], ["set", "teachers", "provt00002", "dept", "SC"],
           ["set", "teachers", "provt00002", "allowance", 3], ["set", "teachers", "provt00003", "name", "Typed X"], ["del", "teachers", "provt00003"]):
    assert split(prov2, [op], ["SC"]) == ([], [(0, OTEACH)]), op
    assert sync.head_split(prov2, [op]) == ([op], []), op
    assert split(prov2, [op], ["MA", "SC"]) == ([op], []), op
assert split(prov2, [["set", "teachers", "provt00002", "name", "Typed X"]], ["MA"])[1] == []
assert split(prov2, [["set", "teachers", "provt00001", "name", "Typed X"]], ["SC"])[1] == []          # their own
assert split(prov2, [["del", "teachers", "provt00001"]], ["SC"])[1] == []
assert split(prov2, [["set", "teachers", "provt00001", "dept", "MA"]], ["SC"]) == ([], [(0, TDEPT)])   # out of their department
added = sent(prov2, new_teacher("Typed Fresh", "MA"))
sync.head_prepare(added, ["SC"])
tid = added[0][2]["_id"]
batch = added + [["set", "teachers", tid, "name", "Typed Fresher"], ["set", "teachers", tid, "allowance", 2], ["del", "teachers", tid]]
assert split(prov2, batch, ["SC"]) == (batch, [])                  # added earlier in the batch, in their department: theirs to edit
passed += 1

# a crafted batch cannot keep the judging busy (it runs under the setup's lock): a band change refused whole is judged
# again at most a few times, then every band change still open is refused whole
cpm = sample()
cpm["school"]["parents_subjects"] = ["Mathematics G3"]
R = next(b for b in cpm["blocks"] if b["block"] == "Sec 1 Mathematics")
def chain(k, band=R):    # each stage: an own group added to the band, the band deleted, the group released (which today's rules refuse)
    ops = []
    for n in range(k):
        rid = f"chain{n:05d}"
        ops += [["add", "lessons", dict(_id=rid, level="Sec 1", subject="Mathematics G3", block="Sec 1 Mathematics", classes=["1A"], teachers=[]), ""],
                ["del", "blocks", band["_id"]], ["set", "lessons", rid, "block", None]]
    return ops
ops = chain(400)
assert len(ops) == 1200
t0 = time.time()
ok, refused = sync.head_split(cpm, ops, ["MA"])
took = time.time() - t0
assert took < 1, took
assert ok == ops[0::3] and refused == [(i, WHY) for i in range(len(ops)) if i % 3], (len(ok), refused[:4])
spec = copy.deepcopy(cpm)
assert sync.apply(spec, ok) == 0 and sync._find(spec, "blocks", R["_id"]) is not None
emptycp = copy.deepcopy(empty)
emptycp["school"]["parents_subjects"] = ["Mathematics G3"]
R2 = next(b for b in emptycp["blocks"] if b["block"] == "Sec 1 Mathematics")
clean = [["del", "blocks", eb["_id"]]]                               # an empty band, deleted at the end: a clean band change
assert split(emptycp, chain(2, R2) + clean, ["MA"]) == (chain(2, R2)[0::3] + clean, [(i, WHY) for i in range(6) if i % 3])   # settled one by one
assert split(emptycp, chain(3, R2) + clean, ["MA"]) == (chain(3, R2)[0::3], [(i, WHY) for i in range(9) if i % 3] + [(9, WHY)])        # past the cap: refused too
sci_cpm = next(b for b in cpm["blocks"] if b["block"] == "Sec 1 Science")
ok, refused = sync.head_split(cpm, ops + [["set", "blocks", sci_cpm["_id"], "note", "x"]], ["MA"])
assert refused[-1] == (1200, BNOT)                                   # not a band change: judged as ever
passed += 1

print(f"{passed} cases passed")

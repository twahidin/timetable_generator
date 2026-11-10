"""Second choices: a setting, a rule or a level's recess can have a second choice that the outside agent gives way to,
one item at a time from the top of the list, stopping as soon as a timetable fits. This module holds the vocabulary
(spec['choices'], one dict per choice), how a choice reads in words, what is wrong with one, and how the first k are applied.

A choice (spec['choices'][i]), by kind:
  setting  key (a SETTING_RULES key), second (the value to try instead)
  rule     rule (index in spec['rules']; rule_id may name it by _id), fallback (Prefer, Instead or Drop), instead (a rule row)
  recess   level, window (['09:00', '11:20']: the recess may float anywhere inside)
and for all, order (the position in the list; a choice without one is last)."""
import copy, re
from .reader import periods_between, _minutes
from .solver import rule_label
from .spec import SETTING_RULES, RECESS_ROWS, TYPED, typed_rules, typed_label

KINDS = ("setting", "rule", "recess")
FALLBACKS = ("Prefer", "Instead", "Drop")
MODES = {"fallback": "Fall back only when needed", "compare": "Make one timetable for each"}
SHEET = "Choices"
USED_SHEET = "Choices used"
_NEVER = float("inf")

def ordered(spec):
    """[(index, choice)] sorted by order, then by position; every row, valid or not"""
    def key(ic):
        o = ic[1].get("order")
        return (o if isinstance(o, (int, float)) and not isinstance(o, bool) else _NEVER, ic[0])
    return sorted(enumerate(spec.get("choices") or []), key=key)

def mode(spec):
    return "compare" if (spec.get("school") or {}).get("choices_mode") == "compare" else "fallback"

def rule_index(spec, c):
    """the index in spec['rules'] of the rule a choice is about, or None when it is gone"""
    rules = spec.get("rules") or []
    i = c.get("rule")
    if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(rules): return i
    rid = c.get("rule_id")
    if rid not in (None, ""):
        return next((j for j, r in enumerate(rules) if isinstance(r, dict) and r.get("_id") == rid), None)
    return None

def rule_words(spec, i):
    """rule i of spec['rules'] in a few words: 'Rule: Level · Sec 1 · Not in periods', or 'Rule: T1 · Must · ...' in words"""
    r = spec["rules"][i]
    if r.get("rule") == TYPED:
        n = next((n for n, j, _ in typed_rules(spec) if j == i), 1)
        return "Rule: " + typed_label(n, r)
    return "Rule: " + " · ".join([rule_label(r)] + _parts(r))

def _num(v):
    """a period or a number as the sheet shows it: 3, not 3.0"""
    return int(v) if isinstance(v, float) and v.is_integer() else v

def _parts(r):
    """what tells two rule rows of one kind apart, after the label: the week (not Both), the day (not All), the periods, the
    number and the venues. Not the strength: that is what a second choice changes."""
    out, blank = [], lambda v: v in (None, "")
    if not blank(r.get("week")) and str(r["week"]).strip() != "Both": out.append(str(r["week"]).strip())
    if not blank(r.get("day")) and str(r["day"]).strip() != "All": out.append(str(r["day"]).strip())
    a, b = _num(r.get("from")), _num(r.get("to"))
    if not blank(a): out.append(f"period {a}" if blank(b) or str(b) == str(a) else f"periods {a}-{b}")
    if not blank(r.get("number")): out.append(f"number {_num(r['number'])}")
    v = r.get("venues")
    v = ", ".join(str(x) for x in v if not blank(x)) if isinstance(v, (list, tuple)) else str(v or "").strip()
    if v: out.append(v)
    return out

def settings_rows(spec):
    """the indexes in spec['rules'] of the rows the Settings sheet stands for (the first Must row of each setting, as
    spec.split_rules places them): a choice on the rule list is never one of these"""
    out, seen = set(), set()
    for j, r in enumerate(spec.get("rules") or []):
        if str(r.get("strength") or "Must") != "Must": continue
        s = next((s for s in SETTING_RULES if s["rule"] and _is_rule(r, s)), None)
        if s and s["key"] not in seen: seen.add(s["key"]); out.add(j)
    return out

def _clock(t):
    """a clock time as 9.00 or 11.20 (no am/pm)"""
    m = _minutes(t); return f"{m // 60}.{m % 60:02d}"

def _setting(key): return next((s for s in SETTING_RULES if s["key"] == key), None)

def _is_rule(r, s):
    """is rule row r the rule that setting s stands for?"""
    w = s["rule"]
    return r.get("rule") == w["rule"] and r.get("scope") == w["scope"] and (w["scope"] != "Department" or r.get("target") == w["target"])

def setting_value(spec, key):
    """a setting as the Settings sheet shows it: Yes, No, the number, or no limit"""
    s, sc = _setting(key), spec.get("school") or {}
    if key == "after_school": return "Yes" if sc.get("after_school", True) else "No"
    if key == "pe_rain_home": return "Yes" if sc.get("pe_rain_home") else "No"
    rows = [r for r in spec.get("rules", []) if _is_rule(r, s) and str(r.get("strength") or "Must") == "Must"]
    if s["number"]: return rows[0].get("number") if rows and rows[0].get("number") not in (None, "") else "no limit"
    return "Yes" if rows else "No"

def set_setting(spec, key, value):
    """change a setting in spec, as the page does when the committee picks it"""
    s, sc, v = _setting(key), spec["school"], str(value if value is not None else "").strip()
    if s is None: return
    if key == "after_school": sc["after_school"] = (v != "No")
    elif key == "pe_rain_home": sc["pe_rain_home"] = (v == "Yes")
    elif s["number"]:
        mine = [r for r in spec["rules"] if _is_rule(r, s) and str(r.get("strength") or "Must") == "Must"]
        if v == "" or v.lower() == "no limit":
            spec["rules"] = [r for r in spec["rules"] if not any(r is m for m in mine)]
        else:
            n = int(float(v))
            if mine: mine[0]["number"] = n
            else: spec["rules"].append(dict(s["rule"], number=n))
    elif v == "Yes":
        if not any(_is_rule(r, s) and str(r.get("strength") or "Must") == "Must" for r in spec["rules"]): spec["rules"].append(dict(s["rule"]))
    else:
        spec["rules"] = [r for r in spec["rules"] if not (_is_rule(r, s) and str(r.get("strength") or "Must") == "Must")]

def recess_first(spec, level):
    """the level's fixed recess (the run of R) on the first day that has one: {from, to, length, text} or None"""
    sc = spec["school"]; st, pm = _minutes(sc["start_time"]), int(sc["period_minutes"])
    for row in (spec.get("day_structure") or {}).get(level, {}).values():
        m = re.search(r"R+", row)
        if m:
            a, b = m.start(), m.end() - 1
            return dict({"from": a, "to": b, "length": b - a + 1},
                        text=f"{_clock_min(st + a * pm)} to {_clock_min(st + (b + 1) * pm)}")
    return None

def _clock_min(m): return f"{m // 60}.{m % 60:02d}"

def _has_window(spec, level):
    return any("W" in row for row in (spec.get("day_structure") or {}).get(level, {}).values())

def item_label(spec, c):
    kind = c.get("kind")
    if kind == "setting":
        s = _setting(c.get("key"))
        return s["label"] if s else "(missing) " + str(c.get("item") or c.get("key") or "setting")
    if kind == "rule":
        i = rule_index(spec, c)
        return rule_words(spec, i) if i is not None else "(missing) " + str(c.get("item") or "Rule")
    if kind == "recess": return f"Recess for {c.get('level')}"
    return "(missing) " + str(c.get("item") or kind or "choice")

def first_text(spec, c):
    kind = c.get("kind")
    if kind == "setting":
        return str(setting_value(spec, c["key"])) if _setting(c.get("key")) else "(missing)"
    if kind == "rule":
        i = rule_index(spec, c)
        return f"As written ({spec['rules'][i].get('strength') or 'Must'})" if i is not None else "(missing)"
    if kind == "recess":
        rf = recess_first(spec, c.get("level"))
        if rf is None: return "(no fixed recess)"
        return f"Fixed at {rf['text']} (" + (f"periods {rf['from']}-{rf['to']}" if rf["from"] != rf["to"] else f"period {rf['from']}") + ")"
    return ""

def second_text(spec, c):
    kind = c.get("kind")
    if kind == "setting": return str(c.get("second") if c.get("second") is not None else "")
    if kind == "rule":
        f = c.get("fallback")
        if f == "Prefer": return "Make it Prefer"
        if f == "Drop": return "Drop it"
        if f == "Instead":
            r = c.get("instead") or {}
            return "Instead: " + (str(r.get("text") or "").strip() if r.get("rule") == TYPED else rule_label(r))
        return ""
    if kind == "recess":
        w = c.get("window")
        try: return f"Floating between {_clock(w[0])} and {_clock(w[1])}"
        except (TypeError, ValueError, IndexError, AttributeError): return "(no window)"
    return ""

def problems(spec):
    """[(index in spec['choices'], one sentence)]: what is wrong with a choice, so it is skipped. Every choice has at most one."""
    out = []
    for i, c in enumerate(spec.get("choices") or []):
        say = lambda t: out.append((i, t))
        kind = c.get("kind")
        if kind == "setting":
            s = _setting(c.get("key"))
            if s is None: say(f"'{c.get('key') or c.get('item') or ''}' is not a setting the timetable knows."); continue
            sec = str(c.get("second") if c.get("second") is not None else "").strip()
            if sec == "": say("The second choice is blank."); continue
            if s["number"]:
                if sec.lower() != "no limit" and not sec.isdigit(): say("The second choice must be a whole number or no limit."); continue
            elif sec not in ("Yes", "No"): say("The second choice must be Yes or No."); continue
            if sec.lower() == str(setting_value(spec, c["key"])).strip().lower(): say("The second choice is the same as the first.")
        elif kind == "rule":
            i_ = rule_index(spec, c)
            if i_ is None: say("The rule this choice falls back on is no longer on the setup."); continue
            if c.get("fallback") not in FALLBACKS: say("Pick Make it Prefer, Instead or Drop it for the second choice."); continue
            if c.get("fallback") == "Instead" and not (c.get("instead") or {}).get("rule"): say("The Instead rule is not filled in.")
        elif kind == "recess":
            lv = c.get("level")
            if _has_window(spec, lv): say(f"{lv} already has a floating recess (W on Day structure)."); continue
            rf = recess_first(spec, lv)
            if rf is None: say(f"{lv} has no fixed recess (R on Day structure) to float."); continue
            w = c.get("window")
            try:
                a, b = _minutes(w[0]), _minutes(w[1]); lo, hi = periods_between(spec["school"], w[0], w[1])
            except (TypeError, ValueError, IndexError, AttributeError):
                say("The window is missing or cannot be read."); continue
            shown = f"{_clock(w[0])} to {_clock(w[1])}"
            if b - a < rf["length"] * int(spec["school"]["period_minutes"]) or hi - lo + 1 < rf["length"]:
                say(f"The window {shown} is shorter than the recess ({rf['length']} period{'s' if rf['length'] != 1 else ''})."); continue
            if hi < rf["from"] or lo > rf["to"]: say(f"The window {shown} does not include the recess ({rf['text']})."); continue
            have = _float_length(spec)
            if have is not None and have != rf["length"]:
                say(f"{lv}'s recess is {_periods(rf['length'])} but Floating recess length on Settings is {have}.")
        else: say("This choice is not a setting, a rule or a recess.")
    bad, first = {i for i, _ in out}, None   # a recess choice floats at the length the first one in the order sets
    for i, c in ordered(spec):
        if c.get("kind") != "recess" or i in bad: continue
        n = recess_first(spec, c.get("level"))["length"]
        if first is None: first = (c.get("level"), n)
        elif n != first[1]: out.append((i, f"{c.get('level')}'s recess is {_periods(n)} but the recess choice for {first[0]} floats {first[1]}."))
    return sorted(out, key=lambda x: x[0])

def _periods(n): return f"{n} period{'s' if n != 1 else ''}"

def _float_length(spec):
    """the Floating recess length on Settings as a whole number, or None when it is not there or blank"""
    row = next((x for x in (spec.get("school") or {}).get("extra_settings") or [] if str(x[0] or "").strip().lower().startswith("floating recess length")), None)
    if row is None or len(row) < 2 or row[1] in (None, ""): return None
    try: return int(float(str(row[1]).strip()))
    except ValueError: return None

def _valid(spec):
    bad = {i for i, _ in problems(spec)}
    return [(i, c) for i, c in ordered(spec) if i not in bad]

def apply_all(spec, k):
    """a copy of spec with the first k valid choices (in order) taken as the second choice"""
    sp = copy.deepcopy(spec)
    picked = _valid(spec)[:max(0, int(k))]
    rows = {i: sp["rules"][rule_index(spec, c)] for i, c in picked if c.get("kind") == "rule"}   # the rule rows themselves, so a removal elsewhere cannot shift them
    drop = []
    for i, c in picked:
        kind = c.get("kind")
        if kind == "setting": set_setting(sp, c["key"], c.get("second"))
        elif kind == "rule":
            r, f = rows[i], c.get("fallback")
            if f == "Prefer": r["strength"] = "Prefer"
            elif f == "Drop": drop.append(r)
            elif f == "Instead":
                new = dict(c["instead"]); new["strength"] = new.get("strength") or r.get("strength") or "Must"
                r.clear(); r.update(new)
        elif kind == "recess": _float_recess(sp, c)
    if drop: sp["rules"] = [r for r in sp["rules"] if not any(r is d for d in drop)]   # every drop is done last
    return sp

def _float_recess(sp, c):
    lv, w, sc = c["level"], c["window"], sp["school"]
    lo, hi = periods_between(sc, w[0], w[1]); rf = recess_first(sp, lv)
    for d, row in sp["day_structure"][lv].items():
        if "R" not in row[lo:hi + 1]: continue
        sp["day_structure"][lv][d] = "".join("W" if lo <= p <= hi and ch in "LR" else ch for p, ch in enumerate(row))
    extra = sc.setdefault("extra_settings", [])
    for label, default, note in RECESS_ROWS[:2]:
        row = next((x for x in extra if str(x[0] or "").strip().lower().startswith(label.lower())), None)
        value = rf["length"] if label.startswith("Floating recess length") else default
        if row is None: extra.append([label, value, note])
        elif label.startswith("Floating recess length") and (len(row) < 2 or row[1] in (None, "")):
            if len(row) < 2: row.append(value)
            else: row[1] = value

def used_rows(spec, k):
    """[{no, item, used, how}] for the Choices used sheet: every valid choice in order, the first k at their second choice"""
    pos = {i: n for n, (i, _) in enumerate(ordered(spec), start=1)}
    out = []
    for n, (i, c) in enumerate(_valid(spec)):
        second = n < k
        out.append(dict(no=pos[i], item=item_label(spec, c), used="Second choice" if second else "First choice",
                        how=second_text(spec, c) if second else first_text(spec, c)))
    return out

def give_way(spec, run, mode="fallback"):
    """[{k, spec, res}]: run(spec_k) -> res for k = 0 (the first choices), 1, 2, ... up to the number of valid choices, spec_k being
    spec with the first k choices given way on. Fallback mode stops at the first res with lessons; compare mode runs every k."""
    out = []
    for k in range(len(_valid(spec)) + 1):
        sp = apply_all(spec, k); res = run(sp)
        out.append(dict(k=k, spec=sp, res=res))
        if mode != "compare" and res.get("lessons"): break
    return out

def used_sheet(path, rows):
    """add the sheet 'Choices used' (No., Item, Used, How) to the workbook at path, replacing one that is there"""
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.load_workbook(path)
    if USED_SHEET in wb.sheetnames: del wb[USED_SHEET]
    ws = wb.create_sheet(USED_SHEET)
    ws.append(["No.", "Item", "Used", "How"])
    for c in ws[1]: c.font = Font(bold=True)
    for r in rows: ws.append([r.get("no"), r.get("item"), r.get("used"), r.get("how")])
    for col, w in zip("ABCD", (6, 50, 16, 60)): ws.column_dimensions[col].width = w
    wb.save(path)

def _used(v):
    s = str(v if v is not None else "").strip().lower()
    if s.startswith(("second", "fallback", "given way", "gave way")) or s in ("2", "2nd"): return "Second choice"
    if s.startswith("first") or s in ("1", "1st"): return "First choice"
    return ""

def used_from_rows(rows):
    """a Choices used sheet as [{no, item, used, how}], read loosely: a title row above the header is skipped, the header is the
    first of the top rows with a Used cell, No. or # is the number, Used reads first/second/1/2/fallback/given way as
    'First choice' or 'Second choice' (anything else as ''), blank rows are skipped"""
    rows = list(rows)
    def cells(row): return [str(h).strip().lower() if h is not None else "" for h in row]
    hi = next((i for i, row in enumerate(rows[:6]) if any(h.startswith("used") for h in cells(row))), None)
    if hi is None: return []
    hdr = cells(rows[hi])
    def col(test): return next((i for i, h in enumerate(hdr) if h and test(h)), None)
    ix = dict(no=col(lambda h: h in ("no", "no.", "#", "number") or h.startswith("no.")), item=col(lambda h: h.startswith("item")),
              used=col(lambda h: h.startswith("used")), how=col(lambda h: h.startswith("how")))
    def g(row, k):
        i = ix[k]; return row[i] if i is not None and i < len(row) else None
    out = []
    for row in rows[hi + 1:]:
        if not any(v not in (None, "") for v in row): continue
        no = g(row, "no"); m = re.match(r"^\s*#?\s*(\d+)", str(no)) if no not in (None, "") else None
        out.append(dict(no=int(m.group(1)) if m else None, item=str(g(row, "item") or "").strip(), used=_used(g(row, "used")), how=str(g(row, "how") or "").strip()))
    return out

def check_used(spec, used):
    """(k, problems): k is the number of leading choices (by no) marked Second choice; problems are sentences for a row that names
    no choice on the list, for a second choice on a choice with a problem (a first choice there is ignored) and for a second
    choice after a first. Rows with no number are ignored."""
    pos = {i: n for n, (i, _) in enumerate(ordered(spec), start=1)}
    valid = [(pos[i], c) for i, c in _valid(spec)]
    by_no = dict(valid); bad = {pos[i] for i, _ in problems(spec)}   # numbered on the sheet, but skipped
    second = {u["no"] for u in used if u.get("no") is not None and u.get("used") == "Second choice"}
    missed = next((no for no, _ in valid if no not in second), None)   # the first choice not given way on
    probs = []
    for u in sorted((u for u in used if u.get("no") is not None), key=lambda u: u["no"]):
        no = u["no"]
        if no not in by_no:
            if no in bad:
                if u.get("used") == "Second choice": probs.append(f"Choices used gives way on item {no}, which has a problem and cannot be given way on.")
            else: probs.append(f"Choices used names item {no}, which is not on the list.")
        elif u.get("used") == "Second choice" and missed is not None and no > missed:
            probs.append(f"Item {no} ({item_label(spec, by_no[no])}) was given way on while item {missed} ({item_label(spec, by_no[missed])}) was not: the agent must give way in order.")
    k = 0
    for no, _ in valid:
        if no in second: k += 1
        else: break
    return k, probs

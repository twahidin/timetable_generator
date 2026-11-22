"""Re-fit: the fewest lesson changes that make the draft fit the setup again. Which warnings it works on is here."""
import helper

MAX_MOVES = 3        # the most changes in one answer
MAX_NODES = 250      # the most search steps for one warning
CAND_LESSONS = 4     # the lessons tried for a change
CAND_SLOTS = 8       # the places tried for a lesson
BUDGET_S = 30.0      # the most seconds for a whole re-fit

NO_FIT = "No list of up to 3 moves fits it."
BAND = "This changes the band itself: change it on the board, or ask the agent for a new timetable."
SPLIT = "Its lessons are taught by different teachers: change them on the board."
NOT_ONE = "More than one teacher changes: change it on the board."
LATE = "Not looked at in time; run Re-fit again."

PARTS = ("teachers", "missing", "periods", "extra", "venue", "half")   # the step 5 differences it works on, in this order

def _rank(w):
    """the place of a warning in the list, or None when a re-fit does not work on it"""
    if w.get("decision"): return None
    kind = w.get("kind")
    if kind == "deployment":
        part = helper._dep_parts(w.get("key"))[1]
        return (0, PARTS.index(part)) if part in PARTS else None
    if kind == "clash": return (1, 0)
    if kind == "rule" and w.get("strength") == "Must": return (2, 0)
    return None

def targets(warnings):
    """the open warnings a re-fit works on: step 5 differences (teachers, missing, periods, extra, venue, half), then clashes, then Must rules.
    Each is dict(kind=<part, "clash" or "rule">, key, text, w). Pure: it reads only the list."""
    found = []
    for w in warnings or []:
        r = _rank(w)
        if r is not None: found.append((r, w))
    found.sort(key=lambda x: x[0])   # stable: warnings of one place keep the order the page lists them in
    return [dict(kind=PARTS[r[1]] if r[0] == 0 else "clash" if r[0] == 1 else "rule", key=w["key"], text=w["text"], w=w) for r, w in found]

def needed(warnings):
    """whether a re-fit has anything to work on (the page's and the route's check)"""
    return bool(targets(warnings))

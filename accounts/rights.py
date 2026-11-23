"""What a person may do, worked out from their record each time (never from the cookie)."""
import datetime

STRONG = {"password", "google"}
_SHARED = {
    "committee": {"committee", "setup", "timetable", "files", "history", "codes", "relief.settings", "relief.save"},
    "head": {"setup", "timetable", "files"},
    "teacher": {"timetable", "files"},
    "student": {"timetable"},
}

def rights(person, via, shared=None, today=None):
    if via == "personal": return frozenset({"own"})
    if person is None:
        return frozenset(_SHARED.get(shared, ())) if via == "shared" else frozenset()
    if person.get("off"): return frozenset()
    g, ex = person.get("group"), person.get("extras") or {}
    r = {"timetable", "files"}
    if g in ("teacher", "leader", "hod", "sh") or ex.get("timetable"): r.add("relief")
    if g in ("leader", "hod", "sh"): r |= {"relief.plan", "relief.settings"}
    if ex.get("timetable"): r |= {"relief.settings", "relief.save"}
    if ex.get("relief"): r |= {"relief", "relief.plan", "relief.settings", "relief.save", "relief.team"}
    until = ex.get("exams")
    if until and until >= (today or datetime.date.today()).isoformat(): r.add("exams")
    if via in STRONG:
        if ex.get("timetable"):
            r |= {"committee", "setup", "history", "codes"}
            if ex.get("admin"): r.add("admin")
        if g in ("hod", "sh"): r |= {"setup", "history.dept"}
    r.add("history.own")   # anyone signed in by name can change something (ask for relief, start an event), so sees their own history
    return frozenset(r)

def _day(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"

def gives(person, depts, today=None):
    """what a person's role and committees let them do, as sentences worked out from rights() itself, so the admin page never
    promises what the server refuses. strong: a line a shared code does not give (it needs a password or a Google account).
    depts: their own ticked departments (matter on the head's Setup line only)"""
    if person.get("off"): return [{"text": "Nothing: switched off, so they cannot sign in.", "strong": False}]
    r = rights(person, "password", today=today)
    out = [{"text": "Sees the published timetable and the files.", "strong": False}]
    def add(text, strong=False): out.append({"text": text, "strong": strong})
    if "relief.team" in r: add("Relief: runs it, with the team's pages and settings.")
    elif "relief.plan" in r: add("Relief: plans cover, as management.")
    elif "relief" in r: add("Relief: opens the relief page and asks for cover.")
    if "setup" in r and "committee" not in r:
        add(f"Setup: changes the teaching groups of {', '.join(depts)} only." if depts else "Setup: no department ticked yet, so nothing to change.", True)
    if "committee" in r:
        add("Setup: every step, the upload, the edit board and Publish.", True)
        add("Exams and events: plans them and approves them.", True)
    elif "exams" in r: add(f"Exams and events: plans them, until {_day(person['extras']['exams'])}.")
    if "history" in r: add("History: sees everyone's changes.", True)
    elif "history.dept" in r: add("History: sees their departments' changes.", True)
    if "admin" in r: add("People and access: this page.", True)
    return out

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

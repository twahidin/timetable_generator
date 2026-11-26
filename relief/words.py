"""The words for a lesson, its periods and times, and the dates of an absence, as the pages, the history and the messages on
Telegram say them, and the labels of the kinds of message (KINDS: Relief settings lists what could not be sent by them, and the
blocked-bot alert names what was refused by them). Pure: reads no files."""
import datetime

from exams.days import bounds, hhmm
from relief import absences as _absences

ENTIRE = "Entire Class"
KINDS = dict(planned="Relief planned", remind="Reminder to acknowledge", officer="To the reporting officer", ask="Request to change", askpick="New pick for a request to change",
             kept="Relief kept", cancelled="Absence cancelled", gone="No longer needed", moved="Relief moved", stopped="Not happening", again="On again", weekly="Weekly summary",
             late="Late request for today", morning="Morning message", repeat="Reminder of a relief", needed="Relief needed again", covered="Who covers you",
             unlinked="Bot blocked alert", work="Please set work")       # a relief, a report and an all clear have none (relief/tgweb.py's UNSENT_LEFT_OUT)


def class_group(x):
    """'1B, 1A Maths (G1)': the classes and subject, and the group unless it is the whole class (as the pages' title)"""
    g = x.get("group") or ""
    head = " ".join(v for v in (", ".join(x.get("classes") or []), x.get("subject") or "") if v)
    return head + (f" ({g})" if g and g != ENTIRE else "")


def periods_text(x):
    p, n = int(x["p"]), int(x.get("n") or 1)
    return f"P{p + 1}" if n == 1 else f"P{p + 1}–P{p + n}"


def times(pub, x, c):
    """(start, end) of cover c of lesson x as HH:MM: the lesson's own, or a part's from exams.days.bounds"""
    if not x.get("parts"): return x.get("start") or "", x.get("end") or ""
    p, n, b = int(c["p"]), int(c.get("n") or 1), bounds((pub or {}).get("model") or {})
    return (hhmm(b[p][0]), hhmm(b[min(p + n, len(b)) - 1][1])) if p < len(b) else ("", "")


def day(iso):
    """'Tue 13 Oct' for an ISO date or date-time"""
    return _absences._say(datetime.date.fromisoformat(str(iso)[:10]))


def days(record):
    """'Tue 13 Oct, Wed 14 Oct': the dates of an absence; three or more school days in a row read 'Mon 30 Nov \u2013 Fri 11 Dec'
    (a date continues a run when it is the next weekday: Friday carries on to Monday)"""
    dates = sorted({datetime.date.fromisoformat(str(d)[:10]) for d in record.get("dates") or []})
    runs = []
    for d in dates:
        nxt = d - datetime.timedelta(days=3 if d.weekday() == 0 else 1)
        if runs and runs[-1][-1] == nxt: runs[-1].append(d)
        else: runs.append([d])
    out = []
    for r in runs:
        if len(r) >= 3: out.append(f"{day(r[0].isoformat())} \u2013 {day(r[-1].isoformat())}")
        else: out.extend(day(d.isoformat()) for d in r)
    return ", ".join(out)


def away(record):
    """'whole day', or the absence's periods ('P1–P3')"""
    per = record.get("periods")
    return periods_text(dict(p=per[0], n=per[1] - per[0] + 1)) if per else "whole day"

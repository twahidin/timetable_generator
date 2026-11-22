"""The plan of a re-fit: one list of fixes for every warning it works on (refit.targets), each searched for on the timetable the
earlier ones leave (refit.solve), with its reasons and its numbers. Nothing here writes, and nothing it is given is changed."""
import logging, os, re, time, traceback
import draft, fixes, helper, refit
from ttgen import verify
from ttgen.export import check_model

LOOK_S = 2.0         # the least seconds of the budget (refit.BUDGET_S) one warning's full search is given
SIFT_S = 10.0        # the most seconds for going through the answers when the list as a whole is not one to offer
BROKEN = "The app could not work this one out: change it on the board."
TEACHER_FIRST = "Its teachers differ from step 5 too: settle that first, then run Re-fit again."

_log = logging.getLogger(__name__)

def _again(w): return bool(re.fullmatch(r"typed:\d+:again(#\d+)?", w["key"]))

def _mistakes(m, ws):
    """the critical mistakes of a list of step 8's, as a set that tells what is new: two lessons at once (of a teacher, of a class, in a room) once for
    every period it names, (its kind, who, day, period), so a line that comes in two is the same; a lesson out of lesson time by its key and the lesson
    (two in one place read the same); any other by its key"""
    out = set()
    for w in ws:
        if not w.get("crit"): continue
        if w["crit"] == "room": who, cells = refit._room_clash(m, w) or (None, None)
        else: who = helper._clash_who(w)[0] if w["crit"] in ("teacher", "class") else None; cells = helper._clash_slots(m, w, who) if who else None
        wh = w.get("where") or {}; which = (wh.get("id"), wh.get("row")) if w["crit"] == "break" else ()
        out |= {(w["crit"], who, d, q) for d, q in cells} if cells else {(w["crit"], helper._base(w["key"]), *which)}
    return out

def _subject(w): return fixes._subject(dict(w, key=helper._base(w["key"])))   # what a rule's warning is about, as the judge counts it

def _musts(ws):
    """the Must rules a list of step 8's says are broken, answered or not, as a set that tells what is new: each by what it is about"""
    return {_subject(w) for w in ws if w["kind"] == "rule" and w["strength"] == "Must"}

def _wishes(ws):
    """the open Prefer warnings of a list of step 8's ("No room" and the typed rules to check again aside), as a set that tells what is new: a rule's
    by what it is about, as the judge counts them, any other by its key"""
    return {_subject(w) if w["kind"] == "rule" else helper._base(w["key"])
            for w in ws if not w["decision"] and w["strength"] == "Prefer" and not w["key"].startswith("room:none:") and not _again(w)}

def _on(w, ws):
    """whether a warning is on a list of step 8's: its key, "#2" aside, and its place, which tells apart two that read the same (a difference from
    step 5 has a key of its own, and its place may change)"""
    k = helper._base(w["key"]); return any(helper._base(x["key"]) == k and (w["kind"] == "deployment" or x.get("where") == w.get("where")) for x in ws)

def _make(lessons, fx, spec, days, nxt):
    """helper._apply of a part of the list, its adds numbered from nxt as in the whole list (an added lesson never takes the number of one deleted
    before it) -> (dict(lessons, touched, was), the next number). ValueError when a fix cannot be made"""
    L, touched, was = list(lessons), set(), []
    for f in fx: helper._own(L, f); fixes.apply_one(L, f, spec, days, new_id=nxt, touched=touched, was=was); nxt += f["kind"] == "add"
    return dict(lessons=L, touched=touched, was=was), nxt

class _Plan:
    """the work of plan: the targets (each is its place in ts) looked at in turn, every one on the timetable the list leaves so far.
    Nothing of m or of the targets is changed"""
    def __init__(self, m, ts, progress, end):
        self.m, self.spec, self.days, self.ts, self.progress, self.end = m, m["checked_setup"], m["days"], ts, progress, end
        self.first = {x["id"] for x in m["lessons"]}             # the lessons on the timetable the plan starts from
        self.changes, self.moved = 0, set()                      # how often the timetable changed; the lessons that stay where they are: moved or put in by the list
        self.also, self.broken = set(), set()                    # the targets settled by the fixes of others; those the search broke on
        self.why, self.told = {}, set()                          # target -> the sentence of its last full look; the targets progress was told of
        self.seen, self.full, self.had = {}, {}, {}              # target -> self.changes at its last look, and at its last full look; the seconds that one had, when it was cut short
        key = [helper._dep_parts(t["key"])[0] for t in ts]; self.teacher = {i: [j for j, u in enumerate(ts) if u["kind"] == "teachers" and key[j] == key[i]] for i, t in enumerate(ts) if t["kind"] == "periods"}   # a periods target -> the teachers target of its key
        self._start()

    # ------------------------------------------------------------ the list
    def _start(self):
        """the empty list: solved, (target, its answer, _make's dict of it) in the order solved; now, the timetable the list leaves; nxt, the number of the next lesson added"""
        self.solved, self.now, self.nxt = [], self.m, 1 + max(self.first, default=0)

    def _keep(self, i, got):
        """target i's answer joins the list"""
        r, self.nxt = _make(self.now["lessons"], got["fixes"], self.spec, self.days, self.nxt); self.solved.append((i, got, r)); self.now = dict(self.m, lessons=r["lessons"])

    def settled(self): return {i for i, *_ in self.solved}
    def all_fixes(self): return [f for _, got, _ in self.solved for f in got["fixes"]]
    def touched(self): return set().union(*(r["touched"] for *_, r in self.solved))
    def was(self): return [x for *_, r in self.solved for x in r["was"]]
    def rechecked(self): return refit.rechecked(self.m, self.spec, self.now["lessons"], self.touched(), self.was(), self.all_fixes())

    # ------------------------------------------------------------ looking at the targets
    def run(self):
        """passes without a move until one settles nothing, then a round of the full search, and so on until a round has nothing to look at or the time is up"""
        while True:
            while self._pass(): pass
            if not self._round(): break
        if self.progress and len(self.told) < len(self.ts): self.progress(len(self.ts), len(self.ts))   # the time ran out, or an add was not looked at

    def _open(self):
        closed = self.settled() | self.also | self.broken
        return [i for i in range(len(self.ts)) if i not in closed]

    def _waits(self, i):
        """the teachers targets that target i waits for: those of its key not settled, when it is a period to be added (by the teacher that change
        decides). Whether that is so is asked of the timetable as it is now, as direct asks it: periods short of the plan, somebody to teach them, and no band"""
        first = [j for j in self.teacher.get(i, ()) if j not in self.also and j not in self.settled()]
        if not first: return []
        k = helper._dep_parts(self.ts[i]["key"])[0]; e = verify.planned_rows(self.spec).get(k); short = {x["key"] for x in fixes.short(self.now, self.spec, self.m["pool"])}
        return first if e and e["teachers"] and verify._kstr(k) in short and not refit._band(e, helper._of_key(self.now["lessons"], k)) else []   # no e: a class whose name has a colon, whose keys cannot be read

    def _pass(self):
        """every target not looked at since the timetable last changed, with no move -> whether the timetable changed"""
        was = self.changes
        for i in self._open():
            if time.monotonic() >= self.end: break
            if self.seen.get(i) != self.changes and not self._waits(i): self._look(i, self.end, 0)
        return self.changes != was

    def _round(self):
        """the full search for every target not searched in full since the timetable last changed, each with its share of the time left; and
        again for one whose search was cut short, when its share is more than it had -> whether any was searched"""
        todo = [i for i in self._open() if (self.full.get(i) != self.changes or i in self.had) and not self._waits(i)]; looked = False
        for left, i in zip(range(len(todo), 0, -1), todo):
            now = time.monotonic()
            if now >= self.end: break
            deadline = min(self.end, now + max(LOOK_S, (self.end - now) / left))
            if self.full.get(i) == self.changes and deadline - now <= self.had[i]: continue
            looked, self.full[i] = True, self.changes
            if self._look(i, deadline): self.had[i] = deadline - now
            else: self.had.pop(i, None)
        return looked

    def _look(self, i, deadline, most=None):
        """look at one target (most: the moves allowed, None: a full look) and take the answer, when there is one -> whether the look was cut short"""
        self.seen[i], s = self.changes, {}
        try: got = refit.solve(self.now, self.spec, self.days, self.ts[i], self.m["pool"], self.moved, deadline, s, most)
        except Exception as e: self._break(i, e); self._tell(i); return False
        if got is not None and not all(f[k] in self.first for f in got["fixes"] for k in ("id", "a", "b") if k in f):
            got, s = None, dict(reason=refit.NO_FIT, late=False)   # it names a lesson the list itself puts in: Apply numbers those its own way
        if got is not None: self._take(i, got)
        elif most is None: self.why[i] = s["reason"]
        if got is not None or most is None: self._tell(i)
        return got is None and s["late"]

    def _break(self, i, e):
        """the search broke on target i: it needs you. The line in the log has no word of the timetable or the setup (the error's own text may have)"""
        *_, (frame, line) = traceback.walk_tb(e.__traceback__)
        _log.error("Re-fit: a target of the kind %s could not be worked out (%s at %s:%s)", self.ts[i]["kind"], type(e).__name__, os.path.basename(frame.f_code.co_filename), line)
        self.why[i] = BROKEN; self.broken.add(i)

    def _take(self, i, got):
        if not got["fixes"]: self.also.add(i); return
        self._keep(i, got); self.changes += 1; self.moved |= got["moved"] | {x["id"] for x in self.now["lessons"]} - self.first

    def _tell(self, i):
        if i in self.told: return
        self.told.add(i)
        if self.progress: self.progress(len(self.told), len(self.ts))

    # ------------------------------------------------------------ the list as a whole
    def check(self, fx, decisions):
        """make sure that the list is one to offer (see _at_fault) -> what step 8 lists before the list and after it (draft.listed). It is so when the
        judging was right. When it is not, the answers are gone through one by one; what is at fault still is taken out; at the last the list is empty"""
        self.fx, self.decisions = fx, decisions; before = draft.listed(self.m, fx, decisions)
        for cure in (self._sift, self._cut, self._clear, None):
            after = self._listed(); self._look_back(after); bad = self._at_fault(before, after)
            if not bad: return before, after
            cure(bad, before)

    def _listed(self):
        """what step 8 would list with the list made (draft.listed)"""
        if not self.solved: return draft.listed(self.m, self.fx, self.decisions)
        checks = check_model(self.now); problems = list(checks["problems"]) + list(self.m.get("choice_problems") or [])   # as model_from_files makes it: the clashes are read from it
        was = list(self.fx["was"]) + self.was() + refit.waiting(self.m["pool"], self.all_fixes())[0]
        return draft.listed(dict(self.now, checks=dict(checks, problems=problems, ok=not problems)), dict(self.fx, touched=set(self.fx["touched"]) | self.touched(), was=was), self.decisions)

    def _new(self, before, after):
        """whether the second of two lists of step 8's has a mistake, a broken Must rule or a wish that the first has not"""
        a, b = before["warnings"], after["warnings"]; return bool(_mistakes(self.m, b) - _mistakes(self.m, a) or _musts(b) - _musts(a) or _wishes(b) - _wishes(a))

    def _accepted(self, m, got):
        """whether the judge has every fix of an answer, in order, on the timetable m"""
        c = helper.chain(m, self.spec, self.days, got["fixes"]); return not refit._refusal(c) and len(c["texts"]) == len(got["fixes"])

    def _done(self, i, m, after):
        """whether target i, open on the timetable m, is settled on the one the list leaves, as the search says it and as step 8 lists it (after)"""
        w = self.ts[i]["w"]; return refit._settled(m, self.spec, self.days, w, self.now["lessons"], helper._before(m, self.spec, w), refit._room_clash(m, w)) and not _on(w, after["warnings"])

    def _at_fault(self, before, after):
        """the solved targets whose answer the judge has not on the timetable the earlier ones leave, or that are open at the end; and None, when the list
        as a whole has a mistake, a broken Must rule or a wish that was not there before. Empty: the list is one to offer"""
        if not self.solved: return set()
        bad, m = {None} if self._new(before, after) else set(), self.m
        for i, got, r in self.solved:
            if not self._accepted(m, got) or not self._done(i, self.m, after): bad.add(i)
            m = dict(self.m, lessons=r["lessons"])
        return bad

    def _sift(self, bad, before):
        """go through the answers once, in their order, and keep those that are accepted, settle their target and bring no mistake, no broken Must rule and no wish, each on what
        the ones kept before it leave.
 One that does not needs you; those not gone through in SIFT_S seconds were not looked at in time"""
        end, old, last = time.monotonic() + SIFT_S, self.solved, before; self._start()
        for i, got, _ in old:
            if time.monotonic() >= end: self.why[i] = refit.LATE; continue
            if self._waits(i): self.why.pop(i, None); continue   # the teacher change it was made after is not kept
            m = self.now; self.why[i] = refit.NO_FIT
            if not self._accepted(m, got): continue
            self._keep(i, got); after = self._listed()
            if self._done(i, m, after) and not self._new(last, after): last = after
            else: self.solved.pop(); self.now = m

    def _cut(self, bad, before):
        """take these targets out of the list, and what the judge has not without them"""
        old = self.solved; self._start()
        for i, got, _ in old:
            if i not in bad and self._waits(i): self.why.pop(i, None)
            elif i not in bad and self._accepted(self.now, got): self._keep(i, got)
            else: self.why[i] = refit.NO_FIT

    def _clear(self, bad, before): self._cut(self.settled(), before)

    def _look_back(self, after):
        """what the list settles besides its own targets, now that it is as it is (after: what step 8 lists then): one found so that is not (any more)
        needs you, and one that is open still and gone by now (the time was up before it was looked at again) is settled too"""
        for i in sorted(self.also | set(self._open())):
            try: gone = bool(self.solved) and not _on(self.ts[i]["w"], after["warnings"]) and self._is_gone(i)
            except Exception as e: self.also.discard(i); self._break(i, e); continue
            if gone: self.also.add(i)
            elif i in self.also: self.also.discard(i); self.why[i] = refit.NO_FIT

    def _is_gone(self, i):
        """whether target i's warning is gone on the timetable the list leaves, as solve asks it"""
        w = self.ts[i]["w"]; return refit._gone(self.now, self.spec, self.days, w, helper._before(self.now, self.spec, w), refit._room_clash(self.m, w))

    # ------------------------------------------------------------ as the page shows it
    def groups(self):
        """the solved targets, each with its steps: numbered over the whole list, worded and flagged on the timetable the earlier steps leave"""
        out, L, nxt, pool, n = [], self.m["lessons"], 1 + max(self.first, default=0), self.m["pool"], 0
        for i, got, _ in self.solved:
            steps = []
            for f, why in zip(got["fixes"], got["why"]):
                r, nxt = _make(L, [f], self.spec, self.days, nxt); n += 1
                steps.append(dict(n=n, fix=f, text=helper.say(dict(self.m, lessons=L), self.spec, self.days, f), why=why, tags=self._tags(f, L, r, pool))); L, pool = r["lessons"], refit.waiting(pool, [f])[1]
            out.append(dict(self._said(i), steps=steps))
        return out

    def _tags(self, f, lessons, r, pool):
        """what a step (its fix, the lessons before it, _make's dict of it, the lessons not placed before it) is flagged with"""
        day = f["kind"] == "move" and helper._first(lessons, f["id"])["d"] != f["d"]; bare = f["kind"] == "add" and fixes._no_room(f["room"])
        return ["another day"] * day + ["no room"] * bare + [f"check T{n} again" for n in refit.rechecked(dict(self.m, pool=pool), self.spec, r["lessons"], r["touched"], r["was"], [f])]

    def _said(self, i): return {k: self.ts[i][k] for k in ("key", "kind", "text")}

    def needs(self):
        done = self.settled() | self.also
        return [dict(self._said(i), why=self._sentence(i)) for i in range(len(self.ts)) if i not in done]

    def _sentence(self, i):
        """why target i needs you: what its last full look gave; without one, it was not looked at in time, unless it waits for a teacher change that was"""
        if i in self.why: return self.why[i]
        first = self._waits(i); return refit.LATE if not first or any(self.why.get(j, refit.LATE) == refit.LATE for j in first) else TEACHER_FIRST

def plan(m, rec, fx, decisions, warnings, progress=None, budget=None):
    """one list of fixes for every target of the warnings (the list step 8 shows), searched for in budget seconds (default refit.BUDGET_S) and checked as a
    whole. m, rec and fx are draft.model_now()'s, decisions the draft's answers; none of what it is given is changed, and nothing is written.
    progress(done, total) is called as the targets are settled or have had their first full look. -> dict(
    stamp: the draft's, so a list made for a draft that has changed since is told apart;
    groups: the targets settled, in that order, each dict(key, kind, text, steps=[dict(n, fix, text, why, tags)]), n from 1 over the whole list;
    fixes: every fix, in order; also: the texts of the targets that others' fixes settle; needs: the rest, in the targets' order, each dict(key, kind, text, why);
    totals: dict(changes, moved (the lessons whose day or period changes), another_day (those whose day does), critical and warnings ([before, after] as step 8
    counts them, without the typed rules the list makes one check again), typed (the numbers of those rules));
    late: whether any of needs was not looked at in time; seconds)"""
    begun = time.monotonic(); p = _Plan(m, refit.targets(warnings), progress, begun + (refit.BUDGET_S if budget is None else budget)); p.run()
    before, after = p.check(fx, decisions); had = {w["key"] for w in before["warnings"] if _again(w)}   # the rules to check again for the edits made already
    count = lambda t: sum(1 for w in t["warnings"] if draft.counted(w) and (w["key"] in had or not _again(w)))
    at = lambda lessons: {x["id"]: (x["d"], x["p"]) for x in lessons}
    a, b = at(m["lessons"]), at(p.now["lessons"]); went = [i for i in a if i in b and a[i] != b[i]]; needs = p.needs()
    totals = dict(changes=len(p.all_fixes()), moved=len(went), another_day=sum(a[i][0] != b[i][0] for i in went), critical=[before["critical"], after["critical"]], warnings=[count(before), count(after)], typed=p.rechecked())
    return dict(stamp=draft.stamp(m["draft_meta"], rec), groups=p.groups(), fixes=p.all_fixes(), needs=needs, also=[t["text"] for i, t in enumerate(p.ts) if i in p.also], totals=totals,
                late=any(x["why"] == refit.LATE for x in needs), seconds=round(time.monotonic() - begun, 1))

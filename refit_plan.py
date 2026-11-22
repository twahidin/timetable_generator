"""The plan of a re-fit: one list of fixes for every warning it works on (refit.targets), each searched for on the timetable the
earlier ones leave (refit.solve), with its reasons and its numbers. Nothing here writes, and nothing it is given is changed."""
import logging, os, re, time, traceback
import draft, fixes, helper, refit
from ttgen import verify
from ttgen.export import check_model

LOOK_S = 2.0         # the least seconds of the budget (refit.BUDGET_S) one warning's full search is given
BROKEN = "The app could not work this one out: change it on the board."
TEACHER_FIRST = "Its teacher changes too: settle that first, then run Re-fit again."

_log = logging.getLogger(__name__)

def _again(w): return bool(re.fullmatch(r"typed:\d+:again(#\d+)?", w["key"]))

def _wishes(ws):
    """how many open Prefer warnings there are, "No room" and the typed rules to check again aside"""
    return sum(1 for w in ws if not w["decision"] and w["strength"] == "Prefer" and not w["key"].startswith("room:none:") and not _again(w))

class _Plan:
    """the work of plan: the targets (each is its place in ts) looked at in turn, every one on the timetable the list leaves so far.
    Nothing of m or of the targets is changed"""
    def __init__(self, m, ts, progress, end):
        self.m, self.spec, self.days, self.ts, self.progress, self.end = m, m["checked_setup"], m["days"], ts, progress, end
        self.first = {x["id"] for x in m["lessons"]}             # the lessons on the timetable the plan starts from
        self.now, self.changes, self.moved = m, 0, set()         # the timetable the list leaves so far; how often it changed; the lessons that stay where they are: moved or put in by the list
        self.solved, self.also, self.broken = [], set(), set()   # (target, its answer) in the order solved; those settled by the fixes of others; those the search broke on
        self.why, self.told = {}, set()                          # target -> the sentence of its last full look; the targets progress was told of
        self.seen, self.full, self.had = {}, {}, {}              # target -> self.changes at its last look, and at its last full look; the seconds that one had, when it was cut short
        key = [helper._dep_parts(t["key"])[0] for t in ts]; self.teacher = {i: [j for j, u in enumerate(ts) if u["kind"] == "teachers" and key[j] == key[i]] for i, t in enumerate(ts) if t["kind"] == "periods"}   # a periods target -> the teachers target of its key

    def all_fixes(self): return [f for _, got in self.solved for f in got["fixes"]]
    def lessons(self): return helper._apply(self.m["lessons"], self.all_fixes(), self.spec, self.days)["lessons"]   # the whole list from the start: an added lesson never takes the number of one deleted before it

    # ------------------------------------------------------------ looking at the targets
    def run(self):
        """passes without a move until one settles nothing, then a round of the full search, and so on until a round has nothing to look at or the time is up"""
        while True:
            while self._pass(): pass
            if not self._round(): break
        self._rest()
        if self.progress and len(self.told) < len(self.ts): self.progress(len(self.ts), len(self.ts))   # the time ran out, or an add was not looked at

    def _rest(self):
        """what is open still but gone on the timetable the list leaves (the time was up before it was looked at again) is settled by the list too"""
        for i in self._open() if self.solved else ():
            try:
                if self._is_gone(i, self.now): self.also.add(i)
            except Exception as e: self._break(i, e)

    def _open(self):
        closed = {i for i, _ in self.solved} | self.also | self.broken
        return [i for i in range(len(self.ts)) if i not in closed]

    def _waits(self, i):
        """the teachers targets that target i waits for: those of its key not settled, when it is a period to be added (by the teacher that change
        decides). Whether that is so is asked of the timetable as it is now, as direct asks it: periods short of the plan, and no band"""
        first = [j for j in self.teacher.get(i, ()) if j not in self.also and all(j != k for k, _ in self.solved)]
        if not first: return []
        k = helper._dep_parts(self.ts[i]["key"])[0]; short = {x["key"] for x in fixes.short(self.now, self.spec, self.m["pool"])}
        return first if verify._kstr(k) in short and not refit._band(verify.planned_rows(self.spec)[k], helper._of_key(self.now["lessons"], k)) else []

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
        self.solved.append((i, got)); self.changes += 1
        self.now = dict(self.m, lessons=self.lessons())
        self.moved |= got["moved"] | {x["id"] for x in self.now["lessons"]} - self.first

    def _tell(self, i):
        if i in self.told: return
        self.told.add(i)
        if self.progress: self.progress(len(self.told), len(self.ts))

    # ------------------------------------------------------------ the list as a whole
    def made(self, fx, decisions):
        """(helper.chain of the whole list on the timetable the plan starts from, what step 8 would list of the timetable it leaves)"""
        c = helper.chain(self.m, self.spec, self.days, self.all_fixes()); m = dict(self.m, lessons=c["lessons"]); checks = check_model(m)
        problems = list(checks["problems"]) + list(m.get("choice_problems") or []); m["checks"] = dict(checks, problems=problems, ok=not problems)   # as model_from_files makes it: the clashes are read from it
        return c, draft.listed(m, dict(fx, touched=set(fx["touched"]) | c["touched"], was=list(fx["was"]) + c["was"]), decisions)

    def _stands(self, i, lessons):
        """whether target i's warning is settled on these lessons, as the search says it (for one settled by others: as refit.solve says it is gone)"""
        if i in self.also: return self._is_gone(i, dict(self.m, lessons=lessons))
        w = self.ts[i]["w"]; return refit._settled(self.m, self.spec, self.days, w, lessons, helper._before(self.m, self.spec, w), refit._room_clash(self.m, w))

    def _is_gone(self, i, m):
        """whether target i's warning is gone on the timetable m, as refit.solve asks it"""
        w = self.ts[i]["w"]; return refit._gone(m, self.spec, self.days, w, helper._before(m, self.spec, w), refit._room_clash(self.m, w))

    def holds(self, c, before, after):
        """whether the list as a whole is one to offer (c, after: made's; before: what step 8 lists now): the judge has every step, every
        target is settled at the end, and there are no more mistakes and no more open wishes than before"""
        if refit._refusal(c) or len(c["texts"]) != len(self.all_fixes()): return False
        if not all(self._stands(i, c["lessons"]) for i in [i for i, _ in self.solved] + sorted(self.also)): return False
        return after["critical"] <= before["critical"] and _wishes(after["warnings"]) <= _wishes(before["warnings"])

    def drop(self):
        """the last solved target is taken out of the list; whatever the rest of it settles is found anew, and what is no longer settled needs you"""
        self.why.update({i: refit.NO_FIT for i in {self.solved.pop()[0]} | self.also}); self.also.clear(); self.now = dict(self.m, lessons=self.lessons()); self._rest()

    def groups(self):
        """the solved targets, each with its steps: numbered over the whole list and worded on the timetable the earlier steps leave"""
        out, L, n = [], self.m["lessons"], 0
        for i, got in self.solved:
            steps = []
            for f, why in zip(got["fixes"], got["why"]):
                r = helper._apply(L, [f], self.spec, self.days); n += 1
                steps.append(dict(n=n, fix=f, text=helper.say(dict(self.m, lessons=L), self.spec, self.days, f), why=why, tags=self._tags(f, L, r))); L = r["lessons"]
            out.append(dict(self._said(i), steps=steps))
        return out

    def _tags(self, f, lessons, r):
        """what a step (its fix, the lessons before it, what helper._apply made of them) is flagged with"""
        day = f["kind"] == "move" and helper._first(lessons, f["id"])["d"] != f["d"]; bare = f["kind"] == "add" and fixes._no_room(f["room"])
        return ["another day"] * day + ["no room"] * bare + [f"check T{n} again" for n in refit.rechecked(self.m, self.spec, r["lessons"], r["touched"], r["was"], [f])]

    def _said(self, i): return {k: self.ts[i][k] for k in ("key", "kind", "text")}

    def needs(self):
        done = {i for i, _ in self.solved} | self.also
        return [dict(self._said(i), why=self._sentence(i)) for i in range(len(self.ts)) if i not in done]

    def _sentence(self, i):
        """why target i needs you: what its last full look gave; without one, it was not looked at in time, unless it waits for a teacher change that was"""
        if i in self.why: return self.why[i]
        first = self._waits(i); return refit.LATE if not first or any(self.why.get(j, refit.LATE) == refit.LATE for j in first) else TEACHER_FIRST

def plan(m, rec, fx, decisions, warnings, progress=None, budget=None):
    """one list of fixes for every target of the warnings (the list step 8 shows), worked out in budget seconds (default refit.BUDGET_S). m, rec and fx are
    draft.model_now()'s, decisions the draft's answers; none of what it is given is changed, and nothing is written. progress(done, total) is called
    as the targets are settled or have had their first full look. -> dict(
    stamp: the draft's, so a list made for a draft that has changed since is told apart;
    groups: the targets settled, in that order, each dict(key, kind, text, steps=[dict(n, fix, text, why, tags)]), n from 1 over the whole list;
    fixes: every fix, in order; also: the texts of the targets that others' fixes settle; needs: the rest, in the targets' order, each dict(key, kind, text, why);
    totals: dict(changes, moved (the lessons whose day or period changes), another_day (those whose day does), critical and warnings ([before, after] as step 8
    counts them, without the typed rules the list makes one check again), typed (the numbers of those rules));
    late: whether any of needs was not looked at in time; seconds)"""
    begun = time.monotonic(); p = _Plan(m, refit.targets(warnings), progress, begun + (refit.BUDGET_S if budget is None else budget)); p.run()
    before = draft.listed(m, fx, decisions); c, after = p.made(fx, decisions)
    while p.solved and not p.holds(c, before, after): p.drop(); c, after = p.made(fx, decisions)   # it always holds when the judging was right
    had = {w["key"] for w in before["warnings"] if _again(w)}   # the rules to check again for the edits made already
    count = lambda t: sum(1 for w in t["warnings"] if draft.counted(w) and (w["key"] in had or not _again(w)))
    at = lambda lessons: {x["id"]: (x["d"], x["p"]) for x in lessons}
    a, b = at(m["lessons"]), at(c["lessons"]); went = [i for i in a if i in b and a[i] != b[i]]; needs = p.needs()
    totals = dict(changes=len(p.all_fixes()), moved=len(went), another_day=sum(a[i][0] != b[i][0] for i in went), critical=[before["critical"], after["critical"]],
                  warnings=[count(before), count(after)], typed=refit.rechecked(m, p.spec, c["lessons"], c["touched"], c["was"], p.all_fixes()))
    return dict(stamp=draft.stamp(m["draft_meta"], rec), groups=p.groups(), fixes=p.all_fixes(), needs=needs, also=[t["text"] for i, t in enumerate(p.ts) if i in p.also], totals=totals,
                late=any(x["why"] == refit.LATE for x in needs), seconds=round(time.monotonic() - begun, 1))

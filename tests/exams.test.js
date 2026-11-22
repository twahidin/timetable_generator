// Plain-assert tests for static/exams.js's Approval tab checks: run with `node tests/exams.test.js`.
// The page is one closure, so the function under test is cut out of the file by its braces and run on its own.
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(path.join(__dirname, "..", "static", "exams.js"), "utf8");
function cut(name) {
  const at = SRC.indexOf(`function ${name}(`); assert(at >= 0, name);
  let i = SRC.indexOf("{", at), depth = 0;
  for (; i < SRC.length; i++) { if (SRC[i] === "{") depth++; else if (SRC[i] === "}" && --depth === 0) break; }
  return SRC.slice(at, i + 1);
}
const has = n => SRC.indexOf(`function ${n}(`) >= 0;
const cutA = n => { const at = SRC.indexOf(`function ${n}(`); return (SRC.slice(at - 6, at) === "async " ? "async " : "") + cut(n); };
const fns = names => names.filter(has).map(cutA).join("\n");
const uniq = a => a.filter((x, i) => a.indexOf(x) === i);
const checkLines = new Function("uniq", `${cut("checkLines")}; return checkLines;`)(uniq);

let n = 0; const t = (name, f) => { f(); n++; };
const free = lines => ({ key: "free", ok: !lines.length, lines });
const others = lines => ({ key: "others", ok: !lines.length, lines });
const TAKES2 = "Sec 4 Exam (approved) takes 2 of these invigilators on Mon 5 Oct.";
const USES = "Sec 4 Exam (approved) uses Hall on Mon 5 Oct too.";
const busy = (who, date) => `${who}, 3-01 on ${date} 07:35–09:00: is on Sec 4 Exam then (Hall).`;

t("a takes line goes when the free lines name that schedule for as many people that day", () => {
  const all = [free([busy("Ms A", "Mon 5 Oct"), busy("Mr B", "Mon 5 Oct")]), others([TAKES2, USES])];
  assert.deepStrictEqual(checkLines(all[1], all), [USES]);
});
t("it stays when the free lines name fewer people than it counts", () => {
  const all = [free([busy("Ms A", "Mon 5 Oct"), busy("Ms A", "Mon 5 Oct").replace("3-01", "3-02")]), others([TAKES2])];
  assert.deepStrictEqual(checkLines(all[1], all), [TAKES2], "one person twice is one person");
});
t("a clash on another date or with another schedule does not count", () => {
  const all = [free([busy("Ms A", "Tue 6 Oct"), busy("Mr B", "Mon 5 Oct").replace("Sec 4 Exam", "Sec 2 Exam")]), others([TAKES2])];
  assert.deepStrictEqual(checkLines(all[1], all), [TAKES2]);
  const own = [free(["Ms A, 3-01 on Mon 5 Oct 07:35–09:00: is on another duty then (3-02).", busy("Mr B", "Mon 5 Oct")]), others([TAKES2])];
  assert.deepStrictEqual(checkLines(own[1], own), [TAKES2], "the own-duty clash is not the other schedule");
});
t("other checks pass through as they are", () => {
  const all = [free([busy("Ms A", "Mon 5 Oct")]), others([])];
  assert.deepStrictEqual(checkLines(all[0], all), all[0].lines);
  assert.deepStrictEqual(checkLines(all[1], all), []);
});
t("an event's free line has no room in brackets", () => {
  const ev = who => `${who}, 3-01 on Mon 5 Oct 07:35–09:00: is on Sec 3 Learning Journey then.`;
  const TAKES = "Sec 3 Learning Journey (waiting) takes 2 of these invigilators on Mon 5 Oct.";
  const all = [free([ev("Ms A"), ev("Mr B")]), others([TAKES])];
  assert.deepStrictEqual(checkLines(all[1], all), []);
});
/* the Lessons tab: one backup item of each state, its sentence and its "Handled ourselves" box */
const esc = x => String(x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const stateCode = SRC.slice(SRC.indexOf("const BACKUP_STATE"), SRC.indexOf("function lessonList("));   /* the state table, the box rule and backupState */
const lessonsTab = view => new Function("esc", "S", "fmtDate", `${stateCode}\n${cut("lessonList")}\n${cut("tabLessons")}; return tabLessons();`)(esc, { view, open: {}, busy: false }, d => d);
const STATES = [["later", "Goes to the relief team when approved", true], ["sent", "Sent to the relief team", true], ["relief", "Relief: Mr Ben Ong", true],
  ["handled", "Handled ourselves", true], ["stopped", "Not happening: 3A is on Sec 3 End-of-Year Exam", false], ["past", "In the past", false], ["elsewhere", "Sent by another schedule", false],
  ["handled_elsewhere", "Handled by another schedule", false]];
t("the Lessons tab says where each backup stands and offers Handled ourselves only where it can", () => {
  const backup = STATES.map(([state], i) => ({ date: "2027-01-04", start: "07:40", end: "08:20", classes: ["3A"], subject: "English", teachers: ["Ms Z"], teacher: "Ms Z" + i, key: "k" + i, state,
    relief: state === "relief" ? "Mr Ben Ong" : null, stopped: state === "stopped" ? "3A is on Sec 3 End-of-Year Exam" : "" }));
  const html = lessonsTab({ lessons: { none: [], backup, runs: [] } });
  STATES.forEach(([state, text, box], i) => {
    assert(html.includes(`>${text}`), state + ": " + text);
    const has = html.includes(`data-t="Ms Z${i}" data-k="k${i}"`);
    assert.strictEqual(has, box, state + " box");
  });
  assert.strictEqual((html.match(/Handled ourselves<\/label>/g) || []).length, 4);
  assert(/data-k="k3" checked/.test(html), "only the handled one is ticked");
  assert(!/data-k="k0" checked/.test(html));
  assert(html.includes("Backups go to the relief team as planned relief when the schedule is approved."));
});
t("the exams page no longer says that sending comes in a later stage", () => {
  assert(!SRC.includes("arrives in a later stage") && !SRC.includes("comes in a later stage"));
});
/* onHandled: the click path with a stubbed api */
const runHandled = async (S, reply) => {
  const calls = [];
  const f = new Function("S", "api", "paint", "paintSave", "isEv", "clearTimeout", `${SRC.slice(SRC.indexOf("  const SERVER_KEYS"), SRC.indexOf("  /* the one place that decides"))}\n${fns(["takeRev", "takeOwn", "blockPage", "onChain"])}\nasync ${cut("onHandled")}; return onHandled;`)(S, async (m, u, b) => { calls.push([m, u, b]); return reply; }, () => {}, () => {}, () => S.base === "/api/events", clearTimeout);
  return [f, calls];
};
const box = (checked, teacher = "Ms Z", key = "k1") => ({ checked, dataset: { t: teacher, k: key } });
(async () => {
  let S = { base: "/api/exams", id: "x1", busy: false, view: { old: 1 }, rv: {}, hpend: {}, chain: Promise.resolve() };
  let [f, calls] = await runHandled(S, { ok: true, status: 200, j: { lessons: { backup: [] } } });
  const el = box(true), p = f(el);
  assert.deepStrictEqual(S.hpend, { "Ms Z|k1": true }, "the chosen value shows while in flight");
  assert.strictEqual(S.busy, true);
  const el2 = box(true); await f(el2);
  assert.strictEqual(el2.checked, false, "a second click while busy is put back");
  assert.strictEqual(calls.length, 1, "and posts nothing");
  await p;
  assert.deepStrictEqual(calls[0], ["POST", "/api/exams/x1/handled", { teacher: "Ms Z", key: "k1", handled: true }]);
  assert.deepStrictEqual(S.view, { lessons: { backup: [] } }); assert.strictEqual(S.rv, null); assert.deepStrictEqual(S.hpend, {}); assert.strictEqual(S.busy, false);
  S = { base: "/api/events", id: "e1", busy: false, view: { old: 1 }, rv: { keep: 1 }, hpend: {}, msg: "", bad: false, chain: Promise.resolve() };
  [f, calls] = await runHandled(S, { ok: false, status: 400, j: { error: "That lesson no longer needs a backup." } });
  await f(box(true));
  assert.strictEqual(calls[0][1], "/api/events/e1/handled");
  assert.strictEqual(S.msg, "That lesson no longer needs a backup."); assert.strictEqual(S.bad, true);
  assert.deepStrictEqual(S.view, { old: 1 }); assert.deepStrictEqual(S.hpend, {});
  S = { base: "/api/exams", id: "x1", busy: false, view: {}, rv: {}, hpend: {}, sched: { rev: 3 }, chain: Promise.resolve() };
  [f, calls] = await runHandled(S, { ok: true, status: 200, j: { lessons: { backup: [] }, rev: 4 } });
  await f(box(true));
  assert.strictEqual(S.sched.rev, 4, "the answer's revision becomes the page's");
  console.log("onHandled cases passed");
})().catch(e => { console.error(e); process.exit(1); });
/* the page's own functions against a fake server that keeps one schedule and its revision */
const CONSTS = SRC.slice(SRC.indexOf("  const SERVER_KEYS"), SRC.indexOf("  /* the one place that decides"));   /* the keys and small helpers takeSched reads */
const NAMES = ["takeRev", "takeSched", "takeOwn", "blockPage", "onChain", "saveInner", "saveNow", "flush", "edit", "refreshView", "serverAction", "viewAction", "approvalAction", "onHandled", "takeReview", "loadReview", "onWhenField", "onClick", "onPaperField", "dropSuggested", "agreeSuggested", "suggestedLine"];
const SENT = who => `This exam was changed by ${who} since you opened it. Reload to carry on.`;
function rig(ev) {
  const srv = { sched: { id: "x1", name: "E", papers: [], going: ["Ms A"], duties: [{ who: "Ms A" }], rev: 1, saved_by: "Ms A" }, calls: [], holds: {}, lock: null, onPost: null, failGet: false, delay: 0, noAdd: false, clean: false, norm: null, cut: {} };
  const S = { base: ev ? "/api/events" : "/api/exams", id: "x1", sched: { id: "x1", name: "E", papers: [], going: ["Ms A"], duties: [{ who: "Ms A" }], rev: 1 }, known: { id: "x1", name: "E", papers: [], going: ["Ms A"], duties: [{ who: "Ms A" }], rev: 1 }, view: null, rv: null, chain: Promise.resolve(), timer: null,
    dirty: false, blocked: false, rev: 0, saving: false, msg: "", bad: false, busy: false, hpend: {}, rvTok: 0, tab: "when", label: "Draft", note: "", sbNote: "", abMsg: "" };
  const api = async (m, u, b) => {
    const rest = u.replace(S.base + "/x1", "");
    srv.calls.push([m, rest]);
    let out;
    const cutOff = srv.cut[m + rest]; delete srv.cut[m + rest];   /* "late": the server's work is done, its answer is cut off; "early": the answer is another page's, nothing reached the server */
    if (cutOff === "early") return { ok: true, status: 200, j: {} };
    if (m === "PUT") { if (srv.lock) await srv.lock; out = b.rev !== srv.sched.rev ? { ok: false, status: 409, j: { error: SENT("Ms B") } }
        : (srv.prev = srv.sched, srv.sched = Object.assign({}, JSON.parse(JSON.stringify(b)), { rev: srv.sched.rev + 1, saved_by: "Ms A" }), srv.norm && srv.norm(srv.sched), srv.clean && (srv.sched.suggested = (srv.sched.suggested || []).filter(id => srv.sched.papers.some(p => p.id === id && !(srv.prev.papers || []).some(q => q.id === id && (q.date !== p.date || q.start !== p.start))))), { ok: true, status: 200, j: JSON.parse(JSON.stringify(srv.sched)) }); }
    else if (m === "GET" && rest === "" && srv.failGet) { srv.failGet = false; out = { ok: false, status: 500, j: { error: "down" } }; }
    else if (m === "GET" && rest === "") out = { ok: true, status: 200, j: JSON.parse(JSON.stringify(srv.sched)) };
    else if (m === "GET" && rest === "/view") out = { ok: true, status: 200, j: { rev: srv.sched.rev, made: null } };
    else if (m === "GET" && rest === "/review") out = { ok: true, status: 200, j: { rev: srv.sched.rev, status: "draft", label: "Draft", note: "" } };
    else if (m === "POST") {
      let done; srv.lock = new Promise(r => { done = r; });
      const h0 = srv.holds[rest]; delete srv.holds[rest];
      if (h0) await h0;
      if (rest === "/fill" && !srv.noAdd) { const n = srv.sched.papers.length + 1; srv.sched.papers = srv.sched.papers.concat([{ id: "p" + n }]); srv.sched.going = srv.sched.going.concat(["G" + n]); }
      if (rest === "/away") { srv.sched.going = srv.sched.going.map(x => x === "Ms A" ? "Ms C" : x); srv.sched.duties = srv.sched.duties.map(d => d.who === "Ms A" ? { who: "Ms C" } : d); }
      if (!(rest === "/fill" && srv.noAdd)) srv.sched.rev++;   /* a fill that adds no one saves nothing */
      srv.lock = null; done();
      out = { ok: true, status: 200, j: rest === "/fill" ? JSON.parse(JSON.stringify(srv.sched)) : rest === "/make" || rest === "/handled" ? { rev: srv.sched.rev, made: {} } : { rev: srv.sched.rev, status: "draft", label: "Draft", note: "" } };
      if (srv.onPost) { const f = srv.onPost; srv.onPost = null; f(); }
    } else throw new Error("unexpected " + m + " " + u);
    const h = srv.holds[m + rest]; delete srv.holds[m + rest];   /* one call is held, the later ones are not */
    if (h) await h;
    if (srv.delay) await sleep(srv.delay);
    return cutOff ? { ok: true, status: 200, j: {} } : out;
  };
  const noop = () => {}, loc = { reloaded: 0, reload() { this.reloaded++; } };
  const names = NAMES.filter(has);
  const f = new Function("S", "api", "paint", "paintSave", "render", "$", "chipClass", "esc", "isEv", "location", "setTimeout", "clearTimeout",
    `${CONSTS}\n${fns(NAMES)}\nreturn {${names.join(",")}};`)(S, api, noop, noop, noop, () => null, () => "", esc, () => S.base === "/api/events", loc, setTimeout, clearTimeout);
  return { S, srv, f, loc };
}
const gate = () => { let go; const p = new Promise(r => { go = r; }); return { p, go }; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const tick = () => new Promise(r => setTimeout(r, 5));
const named = fn => assert(fn, "function missing");

(async () => {
  /* 1: a reply that carries only a revision never moves the page's revision; the contents are still old */
  for (const how of ["review", "make", "view"]) {
    const { S, srv, f } = rig();
    srv.sched = Object.assign({}, srv.sched, { papers: [{ id: "p1" }], rev: 2 });   /* someone else filled the papers */
    if (how === "review") await f.loadReview(false);
    else if (how === "make") await f.viewAction("make", {}, "Made.");
    else await f.refreshView();
    assert.strictEqual(S.sched.rev === 1 || S.blocked, true, how + ": rev 2 was taken with old contents");
    f.edit(() => { S.sched.name = "Mine"; });
    await f.flush();
    assert.deepStrictEqual(srv.sched.papers, [{ id: "p1" }], how + ": the stored papers are intact");
    assert.strictEqual(S.sched.papers.length, 0);
    assert.strictEqual(S.blocked, true, how + ": the page ends blocked");
    assert.strictEqual(srv.sched.name, "E", how + ": nothing of the old copy was saved");
  }
  { /* the approval buttons: the answer counts only as the next revision */
    const { S, srv, f } = rig(); srv.sched.rev = 2;
    assert.strictEqual(await f.approvalAction("send", {}, "Sent."), false);
    assert.strictEqual(S.blocked, true); assert.strictEqual(S.msg === "Sent.", false);
  }
  console.log("stale contents cases passed");

  /* 2: an edit made while the page's own Make runs is saved afterwards, nothing lost, no block */
  for (const how of ["make", "send", "handled"]) {
    const { S, srv, f } = rig(), g = gate();
    const rest = how === "handled" ? "/handled" : "/" + how; srv.holds[rest] = g.p;
    const p = how === "make" ? f.viewAction("make", {}, "Made.") : how === "send" ? f.approvalAction("send", {}, "Sent.") : f.onHandled({ checked: true, dataset: { t: "Ms Z", k: "k1" } });
    await tick(); assert.strictEqual(S.busy, true);
    f.edit(() => { S.sched.name = "Mine"; });
    const w = f.flush(); await tick();
    g.go(); await p; await w;
    assert.strictEqual(S.blocked, false, how + ": no block"); assert.strictEqual(S.dirty, false, how + ": saved");
    assert.strictEqual(srv.sched.name, "Mine", how + ": the edit is stored"); assert.strictEqual(srv.sched.rev, 3);
    assert.strictEqual(S.sched.rev, 3);
  }
  console.log("edit while an action runs cases passed");

  /* 3: a GET that lands late never changes the revision */
  for (const how of ["view", "review"]) {
    const { S, srv, f } = rig(), g = gate();
    srv.holds["GET/" + how] = g.p;
    const late = how === "view" ? f.refreshView() : f.loadReview(true);
    await tick();
    f.edit(() => { S.sched.name = "Mine"; }); await f.flush();
    assert.strictEqual(S.sched.rev, 2);
    g.go(); await late;
    assert.strictEqual(S.sched.rev, 2, how + ": a late answer does not move the revision back");
    assert.strictEqual(S.blocked, false);
  }
  console.log("late GET cases passed");

  /* every caller that may take a revision does, and only as the ruling says */
  { const { S, srv, f } = rig(); f.edit(() => { S.sched.name = "A"; }); await f.flush(); assert.strictEqual(S.sched.rev, 2, "saveNow takes the PUT's rev"); }
  { const { S, srv, f } = rig(); await f.serverAction("POST", "/api/exams/x1/fill", {}); assert.strictEqual(S.sched.rev, 2, "serverAction takes the whole schedule's rev"); }
  { const { S, srv, f } = rig(); assert.strictEqual(await f.viewAction("make", {}, "Made."), true); assert.strictEqual(S.sched.rev, 2, "viewAction takes its own save"); }
  { const { S, srv, f } = rig(); assert.strictEqual(await f.approvalAction("send", {}, "Sent."), true); assert.strictEqual(S.sched.rev, 2, "approvalAction takes the GET's rev"); assert.strictEqual(S.sched.name, "E"); }
  { const { S, srv, f } = rig(); await f.onHandled({ checked: true, dataset: { t: "Ms Z", k: "k1" } }); assert.strictEqual(S.sched.rev, 2, "onHandled takes its own save"); }
  { const { S, srv, f } = rig(); await f.loadReview(false); await f.refreshView(); assert.strictEqual(S.sched.rev, 1, "the two GETs of a part never take it"); }
  { const { S, f } = rig(); S.dirty = true; S.sched.name = "mine";
    const base = Object.assign({}, S.sched, { name: "E" });
    f.takeSched({ id: "x1", name: "E", rev: 4, status: "approved", log: [1], papers: [] }, base);
    assert.deepStrictEqual([S.sched.name, S.sched.rev, S.sched.status, S.sched.log], ["mine", 4, "approved", [1]], "an unsaved edit stays, the server's own parts and revision come in");
    S.sched = Object.assign({}, base); f.takeSched({ id: "x1", name: "theirs", rev: 5 }, base); assert.deepStrictEqual([S.sched.name, S.sched.rev], ["theirs", 5]); }
  console.log("takeRev callers passed");

  /* the sentences */
  { const { S, srv, f } = rig(); srv.sched.rev = 5;
    f.edit(() => { S.sched.name = "A"; }); await f.flush();
    assert.strictEqual(S.blocked, true); assert.strictEqual(S.blockMsg, SENT("Ms B")); assert.strictEqual(S.dirty, true);
    S.msg = "Choose who is away and who takes it."; S.bad = true;
    const html = f.saveInner();
    assert(html.includes(SENT("Ms B")) && !html.includes("Choose who"), "the sentence stays whatever is set after it");
    assert(html.includes('data-act="reload"') && html.includes("<button"), "a Reload button");
    const n = srv.calls.length;
    f.edit(() => { S.sched.name = "B"; }); assert.strictEqual(S.sched.name, "A", "edit does nothing while blocked");
    const ch = S.chain; await f.flush(); assert.strictEqual(srv.calls.length, n, "flush sends nothing while blocked"); assert.strictEqual(S.chain, ch, "and queues nothing");
    S.chain = Promise.resolve().then(() => f.saveNow()); await S.chain; assert.strictEqual(srv.calls.length, n, "a queued save sends nothing");
    await f.serverAction("POST", "/api/exams/x1/fill", {}); assert.strictEqual(srv.calls.length, n, "nor does an action");
  }
  { const { S, srv, f, loc } = rig(); S.id = "x1";
    f.onClick({ target: { closest: () => ({ dataset: { act: "reload" }, matches: () => false }) } });
    assert.strictEqual(loc.reloaded, 1, "the button reloads the page"); }
  { const { S, srv, f } = rig(true); srv.sched.rev = 9; f.edit(() => {}); await f.flush(); assert.strictEqual(S.blockMsg, SENT("Ms B")); }
  { const { S, srv, f } = rig(); srv.sched.rev = 2; await f.viewAction("make", {}, "Made.");
    assert.strictEqual(S.blocked, true); assert.strictEqual(S.blockMsg, "This exam was changed by someone else since you opened it. Reload to carry on."); }
  { const { S, srv, f } = rig(true); srv.sched.rev = 2; await f.viewAction("make", {}, "Made.");
    assert.strictEqual(S.blockMsg, "This event was changed by someone else since you opened it. Reload to carry on."); }
  { /* any other 409 is just a sentence */
    const { S, srv, f } = rig();
    const api409 = async () => ({ ok: false, status: 409, j: { error: "Publish the timetable first." } });
    const g = new Function("S", "api", "paintSave", "refreshView", "copyOf", "takeSched", "blockPage", `${cutA("saveNow")}; return saveNow;`)(S, api409, () => {}, async () => {}, v => v, () => true, () => {});
    S.dirty = true; assert.strictEqual(await g(), false);
    assert.strictEqual(S.blocked, false); assert.strictEqual(S.msg, "Publish the timetable first."); assert.strictEqual(S.bad, true);
  }
  console.log("block cases passed");

  /* round 2: the page keeps what it must, key by key, whenever the whole schedule comes back */
  const FILLED = { id: "p1" };
  const elsewhere = (srv, ch) => { srv.sched = Object.assign({}, srv.sched, ch, { rev: srv.sched.rev + 1 }); };
  { /* a: Fill, and a Name typed before the reply lands */
    const { S, srv, f } = rig(), g = gate(); srv.holds["/fill"] = g.p;
    const p = f.serverAction("POST", "/api/exams/x1/fill", {}, undefined, () => {}); await tick();
    f.edit(() => { S.sched.name = "Mine"; }); const w = f.flush(); await tick();
    g.go(); await p; await w;
    assert.strictEqual(S.blocked, false); assert.strictEqual(S.dirty, false);
    assert.deepStrictEqual(srv.sched.papers, [FILLED], "the filled papers are still stored after the page's save");
    assert.strictEqual(srv.sched.name, "Mine"); assert.deepStrictEqual(S.sched.papers, [FILLED]);
  }
  { /* b: Send, a Name typed, someone else saves the papers before the follow-up read */
    const { S, srv, f } = rig(), g = gate(); srv.holds["/send"] = g.p;
    const p = f.approvalAction("send", {}, "Sent."); await tick();
    f.edit(() => { S.sched.name = "Mine"; }); const w = f.flush(); await tick();
    srv.onPost = () => elsewhere(srv, { papers: [FILLED] });
    g.go(); await p; await w;
    assert.strictEqual(S.blocked, false); assert.deepStrictEqual(srv.sched.papers, [FILLED], "someone else's papers survive");
    assert.strictEqual(srv.sched.name, "Mine"); assert.strictEqual(S.dirty, false);
  }
  { /* b2: both changed the same key to different values: blocked, nothing stored over it */
    const { S, srv, f } = rig(), g = gate(); srv.holds["/send"] = g.p;
    const p = f.approvalAction("send", {}, "Sent."); await tick();
    f.edit(() => { S.sched.name = "Mine"; }); const w = f.flush(); await tick();
    srv.onPost = () => elsewhere(srv, { name: "Theirs" });
    g.go(); await p; await w;
    assert.strictEqual(S.blocked, true); assert.strictEqual(srv.sched.name, "Theirs");
    assert.strictEqual(S.blockMsg, "This exam was changed by someone else since you opened it. Reload to carry on.");
  }
  { /* c: an event's away changes the going list: an edit made meanwhile does not put the away teacher back */
    const { S, srv, f } = rig(true), g = gate(); srv.holds["/away"] = g.p;
    const p = f.approvalAction("away", { away: "Ms A", name: "Ms C" }, ""); await tick();
    f.edit(() => { S.sched.name = "Mine"; }); const w = f.flush(); await tick();
    g.go(); await p; await w;
    assert.strictEqual(S.blocked, false); assert.deepStrictEqual(srv.sched.going, ["Ms C"], "the replacement stays");
    assert.deepStrictEqual(srv.sched.duties, [{ who: "Ms C" }]); assert.strictEqual(srv.sched.name, "Mine");
  }
  { /* c1: someone else saved the papers while the away ran, nothing typed: the page reads the whole schedule and goes on */
    const { S, srv, f } = rig(true), g = gate(); srv.holds["/away"] = g.p;
    const p = f.approvalAction("away", { away: "Ms A", name: "Ms C" }, ""); await tick();
    elsewhere(srv, { papers: [FILLED] }); g.go(); await p;
    assert.strictEqual(S.blocked, false); assert.deepStrictEqual(S.sched.papers, [FILLED]); assert.deepStrictEqual(S.sched.going, ["Ms C"]); assert.strictEqual(S.sched.rev, srv.sched.rev);
  }
  { /* c2: the read after an event's away fails: the page is blocked, not left with the old list at the new revision */
    const { S, srv, f } = rig(true); srv.failGet = true;
    assert.strictEqual(await f.approvalAction("away", { away: "Ms A", name: "Ms C" }, ""), false);
    assert.strictEqual(S.blocked, true);
    assert.strictEqual(S.blockMsg, "This event was changed by someone else since you opened it. Reload to carry on.");
  }
  { /* important 2: a Fill in flight does not make the page's own autosave a stranger */
    const { S, srv, f } = rig(), g = gate(); srv.holds["/fill"] = g.p;
    const p = f.serverAction("POST", "/api/exams/x1/fill", {}, undefined, () => {}); await tick();
    f.edit(() => { S.sched.name = "Mine"; }); const w = f.flush(); await tick();
    g.go(); await p; await w;
    assert.strictEqual(S.blocked, false); assert.strictEqual(srv.sched.name, "Mine");
  }
  { /* minor 3: a tick queued behind a refused save posts nothing and the sentence stays */
    const { S, srv, f } = rig(true), g = gate(); elsewhere(srv, {}); srv.holds["PUT"] = g.p;
    f.edit(() => { S.sched.name = "Mine"; }); const w = f.flush(); await tick();
    const el = { checked: true, dataset: { t: "Ms Z", k: "k1" } }, h = f.onHandled(el); await tick();
    g.go(); await w; await h;
    assert.strictEqual(S.blocked, true); assert.deepStrictEqual(srv.calls.filter(c => c[1] === "/handled"), [], "nothing was posted");
    assert.strictEqual(S.blockMsg, SENT("Ms B")); assert.strictEqual(S.busy, false); assert.deepStrictEqual(S.hpend, {});
  }
  { /* the guards at the click: a blocked page does none of these */
    const { S, srv, f } = rig(); S.blocked = true; S.blockMsg = "x"; S.msg = "keep";
    assert.strictEqual(await f.viewAction("make", {}, "Made."), false); assert.strictEqual(S.msg, "keep");
    assert.strictEqual(await f.approvalAction("send", {}, "Sent."), false); assert.strictEqual(S.msg, "keep");
    const el = { checked: true, dataset: { t: "Ms Z", k: "k1" } }; S.hpend = {}; await f.onHandled(el);
    assert.strictEqual(el.checked, false); assert.deepStrictEqual(S.hpend, {}); assert.strictEqual(S.busy, false);
    assert.deepStrictEqual(srv.calls, []);
  }
  { /* leaving the page: asked while there are unsaved changes, not once blocked (Reload is the way out) */
    const fn = new Function("S", `${cut("onBeforeUnload")}; return onBeforeUnload;`)({ dirty: true, blocked: false });
    let stopped = 0; fn({ preventDefault() { stopped++; } }); assert.strictEqual(stopped, 1);
    const g2 = new Function("S", `${cut("onBeforeUnload")}; return onBeforeUnload;`)({ dirty: true, blocked: true });
    g2({ preventDefault() { stopped++; } }); assert.strictEqual(stopped, 1);
  }
  console.log("round 2 cases passed");

  /* round 3: the merge base is what the page last knew the server held, not a copy taken when the action was clicked */
  const URL = "/api/events/x1/fill", noop2 = () => {};
  const adds = (f, n, gap) => Array.from({ length: n }, (_, i) => sleep(i * gap).then(() => f.serverAction("POST", URL, {}, undefined, noop2)));
  { /* r3a: type Where, Add, Add 20 ms later, type Name */
    const { S, srv, f } = rig(true); srv.delay = 40;
    f.edit(() => { S.sched.where = "Hall"; });
    const ps = adds(f, 2, 20); await sleep(100); f.edit(() => { S.sched.name = "Name"; });
    await Promise.all(ps); await f.flush();
    assert.strictEqual(S.blocked, false, "no false block"); assert.deepStrictEqual(srv.sched.papers, [{ id: "p1" }, { id: "p2" }]);
    assert.strictEqual(srv.sched.name, "Name", "Name is saved"); assert.strictEqual(srv.sched.where, "Hall"); assert.deepStrictEqual(S.sched.papers, srv.sched.papers);
  }
  { /* r3b: the same with nothing typed after */
    const { S, srv, f } = rig(true); srv.delay = 40;
    f.edit(() => { S.sched.where = "Hall"; });
    await Promise.all(adds(f, 2, 20)); await f.flush();
    assert.strictEqual(S.blocked, false); assert.deepStrictEqual(S.sched.papers, [{ id: "p1" }, { id: "p2" }]); assert.strictEqual(srv.sched.where, "Hall");
  }
  { /* r3c: three Adds */
    const { S, srv, f } = rig(true); srv.delay = 40;
    f.edit(() => { S.sched.where = "Hall"; });
    await Promise.all(adds(f, 3, 10)); await f.flush();
    assert.strictEqual(S.blocked, false); assert.strictEqual(S.sched.papers.length, 3); assert.strictEqual(srv.sched.papers.length, 3);
  }
  { /* r3d: a tick in flight and two Adds */
    const { S, srv, f } = rig(true); srv.delay = 40;
    const h = f.onHandled({ checked: true, dataset: { t: "Ms Z", k: "k1" } }); await sleep(5);
    await Promise.all([h].concat(adds(f, 2, 10))); await f.flush();
    assert.strictEqual(S.blocked, false); assert.strictEqual(S.sched.papers.length, 2); assert.strictEqual(S.busy, false);
  }
  { /* r3e: an Add, then Replace now */
    const { S, srv, f } = rig(true); srv.delay = 40;
    f.edit(() => { S.sched.where = "Hall"; });
    const a = adds(f, 1, 0)[0], b = sleep(15).then(() => f.approvalAction("away", { away: "Ms A", name: "Ms C" }, ""));
    await Promise.all([a, b]); await f.flush();
    assert.strictEqual(S.blocked, false); assert.deepStrictEqual(srv.sched.going, ["Ms C", "G1"]); assert.deepStrictEqual(S.sched.going, ["Ms C", "G1"]); assert.strictEqual(srv.sched.where, "Hall");
  }
  { /* r3f: Add B, then a fill that adds no one, while another tab takes B off between them: B does not come back */
    const { S, srv, f } = rig(true); srv.delay = 30;
    srv.sched.papers = [{ id: "A" }]; S.sched.papers = [{ id: "A" }]; S.known.papers = [{ id: "A" }];
    f.edit(() => { S.sched.where = "Hall"; });
    srv.onPost = () => { srv.sched = Object.assign({}, srv.sched, { papers: [{ id: "A" }], rev: srv.sched.rev + 1 }); srv.noAdd = true; };
    await Promise.all(adds(f, 2, 10));
    assert.strictEqual(S.blocked, false); assert.deepStrictEqual(S.sched.papers, [{ id: "A" }], "B stays off");
    f.edit(() => { S.sched.name = "Mine"; }); await f.flush();
    assert.deepStrictEqual(srv.sched.papers, [{ id: "A" }], "and the next save does not put it back"); assert.strictEqual(srv.sched.name, "Mine");
  }
  { /* r3g: what the server cleans on a save reaches the page; what was typed while it was saving stays */
    const { S, srv, f } = rig(); srv.clean = true; srv.delay = 30;
    f.edit(() => { S.sched.suggested = ["zz"]; });
    const w = f.flush(); await sleep(10); f.edit(() => { S.sched.name = "Later"; }); await w;
    assert.deepStrictEqual(srv.sched.suggested, [], "the server dropped it"); assert.deepStrictEqual(S.sched.suggested, [], "and the page has it dropped too");
    assert.strictEqual(S.sched.name, "Later"); assert.strictEqual(S.dirty, true, "the later edit is still to be saved");
    await f.flush(); assert.strictEqual(srv.sched.name, "Later"); assert.strictEqual(S.blocked, false);
  }
  { /* r3h: the work of another tab, read by a late own reply, with nothing typed, is taken whole */
    const { S, srv, f } = rig(true);
    await f.serverAction("POST", URL, {}, undefined, noop2);
    elsewhere(srv, { papers: [] }); srv.noAdd = true;
    await f.serverAction("POST", URL, {}, undefined, noop2);
    assert.deepStrictEqual(S.sched.papers, []); assert.strictEqual(S.sched.rev, srv.sched.rev);
  }
  { /* r3i: a rejected chain still honours a block */
    const { S, srv, f } = rig(); let ran = 0;
    S.chain = Promise.reject(new Error("x")); S.blocked = true;
    assert.strictEqual(await f.onChain(() => { ran++; return true; }), false); assert.strictEqual(ran, 0);
  }
  { /* r3j: a refused conflict stops the action (serverAction): its callback and message do not run */
    const { S, srv, f } = rig(), g = gate(); srv.holds["/fill"] = g.p; let called = 0;
    const p = f.serverAction("POST", "/api/exams/x1/fill", {}, undefined, () => { called++; }); await tick();
    f.edit(() => { S.sched.name = "Mine"; }); srv.sched.name = "Theirs";
    g.go(); await p; assert.strictEqual(called, 0); assert.strictEqual(S.blocked, true);
  }
  { /* r3k: the undo of busy and the tick reach a queued viewAction and approvalAction */
    for (const how of ["view", "approval"]) {
      const { S, srv, f } = rig(), g = gate(); elsewhere(srv, {}); srv.holds["PUT"] = g.p;
      f.edit(() => { S.sched.name = "Mine"; }); const w = f.flush(); await tick();
      const h = how === "view" ? f.viewAction("make", {}, "Made.") : f.approvalAction("send", {}, "Sent."); await tick();
      g.go(); await w; await h;
      assert.strictEqual(S.busy, false, how + ": busy put back"); assert.deepStrictEqual(srv.calls.filter(c => c[0] === "POST"), []);
    }
  }
  { /* r3l: a refused action says so: approvalAction returns false and no success message */
    const { S, srv, f } = rig(), g = gate(); srv.holds["/send"] = g.p;
    const p = f.approvalAction("send", {}, "Sent."); await tick();
    f.edit(() => { S.sched.name = "Mine"; }); srv.onPost = () => { srv.sched.name = "Theirs"; srv.sched.rev++; };
    g.go(); assert.strictEqual(await p, false); assert.notStrictEqual(S.msg, "Sent.");
  }
  { /* r3m: the event page's handled tick succeeds, and its review is read, without moving the revision */
    const { S, srv, f } = rig(true);
    await f.onHandled({ checked: true, dataset: { t: "Ms Z", k: "k1" } }); assert.strictEqual(S.sched.rev, 2); assert.strictEqual(S.blocked, false);
    await f.loadReview(false); assert.strictEqual(S.sched.rev, 2); assert.strictEqual(S.rv.status, "draft");
    assert.deepStrictEqual(srv.calls.map(c => c.join(" ")), ["POST /handled", "GET /review"]);
  }
  { /* r3n: the server's own parts come from theirs, even where the page's copy of them differs from what it last knew (a review sets the status) */
    const { S, srv, f } = rig(); S.sched.name = "mine"; S.dirty = true; S.known.status = "draft"; S.known.made = {};
    S.sched.status = "waiting"; S.sched.made = { a: 1 };
    const ok = f.takeSched({ id: "x1", name: "E", papers: [], going: ["Ms A"], duties: [{ who: "Ms A" }], rev: 3, status: "approved", made: { z: 1 } });
    assert.strictEqual(ok, true); assert.deepStrictEqual([S.sched.status, S.sched.made, S.sched.name, S.sched.rev], ["approved", { z: 1 }, "mine", 3]);
  }
  { /* r3o: a click queued behind an action that ends in a block: nothing posts and the page is not left busy */
    for (const how of ["view", "approval"]) {
      const { S, srv, f } = rig(), g = gate(); srv.holds["/fill"] = g.p; S.sched.name = "Mine"; srv.sched.name = "Theirs";
      const a = f.serverAction("POST", "/api/exams/x1/fill", {}, undefined, noop2);
      const b = how === "view" ? f.viewAction("make", {}, "Made.") : f.approvalAction("send", {}, "Sent."); await tick();
      g.go(); await a; assert.strictEqual(await b, false);
      assert.strictEqual(S.blocked, true); assert.strictEqual(S.busy, false, how + ": busy put back"); assert.deepStrictEqual(srv.calls.filter(c => c[1] === "/make" || c[1] === "/send"), []);
    }
  }
  { /* r3p: opening a schedule sets what the page knows the server holds, so the first action merges against it */
    const sched = { id: "x1", name: "E", papers: [], rev: 1 }, S = { base: "/api/exams", tabs: null, tab: "when", chain: Promise.resolve() };
    const reply = j => ({ ok: true, status: 200, j }), doc = { title: "" };
    const open = new Function("S", "api", "links", "dropNote", "fail", "render", "paintSave", "document", "sessionStorage", "EV_TABS", "ex", `const copyOf = v => JSON.parse(JSON.stringify(v));\n${cutA("startOne")}; return startOne;`)(
      S, async (m, u) => reply(u === "/api/exams/x1" ? sched : u.endsWith("/view") ? {} : u === "/api/exams/me" ? { can_use: true } : { schedules: [], levels: [], classes: [] }),
      () => {}, () => {}, e => { throw new Error(e); }, () => {}, () => {}, doc, { getItem: () => null, removeItem: () => {} }, [], null);
    S.tabs = []; await open("x1", false);
    assert.deepStrictEqual(S.known, sched); assert.notStrictEqual(S.known, S.sched, "a copy, not the page's own object");
  }
  console.log("round 3 cases passed");

  /* round 4: a save's own reply never blocks (it was accepted at the page's revision, so nobody else is in it), and a 200 with no
     schedule in it changes nothing. Every case runs, so one failing does not hide another */
  const r4 = [], c4 = (name, run) => r4.push([name, run]);
  const TIMES = { report: "07:30", min_break: 20, max_papers: 2 };
  const hhmm = t => t ? t.padStart(5, "0") : null;                      /* what the server does to a time, a cleared one too */
  const timed = () => { const r = rig(); for (const x of [r.srv.sched, r.S.sched, r.S.known]) x.times = Object.assign({}, TIMES); r.srv.norm = s => { s.times.report = hhmm(s.times.report); }; r.srv.delay = 30; return r; };
  for (const [name, first, box, then, want] of [
    ["the report time cleared, then the minutes typed", "", "min_break", "30", { report: null, min_break: 30, max_papers: 2 }],
    ["the report time cleared, then typed again", "", "report", "08:30", { report: "08:30", min_break: 20, max_papers: 2 }],
    ["a time the server rewrites, then another time", "8:00", "report", "8:15", { report: "08:15", min_break: 20, max_papers: 2 }],
    ["a time the server rewrites, then the minutes", "8:00", "min_break", "30", { report: "08:00", min_break: 30, max_papers: 2 }],
  ]) c4(name, async () => {
    const { S, srv, f } = timed();
    f.onWhenField({ value: first }, "time", "report");
    const w = f.flush(); await sleep(10); f.onWhenField({ value: then }, "time", box); await w;
    assert.strictEqual(S.blocked, false, "the save's own reply blocked the page");
    assert.strictEqual(S.sched.rev, 2, "the revision is the reply's"); assert.deepStrictEqual(S.known.times, Object.assign({}, TIMES, { report: hhmm(first) }), "what the server holds");
    assert.strictEqual(S.dirty, true, "what was typed meanwhile is still to be saved");
    await f.flush();
    assert.deepStrictEqual(srv.sched.times, want, "stored"); assert.deepStrictEqual(S.sched.times, want, "on the page");
    assert.deepStrictEqual([S.blocked, S.dirty, S.sched.rev, S.msg], [false, false, 3, "Saved"]);
  });
  c4("a suggested paper taken off, then Agreed on another", async () => {
    const { S, srv, f } = rig(); srv.clean = true; srv.delay = 30;
    for (const x of [srv.sched, S.sched, S.known]) Object.assign(x, { papers: [{ id: "a" }, { id: "b" }], suggested: ["a", "b"] });
    S.sched.papers = [{ id: "a" }, { id: "b" }];
    f.edit(() => { S.sched.papers.splice(0, 1); });
    const w = f.flush(); await sleep(10); f.edit(() => { S.sched.suggested = S.sched.suggested.filter(x => x !== "b"); }); await w;
    assert.strictEqual(S.blocked, false, "the save's own reply blocked the page"); assert.strictEqual(S.dirty, true);
    await f.flush();
    assert.deepStrictEqual([srv.sched.suggested, S.sched.suggested, srv.sched.papers], [[], [], [{ id: "b" }]]); assert.strictEqual(S.dirty, false);
  });
  c4("a suggested paper moved to another day, then Agreed on another while the save is in flight", async () => {
    const { S, srv, f } = rig(); srv.clean = true; srv.delay = 30;
    const two = () => [{ id: "a", date: "2026-10-05", start: "07:50", level: "Sec 3" }, { id: "b", date: "2026-10-06", start: "07:50", level: "Sec 3" }];
    for (const x of [srv.sched, S.sched, S.known]) Object.assign(x, { papers: two(), suggested: ["a", "b"] });
    f.onPaperField({ value: "2026-10-07" }, "pdate", "0");
    assert.deepStrictEqual(S.sched.suggested, ["b"], "the page drops the id in the same edit");
    const w = f.flush(); await sleep(10); f.agreeSuggested("b"); await w;
    assert.strictEqual(S.blocked, false); assert.strictEqual(S.dirty, true);
    await f.flush();
    assert.deepStrictEqual([srv.sched.suggested, S.sched.suggested], [[], []], "neither a nor b is suggested"); assert.strictEqual(S.dirty, false);
    assert.strictEqual(srv.sched.papers[0].date, "2026-10-07");
  });
  c4("a start change drops the id, other fields keep it, a day-less paper stays", async () => {
    const { S, f } = rig();
    S.sched.papers = [{ id: "a", date: "2026-10-05", start: "07:50", minutes: 60 }, { id: "b", date: null, start: null }]; S.sched.suggested = ["a", "b"];
    f.onPaperField({ value: "70" }, "pmin", "0"); f.onPaperField({ value: "Maths" }, "psubject", "0"); assert.deepStrictEqual(S.sched.suggested, ["a", "b"]);
    f.onPaperField({ value: "08:20" }, "pstart", "0"); assert.deepStrictEqual(S.sched.suggested, ["b"]);
    f.onPaperField({ value: "" }, "pdate", "1"); assert.deepStrictEqual(S.sched.suggested, ["b"], "no change of date or start");
    f.onPaperField({ value: "2026-10-06" }, "pdate", "1"); assert.deepStrictEqual(S.sched.suggested, []);
  });
  c4("taking a paper off drops its id, and the Approval line counts what is suggested", async () => {
    const { S, f } = rig();
    S.sched.papers = [{ id: "a" }, { id: "b" }]; S.sched.suggested = ["a", "b"];
    assert.strictEqual(f.suggestedLine(), "2 papers have a suggested time.");
    f.dropSuggested(["a"]); assert.deepStrictEqual(S.sched.suggested, ["b"]); assert.strictEqual(f.suggestedLine(), "1 paper has a suggested time.");
    S.sched.suggested = ["a", "gone"]; assert.strictEqual(f.suggestedLine(), "1 paper has a suggested time.", "only papers the page holds are counted");
    S.sched.suggested = []; assert.strictEqual(f.suggestedLine(), ""); delete S.sched.suggested; assert.strictEqual(f.suggestedLine(), "");
  });
  c4("the Approval tab shows the suggested line between the status line and the Send card, and never blocks", async () => {
    const SRCS = ["suggestedLine", "tabApproval"].map(cut).join("\n");
    const draw = (status, ids, extra) => {
      const S = { sched: { papers: [{ id: "a" }, { id: "b" }], suggested: ids }, rv: Object.assign({ status, label: "L", can_send: "", unsent: [], review: { what: [], changes: [], done_without: [] }, changed: true }, extra || {}), me: { can_approve: true }, busy: false, sbNote: "" };
      const sendBox = (title, lead, label, path, why) => `<SEND ${path}${S.busy || why ? " disabled" : ""}>`;
      return new Function("S", "esc", "chipClass", "sendBox", "awayNotes", "whatBlock", "checksBlock", "isEv", "stamp", `${SRCS}; return tabApproval();`)(S, esc, () => "", sendBox, () => "", () => "<WHAT>", () => "<CHECKS>", () => false, x => x);
    };
    let h = draw("draft", ["a", "b"]); const line = "2 papers have a suggested time.";
    assert(h.indexOf("Approval</h2>") < h.indexOf(line) && h.indexOf(line) < h.indexOf("<SEND send"), "below the status line, above the Send card");
    assert(draw("draft", ["a"]).includes("1 paper has a suggested time.")); assert(!draw("draft", []).includes("suggested time"));
    assert(!draw("draft", ["gone"]).includes("suggested time"));
    for (const st of ["approved", "changes", "waiting", "withdrawn"]) {
      h = draw(st, ["a", "b"], { unsent: [{ text: "x" }], changed: true, review: { what: [], changes: [{ text: "c" }], done_without: [] } });
      assert(h.includes(line), st); assert(!/disabled/.test(h), st + ": a button is disabled because of the line");
    }
  });
  c4("an event's going list the server cleans, one more typed", async () => {
    const { S, srv, f } = rig(true); srv.delay = 30; srv.norm = s => { s.going = uniq(s.going); };
    f.edit(() => { S.sched.going = S.sched.going.concat(["Ms A"]); });
    const w = f.flush(); await sleep(10); f.edit(() => { S.sched.going = S.sched.going.concat(["Ms D"]); }); await w;
    assert.strictEqual(S.blocked, false, "the save's own reply blocked the page");
    await f.flush(); assert.deepStrictEqual(srv.sched.going, ["Ms A", "Ms D"]); assert.deepStrictEqual(S.sched.going, ["Ms A", "Ms D"]);
  });
  c4("Fill clicked while the save runs and the minutes are typed", async () => {
    const { S, srv, f } = timed(); f.onWhenField({ value: "" }, "time", "report");
    const w = f.flush(); await sleep(5); const p = f.serverAction("POST", S.base + "/x1/fill", {}, undefined, noop2);
    f.onWhenField({ value: "30" }, "time", "min_break"); await w; await p;
    assert.strictEqual(S.blocked, false); assert.deepStrictEqual(srv.sched.times, { report: null, min_break: 30, max_papers: 2 });
    assert.deepStrictEqual(S.sched.papers, [{ id: "p1" }], "and the Fill is done"); assert.strictEqual(S.sched.rev, srv.sched.rev);
  });
  c4("after such a save, another page's change still blocks and the rest still comes in", async () => {
    for (const same of [true, false]) {
      const { S, srv, f } = timed(); f.onWhenField({ value: "" }, "time", "report");
      const w = f.flush(); await sleep(10); f.onWhenField({ value: "30" }, "time", "min_break"); await w;
      const theirs = Object.assign(JSON.parse(JSON.stringify(srv.sched)), { name: "Theirs", rev: 3 }); if (!same) theirs.times.min_break = 45;
      assert.strictEqual(f.takeSched(theirs), same, same ? "only the page changed the times" : "both changed the times");
      assert.strictEqual(S.blocked, !same); assert.strictEqual(S.sched.times.min_break, 30); assert.strictEqual(S.sched.name, same ? "Theirs" : "E"); assert.strictEqual(S.sched.rev, same ? 3 : 2);
      clearTimeout(S.timer);
    }
  });
  c4("the server's own parts come from the reply, a save's own too", async () => {
    const OWN = ["saved_at", "saved_by", "status", "approved", "approved_at", "approved_by", "sent_at", "sent_by", "sent_fp", "note", "log", "handled", "made", "pins", "use_anyway", "created_at", "created_by", "kind"];
    for (const own of [true, false]) {
      const { S, f } = rig(), all = v => Object.fromEntries(OWN.map(k => [k, v])), sent = Object.assign({ id: "x1", name: "E", rev: 1 }, all("sent"));
      S.known = own ? null : sent; S.sched = Object.assign({ id: "x1", name: "Mine", rev: 1 }, all("page"));
      assert.strictEqual(f.takeSched(Object.assign({ id: "x1", name: "E", rev: 2 }, all("server")), own ? sent : undefined), true);
      assert.deepStrictEqual(S.sched, Object.assign({ id: "x1", name: "Mine", rev: 2 }, all("server"))); assert.strictEqual(S.blocked, false);
    }
  });
  for (const how of ["early", "late"]) c4("a save whose 200 has no schedule in it, " + how, async () => {
    const { S, srv, f } = rig(); srv.cut.PUT = how;
    f.edit(() => { S.sched.name = "Mine"; });
    assert.strictEqual(await f.flush(), false, "the save says it failed");
    assert.deepStrictEqual(S.sched, { id: "x1", name: "Mine", papers: [], going: ["Ms A"], duties: [{ who: "Ms A" }], rev: 1 }, "the page's copy is untouched");
    assert.strictEqual(S.known.name, "E"); assert.deepStrictEqual([S.msg, S.bad, S.dirty, S.blocked], ["Nothing was saved. Try again.", true, true, false]);
    assert.deepStrictEqual(srv.calls, [["PUT", ""]], "and it goes no further");
    if (how === "early") { await f.flush(); assert.strictEqual(srv.sched.name, "Mine", "the next try saves it"); assert.deepStrictEqual([S.msg, S.bad, S.dirty, S.sched.rev], ["Saved", false, false, 2]); }
  });
  c4("a save whose 200 has no schedule in it stops what was clicked after it", async () => {
    const { S, srv, f } = rig(); srv.cut.PUT = "early"; f.edit(() => { S.sched.name = "Mine"; });
    assert.strictEqual(await f.approvalAction("send", {}, "Sent."), false); assert.deepStrictEqual(srv.calls.filter(c => c[0] === "POST"), []); assert.strictEqual(S.sched.name, "Mine");
  });
  c4("a Fill whose 200 has no schedule in it", async () => {
    const { S, srv, f } = rig(); srv.cut["POST/fill"] = "late"; let called = 0;
    await f.serverAction("POST", S.base + "/x1/fill", {}, undefined, () => { called++; });
    assert.deepStrictEqual([S.sched.id, S.sched.name, S.sched.rev, S.known.name], ["x1", "E", 1, "E"], "the page's copy is untouched");
    assert.deepStrictEqual([S.msg, S.bad, S.blocked, called], ["That did not work. Try again.", true, false, 0]);
  });
  c4("the read after an action has no schedule in it: the same as a read that failed", async () => {
    { const { S, srv, f } = rig(); srv.cut.GET = "late"; assert.strictEqual(await f.approvalAction("send", {}, "Sent."), true);
      assert.deepStrictEqual([S.sched.id, S.sched.name, S.sched.rev, S.blocked, S.msg], ["x1", "E", 2, false, "Sent."]); }
    { const { S, srv, f } = rig(true); srv.cut.GET = "late"; assert.strictEqual(await f.approvalAction("away", { away: "Ms A", name: "Ms C" }, "Done."), false);
      assert.deepStrictEqual([S.sched.id, S.blocked, S.blockMsg], ["x1", true, "This event was changed by someone else since you opened it. Reload to carry on."]); assert.notStrictEqual(S.msg, "Done."); }
  });
  for (const typed of [true, false]) c4("a paper added in place while a second Fill runs stays" + (typed ? ", after a reply that was merged" : ""), async () => {
    const { S, srv, f } = rig(), g = gate(); srv.holds["/fill"] = g.p; srv.delay = 30; srv.onPost = () => { srv.noAdd = true; };
    const p1 = f.serverAction("POST", S.base + "/x1/fill", {}, undefined, noop2), p2 = f.serverAction("POST", S.base + "/x1/fill", {}, undefined, noop2); await tick();
    if (typed) f.edit(() => { S.sched.name = "Mine"; });
    g.go(); await p1; await tick(); f.edit(() => { S.sched.papers.push({ id: "mine" }); }); await p2;
    assert.strictEqual(S.blocked, false); assert.deepStrictEqual(S.sched.papers, [{ id: "p1" }, { id: "mine" }], "what the page knows is a copy, not the page's own lists");
    await f.flush(); assert.deepStrictEqual(srv.sched.papers, [{ id: "p1" }, { id: "mine" }]); assert.strictEqual(srv.sched.name, typed ? "Mine" : "E");
  });
  const r4bad = [];
  for (const [name, run] of r4) { try { await run(); } catch (e) { r4bad.push(`${name}: ${String(e && e.message).split("\n").slice(0, 2).join(" ")}`); } }
  if (r4bad.length) { console.error(`round 4: ${r4bad.length} of ${r4.length} failed\n  ${r4bad.join("\n  ")}`); process.exit(1); }
  console.log(`round 4 cases passed (${r4.length})`);
})().catch(e => { console.error(e); process.exit(1); });
console.log(`${n} exams page tests passed`);

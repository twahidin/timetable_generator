// Plain-assert tests for the relief team's Planned Relief Assignments page (static/relief-ahead.js): run with `node tests/relief_ahead.test.js`.
// The page's script runs, with the real relief-form.js, in a small stand-in for the page, against an /api/relief/ahead answer written here.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const read = f => fs.readFileSync(path.join(__dirname, "..", "static", f), "utf8");
const TODAY = "2026-10-12";
const SAM = "Mr Sam Tan", MAYA = "Ms Maya Lee", EVE = "Ms Evelyn Koh", TEAM = "Mr Hugo Ong";
const counts = more => Object.assign({ need: 0, waiting: 0, approved: 0, unsent: 0, held: 0, acknowledged: 0, change: 0, nobody: 0, open: 0 }, more);
const row = more => Object.assign({ id: "a1", ckey: "k5", key: "k5", split: false, absent: EVE, classes: ["1A"], subject: "Science", group: "", room: "R1", p: 5, n: 2, start: "10:30", end: "11:30", work_set: true,
  state: "approved", pick: { who: SAM, by: "team", reason: "Chosen by the relief team." }, approved: { by: TEAM, at: "2026-10-12T07:15:00+08:00" }, ack: null, change: null, stopped: "", duty: "", out: "sent", goes_at: null, sent_out: null, planned_by: "", away: false }, more);
const dayOf = (date, rows, c) => ({ date, away: new Set(rows.map(r => r.absent)).size, counts: counts(Object.assign({ need: rows.length }, c)), rows });

/* the page, opened on this answer; the stand-in records each URL asked and each call of go and showDay */
async function open(answer, span = "weeks") {
  const els = {}, on = {}, urls = [], shows = [], gos = [];
  const el = id => els[id] || (els[id] = { innerHTML: "", querySelector: () => null });
  const pane = { innerHTML: "", contains: x => !!x && x.inPane, querySelector: s => (s[0] === "#" ? el(s.slice(1)) : { focus: () => focusLog.push(s) }), addEventListener: (k, f) => { on[k] = f; } };
  const focusLog = [], doc = { querySelector: q => (q === "#tab-today" ? { focus: () => focusLog.push("#tab-today") } : null), activeElement: null };
  const window = {}, ctx = vm.createContext({ window, document: doc });
  vm.runInContext(read("relief-form.js"), ctx);
  const RF = window.ReliefForm;
  RF.setToday(TODAY);
  let tab = null;
  const p = { answer, doc, focusLog, urls, shows, gos, html: () => el("ahBox").innerHTML };
  window.Relief = { cur: "ahead", tab: (name, mod) => { assert.strictEqual(name, "ahead"); tab = mod; }, plural: (n, one) => `${n} ${one}${n === 1 ? "" : "s"}`, say: m => (m ? RF.esc(m.text) : ""), json: (method, body) => ({ method, body }),
    api: async url => { urls.push(url); const a = await (typeof p.answer === "function" ? p.answer(url) : p.answer); return a.ok === false ? a : { ok: true, data: a }; },
    go: n => gos.push(n), showDay: d => shows.push(d) };
  vm.runInContext(read("relief-ahead.js"), ctx);
  const settle = () => new Promise(f => setImmediate(f));
  p.press = async (attrs) => { const b = { dataset: attrs, disabled: false }; on.click({ target: { closest: () => b } }); await settle(); };
  p.shown = async () => { tab.shown(pane); await settle(); };
  tab.init(pane);
  await settle();
  return p;
}
const answer = (days, more) => Object.assign({ as_of: "2026-10-12T09:00:00+08:00", span: "weeks", until: "2026-10-26", days }, more);
const flat = s => s.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");

let n = 0; const all = []; const t = (name, f) => all.push([name, f]);

t("a day's heading counts teachers, lessons and what waits", async () => {
  const two = dayOf("2026-10-13", [row({ state: "waiting", approved: null, out: null }), row({ ckey: "k2", p: 1, n: 1, state: "open", pick: null, approved: null, out: null })], { waiting: 1, open: 1 });
  const done = dayOf("2026-10-14", [row({ state: "acknowledged", ack: { by: SAM, at: "2026-10-12T08:00:00+08:00" } })], { acknowledged: 1 });
  const p = await open(answer([two, done])), html = p.html(), text = flat(html);
  assert.ok(html.includes("Tue 13 Oct") && text.includes("1 teacher away · 2 lessons") && text.includes("1 waiting for you") && text.includes("1 no relief teacher yet"), text);
  assert.ok(text.includes("Wed 14 Oct") && text.includes("1 teacher away · 1 lesson") && text.includes("all approved"), text);
  assert.strictEqual(text.split("all approved").length, 2, "only the day with nothing left says all approved");
  assert.ok(text.includes("Planned Relief Assignments") && text.includes("Every relief on the school days after today, up to Mon 26 Oct · as of Mon 12 Oct, 09:00"), text);
  assert.ok(html.includes('data-ah="open" data-date="2026-10-13"') && html.includes('data-ah="open" data-date="2026-10-14"'));
});
t("the chip for approved and not yet sent out, and no all approved while any is unsent", async () => {
  const p = await open(answer([dayOf("2026-10-13", [row({ out: "unsent" })], { unsent: 1 })])), text = flat(p.html());
  assert.ok(text.includes("1 approved, not sent out") && !text.includes("all approved"), text);
});
t("each status reads as Today says it", async () => {
  const days = [dayOf("2026-10-13", [
    row({ ckey: "a", state: "open", pick: null, approved: null, out: null }),
    row({ ckey: "b", state: "waiting", approved: null, out: null }),
    row({ ckey: "c", out: "unsent" }),
    row({ ckey: "d", out: "held", goes_at: "2026-10-14T06:45:00+08:00" }),
    row({ ckey: "e", out: "held", goes_at: null }),
    row({ ckey: "f", out: "sent" }),
    row({ ckey: "g", state: "acknowledged", ack: { by: SAM, at: "2026-10-12T08:00:00+08:00" } }),
    row({ ckey: "h", state: "change", change: { why: "A talk", at: "2026-10-12T08:00:00+08:00", pick: null, stale: false } }),
    row({ ckey: "i", state: "stopped", pick: null, approved: null, out: null, stopped: "1A are on an exam" }),
    row({ ckey: "j", state: "cancelled", pick: null, approved: null, out: null }),
  ])];
  const text = flat((await open(answer(days))).html());
  for (const s of ["No relief teacher yet", "Waiting for you", "Approved · not sent out", "Approved · will be sent Wed 14 Oct, 06:45", "Approved · sent out", "✓ Acknowledged", "Asked to change", "Not happening", "1A are on an exam"])
    assert.ok(text.includes(s), s + " | " + text);
  assert.ok(!text.includes("stopped"), "the reason is shown, never the bare word | " + text);
  assert.strictEqual(text.split("Approved · sent out").length - 1, 1, "only a sent one reads as sent out");
  assert.strictEqual(text.split("Approved · not sent out").length - 1, 2, "a held one with no goes_at reads as Today reads it");
});
t("the time, lesson, room and the relief teacher's planner are written", async () => {
  const text = flat((await open(answer([dayOf("2026-10-13", [row({ planned_by: TEAM })])]))).html());
  assert.ok(text.includes("P6–P7") && text.includes("10:30–11:30") && text.includes("1A Science") && text.includes("R1") && text.includes(EVE) && text.includes(SAM) && text.includes(`Planned by ${TEAM}`), text);
});
t("a request to change shows the old name struck and the new pick", async () => {
  const c = { why: "A talk", at: "2026-10-12T08:00:00+08:00", pick: { who: MAYA, by: "ai", reason: "x" }, stale: false };
  const html = (await open(answer([dayOf("2026-10-13", [row({ state: "change", change: c })])]))).html();
  assert.ok(html.includes('<s class="muted">Mr Sam Tan</s>') && html.includes("New pick: Ms Maya Lee"), html);
});
t("This term asks the server for the term", async () => {
  const p = await open(answer([dayOf("2026-10-13", [row()])]));
  assert.strictEqual(p.urls[0], "/api/relief/ahead?span=weeks");
  await p.press({ ah: "span", v: "term" });
  assert.strictEqual(p.urls[p.urls.length - 1], "/api/relief/ahead?span=term");
  const btn = p.html().match(/<button[^>]*data-v="term"[^>]*>/)[0], other = p.html().match(/<button[^>]*data-v="weeks"[^>]*>/)[0];
  assert.ok(btn.includes('aria-pressed="true"') && other.includes('aria-pressed="false"'), btn + other);
  assert.ok(flat(p.html()).includes("Next 2 weeks") && flat(p.html()).includes("This term"));
});
t("Open this day hands the date to Today", async () => {
  const p = await open(answer([dayOf("2026-10-13", [row()])]));
  await p.press({ ah: "open", date: "2026-10-13" });
  assert.deepStrictEqual(p.shows, ["2026-10-13"]);
});
t("a stopped lesson with no reason has no small line", async () => {
  const text = flat((await open(answer([dayOf("2026-10-13", [row({ state: "stopped", pick: null, approved: null, out: null, stopped: "" })])]))).html());
  assert.ok(text.includes("Not happening") && !text.includes("stopped"), text);
});
t("a backup for an exam duty or event says which duty, as Today does", async () => {
  const html = (await open(answer([dayOf("2026-10-13", [row({ duty: "Invigilating: Sec 3 End-of-Year Exam", state: "waiting", approved: null, out: null }), row({ ckey: "z", duty: "" })])]))).html();
  assert.ok(flat(html).includes("(Invigilating: Sec 3 End-of-Year Exam)"), html);
  assert.strictEqual(html.split("Invigilating").length - 1, 1, "a row with no duty has no line");
  const bad = (await open(answer([dayOf("2026-10-13", [row({ duty: "<b>x</b>" })])]))).html();
  assert.ok(!bad.includes("<b>x") && bad.includes("&lt;b&gt;x"), bad);
});
t("a day with requests to change has a chip for them", async () => {
  const c = { why: "A talk", at: "2026-10-12T08:00:00+08:00", pick: null, stale: false };
  const text = flat((await open(answer([dayOf("2026-10-13", [row({ state: "change", change: c }), row({ ckey: "q", state: "change", change: c })], { change: 2 }), dayOf("2026-10-14", [row()], { approved: 1 })]))).html());
  assert.ok(text.includes("2 asked to change") && text.split("asked to change").length === 2 && !text.includes("all approved asked"), text);
});
t("the line under the heading says how far the list reaches", async () => {
  const text = flat((await open(answer([dayOf("2026-10-13", [row()])], { until: "2026-10-26" }))).html());
  assert.ok(text.includes("Every relief on the school days after today, up to Mon 26 Oct · as of Mon 12 Oct, 09:00"), text);
  for (const until of [undefined, null, "", "soon", "26/10/2026"]) {
    const t2 = flat((await open(answer([dayOf("2026-10-13", [row()])], { until }))).html());
    assert.ok(t2.includes("Every relief on the school days after today · as of Mon 12 Oct, 09:00") && !t2.includes("up to"), String(until) + " | " + t2);
  }
});
t("Open this day names its date, and the focus goes to the Today tab", async () => {
  const p = await open(answer([dayOf("2026-10-13", [row()])])), html = p.html();
  assert.ok(html.includes('aria-label="Open Tue 13 Oct on Today&#39;s Relief Assignments"'), html);
  p.focusLog.length = 0;
  await p.press({ ah: "open", date: "2026-10-13" });
  assert.deepStrictEqual(p.shows, ["2026-10-13"]); assert.deepStrictEqual(p.focusLog, ["#tab-today"]);   /* the stand-in's document gives #tab-today a focus() that is logged */
});
t("Refresh and showing the tab read again", async () => {
  const p = await open(answer([dayOf("2026-10-13", [row()])]));
  await p.press({ ah: "reload" }); await p.shown();
  assert.strictEqual(p.urls.length, 3);
});
t("nothing of a name is written into the page as markup", async () => {
  const r = row({ absent: "<b>x</b>", pick: { who: "<i>y</i>", by: "team", reason: "" }, planned_by: "<u>z</u>", subject: "<em>w</em>", room: "<q>r</q>" });
  const html = (await open(answer([dayOf("2026-10-13", [r, row({ state: "change", absent: "<b>x</b>", change: { why: "", at: "", pick: { who: "<i>n</i>" }, stale: false } })])]))).html();
  for (const bad of ["<b>x", "<i>y", "<u>z", "<em>w", "<q>r", "<i>n"]) assert.ok(!html.includes(bad), bad + " | " + html);
  assert.ok(html.includes("&lt;b&gt;x"));
});
t("an empty answer says so for each span", async () => {
  const p = await open(answer([]));
  assert.ok(flat(p.html()).includes("No relief on the school days after today."), p.html());
  p.answer = answer([], { span: "term" });
  await p.press({ ah: "span", v: "term" });
  assert.ok(flat(p.html()).includes("No relief for the rest of the term.") && !flat(p.html()).includes("after today."), p.html());
});
t("the first read says Loading… under the controls", async () => {
  const p = await open(() => new Promise(() => {})), html = p.html();
  assert.ok(html.includes("Loading…") && html.includes("Planned Relief Assignments") && html.includes('data-v="term"') && html.includes('data-ah="reload" disabled>Reading…'), html);
});
t("a later read keeps the old list and Refresh reads Reading… and is off", async () => {
  const p = await open(answer([dayOf("2026-10-13", [row()])]));
  let release; p.answer = () => new Promise(f => { release = f; });
  const again = p.press({ ah: "reload" });
  const html = p.html();
  assert.ok(html.includes("Tue 13 Oct") && !html.includes("Loading…") && html.includes('data-ah="reload" disabled>Reading…'), html);
  release(answer([dayOf("2026-10-14", [row()])])); await again; await new Promise(f => setImmediate(f));
  assert.ok(p.html().includes("Wed 14 Oct") && p.html().includes(">Refresh<") && !p.html().includes("disabled"), p.html());
});
t("a failed read shows the server's sentence and Try again", async () => {
  const p = await open({ ok: false, error: "Only the relief team can open this.", status: 403 });
  const html = p.html();
  assert.ok(html.includes("Only the relief team can open this.") && html.includes("Try again") && html.includes('data-ah="reload"') && html.includes('data-v="term"') && html.includes("<h2>Planned Relief Assignments</h2>"), html);
  p.answer = answer([dayOf("2026-10-13", [row()])]);
  await p.press({ ah: "reload" });
  assert.ok(!p.html().includes("Try again") && p.html().includes("Tue 13 Oct"), p.html());
});
t("a failed Refresh keeps the last list under the sentence", async () => {
  const p = await open(answer([dayOf("2026-10-13", [row()])]));
  p.answer = { ok: false, error: "Could not reach the server.", status: 0 };
  await p.press({ ah: "reload" });
  const html = p.html();
  assert.ok(html.includes("Could not reach the server.") && html.includes("Try again") && html.includes("Tue 13 Oct"), html);
  assert.ok(html.indexOf("Try again") < html.indexOf("Tue 13 Oct"));
});
t("when two reads are out, the last asked one's answer stays", async () => {
  const p = await open(answer([]));
  const waits = []; p.answer = () => new Promise(f => waits.push(f));
  const one = p.press({ ah: "reload" }), two = p.press({ ah: "reload" });
  waits[1](answer([dayOf("2026-10-14", [row()])])); await two;
  waits[0](answer([dayOf("2026-10-13", [row()])])); await one; await new Promise(f => setImmediate(f));
  assert.ok(p.html().includes("Wed 14 Oct") && !p.html().includes("Tue 13 Oct"), p.html());
});
t("an answer with no days, and a day with no rows, do not throw", async () => {
  const p = await open({ as_of: "2026-10-12T09:00:00+08:00", span: "weeks" });
  assert.ok(flat(p.html()).includes("No relief on the school days after today."), p.html());
  const q = await open(answer([{ date: "2026-10-13", away: 0, counts: counts() }]));
  assert.ok(q.html().includes("Tue 13 Oct") && flat(q.html()).includes("0 teachers away · 0 lessons"), q.html());
});
t("the lessons of a day are counts.need, not every row", async () => {
  const d = dayOf("2026-10-13", [row(), row({ ckey: "z", state: "stopped", stopped: "x", pick: null, out: null })]); d.counts.need = 1;
  assert.ok(flat((await open(answer([d]))).html()).includes("1 lesson") && !flat((await open(answer([d]))).html()).includes("2 lessons"));
});
t("the focus stays on Refresh and on the span button after their reads", async () => {
  const p = await open(answer([dayOf("2026-10-13", [row()])]));
  p.focusLog.length = 0;
  await p.press({ ah: "reload" });
  assert.deepStrictEqual(p.focusLog, ['[data-ah="reload"]']);
  p.focusLog.length = 0;
  await p.press({ ah: "span", v: "term" });
  assert.deepStrictEqual(p.focusLog, ['[data-ah="span"][data-v="term"]']);
  p.focusLog.length = 0; p.doc.activeElement = { inPane: true, dataset: { ah: "reload" } };   /* a read started by showing the tab */
  await p.shown();
  assert.deepStrictEqual(p.focusLog, ['[data-ah="reload"]']);
  p.focusLog.length = 0; p.doc.activeElement = { inPane: false, dataset: { ah: "reload" } };
  await p.shown();
  assert.deepStrictEqual(p.focusLog, [], "focus elsewhere is left alone");
});
t("every day's table has the one fixed layout", async () => {
  const html = (await open(answer([dayOf("2026-10-13", [row()]), dayOf("2026-10-14", [row()])]))).html();
  assert.strictEqual(html.split('<table class="rtable ah">').length - 1, 2);
  assert.ok(/table\.ah\{[^}]*table-layout:fixed[^}]*min-width:640px/.test(fs.readFileSync(path.join(__dirname, "..", "static", "relief.html"), "utf8")));
});

(async () => {
  for (const [name, f] of all) {
    try { await f(); n++; } catch (e) { console.error("FAIL", name); throw e; }
  }
  console.log(`${n} relief Planned Relief Assignments tests passed`);
})().catch(e => { console.error(e); process.exit(1); });

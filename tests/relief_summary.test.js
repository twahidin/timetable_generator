// Plain-assert tests for the relief team's Weekly summary page (static/relief-summary.js): run with `node tests/relief_summary.test.js`.
// The page's script runs, with the real relief-form.js, in a small stand-in for the page, against /api/relief/summary answers written here.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const read = f => fs.readFileSync(path.join(__dirname, "..", "static", f), "utf8");
const FORM = read("relief-form.js"), PAGE = read("relief-summary.js");
const TODAY = "2026-10-14", W5 = "2026-10-05", W12 = "2026-10-12", W19 = "2026-10-19";
const LOADING = "Loading…", AGAIN = 'data-sm="reload">Try again</button>';

/* a made-up week */
const WEEK = {
  start: W12, end: "2026-10-16", label: "Week 6 (12–16 Oct)", fat_role: true, periods: 14, absences: 6, fat_periods: 6, fat_percent: 43, ahead: 9, on_day: 5, on_time: 5, late: 2, never: 3, waiting: 4,
  asked: 3, moved: 1, kept: 1, top: [["Mr Sam Tan", 9], ["Ms Maya Lee", 5]], by_dept: [["Science", 10], ["English", 4]], by_day: { Fri: 3, Mon: 3, Thu: 4, Tue: 3, Wed: 1 },
  rows: [{ date: "2026-10-13", lesson: "4D Maths P1–P3", absent: "Ms Evelyn Koh", relief: "Mr Sam Tan", ack: "late 10:31" }, { date: "2026-10-14", lesson: "1A Art P2", absent: "Ms Ruth Goh", relief: "Ms Maya Lee", ack: "never" },
         { date: "2026-10-15", lesson: "1B Art P4", absent: "Ms Ruth Goh", relief: "Ms Maya Lee", ack: "waiting" }, { date: "2026-10-16", lesson: "1C Art P5", absent: "Ms Ruth Goh", relief: "Ms Maya Lee", ack: "Mon 12 Oct, 15:20" }]
};
const week = more => ({ ok: true, status: 200, data: Object.assign(JSON.parse(JSON.stringify(WEEK)), more) });
const refused = (error, status) => ({ ok: false, status: status === undefined ? 403 : status, error });

/* the page opened at /relief{search}: asked, the addresses it asked the server for (give(i, answer) answers the i-th); html() and title(), what it shows; focus(), the id that has the focus */
function open(search) {
  const asked = [], answer = [], els = {}, on = {};
  let focused = "";
  const el = id => els[id] || (els[id] = { textContent: "", innerHTML: "", hidden: false, focus() { focused = id; } });
  const pane = { innerHTML: "", querySelector: s => el(s.slice(1)), addEventListener: (k, f) => { on[k] = f; } };
  const window = {}, ctx = vm.createContext({ window, document: { querySelector: () => null }, location: { search }, URLSearchParams });
  vm.runInContext(FORM, ctx);
  const RF = window.ReliefForm;
  RF.setToday(TODAY);
  let tab = null;
  window.Relief = { say: m => (m && m.text ? `<span class="msg ${m.bad ? "bad" : "ok"}">${RF.esc(m.text)}</span>` : ""), plural: (n, one) => `${n} ${one}${n === 1 ? "" : "s"}`,
                    tab: (name, mod) => { assert.strictEqual(name, "summary"); tab = mod; }, api: url => { asked.push(url); return new Promise(f => answer.push(f)); } };
  vm.runInContext(PAGE, ctx);
  tab.init(pane, {});
  return {
    asked, pane, tab, html: () => el("smBody").innerHTML, title: () => el("smTitle").textContent, away: () => !el("smNow").hidden, focus: () => focused,
    give: async (i, a) => { answer[i](a); await new Promise(f => setImmediate(f)); },
    press: what => { focused = "the button"; on.click({ target: { closest: () => ({ disabled: false, dataset: { sm: what } }) } }); }
  };
}
const url = monday => `/api/relief/summary?week=${monday}`;
const has = (page, ...texts) => texts.forEach(x => assert.ok(page.html().includes(x), x));
const hasNot = (page, ...texts) => texts.forEach(x => assert.ok(!page.html().includes(x), x));

const { css } = require("./dom.js");
let n = 0; const all = []; const t = (name, f) => all.push([name, f]);

t("the week in the address is the one it starts at, any date of it; this week without one", () => {
  for (const [search, monday] of [["", W12], ["?week=2026-10-05", W5], ["?week=2026-10-07", W5], ["?week=2026-10-11", W5], ["?week=2026-10-12", W12], ["?week=2026-10-18", W12], ["?week=2027-01-01&x=1", "2026-12-28"], ["?x=1", W12]])
    assert.deepStrictEqual(open(search).asked, [url(monday)], search);
});
t("an odd week, and a date there is not, is this week", () => {
  for (const search of ["?week=", "?week=x", "?week=2026", "?week=2026-10", "?week=12-10-2026", "?week=2026-10-05T00:00", "?week=%202026-10-05", "?week=2026-10-05%0a", "?week=%3Cscript%3E", "?week=null"])
    assert.deepStrictEqual(open(search).asked, [url(W12)], search);
  for (const search of ["?week=2026-02-31", "?week=2026-02-29", "?week=2026-13-01", "?week=2026-00-10", "?week=2026-09-31", "?week=2026-10-00", "?week=0000-00-00", "?week=9999-99-99"])
    assert.deepStrictEqual(open(search).asked, [url(W12)], search);
});
t("it says it is loading, then what the server says, the days in order", async () => {
  const p = open("");
  assert.strictEqual(p.title(), "Week of Mon 12 Oct"); has(p, LOADING); assert.strictEqual(p.away(), false);
  for (const label of ['aria-label="Week before"', 'aria-label="Week after"']) assert.ok(p.pane.innerHTML.includes(label), label);
  await p.give(0, week());
  assert.strictEqual(p.title(), "Week 6 (12–16 Oct)"); hasNot(p, LOADING, AGAIN, "undefined", "NaN", "null");
  has(p, "43%", "6 periods", "9 planned ahead · 5 on the day", "5 on time · 2 late · 3 never · 4 waiting", "3 (1 moved, 1 kept)", "Mr Sam Tan <b>9</b>", "Tue 13 Oct", '<div class="counter bad"><span class="small muted">Never acknowledged</span><b>3</b>',
      '<span class="chip st-amber">late 10:31</span>', '<span class="chip st-warn">never</span>', '<span class="chip">waiting</span>', '<span class="chip st-ok">Mon 12 Oct, 15:20</span>');
  const bars = [...p.html().matchAll(/<dt>(\w+)<\/dt>\s*<dd><span class="sm-bar" aria-hidden="true"><i style="width:(\d+)%"><\/i><\/span><b>(\d+)<\/b>/g)].map(m => m.slice(1).join(" "));
  assert.deepStrictEqual(bars, ["Mon 75 3", "Tue 75 3", "Wed 25 1", "Thu 100 4", "Fri 75 3", "Science 100 10", "English 40 4"]);
});
t("every name and lesson is escaped", async () => {
  const mark = x => `<u title="${x}">'${x}'</u>&`, safe = x => `&lt;u title=&quot;${x}&quot;&gt;&#39;${x}&#39;&lt;/u&gt;&amp;`, p = open("");
  await p.give(0, week({ label: mark("label"), top: [[mark("most"), 9], ["Ms Maya Lee", 5]], by_dept: [[mark("dept"), 14]], rows: [{ date: mark("date"), lesson: mark("lesson"), absent: mark("absent"), relief: mark("relief"), ack: mark("ack") }] }));
  has(p, ...["most", "dept", "date", "lesson", "absent", "relief", "ack"].map(safe)); hasNot(p, "<u");
  assert.strictEqual(p.title(), mark("label"), "as text, never as HTML");
  await p.give(0, week()); p.press("after"); await p.give(1, refused(mark("refusal"))); has(p, safe("refusal")); hasNot(p, "<u");
});
t("another week: the old numbers go at once", async () => {
  const p = open(""); await p.give(0, week()); p.press("before");
  assert.deepStrictEqual(p.asked.slice(1), [url(W5)]); assert.strictEqual(p.title(), "Week of Mon 5 Oct"); has(p, LOADING); hasNot(p, "43%", "Mr Sam Tan"); assert.strictEqual(p.away(), true);
  await p.give(1, week({ label: "Week 5 (5–9 Oct)", fat_percent: 21 })); assert.strictEqual(p.title(), "Week 5 (5–9 Oct)"); has(p, "21%");
  p.press("after"); p.press("after"); assert.deepStrictEqual(p.asked.slice(2), [url(W12), url(W19)]); assert.strictEqual(p.title(), "Week of Mon 19 Oct");
});
t("a late answer for another week is not shown", async () => {
  const p = open(""); await p.give(0, week()); p.press("before"); p.press("before");
  await p.give(2, week({ label: "Week 4 (28 Sep–2 Oct)", fat_percent: 14 })); await p.give(1, week({ label: "Week 5 (5–9 Oct)", fat_percent: 21 }));
  assert.strictEqual(p.title(), "Week 4 (28 Sep–2 Oct)"); has(p, "14%"); hasNot(p, "21%");
  p.press("after"); p.press("after"); await p.give(3, refused("A late refusal")); has(p, LOADING); hasNot(p, "A late refusal", AGAIN);
  await p.give(4, week()); has(p, "43%");
});
t("a refusal is the server's sentence, with Try again", async () => {
  const p = open(""); await p.give(0, refused("Only the relief team can open What's in."));
  has(p, "Only the relief team can open What&#39;s in.", AGAIN); hasNot(p, LOADING, "undefined"); assert.strictEqual(p.title(), "Week of Mon 12 Oct");
  p.press("reload"); assert.deepStrictEqual(p.asked, [url(W12), url(W12)]); has(p, LOADING); hasNot(p, "Only the relief team", AGAIN);
  await p.give(1, refused("Could not reach the server.", 0)); has(p, "Could not reach the server.", AGAIN);
  p.press("before"); assert.strictEqual(p.asked[2], url(W5)); has(p, LOADING); hasNot(p, AGAIN, "Could not reach");
  await p.give(2, week()); has(p, "43%"); hasNot(p, AGAIN);
});
t("read again when the tab is shown: what is there stays, also when that fails", async () => {
  const p = open(""); await p.give(0, week()); p.tab.shown(); assert.strictEqual(p.asked.length, 2); has(p, "43%"); hasNot(p, LOADING);
  await p.give(1, refused("Could not reach the server.", 0)); has(p, "43%", "Could not reach the server.", AGAIN);
  p.press("reload"); has(p, "43%"); hasNot(p, AGAIN); await p.give(2, week({ fat_percent: 50 })); has(p, "50%"); hasNot(p, "43%", AGAIN);
});
t("after a button that goes, the focus is on the heading", async () => {
  const p = open(""); await p.give(0, refused("No.")); p.press("reload"); assert.strictEqual(p.focus(), "smTitle", "Try again");
  await p.give(1, refused("No.")); assert.strictEqual(p.focus(), "smTitle", "refused again"); p.press("reload"); await p.give(2, week()); assert.strictEqual(p.focus(), "smTitle", "and answered");
  p.press("before"); assert.strictEqual(p.focus(), "the button", "this one stays"); p.press("after"); assert.strictEqual(p.focus(), "the button");
  p.press("before"); p.press("now"); assert.strictEqual(p.focus(), "smTitle", "This week"); assert.strictEqual(p.away(), false); assert.strictEqual(p.asked[p.asked.length - 1], url(W12));
});
t("room under the week's heading; on a phone each fact's label above its value", async () => {
  const p = open("");
  assert.ok(/class="card sm"><div class="ab-top">/.test(p.pane.innerHTML) && p.pane.innerHTML.includes('<div id="smBody">'));
  assert.ok(/margin-bottom:(\d+)px/.exec(css("relief.html", ".sm .ab-top"))[1] >= 10);
  await p.give(0, week());
  assert.strictEqual((p.html().match(/<div><dt>(?:Arranged|Acknowledged|Asked to change)<\/dt><dd>/g) || []).length, 3, "all three are one kind of line");
  assert.ok(css("relief.html", ".sm-facts>div", "(max-width:640px)").includes("display:block"), "and drawn one way");
});
t("no relief, no Flexi Adjunct role, nobody asked", async () => {
  let p = open(""); await p.give(0, week({ periods: 0, asked: 0, never: 0, rows: [], top: [], by_dept: [], by_day: { Mon: 0 } })); has(p, "No relief this week."); hasNot(p, "counter", "<table", "Asked to change");
  p = open(""); await p.give(0, week({ fat_role: false, never: 0, asked: 0 })); has(p, '<div class="counter"><span class="small muted">Never acknowledged</span><b>0</b>', "<dt>Asked to change</dt><dd>0</dd>"); hasNot(p, "Flexi", "counter bad", "No relief");
  p = open(""); await p.give(0, { ok: true, status: 200, data: {} }); has(p, "No relief this week.");
  assert.strictEqual(p.tab.dirty(), false);
});

(async () => {
  for (const [name, f] of all) {
    try { await f(); n++; } catch (e) { console.error(`${name}:`); throw e; }
  }
  console.log(n + " cases passed");
})().catch(e => { console.error(e); process.exit(1); });

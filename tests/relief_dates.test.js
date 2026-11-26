// Plain-assert tests for the dates of a relief absence (static/relief-form.js): run with `node tests/relief_dates.test.js`.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const window = {}, ctx = vm.createContext({ window, document: { querySelector: () => null } });
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "static", "relief-form.js"), "utf8"), ctx);
const RF = window.ReliefForm;

let n = 0; const t = (name, f) => { try { f(); n++; } catch (e) { console.error("FAIL", name); throw e; } };
const oct = (...x) => x.map(d => `2026-10-${String(d).padStart(2, "0")}`);

/* ---- Calendar, Task 2 ---- */
t("dayRuns: two dates are listed", () => assert.strictEqual(RF.dayRuns(oct(13, 14)), "Tue 13 Oct, Wed 14 Oct"));
t("dayRuns: three in a row is a run", () => assert.strictEqual(RF.dayRuns(oct(12, 13, 14)), "Mon 12 Oct – Wed 14 Oct"));
t("dayRuns: a weekend joins", () => assert.strictEqual(RF.dayRuns(oct(15, 16, 19, 20)), "Thu 15 Oct – Tue 20 Oct"));
t("dayRuns: a missing weekday breaks it", () => assert.strictEqual(RF.dayRuns(oct(21, 22, 26, 27)), "Wed 21 Oct, Thu 22 Oct, Mon 26 Oct, Tue 27 Oct"));
t("dayRuns: unsorted with a duplicate", () => assert.strictEqual(RF.dayRuns(oct(20, 16, 12, 13, 14, 15, 13)), "Mon 12 Oct – Fri 16 Oct, Tue 20 Oct"));
t("dayRuns: none is empty", () => { assert.strictEqual(RF.dayRuns([]), ""); assert.strictEqual(RF.dayRuns(null), ""); });
t("dayRuns: a label names each date", () => assert.strictEqual(RF.dayRuns(oct(12, 13, 14), d => d === "2026-10-12" ? "Today" : RF.day(d)), "Today – Wed 14 Oct"));

/* ---- Calendar, Task 3 ---- */
/* static/relief-dates.js, loaded after relief-form.js as on the page; a made-up school: today Thu 26 Nov 2026, the school days are the
   weekdays to 31 Dec but for Founders' Day (Fri 4 Dec) and Christmas Day */
const read = f => fs.readFileSync(path.join(__dirname, "..", "static", f), "utf8");
vm.runInContext(read("relief-dates.js"), ctx);
const RD = window.ReliefDates;
const same = (a, b, msg) => assert.deepStrictEqual(JSON.parse(JSON.stringify(a)), b, msg);   /* a value from the page's own context */
const weekdays = (from, to) => { const out = []; for (let d = from; d <= to; d = RF.addDays(d, 1)) { const w = new Date(d + "T00:00:00Z").getUTCDay(); if (w > 0 && w < 6) out.push(d); } return out; };
const OFF = { "2026-12-04": "Founders' Day", "2026-12-25": "Christmas Day" };
const LIST = weekdays("2026-11-26", "2026-12-31").filter(d => !OFF[d]);
const INFO = { today: "2026-11-26", days: new Set(LIST), list: LIST, off: OFF };
const LONG_LIST = weekdays("2026-11-26", "2027-02-26").filter(d => !OFF[d]);   /* the same school, its term running to February */
const LONG = { today: "2026-11-26", days: new Set(LONG_LIST), list: LONG_LIST, off: OFF };
const SEVEN = ["2026-11-27", "2026-11-30", "2026-12-01", "2026-12-02", "2026-12-03", "2026-12-07", "2026-12-08"];

t("dayRuns: a run across the year end", () => assert.strictEqual(RF.dayRuns(["2026-12-30", "2026-12-31", "2027-01-01"]), "Wed 30 Dec – Fri 1 Jan"));

t("why: each grey day says why, a school day says nothing", () => {
  assert.strictEqual(RD.why("2026-11-25", INFO), "In the past");
  assert.strictEqual(RD.why("2026-11-28", INFO), "Weekend");
  assert.strictEqual(RD.why("2026-12-04", INFO), "Founders' Day");
  assert.strictEqual(RD.why("2027-01-04", INFO), "Not in a term");
  assert.strictEqual(RD.why("2026-11-27", INFO), "");
});
t("between: the school days from one to the other, either order, in date order", () => {
  same(RD.between("2026-12-08", "2026-11-27", INFO), SEVEN);
  same(RD.between("2026-11-27", "2026-12-08", INFO), SEVEN);
});
t("dragResult: a drag ticks every school day between", () => same(RD.dragResult([], "2026-11-27", "2026-12-08", INFO, 20), { picked: SEVEN, capped: false }));
t("dragResult: a drag from a ticked day takes the ticked days between off", () =>
  same(RD.dragResult(SEVEN, "2026-11-30", "2026-12-02", INFO, 20), { picked: ["2026-11-27", "2026-12-03", "2026-12-07", "2026-12-08"], capped: false }));
t("dragResult: past the most, the days are taken from the anchor (a drag backwards)", () =>
  same(RD.dragResult(["2026-12-14"], "2026-12-08", "2026-11-27", INFO, 3), { picked: ["2026-12-07", "2026-12-08", "2026-12-14"], capped: true }));
t("dragResult: past the most, a drag forwards", () =>
  same(RD.dragResult([], "2026-11-27", "2026-12-08", INFO, 3), { picked: ["2026-11-27", "2026-11-30", "2026-12-01"], capped: true }));
t("dragResult: a click takes a ticked day off and ticks another", () => {
  same(RD.dragResult(SEVEN, "2026-12-01", "2026-12-01", INFO, 20), { picked: SEVEN.filter(d => d !== "2026-12-01"), capped: false });
  same(RD.dragResult(["2026-12-14"], "2026-12-09", "2026-12-09", INFO, 20), { picked: ["2026-12-09", "2026-12-14"], capped: false });
});
t("dragResult: a click with 20 ticked changes nothing", () => {
  const full = LIST.slice(0, 20);
  same(RD.dragResult(full, LIST[20], LIST[20], INFO, 20), { picked: full, capped: true });
});
t("months: the month of the first and of the last school day", () => {
  same(RD.months(INFO), { first: "2026-11", last: "2026-12" });
  same(RD.months({ today: "2026-12-21", days: new Set(["2027-01-04", "2027-03-12"]), list: ["2027-01-04", "2027-03-12"], off: {} }), { first: "2027-01", last: "2027-03" });
});

const view = more => Object.assign({ info: INFO, first: "2026-11", picked: [], preview: { add: [], rem: [] }, max: 20, capped: false }, more);
const tag = (h, sel) => (h.match(new RegExp(`<button[^>]*${sel}[^>]*>`)) || [""])[0];   /* the first button holding sel */
const attr = (tg, name) => {   /* an attribute's value as the browser reads it, or null */
  const m = new RegExp(`\\s${name}="([^"]*)"`).exec(tg);
  return m ? m[1].replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&") : null;
};
const flag = (tg, name) => new RegExp(`\\s${name}(\\s|=|>)`).test(tg);
const cls = (h, d) => (attr(tag(h, `data-d="${d}"`), "class") || "").split(" ");
const sumText = h => h.slice(h.indexOf('class="rd-sum"')).replace(/^[^>]*>/, "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();

t("html: two months from first, Monday first", () => {
  const h = RD.html(view());
  assert.ok(h.includes("November 2026") && h.includes("December 2026") && !h.includes("October 2026") && !h.includes("January 2027"));
  assert.strictEqual((h.match(/class="rd-month"/g) || []).length, 2);
  const nov = h.slice(h.indexOf("November 2026"), h.indexOf("December 2026"));
  assert.strictEqual((nov.match(/class="rd-dow"[^>]*>(\w+)</) || [])[1], "Mon");
  assert.strictEqual(nov.slice(0, nov.indexOf('data-d="2026-11-01"')).split('class="rd-blank"').length - 1, 6, "Sun 1 Nov is in the seventh column");
  assert.ok(tag(h, 'data-d="2026-11-27"').startsWith('<button type="button" class="rd-d'));
});
t("html: the arrows are disabled at the first and the last month", () => {
  const h = RD.html(view());
  assert.ok(flag(tag(h, 'data-rd="prev"'), "disabled") && flag(tag(h, 'data-rd="next"'), "disabled"));
  assert.ok(h.indexOf('data-rd="prev"') < h.indexOf("December 2026") && h.indexOf('data-rd="next"') > h.indexOf("December 2026"), "‹ on the left month, › on the right one");
  const mid = RD.html(view({ info: LONG, first: "2026-12" }));
  assert.ok(!flag(tag(mid, 'data-rd="prev"'), "disabled") && !flag(tag(mid, 'data-rd="next"'), "disabled"));
  assert.ok(flag(tag(RD.html(view({ info: LONG, first: "2027-01" })), 'data-rd="next"'), "disabled"));
});
t("html: a grey day says why and cannot be pressed; today is marked", () => {
  const h = RD.html(view()), hol = tag(h, 'data-d="2026-12-04"');
  assert.ok(cls(h, "2026-12-04").includes("off"));
  assert.strictEqual(attr(hol, "aria-disabled"), "true");
  assert.strictEqual(attr(hol, "title"), "Founders' Day");
  assert.strictEqual(attr(tag(h, 'data-d="2026-11-28"'), "title"), "Weekend");
  assert.strictEqual(attr(tag(h, 'data-d="2026-11-20"'), "title"), "In the past");
  assert.ok(cls(h, "2026-11-26").includes("today") && !cls(h, "2026-11-26").includes("off"));
  assert.ok(!cls(h, "2026-11-27").includes("off") && attr(tag(h, 'data-d="2026-11-27"'), "aria-disabled") === null);
});
t("html: a picked day is pressed; the days a drag would add or take off are marked", () => {
  const h = RD.html(view({ picked: ["2026-11-27"] }));
  assert.ok(cls(h, "2026-11-27").includes("pick"));
  assert.strictEqual(attr(tag(h, 'data-d="2026-11-27"'), "aria-pressed"), "true");
  assert.ok(!cls(h, "2026-11-30").includes("pick") && attr(tag(h, 'data-d="2026-11-30"'), "aria-pressed") !== "true");
  const p = RD.html(view({ picked: ["2026-11-27"], preview: { add: ["2026-11-30"], rem: ["2026-11-27"] } }));
  assert.ok(cls(p, "2026-11-30").includes("add") && cls(p, "2026-11-27").includes("rem") && !cls(p, "2026-12-01").includes("add"));
});
t("html: the line reads as runs, with Clear all", () => {
  const h = RD.html(view({ picked: SEVEN }));
  assert.strictEqual(sumText(h), "7 school days: Fri 27 Nov – Thu 3 Dec, Mon 7 Dec, Tue 8 Dec Clear all");
  assert.ok(tag(h, 'data-rd="clear"').includes('type="button"'));
  assert.strictEqual(sumText(RD.html(view({ picked: ["2026-11-27"] }))), "1 school day: Fri 27 Nov Clear all");
});
t("html: with 20 picked it says that is the most", () => {
  const h = RD.html(view({ picked: LIST.slice(0, 20) }));
  assert.ok(sumText(h).startsWith("20 school days: ") && sumText(h).endsWith("Clear all That is 20 school days, the most at one time."));
  assert.ok(!RD.html(view({ picked: LIST.slice(0, 19) })).includes("the most at one time"));
});
t("html: with none picked", () => {
  const h = RD.html(view());
  assert.strictEqual(sumText(h), "No dates yet. Up to 20 school days.");
  assert.strictEqual(tag(h, 'data-rd="clear"'), "");
});

/* the calendar in a small stand-in page: a box records what is drawn into it and its listeners, a day is a stand-in button */
const later = []; const ta = (name, f) => later.push([name, f]);
const OK = { ok: true, status: 200, data: { today: "2026-11-26", days: LONG_LIST, off: OFF } };
function page(answer) {
  const doc = { on: {}, under: null, addEventListener: (k, f) => (doc.on[k] = doc.on[k] || []).push(f), elementFromPoint: () => doc.under, querySelector: () => null };
  const w = {}, c = vm.createContext({ window: w, document: doc }), calls = { api: 0 };
  vm.runInContext(read("relief-form.js"), c);
  vm.runInContext(read("relief-dates.js"), c);
  w.Relief = { api: async url => { calls.api++; assert.strictEqual(url, "/api/relief/school-days"); return typeof answer === "function" ? answer(calls.api) : answer; },
               say: m => `<span class="msg bad">${w.ReliefForm.esc(m.text)}</span>` };
  return { RD: w.ReliefDates, doc, calls };
}
function dayEl(d) { const el = { dataset: { d }, cls: new Set(), classList: { toggle: (k, on) => (on ? el.cls.add(k) : el.cls.delete(k)) }, closest: s => (s.startsWith(".rd-d") ? el : null) }; return el; }
function btnEl(rd) { const el = { dataset: { rd }, disabled: false, closest: s => (s.startsWith("button[data-rd]") ? el : null) }; return el; }
function standBox(days) {
  let html = "";
  const b = { on: {}, draws: 0, get innerHTML() { return html; }, set innerHTML(v) { html = v; b.draws++; }, addEventListener: (k, f) => (b.on[k] = b.on[k] || []).push(f),
              querySelector: () => null, querySelectorAll: () => days || [], contains: () => true };
  return b;
}
const fire = (where, type, more) => (where.on[type] || []).forEach(f => f(Object.assign({ button: 0, detail: 0, pointerId: 1, clientX: 0, clientY: 0, preventDefault() {} }, more)));
const tick = () => new Promise(f => setImmediate(f));
const fiveDays = () => ["2026-11-27", "2026-11-30", "2026-12-04", "2026-12-08", "2026-12-09"].map(dayEl);

ta("mount: reading the school calendar until the answer, then two months; read once per page", async () => {
  let answer;
  const p = page(() => new Promise(f => { answer = f; })), box = standBox();
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange() {} });
  assert.ok(box.innerHTML.includes("Reading the school calendar…"), box.innerHTML);
  answer(OK); await tick();
  assert.ok(box.innerHTML.includes("November 2026") && box.innerHTML.includes("December 2026"), box.innerHTML);
  const other = standBox();
  p.RD.mount(other, { key: "ask", picked: ["2026-11-27"], max: 20, onChange() {} });
  assert.ok(other.innerHTML.includes("November 2026") && sumText(other.innerHTML).startsWith("1 school day: Fri 27 Nov"), "drawn at once, from what was read");
  assert.strictEqual(p.calls.api, 1);
});
ta("mount: a refusal says the server's sentence; Try again only when the server was not reached, and it reads again", async () => {
  const p = page(n => (n === 1 ? { ok: false, status: 0, error: "The server could not be reached." } : OK)), box = standBox();
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange() {} }); await tick();
  assert.ok(box.innerHTML.includes("The server could not be reached.") && box.innerHTML.includes('data-rd="retry"'), box.innerHTML);
  fire(box, "click", { target: btnEl("retry"), detail: 1 }); await tick();
  assert.strictEqual(p.calls.api, 2);
  assert.ok(box.innerHTML.includes("November 2026"), box.innerHTML);
  p.RD.mount(standBox(), { key: "ask", picked: [], max: 20 }); await tick();
  assert.strictEqual(p.calls.api, 2, "kept once it was read");
  const q = page({ ok: false, status: 409, error: "Nothing is published yet." }), b = standBox();
  q.RD.mount(b, { key: "plan", picked: [], max: 20 }); await tick();
  assert.ok(b.innerHTML.includes("Nothing is published yet.") && !b.innerHTML.includes('data-rd="retry"') && !b.innerHTML.includes("rd-month"), b.innerHTML);
});
ta("view state is kept by key", async () => {
  const p = page(OK), one = standBox();
  p.RD.mount(one, { key: "plan", picked: [], max: 20 }); await tick();
  fire(one, "click", { target: btnEl("next"), detail: 1 });
  assert.ok(one.innerHTML.includes("December 2026") && one.innerHTML.includes("January 2027") && !one.innerHTML.includes("November 2026"), one.innerHTML);
  const two = standBox();
  p.RD.mount(two, { key: "plan", picked: [], max: 20 });   /* a form repaint makes a new box */
  assert.ok(two.innerHTML.includes("December 2026") && two.innerHTML.includes("January 2027") && !two.innerHTML.includes("November 2026"));
  const ask = standBox();
  p.RD.mount(ask, { key: "ask", picked: [], max: 20 });
  assert.ok(ask.innerHTML.includes("November 2026") && ask.innerHTML.includes("December 2026") && !ask.innerHTML.includes("January 2027"));
});
ta("a drag changes classes only while it moves, calls onChange once on release, and the click after it is not counted", async () => {
  const days = fiveDays(), [d27, d30, d04, d08, d09] = days, p = page(OK), box = standBox(days), got = [];
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange: l => got.push(Array.from(l)) }); await tick();
  const drawn = box.draws;
  fire(box, "pointerdown", { target: d27 });
  p.doc.under = d08; fire(p.doc, "pointermove", {});
  assert.strictEqual(box.draws, drawn, "the grid is not drawn again during a drag");
  assert.ok(d27.cls.has("add") && d30.cls.has("add") && d08.cls.has("add") && !d04.cls.has("add") && !d09.cls.has("add"));
  p.doc.under = d04; fire(p.doc, "pointermove", {});   /* over a grey day: the last school day stays the end */
  p.doc.under = null; fire(p.doc, "pointermove", {});
  assert.ok(d08.cls.has("add") && !d09.cls.has("add"));
  assert.strictEqual(got.length, 0, "nothing changes before the release");
  fire(p.doc, "pointerup", {});
  same(got, [SEVEN]);
  assert.strictEqual(box.draws, drawn + 1);
  fire(box, "click", { target: d08, detail: 1 });   /* the browser's own click after the pointer */
  assert.strictEqual(got.length, 1);
  fire(box, "click", { target: d09, detail: 0 });   /* Enter or Space on 9 Dec */
  same(got[1], [...SEVEN, "2026-12-09"]);
  fire(box, "pointerdown", { target: d08 }); p.doc.under = d27; fire(p.doc, "pointermove", {});   /* from a ticked day: takes off */
  assert.ok(d08.cls.has("rem") && d27.cls.has("rem") && !d27.cls.has("add") && !d09.cls.has("rem"));
  fire(p.doc, "pointerup", {});
  same(got[2], ["2026-12-09"]);
});
ta("a click is a press and release on one day; only the main button and a school day start one", async () => {
  const days = fiveDays(), [, d30, d04] = days, p = page(OK), box = standBox(days), got = [];
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange: l => got.push(Array.from(l)) }); await tick();
  fire(box, "pointerdown", { target: d30, button: 2 }); fire(p.doc, "pointerup", {});
  fire(box, "pointerdown", { target: d04 }); fire(p.doc, "pointerup", {});
  fire(box, "click", { target: d04, detail: 0 });
  assert.strictEqual(got.length, 0);
  fire(box, "pointerdown", { target: d30 }); fire(p.doc, "pointerup", {});
  fire(box, "click", { target: d30, detail: 1 });
  same(got, [["2026-11-30"]]);
  fire(box, "pointerdown", { target: d30 }); fire(p.doc, "pointerup", {});
  same(got, [["2026-11-30"], []]);
});
ta("pointercancel ends a drag with no change", async () => {
  const days = fiveDays(), [d27, , , d08] = days, p = page(OK), box = standBox(days), got = [];
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange: l => got.push(l) }); await tick();
  fire(box, "pointerdown", { target: d27 }); p.doc.under = d08; fire(p.doc, "pointermove", {});
  fire(p.doc, "pointercancel", {}); fire(p.doc, "pointerup", {});
  assert.strictEqual(got.length, 0);
  assert.ok(!box.innerHTML.includes(" pick"), "nothing ticked");
});
ta("a mount during a drag only records the dates; the calendar is drawn on release", async () => {
  const days = fiveDays(), [d27] = days, p = page(OK), first = standBox(days), got = [];
  p.RD.mount(first, { key: "plan", picked: [], max: 20, onChange: () => got.push("old") }); await tick();
  fire(first, "pointerdown", { target: d27 });
  const again = standBox(days), had = first.draws;
  p.RD.mount(again, { key: "plan", picked: ["2026-12-14"], max: 20, onChange: l => got.push(Array.from(l)) });
  assert.strictEqual(again.draws, 0, "not drawn during the drag");
  fire(p.doc, "pointerup", {});
  assert.strictEqual(again.draws, 1);
  assert.strictEqual(first.draws, had);
  same(got, [["2026-11-27", "2026-12-14"]]);
});
ta("focusFirst while the school days are being read focuses the first school day once they are drawn", async () => {
  let answer;
  const p = page(() => new Promise(f => { answer = f; })), box = standBox(), first = dayEl("2026-11-26"), focused = [];
  first.focus = () => focused.push(first.dataset.d);
  box.querySelector = s => (s === ".rd-d:not(.off)" && box.innerHTML.includes("rd-month") ? first : null);
  p.RD.mount(box, { key: "plan", picked: [], max: 20 });
  p.RD.focusFirst(box);   /* Pick dates was just chosen; the calendar says "Reading the school calendar…" */
  assert.strictEqual(focused.length, 0);
  answer(OK); await tick();
  same(focused, ["2026-11-26"]);
  assert.strictEqual(first.tabIndex, 0);
});
ta("a press while a drag is still open (its release lost) ends that drag with no change and starts a new one", async () => {
  const days = fiveDays(), [d27, d30, , d08] = days, p = page(OK), box = standBox(days), got = [];
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange: l => got.push(Array.from(l)) }); await tick();
  fire(box, "pointerdown", { target: d27, pointerId: 1 }); p.doc.under = d08; fire(p.doc, "pointermove", { pointerId: 1 });
  const drawn = box.draws;
  fire(box, "pointerdown", { target: d30, pointerId: 2 });
  assert.strictEqual(got.length, 0);
  assert.strictEqual(box.draws, drawn + 1, "the old drag's preview is drawn away");
  assert.ok(d30.cls.has("add") && !d27.cls.has("add") && !d08.cls.has("add"), "the new drag starts at 30 Nov");
  fire(p.doc, "pointerup", { pointerId: 1 });
  assert.strictEqual(got.length, 0, "the old pointer's late release does nothing");
  fire(p.doc, "pointerup", { pointerId: 2 });
  same(got, [["2026-11-30"]]);
});
ta("a context menu ends a mouse drag with no change; a finger held still goes on", async () => {
  const days = fiveDays(), [d27, , , d08] = days, p = page(OK), box = standBox(days), got = [];
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange: l => got.push(Array.from(l)) }); await tick();
  fire(box, "pointerdown", { target: d27, pointerType: "mouse" }); p.doc.under = d08; fire(p.doc, "pointermove", {});
  const drawn = box.draws;
  fire(p.doc, "contextmenu", {});
  assert.strictEqual(box.draws, drawn + 1);
  fire(p.doc, "pointerup", {});
  assert.strictEqual(got.length, 0);
  fire(box, "pointerdown", { target: d27, pointerType: "touch" }); fire(p.doc, "pointermove", {});
  fire(p.doc, "contextmenu", {}); fire(p.doc, "pointerup", {});
  same(got, [SEVEN]);
});
ta("a pointer move with no button down ends the drag with no change", async () => {
  const days = fiveDays(), [d27, , , d08] = days, p = page(OK), box = standBox(days), got = [];
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange: l => got.push(l) }); await tick();
  fire(box, "pointerdown", { target: d27 }); p.doc.under = d08; fire(p.doc, "pointermove", { buttons: 1 });
  assert.ok(d08.cls.has("add"));
  const drawn = box.draws;
  fire(p.doc, "pointermove", { buttons: 0 });
  assert.strictEqual(box.draws, drawn + 1);
  fire(p.doc, "pointerup", {});
  assert.strictEqual(got.length, 0);
});
ta("a press with Ctrl or Cmd starts nothing", async () => {
  const days = fiveDays(), [d27] = days, p = page(OK), box = standBox(days), got = [];
  p.RD.mount(box, { key: "plan", picked: [], max: 20, onChange: l => got.push(l) }); await tick();
  fire(box, "pointerdown", { target: d27, ctrlKey: true }); fire(p.doc, "pointerup", {});
  fire(box, "pointerdown", { target: d27, metaKey: true }); fire(p.doc, "pointerup", {});
  assert.strictEqual(got.length, 0);
  assert.ok(!d27.cls.has("add"));
});
ta("Clear all takes every date off", async () => {
  const p = page(OK), box = standBox(), got = [];
  p.RD.mount(box, { key: "plan", picked: SEVEN, max: 20, onChange: l => got.push(Array.from(l)) }); await tick();
  fire(box, "click", { target: btnEl("clear"), detail: 1 });
  same(got, [[]]);
  assert.ok(box.innerHTML.includes("No dates yet. Up to 20 school days."));
});
ta("arrow keys move the months on when focus leaves them, and stop at the ends", async () => {
  const p = page(OK), box = standBox();
  p.RD.mount(box, { key: "plan", picked: [], max: 20 }); await tick();
  const had = box.draws;
  fire(box, "keydown", { target: dayEl("2026-11-27"), key: "ArrowUp" });   /* 20 Nov is in the past, in a month already shown */
  fire(box, "keydown", { target: dayEl("2026-11-02"), key: "ArrowUp" });   /* 26 Oct: before the first month */
  assert.strictEqual(box.draws, had);
  fire(box, "keydown", { target: dayEl("2026-12-31"), key: "ArrowDown" });
  assert.ok(box.innerHTML.includes("December 2026") && box.innerHTML.includes("January 2027") && !box.innerHTML.includes("November 2026"), box.innerHTML);
  fire(box, "keydown", { target: dayEl("2027-01-28"), key: "ArrowDown" });
  assert.ok(box.innerHTML.includes("January 2027") && box.innerHTML.includes("February 2027") && !box.innerHTML.includes("December 2026"));
  const end = box.draws;
  fire(box, "keydown", { target: dayEl("2027-02-26"), key: "ArrowDown" });   /* 5 Mar: after the last school day's month */
  assert.strictEqual(box.draws, end);
  assert.ok(box.innerHTML.includes("February 2027") && !box.innerHTML.includes("March 2027"));
});

/* ---- Calendar, Task 4 ---- */
/* Pick dates on Plan relief (relief-plan.js) and on Ask for relief (relief.js) is the calendar: the date box, its chips and the
   10 are gone */
const callOf = (code, name) => {   /* the text of the first call name(...), to its closing parenthesis; "" when there is none */
  const at = code.indexOf(name + "(");
  if (at < 0) return "";
  for (let i = at + name.length, depth = 0; i < code.length; i++) {
    if (code[i] === "(") depth++;
    else if (code[i] === ")" && --depth === 0) return code.slice(at, i + 1);
  }
  return "";
};
for (const [f, key] of [["relief-plan.js", "plan"], ["relief.js", "ask"]]) {
  t(`${f}: no date box, no chips, no 10 dates`, () => {
    const code = read(f);
    for (const gone of ['type="date" id="plDate"', 'id="askDate"', "adddate", "undate", "Up to 10 dates", "10 dates"]) assert.ok(!code.includes(gone), `${f} still holds ${gone}`);
  });
  t(`${f}: Pick dates mounts the calendar with key "${key}" and at most 20, and gives it the focus`, () => {
    const code = read(f), call = callOf(code, "ReliefDates.mount");
    assert.ok(call, `${f} calls ReliefDates.mount(`);
    assert.ok(call.includes(`key: "${key}"`) && call.includes("max: 20"), call);
    assert.ok(!call.includes("paintDay"), "the calendar draws itself again on a change: the form does not");
    assert.ok(code.includes("ReliefDates.focusFirst("), `${f}: choosing Pick dates focuses the first school day`);
  });
}

const DOM = require("./dom.js");
t("relief.html: above 640 px the two months stay side by side and shrink rather than wrap; under it they stack", () => {
  const cal = DOM.css("relief.html", ".rd-cal"), month = DOM.css("relief.html", ".rd-month");
  assert.ok(!/flex-wrap:\s*wrap/.test(cal), cal);
  assert.ok(/(^|;)flex:1 1 0(;|$)/.test(month) && /(^|;)min-width:0(;|$)/.test(month) && /(^|;)max-width:\d+px(;|$)/.test(month), month);
  assert.ok(DOM.css("relief.html", ".rd-cal", "(max-width:640px)").includes("flex-direction:column"), "stacked under 640 px");
  assert.ok(DOM.css("relief.html", ".rd-month", "(max-width:640px)").includes("width:100%"));
});
t("relief.html: today ticked keeps a ring of its own (its navy outline is lost on the navy of a ticked day)", () => {
  const rule = DOM.css("relief.html", ".rd-d.today.pick");
  assert.ok(/box-shadow:inset [^;]*#fff/.test(rule), rule);
});

/* the two forms in the page stand-in (tests/dom.js), with their own scripts: Pick dates draws the calendar, a click or a drag
   reads the lessons of those dates, Send sends them, and the form starts again with no dates. The stand-in cannot read the
   selector :not(.off), so ReliefDates.focusFirst is recorded rather than run. A made-up school: today Tue 13 Oct 2026, its school
   days the weekdays to Fri 18 Dec but for Sports Day (Fri 23 Oct). */
const EVE = "Ms Evelyn Koh", MAYA = "Ms Maya Lee", ACC = "Mr Accounts Only", SLASH = "Mr Raj s/o Dev";
const TERM = weekdays("2026-10-13", "2026-12-18").filter(d => d !== "2026-10-23");
function form(hash) {
  const sent = [];
  const p = DOM.open("relief.html", { now: "2026-10-13T07:20:00+08:00", hash, server: c => {
    const ok = data => ({ status: 200, data });
    if (c.url === "/api/relief/me") return ok({ name: EVE, depts: ["Science"], published: true, today: "2026-10-13", can_plan: true });
    if (c.url === "/api/relief/school-days") return ok({ today: "2026-10-13", days: TERM, off: { "2026-10-23": "Sports Day" } });
    if (c.url === "/api/relief/people") return ok([{ name: EVE, depts: ["Science"] }, { name: MAYA, depts: ["Science"] }, { name: ACC, depts: [], staff_only: true }, { name: SLASH, depts: ["Science"] }]);
    if (c.method === "POST" && c.url === "/api/relief/absences") {
      const r = { id: "a" + (sent.length + 1), teacher: c.body.teacher || EVE, dates: c.body.dates, periods: null, reason: "", reason_text: "", lessons: [], acknowledged: false };
      sent.push(r);
      return ok(r);
    }
    if (c.url === "/api/relief/absences/planned") return ok({ absences: sent });
    return ok({ absences: [], lessons: [], periods: [], duties: {} });
  } });
  p.run("relief-form.js", "relief-dates.js");
  p.firsts = [];
  p.window.ReliefDates.focusFirst = box => p.firsts.push(box);
  p.run("relief.js", "relief-plan.js");
  p.reads = () => p.calls.filter(c => c.url.startsWith("/api/relief/lessons?")).map(c => c.url);
  p.posted = () => p.calls.filter(c => c.method === "POST" && c.url === "/api/relief/absences").map(c => c.body);
  return p;
}
const press = (p, el, type, more) => {   /* as tests/dom.js fires an event: up from the element, then the document and the window */
  assert.ok(el, `no element for ${type}`);
  const e = Object.assign({ type, target: el, button: 0, buttons: 1, detail: 1, pointerId: 1, pointerType: "mouse", clientX: 0, clientY: 0, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } }, more);
  for (let x = el; x; x = x.parent) (x.on[type] || []).slice().forEach(f => f(e));
  for (const x of [p.document, p.window]) (x.on[type] || []).slice().forEach(f => f(e));
};
async function dragOn(p, box, from, to) {   /* press on one day, move to another, release */
  const a = box.querySelector(`.rd-d[data-d="${from}"]`), b = box.querySelector(`.rd-d[data-d="${to}"]`);
  press(p, a, "pointerdown");
  p.document.elementFromPoint = () => b;
  press(p, b, "pointermove");
  press(p, b, "pointerup");
  await p.settle();
}
const TEN = ["2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"];
const TWENTY = TERM.filter(d => d >= "2026-10-16").slice(0, 20);

ta("Ask for relief: Pick dates is the calendar; a click and a drag read the lessons of those dates; Send sends them; then no dates", async () => {
  const p = form("#ask"); await p.settle();
  await p.click('#askDay [data-v="pick"]');
  const box = p.$("#askDay .rd-box");
  assert.ok(box, p.$("#askDay").innerHTML);
  assert.ok(p.text(box).includes("October 2026") && p.text(box).includes("November 2026"), p.text(box));
  assert.strictEqual(p.text("#askDay .rd-sum"), "No dates yet. Up to 20 school days.");
  assert.ok(p.firsts.length === 1 && p.firsts[0] === box, "choosing Pick dates focuses the calendar's first school day");
  assert.ok(p.text("#askSend").includes("Choose the dates first."), p.text("#askSend"));
  const had = p.reads().length;
  press(p, box.querySelector('.rd-d[data-d="2026-10-23"]'), "pointerdown"); press(p, box.querySelector('.rd-d[data-d="2026-10-23"]'), "pointerup"); await p.settle();
  assert.strictEqual(p.reads().length, had, "Sports Day cannot be ticked");
  assert.strictEqual(box.querySelector('.rd-d[data-d="2026-10-23"]').getAttribute("title"), "Sports Day");
  press(p, box.querySelector('.rd-d[data-d="2026-10-16"]'), "click", { detail: 0 }); await p.settle();   /* Enter on a day */
  assert.strictEqual(p.reads().slice(-1)[0], "/api/relief/lessons?dates=2026-10-16");
  assert.strictEqual(p.text("#askDay .rd-sum"), "1 school day: Fri 16 Oct Clear all");
  assert.strictEqual(p.$("#askDay .rd-box"), box, "the form does not draw the calendar again: it draws itself");
  await dragOn(p, box, "2026-10-19", "2026-10-30");
  assert.strictEqual(p.reads().slice(-1)[0], `/api/relief/lessons?dates=${encodeURIComponent(TEN.join(","))}`);
  assert.strictEqual(p.text("#askDay .rd-sum"), "10 school days: Fri 16 Oct – Thu 22 Oct, Mon 26 Oct – Fri 30 Oct Clear all");
  await p.click('#askSend [data-a="send"]');
  assert.deepStrictEqual(p.posted().map(b => b.dates), [TEN]);
  assert.ok(p.text("#askSend").includes("Sent."), p.text("#askSend"));
  assert.strictEqual(p.$('#askDay [data-v="today"]').getAttribute("aria-pressed"), "true");
  assert.strictEqual(p.$("#askDay .rd-box"), null);
  await p.click('#askDay [data-v="pick"]');
  assert.strictEqual(p.text("#askDay .rd-sum"), "No dates yet. Up to 20 school days.");
  assert.strictEqual(p.$("#askDay .rd-d.pick"), null);
});
ta("Plan relief: Pick dates is the calendar; a long drag stops at 20 and a 21st is refused; the lessons and Send carry the 20", async () => {
  const p = form("#plan"); await p.settle();
  await p.click('#plDay [data-v="pick"]');
  const box = p.$("#plDay .rd-box");
  assert.ok(box, p.$("#plDay").innerHTML);
  assert.ok(p.firsts.length === 1 && p.firsts[0] === box);
  assert.ok(p.text("#plSend").includes("Choose the dates first."), p.text("#plSend"));
  await dragOn(p, box, "2026-10-16", "2026-11-30");
  const line = "20 school days: Fri 16 Oct – Thu 22 Oct, Mon 26 Oct – Fri 13 Nov Clear all That is 20 school days, the most at one time.";
  assert.strictEqual(p.text("#plDay .rd-sum"), line);
  assert.ok(p.text("#plSend").includes("Choose the absent teacher first."), p.text("#plSend"));
  press(p, box.querySelector('.rd-d[data-d="2026-11-16"]'), "click", { detail: 0 }); await p.settle();
  assert.strictEqual(p.text("#plDay .rd-sum"), line, "a 21st day is refused");
  assert.ok(!box.querySelector('.rd-d[data-d="2026-11-16"]').classList.contains("pick"));
  await p.click(`#plWho [data-pp="pick"][data-name="${MAYA}"]`);
  assert.strictEqual(p.reads().slice(-1)[0], `/api/relief/lessons?teacher=${encodeURIComponent(MAYA)}&dates=${encodeURIComponent(TWENTY.join(","))}`);
  await p.click('#plSend [data-pl="send"]');
  assert.deepStrictEqual(p.posted().map(b => [b.teacher, b.dates]), [[MAYA, TWENTY]]);
  assert.strictEqual(p.$('#plDay [data-v="today"]').getAttribute("aria-pressed"), "true");
  assert.strictEqual(p.$("#plDay .rd-box"), null);
  assert.ok(p.text("#plPlannedList").includes("Fri 16 Oct – Thu 22 Oct, Mon 26 Oct – Fri 13 Nov"), p.text("#plPlannedList"));
  await p.click('#plDay [data-v="pick"]');
  assert.strictEqual(p.text("#plDay .rd-sum"), "No dates yet. Up to 20 school days.");
});
/* ---- Calendar, Task 5 ---- */
const LINK = n => `<a class="ghost filebtn small" href="/timetable#teachers/${encodeURIComponent(n)}" target="_blank" rel="noopener">Their timetable ↗</a>`;
ta("Task 5: the picker draws opts.after after Change, and nothing more without it", async () => {
  const p = form("#plan"); await p.settle();
  const box = p.$("#plWho");
  await p.click('#plWho [data-pp="pick"][data-name="' + MAYA + '"]');   /* the picker is closed, as when a teacher is chosen */
  const people = [{ name: "Ms Ada Ong", depts: [] }];
  p.window.ReliefForm.person(box, { people, value: "Ms Ada Ong" });
  const plain = box.innerHTML;
  assert.ok(plain.includes(">Change</button></div>") && !plain.includes("Their timetable"), plain);
  p.window.ReliefForm.person(box, { people, value: "Ms Ada Ong", after: n => `<a href="/x/${n}">Their timetable ↗</a>` });
  assert.ok(box.innerHTML.includes(`>Change</button><a href="/x/Ms Ada Ong">Their timetable ↗</a></div>`), box.innerHTML);
});
ta("Task 5: Plan relief shows the link for a teacher with a timetable, encoded, also with a slash; not for an accounts-only person; Ask for relief has none", async () => {
  const p = form("#plan"); await p.settle();
  assert.ok(!p.text("#plWho").includes("Their timetable"));
  await p.click(`#plWho [data-pp="pick"][data-name="${MAYA}"]`);
  assert.ok(p.$("#plWho").innerHTML.includes(LINK(MAYA)), p.$("#plWho").innerHTML);
  assert.ok(p.$("#plWho").innerHTML.indexOf("Change") < p.$("#plWho").innerHTML.indexOf("Their timetable"));
  await p.click('#plWho [data-pp="open"]');
  await p.click(`#plWho [data-pp="pick"][data-name="${SLASH}"]`);
  assert.ok(p.$("#plWho").innerHTML.includes(`href="/timetable#teachers/Mr%20Raj%20s%2Fo%20Dev"`), p.$("#plWho").innerHTML);
  await p.click('#plWho [data-pp="open"]');
  await p.click(`#plWho [data-pp="pick"][data-name="${ACC}"]`);
  assert.ok(p.text("#plWho").includes(ACC) && !p.text("#plWho").includes("Their timetable"), p.text("#plWho"));
  assert.ok(!read("relief.js").includes("Their timetable"));
});

(async () => {
  for (const [name, f] of later) { try { await f(); n++; } catch (e) { console.error("FAIL", name); throw e; } }
  console.log(`${n} relief dates tests passed`);
})().catch(e => { console.error(e); process.exitCode = 1; });

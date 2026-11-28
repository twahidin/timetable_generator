// Plain-assert tests for the relief team's All Relief Requests page (static/relief-inbox.js): run with `node tests/relief_inbox.test.js`.
// The page's script runs, with the real relief-form.js, in a small stand-in for the page, against an /api/relief/absences answer written here.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const read = f => fs.readFileSync(path.join(__dirname, "..", "static", f), "utf8");
const TODAY = "2026-10-12";
const record = more => Object.assign({ id: "a", teacher: "Ms Evelyn Koh", by: "Ms Evelyn Koh", how: "asked", at: "2026-10-12T07:05:00+08:00", dates: ["2026-10-13"], periods: null, reason: "Medical",
                                       reason_text: "", acknowledged: null, cancelled: null, lessons: [], cover: { total: 0, approved: 0, waiting: 0, open: 0 } }, more);

/* what the page shows for these absences */
async function shown(absences) {
  const els = {}, on = {};
  const el = id => els[id] || (els[id] = { innerHTML: "", querySelector: () => null });
  const pane = { innerHTML: "", querySelector: s => (s[0] === "#" ? el(s.slice(1)) : null), addEventListener: (k, f) => { on[k] = f; } };
  const window = {}, ctx = vm.createContext({ window, document: { querySelector: () => null } });
  vm.runInContext(read("relief-form.js"), ctx);
  const RF = window.ReliefForm;
  RF.setToday(TODAY);
  let tab = null;
  window.Relief = { cur: "inbox", tab: (name, mod) => { assert.strictEqual(name, "inbox"); tab = mod; }, plural: (n, one) => `${n} ${one}${n === 1 ? "" : "s"}`, span: () => "whole day", reason: r => r.reason,
                    say: m => (m ? RF.esc(m.text) : ""), json: (method, body) => ({ method, body }), api: async url => (url.endsWith("/seen") ? { ok: true, data: {} } : { ok: true, data: { absences, as_of: "2026-10-12T09:00:00+08:00" } }) };
  vm.runInContext(read("relief-change.js"), ctx);   /* Edit shows only where the editor is there */
  vm.runInContext(read("relief-inbox.js"), ctx);
  tab.init(pane);
  await new Promise(f => setImmediate(f));
  return el("inBox").innerHTML;
}

let n = 0; const all = []; const t = (name, f) => all.push([name, f]);

t("an absence asked on Telegram says so, in place of how it came", async () => {
  const html = await shown([record({ via: "telegram" })]);
  assert.ok(html.includes('<div class="small muted">asked on Telegram</div>'), html);
  assert.ok(!html.includes("for themselves"));
});
t("one with no via is as before: asked on the page, planned", async () => {
  const asked = await shown([record()]), planned = await shown([record({ how: "planned", by: "Mr Hugo Ong" })]);
  assert.ok(asked.includes("for themselves · app") && planned.includes("planned · app"));
  for (const html of [asked, planned]) assert.ok(!html.includes("Telegram"));
});
t("only the very word is taken for it, and nothing of it is written into the page", async () => {
  for (const via of ["Telegram", "code", "<b>telegram</b>", "", null, 7, ["telegram"], {}, true]) {
    const html = await shown([record({ via })]);
    assert.ok(html.includes("for themselves · app") && !html.includes("<b>"), String(via));
  }
});
t("a long absence's dates read as one run in the row", async () => {
  const html = await shown([record({ dates: ["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"] })]);
  assert.ok(html.includes("Tue 13 Oct \u2013 Fri 16 Oct"), html);
});

t("Not acknowledged is the view's name, and it takes a head's planning or a relief of today", async () => {
  const html = await shown([record({ id: "a", nudge: true, how: "planned", by: "Mr Hugo Ong" }), record({ id: "b", unacked: [{ who: "Mr Sam Tan", p: 6, n: 3, started: false }] }), record({ id: "c" })]);
  assert.ok(html.includes("Not acknowledged (2)") && !html.includes("Needs a nudge"), html);
});
t("a row says which relief teacher has not acknowledged, and when the lesson has started", async () => {
  const html = await shown([record({ unacked: [{ who: "Mr Sam Tan", p: 6, n: 3, started: false }, { who: "Ms Maya Lee", p: 11, n: 1, started: true }] })]);
  assert.ok(html.includes("Relief not acknowledged: Mr Sam Tan, P7\u2013P9") && html.includes("Relief not acknowledged: Ms Maya Lee, P12 \u00b7 started"), html);
});
t("an answer without unacked (an older server) is as before", async () => {
  const html = await shown([record()]);
  assert.ok(html.includes("Not acknowledged (0)") && !html.includes("Relief not acknowledged"), html);
});

const edits = html => (html.match(/data-in="edit"/g) || []).length;
t("Edit: on a request still to come, never on a cancelled one, one all past, or a backup for an exam or event", async () => {
  assert.strictEqual(edits(await shown([record()])), 1);
  assert.strictEqual(edits(await shown([record({ dates: ["2026-10-09", TODAY] })])), 1, "a date today is still to come");
  for (const more of [{ cancelled: { by: "Ms Evelyn Koh", why: "Well again", at: "2026-10-12T07:00:00+08:00" } }, { dates: ["2026-10-09"] }, { exams: { id: "x1", kind: "exam" } }]) {
    const html = await shown([record(more)]);
    assert.strictEqual(edits(html), 0, JSON.stringify(more));
  }
  const coming = await shown([record({ id: "a" }), record({ id: "b", exams: { id: "x1", kind: "event" } })]);
  assert.strictEqual(edits(coming), 1);
  assert.ok(coming.includes('data-in="edit" data-id="a"'), coming);
});
t("the last column: every row has it, the cancelled one's chip spans to it", async () => {
  const html = await shown([record({ id: "a" })]);
  assert.strictEqual((html.match(/<th[ >]/g) || []).length, 9, html);
});
t("Changed by: under the stamp, the last change's who and when", async () => {
  const html = await shown([record({ changes: [{ at: "2026-10-09T10:00:00+08:00", by: "Ms Evelyn Koh" }, { at: "2026-10-12T08:15:00+08:00", by: "Mr Hugo Ong" }], changed_at: "2026-10-12T08:15:00+08:00" })]);
  assert.ok(html.includes("Changed by Mr Hugo Ong, Today, 08:15") && !html.includes("Changed by Ms Evelyn Koh"), html);
  const before = await shown([record({ changes: [{ at: "2026-10-09T10:00:00+08:00", by: "Ms Evelyn Koh" }] })]);
  assert.ok(before.includes("Changed by Ms Evelyn Koh, Fri 9 Oct, 10:00"), before);
  for (const changes of [undefined, null, [], "x", [{}], [null]]) assert.ok(!(await shown([record({ changes })])).includes("Changed by"), JSON.stringify(changes));
});

/* ---------------------------------------------------------------- Edit, on the Relief page itself (tests/dom.js) */
const { open } = require("./dom.js");
const ok = data => ({ status: 200, data });
const weekdays = (from, to) => { const out = []; for (let d = new Date(from + "T00:00:00Z"); d <= new Date(to + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + 1)) if (d.getUTCDay() % 6) out.push(d.toISOString().slice(0, 10)); return out; };
const LESSON = { key: "k5", date: "2026-10-13", p: 5, n: 2, classes: ["1A"], subject: "Science", group: "", room: "R1", start: "10:00", end: "11:00", needed: true, not_needed: null, stopped: "", work: {},
  covers: [{ ckey: "k5", p: 5, n: 2, start: "10:00", end: "11:00", state: "open", relief: null }] };
async function page(list) {
  const p = open("relief.html", { now: "2026-10-12T09:00:00+08:00", hash: "#inbox", server: call => {
    if (call.url === "/api/relief/me") return ok({ name: "Mr Hugo Ong", depts: [], published: true, today: TODAY, can_team: true, can_plan: true, can_settings: false });
    if (call.url === "/api/relief/absences") return ok({ absences: p.list, as_of: "2026-10-12T09:00:00+08:00" });
    if (call.url === "/api/relief/school-days") return ok({ today: TODAY, days: weekdays(TODAY, "2026-11-20"), off: {} });
    if (call.url.endsWith("/change/preview")) return ok(Object.assign({ kept: [], added: [], gone: [], earlier: 0, dates: ["2026-10-13"], periods: null, unchanged: true, day_periods: [] }, p.preview));
    if (call.url.endsWith("/change")) return p.save;
    if (call.url.includes("/lessons/") || call.url.endsWith("/cancel")) return p.step;
    return ok({ absences: [], covers: [], lessons: [], periods: [] });
  } });
  p.list = list; p.step = ok({}); p.preview = {}; p.save = ok({});
  p.run("relief-form.js", "relief-dates.js", "relief-change.js", "relief.js", "relief-inbox.js");
  await p.settle();
  p.reads = () => p.calls.filter(c => c.method === "GET" && c.url === "/api/relief/absences").length;
  p.edit = id => p.$(`#inBox button[data-in="edit"][data-id="${id}"]`);
  return p;
}
t("Edit opens the editor under the table, outside its scroller, named, its row marked, with one lesson and the cancel; one at a time", async () => {
  const p = await page([record({ id: "a", lessons: [LESSON] }), record({ id: "b", teacher: "Mr Sam Tan", by: "Mr Sam Tan", lessons: [LESSON] })]);
  assert.strictEqual(p.text(p.edit("a")), "Edit");
  await p.click(p.edit("a"));
  const box = p.find("#inBox .in-edit");
  assert.strictEqual(box.closest(".tablewrap"), null, "never in the table's own scroller (a phone could not reach its right side)");
  assert.strictEqual(box.closest("table"), null);
  assert.strictEqual(box.parent, p.find("#inBox .tablewrap").parent, "under the table, the width of the card");
  assert.ok(p.text(box).startsWith("Edit: Ms Evelyn Koh's request · Tue 13 Oct · whole day"), p.text(box));
  for (const words of ["Change the dates or times", "Or change one lesson", "Tue 13 Oct · P6–P7 · 1A Science · no relief teacher yet", "Or cancel the whole request"]) assert.ok(p.text(box).includes(words), p.text(box));
  assert.strictEqual(p.edit("a").getAttribute("aria-expanded"), "true");
  assert.deepStrictEqual(p.all("#inBox tbody tr").map(r => r.classes().includes("editing")), [true, false], "its row is marked");
  assert.strictEqual(p.all("#inBox tr.in-edit").length + p.all("#inBox table .in-box").length, 0, "no row in the table for it");
  await p.click(p.edit("b"));
  assert.strictEqual(p.all("#inBox .in-edit").length, 1);
  assert.ok(p.text("#inBox .in-edit").includes("Mr Sam Tan"), "the newest is open");
  assert.deepStrictEqual(p.all("#inBox tbody tr").map(r => r.classes().includes("editing")), [false, true]);
  await p.click("#inBox .in-edit button", "Close");
  assert.strictEqual(p.all("#inBox .in-edit").length, 0);
  assert.strictEqual(p.focus(), p.edit("b"));
});
t("a cancelled row's chip spans to the last column", async () => {
  const p = await page([record({ id: "a", cancelled: { by: "Ms Evelyn Koh", why: "Well again", at: "2026-10-12T07:00:00+08:00" } })]);
  await p.click('#inBox [data-in="view"][data-v="cancelled"]');
  const cells = p.find("#inBox tbody tr").querySelectorAll("td");
  assert.strictEqual(cells.reduce((n, c) => n + Number(c.getAttribute("colspan") || 1), 0), 9);
  assert.strictEqual(p.all("#inBox thead th").length, 9);
  assert.strictEqual(p.all('#inBox [data-in="edit"]').length, 0);
});
t("what is chosen stays through a Refresh; a view without its row closes it, and nothing hidden counts as unsaved", async () => {
  const p = await page([record({ id: "a", lessons: [LESSON] })]);
  await p.click(p.edit("a"));
  await p.type('#inBox input[data-rc="cwhy"]', "Appointment moved");
  assert.strictEqual(p.window.Relief.dirtyAny(), true);
  await p.click("#inBox button", "Refresh");
  assert.strictEqual(p.find('#inBox input[data-rc="cwhy"]').value, "Appointment moved");
  let asked = 0; p.window.confirm = () => { asked++; return true; };
  await p.click('#inBox [data-in="view"][data-v="cancelled"]');
  assert.strictEqual(asked, 1, "asked first: it holds what was typed");
  assert.strictEqual(p.all("#inBox .in-edit").length, 0);
  assert.strictEqual(p.window.Relief.dirtyAny(), false);
  await p.click('#inBox [data-in="view"][data-v="coming"]');
  assert.strictEqual(p.all("#inBox .in-edit").length, 0, "closed, not hidden");
  assert.strictEqual(p.edit("a").getAttribute("aria-expanded"), "false");
  assert.ok(!p.text("#inBox").includes("can no longer be changed"), "the person's own step: nothing to say");
});
t("a save refused because the request changed meanwhile: the list is read again, the Edit stays open", async () => {
  const LOOKED = "The request has changed since you looked: look again before saving.";
  const p = await page([record({ id: "a", lessons: [LESSON] })]);
  await p.click(p.edit("a"));
  p.preview = { dates: [TODAY], unchanged: false, gone: [{ key: "k5", date: "2026-10-13", p: 5, n: 2, title: "1A Science", periods: "P6–P7", line: "nobody was approved yet" }] };
  await p.click("#inBox .in-edit button", "Today");
  assert.ok(!p.find("#inBox .in-edit button", "Save the change").disabled);
  const before = p.reads();
  p.save = { status: 400, data: { error: LOOKED } };
  await p.click("#inBox .in-edit button", "Save the change");
  assert.strictEqual(p.reads(), before + 1, "read again");
  assert.strictEqual(p.all("#inBox .in-edit").length, 1);
  assert.ok(p.text("#inBox .in-edit").includes(LOOKED), p.text("#inBox .in-edit"));
});
t("a Refresh finds the request can no longer be changed: the Edit closes and the line above the table says so", async () => {
  const cancelled = { by: "Ms Grace Wong", why: "Well again", at: "2026-10-12T08:00:00+08:00" };
  for (const now of [record({ id: "a", cancelled }), record({ id: "a", dates: ["2026-10-09"] }), null]) {
    const p = await page([record({ id: "a", lessons: [LESSON] }), record({ id: "b", teacher: "Mr Sam Tan", by: "Mr Sam Tan" })]);
    await p.click(p.edit("a"));
    p.list = now ? [now, p.list[1]] : [p.list[1]];
    await p.click("#inBox button", "Refresh");
    assert.strictEqual(p.all("#inBox .in-edit").length, 0, JSON.stringify(now));
    assert.strictEqual(p.text("#inBox .in-said"), "Ms Evelyn Koh's request can no longer be changed.");
    assert.strictEqual(p.window.Relief.dirtyAny(), false);
  }
});
t("a lesson's step: the Edit stays open, the dates chosen kept, what was done beside the lesson, and the list is read again", async () => {
  const p = await page([record({ id: "a", lessons: [LESSON] })]), before = p.reads();
  await p.click(p.edit("a"));
  p.preview = { dates: [TODAY], unchanged: false, gone: [{ key: "k5", date: "2026-10-13", p: 5, n: 2, title: "1A Science", periods: "P6–P7", line: "nobody was approved yet" }] };
  await p.click("#inBox .in-edit button", "Today");
  await p.type('#inBox .in-edit input[data-rc="why"]', "Back on Tuesday");
  const done = record({ id: "a", lessons: [Object.assign({}, LESSON, { needed: false, not_needed: { by: "Mr Hugo Ong", why: "", at: "2026-10-12T09:00:00+08:00" } })] });
  p.step = ok(done); p.list = [done];
  await p.click("#inBox .in-edit button", "Relief not needed");
  await p.click("#inBox .in-edit button", "Mark relief not needed");
  assert.strictEqual(p.all("#inBox .in-edit").length, 1, "still open");
  assert.ok(p.text("#inBox .in-edit").includes("1A Science: relief not needed."), p.text("#inBox .in-edit"));
  assert.ok(p.text("#inBox .in-edit").includes("Tue 13 Oct · P6–P7 · 1A Science · relief not needed"), p.text("#inBox .in-edit"));
  assert.deepStrictEqual(p.all('#inBox .in-edit button[data-rc="day"]').filter(b => b.getAttribute("aria-pressed") === "true").map(b => p.text(b)), ["Today"]);
  assert.strictEqual(p.find('#inBox .in-edit input[data-rc="why"]').value, "Back on Tuesday");
  assert.strictEqual(p.text("#inBox .in-said"), null, "nothing said above the table");
  assert.strictEqual(p.reads(), before + 1, "the list is read again");
  assert.strictEqual(p.focus(), p.find("#inBox .in-edit button", "Needed again"), "the focus on the lesson's new button");
  assert.strictEqual(p.window.Relief.dirtyAny(), true, "what was chosen is still unsaved");
});
t("Cancel the request: the Edit closes, what was done is said above the table, and the list is read again", async () => {
  const p = await page([record({ id: "a", lessons: [LESSON] })]), before = p.reads();
  await p.click(p.edit("a"));
  p.step = ok(record({ id: "a", cancelled: { by: "Mr Hugo Ong", why: "Course moved", at: "2026-10-12T09:00:00+08:00" } }));
  await p.type('#inBox .in-edit input[data-rc="cwhy"]', "Course moved");
  await p.click("#inBox .in-edit button", "Cancel the request");
  assert.strictEqual(p.all("#inBox .in-edit").length, 0);
  assert.ok(p.text("#inBox .in-said").includes("Cancelled."), p.text("#inBox"));
  assert.strictEqual(p.reads(), before + 1);
});
t("a lesson the app marked not needed (a co-teacher there) has Ask for relief anyway in the Edit, and says why", async () => {
  const shared = Object.assign({}, LESSON, { needed: false, not_needed: { by: "app", why: "Mr Busy Chan is there" } });
  const p = await page([record({ id: "a", lessons: [shared] })]);
  await p.click(p.edit("a"));
  assert.ok(p.text("#inBox .in-edit").includes("Tue 13 Oct · P6–P7 · 1A Science · Mr Busy Chan is there: no relief needed"), p.text("#inBox .in-edit"));
  p.step = ok(record({ id: "a", lessons: [LESSON] }));
  await p.click("#inBox .in-edit button", "Ask for relief anyway");
  assert.deepStrictEqual(p.calls.filter(c => c.url.includes("/lessons/")).map(c => [c.method, c.url]), [["POST", "/api/relief/absences/a/lessons/k5/needed"]]);
  assert.ok(p.text("#inBox .in-edit").includes("1A Science: relief asked for."), p.text("#inBox .in-edit"));
});
t("a view without the Edit's row asks first when it holds unsaved choices; without them it closes as before", async () => {
  const p = await page([record({ id: "a", lessons: [LESSON] })]), asked = [];
  let answer = false;
  p.window.confirm = q => { asked.push(q); return answer; };
  await p.click(p.edit("a"));
  await p.click('#inBox [data-in="view"][data-v="today"]');
  assert.deepStrictEqual(asked, [], "nothing chosen: not asked");
  assert.strictEqual(p.all("#inBox .in-edit").length, 0);
  await p.click('#inBox [data-in="view"][data-v="coming"]');
  await p.click(p.edit("a"));
  await p.type('#inBox .in-edit input[data-rc="why"]', "Moved");
  await p.click('#inBox [data-in="view"][data-v="nudge"]');
  assert.deepStrictEqual(asked, ["Close the Edit of Ms Evelyn Koh's request? What you chose there is not saved."]);
  assert.strictEqual(p.all("#inBox .in-edit").length, 1, "kept: the view stays");
  assert.strictEqual(p.find('#inBox [data-in="view"][data-v="coming"]').getAttribute("aria-pressed"), "true");
  answer = true;
  await p.click('#inBox [data-in="view"][data-v="nudge"]');
  assert.strictEqual(p.all("#inBox .in-edit").length, 0);
  assert.strictEqual(p.window.Relief.dirtyAny(), false);
});

(async () => {
  for (const [name, f] of all) {
    try { await f(); n++; } catch (e) { console.error("FAIL", name); throw e; }
  }
  console.log(`${n} relief All Relief Requests tests passed`);
})().catch(e => { console.error(e); process.exit(1); });

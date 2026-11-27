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

(async () => {
  for (const [name, f] of all) {
    try { await f(); n++; } catch (e) { console.error("FAIL", name); throw e; }
  }
  console.log(`${n} relief All Relief Requests tests passed`);
})().catch(e => { console.error(e); process.exit(1); });

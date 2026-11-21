// Plain-assert tests for static/history.js (the history page), run in a small stand-in for the browser's page:
// run with `node tests/history.test.js`. Made-up entries only.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SRC = fs.readFileSync(path.join(__dirname, "..", "static", "history.js"), "utf8");

/* just enough of the page's document for history.js: elements, text, ids, classes, listeners */
function makeDocument() {
  function text(s) { return { nodeType: 3, parent: null, get textContent() { return s; } }; }
  class El {
    constructor(tag) { this.tagName = tag; this.nodeType = 1; this.children = []; this.attrs = {}; this.dataset = {}; this.style = {}; this.on = {}; this.own = ""; this.className = ""; this.parent = null; this.disabled = false; }
    get classList() {
      const el = this, names = () => el.className.split(" ").filter(Boolean);
      return {
        toggle(c, want) { const s = new Set(names()); if (want === undefined ? !s.has(c) : want) s.add(c); else s.delete(c); el.className = [...s].join(" "); },
        contains(c) { return names().includes(c); },
      };
    }
    set textContent(v) { this.children = []; this.own = String(v); }
    get textContent() { return this.own + this.children.map(c => c.textContent).join(""); }
    setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") this.id = String(v); if (k === "disabled") this.disabled = true; }
    addEventListener(k, f) { (this.on[k] = this.on[k] || []).push(f); }
    append(...xs) { for (const x of xs) { const n = x && x.nodeType ? x : text(String(x)); n.parent = this; this.children.push(n); } }
    replaceChildren(...xs) { this.children = []; this.own = ""; this.append(...xs); }
    contains(x) { for (; x; x = x.parent) if (x === this) return true; return false; }
    all() { return [this].concat(...this.children.filter(c => c.nodeType === 1).map(c => c.all())); }
  }
  const body = new El("body");
  for (const id of ["msg", "scope", "filters", "list", "more"]) { const d = new El("div"); d.setAttribute("id", id); body.append(d); }
  return {
    body, activeElement: null,
    createElement: tag => new El(tag),
    createTextNode: text,
    querySelector: s => body.all().find(e => "#" + e.id === s) || null,
  };
}

/* the page loaded with fetch answering from `answer(url, opts)`; -> {doc, calls, settle} */
function page(answer, search = "") {
  const doc = makeDocument(), calls = [];
  const fetch = async (url, opts) => {
    calls.push([url, opts]);
    const [status, data] = answer(url, opts || {});
    return { status, ok: status >= 200 && status < 300, json: async () => data };
  };
  const ctx = vm.createContext({
    document: doc, fetch, URL, URLSearchParams, setTimeout, clearTimeout, console,
    location: { search, href: "http://localhost/history" + search }, history: { replaceState() {} },
    window: { confirm: () => true },
  });
  vm.runInContext(SRC, ctx);
  const settle = async () => { for (let i = 0; i < 20; i++) await new Promise(r => setImmediate(r)); };
  return { doc, calls, settle, $: s => doc.querySelector(s) };
}

const ENTRY = { as: "Ann Lee", via: "password", at: "2026-11-19T10:02:00+08:00", ts: 1795140120 };
const reply = (entries, more) => Object.assign({ entries, more: false, admin: false, depts: [], scope: "all", download: true }, more || {});

let n = 0;
const t = async (name, f) => { try { await f(); } catch (e) { console.error("FAILED: " + name); throw e; } n++; };

(async () => {
  await t("the Department filter lists every department", async () => {
    const p = page(() => [200, reply([Object.assign({ id: "h1", kind: "setup", where: "Step 4 · Teachers", depts: ["SC"], text: "x" }, ENTRY)], { depts: ["EL", "MA"] })]);
    await p.settle();
    const sel = p.$("#fDept");
    assert.deepStrictEqual(sel.children.map(c => [c.tagName, c.textContent]), [["option", "All departments"], ["option", "EL"], ["option", "MA"], ["option", "SC"]]);
  });

  await t("a head's Department filter lists only their departments", async () => {
    const p = page(() => [200, reply([Object.assign({ id: "h1", kind: "setup", where: "Step 4 · Teachers", depts: ["SC"], text: "x" }, ENTRY)], { depts: ["MA"], scope: "dept", download: false })]);
    await p.settle();
    assert.deepStrictEqual(p.$("#fDept").children.map(c => c.textContent), ["All departments", "MA"]);
  });

  await t("step 8, step 9 and a replaced setup link to where they are undone", async () => {
    const es = [
      Object.assign({ id: "h3", kind: "draft", what: "fix", where: "Step 8 · Upload and edit", text: "A fix", link: "/" }, ENTRY),
      Object.assign({ id: "h2", kind: "draft", what: "publish", where: "Step 9 · Publish", text: "Published", link: "/" }, ENTRY),
      Object.assign({ id: "h1", kind: "setup-replaced", where: "Setup", text: "Restored", link: "/" }, ENTRY),
    ];
    const p = page(() => [200, reply(es)]);
    await p.settle();
    const links = p.$("#list").all().filter(e => e.tagName === "a").map(a => [a.attrs.href, a.textContent]);
    assert.deepStrictEqual(links, [["/", "Undo it on step 8"], ["/", "Open step 9"], ["/", "Use a saved copy on the committee page"]]);
  });

  await t("Put back's success is said plainly, a refusal as a warning", async () => {
    for (const [status, data, want, cls] of [[200, { done: true, text: "Put back." }, "Put back.", "msg ok"], [409, { error: "Can't put back: this was changed again since." }, "Can't put back: this was changed again since.", "msg"]]) {
      const e = Object.assign({ id: "h1", kind: "setup", batch: "b1", op: "set", where: "Step 4 · Teachers", label: "Ann", field: "short", was: "A", now: "B", back: { unit: "b:b1", n: 1, ok: true, why: null } }, ENTRY);
      const p = page((url, opts) => (opts.method === "POST" ? [status, data] : [200, reply([e])]));
      await p.settle();
      const btn = p.$("#list").all().find(x => x.tagName === "button" && x.className === "putback");
      assert.ok(btn && !btn.disabled, "a Put back button");
      btn.on.click[0]();
      await p.settle();
      assert.ok(p.calls.some(([u, o]) => u === "/api/history/back" && o.method === "POST" && JSON.parse(o.body).id === "h1"), "posted");
      const m = p.$("#msg").children;
      assert.deepStrictEqual(m.map(x => [x.className, x.textContent]), [[cls, want]]);
    }
  });

  console.log(`${n} history page cases passed`);
})().catch(e => { console.error(e); process.exit(1); });

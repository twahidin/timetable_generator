// A small stand-in for a browser's page, for the node tests that run a page's own script (relief_telegram, relief_today and
// relief_settings): the page's own HTML from static/, its scripts, selectors, events that bubble, the focus, and a clock and
// timers the test moves itself. HTML that is not well nested throws. There is no network: every fetch is answered by the test.
// It knows no visibility and no layout: what is hidden, or in a hidden tab of the page, can be pressed and given the focus.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const read = f => fs.readFileSync(path.join(__dirname, "..", "static", f), "utf8");
const INLINE = new Set(["a", "b", "i", "s", "u", "span", "label"]);
const VOID = new Set(["input", "br", "img", "hr", "link", "meta"]);
const TOKEN = /<!--[\s\S]*?-->|<\/([a-zA-Z][a-zA-Z0-9]*)\s*>|<([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^\s"'<>\/=]+(?:="[^"]*"|='[^']*'|=[^\s"'<>]+)?)*)\s*\/?>|[^<]+/g;
const CHARS = { "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&amp;": "&" };
const decode = s => s.replace(/&(?:lt|gt|quot|#39|amp);/g, c => CHARS[c]);
const encode = s => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const kebab = k => "data-" + k.replace(/[A-Z]/g, c => "-" + c.toLowerCase());

class El {
  constructor(page, tag) {
    Object.assign(this, { tag, attrs: {}, kids: [] });
    const dataset = new Proxy({}, { get: (_, k) => this.attrs[kebab(String(k))], set: (_, k, v) => { this.attrs[kebab(k)] = String(v); return true; }, has: (_, k) => kebab(String(k)) in this.attrs });
    const classList = { contains: c => this.classes().includes(c), toggle: (c, on) => { const l = this.classes().filter(x => x !== c); if (on) l.push(c); this.attrs.class = l.join(" "); } };
    for (const [k, value] of Object.entries({ page, parent: null, on: {}, style: {}, typed: undefined, dataset, classList })) Object.defineProperty(this, k, { value, writable: true, enumerable: false });   /* a failed assert writes an element down: what is in it, not the whole page */
  }
  classes() { return (this.attrs.class || "").split(/\s+/).filter(Boolean); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  flag(k, v) { if (v) this.attrs[k] = ""; else delete this.attrs[k]; }
  get id() { return this.attrs.id || ""; }
  get hidden() { return "hidden" in this.attrs; } set hidden(v) { this.flag("hidden", v); }
  get open() { return "open" in this.attrs; } set open(v) { this.flag("open", v); }
  get disabled() { return "disabled" in this.attrs; } set disabled(v) { this.flag("disabled", v); }
  get className() { return this.attrs.class || ""; } set className(v) { this.attrs.class = v; }
  get value() { return this.typed !== undefined ? this.typed : this.tag === "textarea" ? this.textContent : this.attrs.value || ""; } set value(v) { this.typed = String(v); }
  set title(v) { this.attrs.title = v; } set href(v) { this.attrs.href = v; }
  get parentElement() { return this.parent; }
  add(kid) { if (kid instanceof El) kid.parent = this; this.kids.push(kid); }
  remove() { if (this.parent) this.parent.kids = this.parent.kids.filter(k => k !== this); this.parent = null; }
  elements() { return this.kids.flatMap(k => (k instanceof El ? [k, ...k.elements()] : [])); }
  contains(el) { for (let x = el; x; x = x.parent) if (x === this) return true; return false; }
  get textContent() { return this.kids.map(k => (k instanceof El ? k.textContent : k)).join(""); }
  set textContent(v) { this.empty(); this.add(String(v)); this.page.drawn.push(this); }
  empty() { for (const k of this.kids) if (k instanceof El) k.parent = null; this.kids = []; }
  get innerHTML() { return this.kids.map(k => (k instanceof El ? k.outerHTML : encode(k))).join(""); }
  set innerHTML(v) { this.empty(); this.page.parse(this, String(v)); this.page.drawn.push(this); }
  insertAdjacentHTML(where, html) { assert.strictEqual(where, "beforeend", "the stand-in knows no other place"); this.page.parse(this, html); }
  get outerHTML() {
    const attrs = Object.entries(this.attrs).map(([k, v]) => ` ${k}="${encode(v)}"`).join("");
    return VOID.has(this.tag) ? `<${this.tag}${attrs}>` : `<${this.tag}${attrs}>${this.innerHTML}</${this.tag}>`;
  }
  one(compound) {   /* tag, #id, .class, [attr], [attr="v"], :disabled, :not(:disabled) */
    let rest = compound;
    while (rest) {
      const m = /^(?:([a-zA-Z][a-zA-Z0-9]*)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:="((?:[^"\\]|\\.)*)")?\]|(:disabled)|(:not\(:disabled\)))/.exec(rest);
      assert.ok(m, `a selector the stand-in cannot read: ${compound}`);
      if (m[1] && m[1].toLowerCase() !== this.tag) return false;
      if (m[2] && this.id !== m[2]) return false;
      if (m[3] && !this.classes().includes(m[3])) return false;
      if (m[4] && !(m[4] in this.attrs)) return false;
      if (m[5] !== undefined && this.attrs[m[4]] !== m[5].replace(/\\(.)/g, "$1")) return false;
      if (m[6] && !this.disabled || m[7] && this.disabled) return false;
      rest = rest.slice(m[0].length);
    }
    return true;
  }
  matches(sel) {
    return sel.split(",").some(s => {
      const parts = s.trim().split(/\s+(?![^[]*\])/);
      if (!this.one(parts.pop())) return false;
      let el = this.parent;
      for (const p of parts.reverse()) { while (el && !el.one(p)) el = el.parent; if (!el) return false; el = el.parent; }
      return true;
    });
  }
  querySelectorAll(sel) { return this.elements().filter(e => e.matches(sel)); }
  querySelector(sel) { return this.elements().find(e => e.matches(sel)) || null; }
  closest(sel) { for (let x = this; x; x = x.parent) if (x.matches(sel)) return x; return null; }
  addEventListener(type, f) { (this.on[type] = this.on[type] || []).push(f); }
  focus() { if (!this.disabled && this.page.root.contains(this)) this.page.focused = this; }
  scrollIntoView() {}
}

/* the page static/{html}, its scripts not run yet. server(call): the answer to a fetch of {method, url, body}: {status, data}, a promise of one, or an Error (nobody answers) */
function open(html, { server, hash = "", search = "", now = "2026-10-13T07:20:00+08:00", hidden = false }) {
  const page = { calls: [], drawn: [], focused: null, now: Date.parse(now), timers: [], server };
  page.parse = (into, text) => {
    const open_ = [into];
    let at = 0;
    for (const m of text.matchAll(TOKEN)) {
      assert.strictEqual(m.index, at, `HTML that cannot be read at: ${text.slice(at, at + 60)}`);
      at += m[0].length;
      const top = open_[open_.length - 1];
      if (m[1]) { assert.ok(open_.length > 1 && top.tag === m[1].toLowerCase(), `</${m[1]}> closes <${top.tag}>: ${text.slice(Math.max(0, m.index - 80), at)}`); open_.pop(); }
      else if (m[2]) {
        const el = new El(page, m[2].toLowerCase());
        for (const a of m[3].matchAll(/([^\s"'=]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s"'<>]+)))?/g)) el.attrs[a[1]] = decode(a[2] ?? a[3] ?? a[4] ?? "");
        top.add(el);
        if (!VOID.has(el.tag)) open_.push(el);
      } else if (!m[0].startsWith("<!--")) top.add(decode(m[0]));
    }
    assert.strictEqual(at, text.length, `HTML that cannot be read at: ${text.slice(at, at + 60)}`);
    assert.strictEqual(open_.length, 1, `<${open_[open_.length - 1].tag}> is not closed`);
  };
  page.root = new El(page, "html");
  const body = new El(page, "body");
  page.root.add(body);
  page.parse(body, /<body>([\s\S]*)<\/body>/.exec(read(html))[1].replace(/<script\b[^>]*><\/script>/g, ""));
  page.document = { on: {}, body, title: "", visibilityState: hidden ? "hidden" : "visible", addEventListener(type, f) { (this.on[type] = this.on[type] || []).push(f); },
                    querySelector: s => page.root.querySelector(s), querySelectorAll: s => page.root.querySelectorAll(s), getElementById: id => page.root.querySelector("#" + id),
                    get activeElement() { return page.focused && page.root.contains(page.focused) ? page.focused : body; } };
  page.window = { on: {}, addEventListener(type, f) { (this.on[type] = this.on[type] || []).push(f); } };
  page.location = { hash, search, href: "" };
  class Clock extends Date { constructor(...a) { if (a.length) super(...a); else super(page.now); } static now() { return page.now; } }
  let n = 0;
  const ctx = vm.createContext({
    window: page.window, document: page.document, location: page.location, Date: Clock, URLSearchParams,
    history: { replaceState: (a, b, url) => { page.location.hash = url; } }, localStorage: { getItem: () => null, setItem: (k, v) => { page.stored = [k, v]; } },
    setTimeout: (f, ms) => { page.timers.push({ id: ++n, f, at: page.now + (ms || 0) }); return n; }, clearTimeout: id => { page.timers = page.timers.filter(t => t.id !== id); },
    fetch: async (url, o = {}) => {
      const call = { method: o.method || "GET", url, body: o.body === undefined ? undefined : JSON.parse(o.body), opts: o };
      page.calls.push(call);
      const a = await page.server(call);
      if (a instanceof Error) throw a;
      const data = a.data === undefined ? undefined : JSON.stringify(a.data);   /* as it is when the server answers */
      return { ok: a.status >= 200 && a.status < 300, status: a.status, json: async () => JSON.parse(data), text: async () => data };
    }
  });
  page.run = (...files) => { for (const f of files) vm.runInContext(read(f), ctx, { filename: f }); };
  page.settle = async () => { for (let i = 0; i < 6; i++) await new Promise(f => setImmediate(f)); };
  page.tick = async ms => {   /* time passes, and the timers that are due run */
    const end = page.now + ms;
    for (;;) {
      const t = page.timers.filter(x => x.at <= end).sort((a, b) => a.at - b.at || a.id - b.id)[0];
      if (!t) break;
      page.now = Math.max(page.now, t.at);
      page.timers = page.timers.filter(x => x !== t);
      t.f();
      await page.settle();
    }
    page.now = end;
  };
  const fire = (el, type, more) => {
    const e = Object.assign({ type, target: el, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } }, more);
    for (let x = el; x; x = x.parent) (x.on[type] || []).slice().forEach(f => f(e));
    for (const x of [page.document, page.window]) (x.on[type] || []).slice().forEach(f => f(e));
    return e;
  };
  page.$ = sel => page.root.querySelector(sel);
  page.all = sel => page.root.querySelectorAll(sel);
  const words = el => el.kids.map(k => (k instanceof El ? (INLINE.has(k.tag) ? words(k) : ` ${words(k)} `) : k)).join("");
  page.text = sel => { const el = typeof sel === "string" ? page.$(sel) : sel; return el ? words(el).replace(/\s+/g, " ").trim() : null; };   /* what is read: blocks and buttons apart */
  page.find = (sel, label) => {   /* the one element, by its words too when more than one fits */
    const got = page.all(sel).filter(e => label === undefined || page.text(e) === label);
    assert.strictEqual(got.length, 1, `${sel}${label === undefined ? "" : ` “${label}”`}: ${got.length} of them`);
    return got[0];
  };
  page.click = async (sel, label) => {   /* pressed, as a mouse or Return does it; a disabled one does nothing */
    const el = typeof sel === "string" ? page.find(sel, label) : sel;
    if (el.disabled) return el;
    el.focus();
    if (el.tag === "summary") el.parent.open = !el.parent.open;
    fire(el, "click");
    await page.settle();
    return el;
  };
  page.key = async (el, key) => { const e = fire(el, "keydown", { key }); await page.settle(); return e; };
  page.type = async (sel, v) => { const el = page.find(sel); el.focus(); el.value = v; fire(el, "input"); await page.settle(); };
  page.show = async on => { page.document.visibilityState = on ? "visible" : "hidden"; fire(page.document.body, "visibilitychange"); await page.settle(); };
  page.leave = async () => { (page.window.on.pagehide || []).forEach(f => f({ type: "pagehide" })); await page.settle(); };   /* another page in its place; back: it is there again, kept (persisted) or not */
  page.back = async persisted => { (page.window.on.pageshow || []).forEach(f => f({ type: "pageshow", persisted })); await page.settle(); };
  page.focus = () => { const a = page.document.activeElement; return a === body ? "" : a; };
  return page;
}

/* an answer the test gives when it likes: {answer: what server() is to give, give(status, data)} */
function later() {
  let done;
  const answer = new Promise(f => { done = f; });
  return { answer, give: (status, data) => done({ status, data }), fail: () => done(new Error("nobody answers")) };
}

/* what the rules of static/{file} (a page's own <style>, or style.css) say of a selector, as written; within: of those in the @media that starts so */
function css(file, sel, within = "") {
  const text = read(file), style = (file.endsWith(".css") ? text : /<style>([\s\S]*?)<\/style>/.exec(text)[1]).replace(/\/\*[\s\S]*?\*\//g, "");
  const media = [], plain = style.replace(/@media ([^{]+)\{((?:[^{}]*\{[^}]*\})*)\s*\}/g, (_, q, rules) => { media.push([q.trim(), rules]); return ""; });
  const of = rules => [...rules.matchAll(/([^{}]+)\{([^}]*)\}/g)].filter(m => m[1].split(",").some(x => x.trim() === sel)).map(m => m[2].trim()).join(";");
  return of(within ? media.filter(m => m[0].startsWith(within)).map(m => m[1]).join("\n") : plain);
}

/* every [name, f] of all, one by one; one that waits for an answer nobody gives is a failure too */
function run(all) {
  let now = "", n = 0;
  process.on("exit", () => { if (now) { console.error(`${now}: never ended`); process.exitCode = 1; } });
  (async () => {
    for (const [name, f] of all) {
      now = name;
      await f();
      n++;
    }
    now = "";
    console.log(n + " cases passed");
  })().catch(e => { console.error(`${now}:`); console.error(e); now = ""; process.exit(1); });
}

module.exports = { open, later, run, read, css };

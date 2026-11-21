// Plain-assert tests for the published page's dates (ttgen/timetable_page.html): run with `node tests/timetable_page.test.js`.
// The page's last script runs in a small fake DOM, on a made-up school, against /api/day answers written here.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const PAGE = fs.readFileSync(path.join(__dirname, "..", "ttgen", "timetable_page.html"), "utf8");
const SCRIPT = PAGE.split("<script>").pop().split("</script>")[0];
const STAMP = "2026-10-01T08:00:00";

/* a made-up school: 26 periods of 20 minutes from 07:40, written as the published model writes them ("12.40", "1.00") */
function data(app) {
  const NP = 26, clock = m => `${((Math.floor(m / 60) + 11) % 12) + 1}.${String(m % 60).padStart(2, "0")}`;
  const times = Array.from({ length: NP }, (_, p) => [clock(460 + 20 * p), clock(480 + 20 * p)]);
  const days = ["Odd Mon", "Odd Tue", "Odd Wed", "Odd Thu", "Odd Fri", "Even Mon", "Even Tue", "Even Wed", "Even Thu", "Even Fri"];
  const row = Array.from({ length: NP }, (_, p) => ({ 4: "R", 10: "U", 11: "U" }[p] || "L")).join("");
  const E = "Entire Class";
  const lessons = [
    [0, 0, 0, 2, "Sec 3", "", ["3A"], "English", E, ["Ms Aisha Rahman"], "3-01", 0],
    [1, 0, 1, 2, "Sec 4", "", ["4A"], "Mathematics", E, ["Mr Daniel Koh"], "4-01", 0],
    [2, 0, 6, 3, "Sec 3", "", ["3A", "3B"], "Combined Science", "3CS1", ["Ms Grace Yeo"], "3-02", 0],
    [3, 0, 9, 2, "Sec 4", "", ["4A"], "English", E, ["Mr Ben Ong"], "LT2", 0]
  ];
  const students = [["3A-01", "Student 3A-01", "3A", ["3CS1"]], ["3B-01", "Student 3B-01", "3B", ["3CS1"]], ["4A-01", "Student 4A-01", "4A", []]];
  return {
    school: { name: "Sample School", timetable: "2027", weeks: 2, period_minutes: 20, start_time: "07:40" }, generated: "1 Oct 2026",
    days, NP, times, grid: { "Sec 3": days.map(() => row), "Sec 4": days.map(() => row) }, cgrid: {}, levels: ["Sec 3", "Sec 4"],
    classes: [["3A", "Sec 3", 30, "3-01", []], ["3B", "Sec 3", 30, "3-02", []], ["4A", "Sec 4", 30, "4-01", []]], parents_name: "Form teachers",
    teachers: ["Ms Aisha Rahman", "Mr Ben Ong", "Mr Daniel Koh", "Ms Grace Yeo"].map(n => [n, n, "Teaching", ""]),
    rooms: [["3-01", "classroom", 1, [], "", []], ["3-02", "classroom", 1, [], "", []], ["4-01", "classroom", 1, [], "", []],
      ["LT1", "classroom", 1, [], "", []], ["LT2", "classroom", 1, [], "", []], ["LT1&2", "classroom", 1, [], "", ["LT1", "LT2"]]],
    subjects: { English: ["EL", 0, ""], Mathematics: ["MA", 1, ""], "Combined Science": ["CS", 2, ""] }, palette: [["dde", "223"], ["ded", "232"], ["edd", "322"]], ext: ["eee", "555"],
    lessons, students, checks: { ok: true, problems: [], after: [], notes: [] }, app
  };
}

const item = (o) => Object.assign({ exam: "Sec 3 Exam" }, o);
/* what /api/day gives for Mon 5 Oct: 3A's English and the science band stop, 4A's maths runs only in part, papers and duties */
const DAY = {
  date: "2026-10-05", day: "Odd Mon", published_at: STAMP,
  exams: {
    classes: { "3A": [item({ start: "07:50", end: "08:50", label: "Sec 3 English Paper 1", room: "3-01", seat_note: "", p: 0.5, n: 3 })] },
    stopped: [0, 2, 1], shortened: [[1, "08:20", "08:40"]],
    teachers: { "Ms Aisha Rahman": [item({ start: "07:35", end: "09:00", label: "Sec 3 English Paper 1", room: "3-01", role: "Invigilate", p: 0, n: 4 })] },
    rooms: { "3-01": [item({ start: "07:35", end: "09:00", label: "Sec 3 English Paper 1", p: 0, n: 4 })],
      "LT1": [item({ start: "09:45", end: "11:10", label: "Sec 3 Pure Chemistry Paper 1", p: 6.25, n: 4.25 })] },
    banner: "Sec 3 Exam"
  }
};
const HOLIDAY = { date: "2026-10-12", day: null, published_at: STAMP, exams: { classes: {}, stopped: [], shortened: [], teachers: {}, rooms: {}, banner: "" } };

function boot(answers, app) {
  const reg = new Map(), fetched = [];
  const el = (id, tag) => {
    const cls = new Set();
    return { id, tagName: (tag || "div").toUpperCase(), _html: "", textContent: "", style: {}, dataset: {}, hidden: false, value: "", className: "", listeners: {},
      classList: { add: c => cls.add(c), remove: c => cls.delete(c), toggle: (c, on) => (on === undefined ? (cls.has(c) ? cls.delete(c) : cls.add(c)) : on ? cls.add(c) : cls.delete(c)), contains: c => cls.has(c) },
      get innerHTML() { return this._html; }, set innerHTML(v) { this._html = String(v); scan(this); },
      insertAdjacentHTML(pos, h) { this._html = pos === "afterbegin" ? h + this._html : this._html + h; scan(this); },
      before(o) { adopt(o); }, after(o) { adopt(o); }, addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
      scrollIntoView() {}, focus() {}, showModal() {}, close() {}, querySelectorAll: () => [], open: false };
  };
  const adopt = o => { if (o.id) reg.set(o.id, o); scan(o); };
  const scan = e => { for (const m of e._html.matchAll(/id="([^"]+)"/g)) if (!reg.has(m[1])) reg.set(m[1], el(m[1])); };
  for (const id of ["q", "results", "status", "theme", "tabs", "main", "browse", "fq", "chips", "list", "view", "dlg", "dlgT", "dlgB", "school", "ttl"]) reg.set(id, el(id));
  const header = el("", "header");
  const document = {
    documentElement: { classList: el("html").classList, dataset: {} },
    querySelector: sel => sel === "header.top" ? header : sel === ".search" ? el("") : (/^#([\w-]+)$/.exec(sel) ? reg.get(sel.slice(1)) || null : null),
    querySelectorAll: () => [], createElement: t => el("", t), addEventListener() {}, activeElement: { tagName: "BODY" }
  };
  const loc = { hash: "", href: "http://x/timetable" };
  const ctx = {
    document, location: loc, history: { replaceState: (a, b, h) => { loc.hash = h; } }, window: { addEventListener() {}, print() {} },
    localStorage: { getItem: () => null, setItem() {} }, matchMedia: () => ({ matches: false }), CSS: { escape: s => s }, navigator: {},
    setTimeout, clearTimeout, URL, Blob: function () {}, console,
    fetch: url => {
      fetched.push(url);
      const k = Object.keys(answers).find(a => url === a || url.startsWith(a + "&"));
      if (!k) return Promise.reject(new Error("no answer for " + url));
      const [status, body] = answers[k];
      return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(JSON.parse(JSON.stringify(body))) });
    }
  };
  ctx.dlg = reg.get("dlg");
  vm.createContext(ctx);
  vm.runInContext(`const DATA = ${JSON.stringify(data(app))};`, ctx);
  vm.runInContext(SCRIPT, ctx);
  const tick = () => new Promise(r => setImmediate(r)).then(() => new Promise(r => setImmediate(r))).then(() => new Promise(r => setImmediate(r)));
  const pick = async iso => { reg.get("onDate").listeners.change[0]({ target: { value: iso } }); await tick(); };
  return { run: c => vm.runInContext(c, ctx), view: () => reg.get("view")._html, el: id => reg.get(id), fetched, tick, pick };
}

const APP = { mode: "teacher", tabs: ["classes", "teachers", "rooms", "students", "lessons", "free", "exams"], pdf: true, logout: "/logout", files: [], dates: true, exams: true, published_at: STAMP };
const LIST = [200, { schedules: [], banner: null }];
const count = (s, w) => s.split(w).length - 1;
const names = (v, from, to) => [...v.split(from)[1].split(to)[0].matchAll(/data-key="([^"]+)"/g)].map(m => m[1]);
let n = 0; const t = async (name, f) => { await f(); n++; };

(async () => {
  await t("a class on a date: one day, lessons that don't happen crossed out, a shortened one says when it runs, the paper drawn", async () => {
    const P = boot({ "/api/published/exams": LIST, "/api/day?date=2026-10-05": [200, DAY] }, APP);
    await P.tick();
    P.run('show("classes", "3A")');
    assert.strictEqual(count(P.view(), 'class="row'), 10, "the usual timetable: ten days");
    await P.pick("2026-10-05");
    const v = P.view();
    assert(v.includes('<p class="onday">On Mon 5 Oct (Odd Mon): Sec 3 Exam. Lessons that don&#39;t happen are crossed out.</p>'), v);
    assert.strictEqual(count(v, 'class="row'), 1, "only that day");
    assert.strictEqual(count(v, 'class="cell x"'), 2, "English and the science band are crossed out");
    assert.strictEqual(count(v, 'class="cell exam"'), 1, v);
    assert(v.includes('<b>Sec 3 English Paper 1</b><span class="">3-01</span><span class="m">07:50–08:50</span>'), v);
    P.run('show("classes", "4A")');
    assert(P.view().includes("runs 08:20–08:40 only") && !P.view().includes('class="cell x"'), P.view());
  });

  await t("a teacher and a room on a date; a combined venue shows the paper held in one of its rooms", async () => {
    const P = boot({ "/api/published/exams": LIST, "/api/day?date=2026-10-05": [200, DAY] }, APP);
    await P.tick(); await P.pick("2026-10-05");
    P.run('show("teachers", "Ms Aisha Rahman")');
    assert(P.view().includes('<b>Invigilate · 3-01</b><span class="">Sec 3 English Paper 1</span><span class="m">07:35–09:00</span>'), P.view());
    P.run('show("rooms", "3-01")');
    assert(P.view().includes("<b>Exam</b><span class=\"\">Sec 3 English Paper 1</span>"), P.view());
    P.run('show("rooms", "LT1&2")');
    assert(P.view().includes("<b>Exam</b><span class=\"\">Sec 3 Pure Chemistry Paper 1</span><span class=\"m\">09:45–11:10</span><span class=\"m\">in LT1</span>"), P.view());
    P.run('show("rooms", "LT2")');
    assert(!P.view().includes("Pure Chemistry"), "LT2 is not part of LT1");
  });

  await t("who's free on a date: duties and exam rooms are busy, a lesson that doesn't happen is not", async () => {
    const P = boot({ "/api/published/exams": LIST, "/api/day?date=2026-10-05": [200, DAY] }, APP);
    await P.tick(); await P.pick("2026-10-05");
    P.run("S.ff = { d: 0, from: 1, to: 3 }; show('free', null)");
    let v = P.view();
    assert(v.includes("Duties and exam rooms count as busy; lessons that don't happen do not.") && !v.includes('data-ff="d"'), v);
    let tf = names(v, "Teachers free", "Rooms free");
    assert(!tf.includes("Ms Aisha Rahman") && !tf.includes("Mr Daniel Koh"), "a duty; maths still runs 08:20–08:40: " + tf);
    P.run("S.ff = { d: 0, from: 6, to: 8 }; show('free', null)");
    v = P.view(); tf = names(v, "Teachers free", "Rooms free");
    const rf = names(v, "Rooms free", "Classes with no lesson");
    assert(tf.includes("Ms Grace Yeo") && tf.includes("Ms Aisha Rahman"), "the science band stops: " + tf);
    assert(!rf.includes("LT1") && !rf.includes("LT1&2") && rf.includes("LT2") && rf.includes("3-02"), "LT1 holds a paper: " + rf);
  });

  await t("a holiday says it is not a school day; Usual timetable goes back", async () => {
    const P = boot({ "/api/published/exams": LIST, "/api/day?date=2026-10-12": [200, HOLIDAY] }, APP);
    await P.tick(); P.run('show("classes", "3A")'); await P.pick("2026-10-12");
    assert(P.view().includes("<b>Not a school day.</b><br>Mon 12 Oct is outside the terms or a holiday in the school calendar."), P.view());
    P.run("show('free', null)");
    assert(P.view().includes("Not a school day."), P.view());
    P.run('show("classes", "3A")');
    P.el("onUsual").onclick(); await P.tick();
    assert.strictEqual(count(P.view(), 'class="row'), 10);
  });

  await t("a page left open across a publish says so instead of drawing the new answer on the old timetable", async () => {
    const REPUB = "The timetable was published again: reload the page.";
    const P = boot({ "/api/published/exams": LIST, "/api/day?date=2026-10-05": [200, Object.assign({}, DAY, { published_at: "2026-10-09T10:00:00" })],
      "/api/day?date=2026-10-06": [409, { error: REPUB, published_at: "2026-10-09T10:00:00" }] }, APP);
    await P.tick(); P.run('show("classes", "3A")');
    await P.pick("2026-10-05");
    assert.strictEqual(P.fetched.pop(), "/api/day?date=2026-10-05&published_at=2026-10-01T08%3A00%3A00", "the page sends the timetable it was drawn from");
    assert.strictEqual(P.el("onmsg").textContent, REPUB);
    assert(!P.view().includes('class="cell x"') && !P.view().includes("onday") && count(P.view(), 'class="row') === 10, P.view());
    await P.pick("2026-10-06");
    assert.strictEqual(P.el("onmsg").textContent, REPUB);
    const Q = boot({ "/api/published/exams": LIST, "/api/day?date=2026-10-05": [200, DAY] }, Object.assign({}, APP, { published_at: null }));
    await Q.tick(); await Q.pick("2026-10-05");
    assert.strictEqual(Q.fetched.pop(), "/api/day?date=2026-10-05", "a page with no stamp (a sample) sends none");
  });
})().then(() => console.log(`${n} published page tests passed`), e => { console.error(e); process.exit(1); });

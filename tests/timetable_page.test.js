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
/* an event on Mon 5 Oct, as /api/day gives it to staff: 3A goes out, Ms Grace Yeo goes with a duty, LT2 is a venue it takes */
const TRIP = "Sec 3 Learning Journey", ev = o => Object.assign({ exam: TRIP, kind: "event", p: 0, n: 9, start: "07:40", end: "10:40", label: TRIP }, o);
const EVDAY = {
  date: "2026-10-05", day: "Odd Mon", published_at: STAMP,
  exams: {
    classes: { "3A": [ev({ room: "Off site (museum)", seat_note: "" })] }, stopped: [0], shortened: [],
    teachers: { "Ms Grace Yeo": [ev({ room: "Off site (museum)", role: "At event", duty: "Bus marshal 07:45" })] },
    rooms: { LT2: [ev({})] }, banner: TRIP
  }
};
const QUIET = { date: "2026-10-06", day: "Odd Tue", published_at: STAMP, exams: { classes: {}, stopped: [], shortened: [], teachers: {}, rooms: {}, banner: "" } };
/* /api/published/exams with an event: the staff row has the teacher in charge, who goes and the duties; a student's row has none of them */
const EVROW = { id: "ev1", name: TRIP, kind: "event", start: "2026-10-05", end: "2026-10-05", classes: ["3A", "3B"], where: "Off site (museum)",
  days: [{ date: "2026-10-05", start: "07:40", end: "10:40" }], in_charge: "Ms Grace Yeo", going: ["Ms Grace Yeo", "Mr Ben Ong"],
  duties: [{ duty: "Bus marshal", who: "Ms Grace Yeo", time: "07:45" }] };
const STUROW = { id: "ev2", name: "Sec 3 <i>Trip</i>", kind: "event", start: "2026-10-06", end: "2026-10-07", classes: ["3B"], where: "Science Centre & museum",
  days: [{ date: "2026-10-06", start: "07:40", end: "13:00" }, { date: "2026-10-07", start: "07:40", end: "10:40" }] };

function boot(answers, app, tweak) {
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
  const d = data(app); if (tweak) tweak(d);   /* tweak: the data as the server cuts it for this view */
  vm.runInContext(`const DATA = ${JSON.stringify(d)};`, ctx);
  vm.runInContext(SCRIPT, ctx);
  const tick = () => new Promise(r => setImmediate(r)).then(() => new Promise(r => setImmediate(r))).then(() => new Promise(r => setImmediate(r)));
  const pick = async iso => { reg.get("onDate").listeners.change[0]({ target: { value: iso } }); await tick(); };
  return { run: c => vm.runInContext(c, ctx), view: () => reg.get("view")._html, el: id => reg.get(id), fetched, tick, pick };
}

const APP = { mode: "teacher", tabs: ["classes", "teachers", "rooms", "students", "lessons", "free", "exams"], pdf: true, logout: "/logout", files: [], dates: true, exams: true, published_at: STAMP };
const LIST = [200, { schedules: [], banner: null }];
const count = (s, w) => s.split(w).length - 1;
const keys = h => [...h.matchAll(/data-key="([^"]+)"/g)].map(m => m[1]).join(",");
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
    assert(v.includes("Duties, events and the rooms they take count as busy; lessons that don't happen do not.") && !v.includes('data-ff="d"'), v);
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

  await t("an event on a date: the class's block, the teacher's duty, the venue, and who's free", async () => {
    const P = boot({ "/api/published/exams": LIST, "/api/day?date=2026-10-05": [200, EVDAY], "/api/day?date=2026-10-06": [200, QUIET] }, APP);
    await P.tick(); await P.pick("2026-10-05");
    P.run('show("classes", "3A")');
    let v = P.view();
    assert(v.includes('<b>Sec 3 Learning Journey</b><span class="">Off site (museum)</span><span class="m">07:40–10:40</span>'), v);
    assert(v.includes('<p class="onday">On Mon 5 Oct (Odd Mon): Sec 3 Learning Journey. Lessons that don&#39;t happen are crossed out.</p>') && count(v, 'class="cell x"') === 1, v);
    P.run('show("teachers", "Ms Grace Yeo")');
    v = P.view();
    assert(v.includes('<b>At event · Off site (museum)</b><span class="">Sec 3 Learning Journey</span><span class="m">07:40–10:40</span><span class="m">Bus marshal 07:45</span>'), v);
    P.run('show("rooms", "LT2")');
    assert(P.view().includes('<b>Event</b><span class="">Sec 3 Learning Journey</span><span class="m">07:40–10:40</span>') && !P.view().includes("<b>Exam</b>"), P.view());
    P.run('show("rooms", "LT1&2")');
    assert(P.view().includes('<b>Event</b><span class="">Sec 3 Learning Journey</span><span class="m">07:40–10:40</span><span class="m">in LT2</span>'), "a combined venue holds its room's event: " + P.view());
    P.run("S.ff = { d: 0, from: 0, to: 3 }; show('free', null)");
    v = P.view();
    assert(v.includes("Duties, events and the rooms they take count as busy; lessons that don't happen do not."), v);
    const tf = names(v, "Teachers free", "Rooms free"), rf = names(v, "Rooms free", "Classes with no lesson");
    assert(!tf.includes("Ms Grace Yeo") && tf.includes("Ms Aisha Rahman") && tf.includes("Mr Ben Ong"), "she is at the event; 3A's English does not happen: " + tf);
    assert(!rf.includes("LT2") && !rf.includes("LT1&2") && rf.includes("LT1") && rf.includes("3-01"), "the event takes LT2: " + rf);
    await P.pick("2026-10-06");
    P.run('show("classes", "3A")');
    assert(P.view().includes('<p class="onday">On Tue 6 Oct (Odd Tue): no exams, tests or events. This is the usual Odd Tue timetable.</p>'), P.view());
    P.run("show('free', null)");
    assert(P.view().includes('<p class="onday">On Tue 6 Oct (Odd Tue): no exams, tests or events.</p>'), P.view());
  });

  await t("the Exams and events tab draws an event; a student's row has no one going; My exam timetable lists the event's day", async () => {
    const P = boot({ "/api/published/exams": [200, { schedules: [EVROW, STUROW], banner: "Sec 3 Learning Journey: Mon 5 Oct." }] }, APP);
    await P.tick();
    assert(P.el("tabs").innerHTML.includes('data-tab="exams">Exams and events</button>'), P.el("tabs").innerHTML);
    assert(P.el("exbanner").innerHTML === 'Sec 3 Learning Journey: Mon 5 Oct. <a href="#exams" data-tab="exams">See Exams and events</a>', P.el("exbanner").innerHTML);
    P.run("show('exams', null)");
    const v = P.view(), [one, two] = v.split("<h2>").slice(1);
    assert(v.includes('<h1 style="margin:0 0 4px;font-size:20px">Exams and events</h1>'), v);
    assert(one.startsWith("Sec 3 Learning Journey<small>Event · Mon 5 Oct</small></h2>") && one.includes("Classes 3A, 3B · Off site (museum)"), one);
    assert(one.includes("<th>Date</th><th>Time</th>") && one.includes("<tr><td>Mon 5 Oct</td><td>07:40–10:40</td></tr>"), one);
    assert(one.includes("Teacher in charge: Ms Grace Yeo") && one.includes("Going: Ms Grace Yeo, Mr Ben Ong"), one);
    assert(one.includes("<th>Duty</th><th>Who</th><th>Time</th>") && one.includes("<tr><td>Bus marshal</td><td>Ms Grace Yeo</td><td>07:45</td></tr>"), one);
    assert(two.startsWith("Sec 3 &lt;i&gt;Trip&lt;/i&gt;<small>Event · Tue 6 Oct–Wed 7 Oct</small></h2>") && two.includes("Classes 3B · Science Centre &amp; museum"), "names are escaped: " + two);
    assert(two.includes("<tr><td>Tue 6 Oct</td><td>07:40–13:00</td></tr><tr><td>Wed 7 Oct</td><td>07:40–10:40</td></tr>"), two);
    assert(!two.includes("Teacher in charge") && !two.includes("Going") && !two.includes("<th>Duty</th>") && !v.includes("<i>"), "a student's row: no one going: " + two);
    const Q = boot({ "/api/published/exams": [200, { schedules: [], banner: null }] }, APP);
    await Q.tick(); Q.run("show('exams', null)");
    assert(Q.view().includes('<div class="empty">No exams, tests or events on the main site now.</div>'), Q.view());
    const ME = { mode: "personal", exams: true, pdf: true, logout: "/logout", files: [] };
    const trip = { id: "ev1", name: TRIP, kind: "event", where: "Off site (museum)", papers: [], days: [{ date: "2026-10-05", start: "07:40", end: "10:40", note: "then lessons from 10:40" }] };
    const R = boot({ "/api/me/exams": [200, { schedules: [trip, { id: "x9", name: "Sec 4 Exam", kind: "exam", papers: [] }] }] }, ME);
    await R.tick();
    const m = R.view();
    assert(R.fetched.includes("/api/me/exams") && !R.fetched.includes("/api/published/exams"), R.fetched.join(", "));
    assert(m.startsWith('<div class="card myexams" id="myexams"><h2>My exam timetable</h2><h3>Sec 3 Learning Journey</h3>'), m);
    assert(m.includes("<tr><td>Mon 5 Oct</td><td>Sec 3 Learning Journey · Off site (museum) · 07:40–10:40</td><td>then lessons from 10:40</td></tr>"), m);
    assert(!m.includes("Sec 4 Exam"), "a schedule with no papers and no days does not show");
    const N = boot({ "/api/me/exams": [200, { schedules: [Object.assign({}, trip, { days: [] })] }] }, ME);
    await N.tick();
    assert(!N.view().includes("myexams"), "an event with no day for this class shows nothing");
  });

  await t("a teacher's own page (staff mode): My timetable opens first and lists only them; the classes are all there", async () => {
    const STAFF = Object.assign({}, APP, { mode: "staff", tabs: ["classes", "teachers", "exams"], me: "Mr Ben Ong", files: [["Class PDFs", "/files/book/classes"]] });
    const cut = d => { d.teachers = d.teachers.map(r => [r[0], r[1], "", ""]); d.rooms = []; d.students = []; };   /* html_data's staff view */
    const P = boot({ "/api/published/exams": LIST }, STAFF, cut);
    await P.tick();
    const tabs = P.el("tabs").innerHTML;
    assert(tabs.includes('data-tab="teachers">My timetable</button>') && !tabs.includes(">Teachers<"), tabs);
    assert(tabs.indexOf('data-tab="teachers"') < tabs.indexOf('data-tab="classes"'), "My timetable comes first: " + tabs);
    assert.strictEqual(P.run("location.hash"), "#teachers/Mr%20Ben%20Ong");
    assert(P.view().includes("Mr Ben Ong") && count(P.view(), 'class="row') === 10, P.view());
    assert.strictEqual(keys(P.el("list").innerHTML), "Mr Ben Ong");
    assert(!P.el("list").innerHTML.includes('class="grp"'), "no empty department heading: " + P.el("list").innerHTML);
    assert(!P.view().includes("allowance") && P.view().includes("periods a cycle"), "no empty allowance stat");
    const box = id => { P.run(`lessonDialog(${id})`); return P.el("dlgB").innerHTML; };
    let b = box(3);
    assert(b.includes('<a data-go="teachers" data-key="Mr Ben Ong">Mr Ben Ong</a>') && b.includes('<a data-go="classes" data-key="4A">4A</a>') && !b.includes('data-go="rooms"') && b.includes("LT2"), b);
    b = box(2);
    assert(!b.includes('data-go="teachers"') && b.includes("Ms Grace Yeo") && !b.includes('data-go="rooms"') && !b.includes('data-go="lessons"') && b.includes("3-02"), "another teacher, the room and all lessons are plain text: " + b);
    P.run('show("teachers", "Ms Grace Yeo")');
    assert.strictEqual(P.run("S.key"), "Mr Ben Ong", "another teacher's timetable is not shown");
    P.run('show("classes", null)');
    assert.strictEqual(keys(P.el("list").innerHTML), "3A,3B,4A");
    assert.strictEqual(P.run('INDEX_OK.filter(e => e.t === "teachers").map(e => e.k).join(",")'), "Mr Ben Ong", "the search finds only them");
    const F = boot({ "/api/published/exams": LIST }, APP);
    F.run('show("teachers", "Mr Ben Ong")'); assert(F.view().includes("allowance"), "a teacher's page keeps the allowance stat");
    F.run("lessonDialog(2)"); b = F.el("dlgB").innerHTML;
    assert(b.includes('data-go="teachers" data-key="Ms Grace Yeo"') && b.includes('data-go="rooms" data-key="3-02"') && b.includes('data-go="lessons"'), "the full page keeps every link: " + b);
    const ST = boot({ "/api/published/exams": LIST }, Object.assign({}, APP, { mode: "student", tabs: ["classes", "students", "exams"] }), cut);
    ST.run("lessonDialog(2)"); b = ST.el("dlgB").innerHTML;
    assert(!b.includes('data-go="teachers"') && !b.includes('data-go="rooms"') && !b.includes('data-go="lessons"') && b.includes('data-go="classes" data-key="3A"'), "a student's page: only the classes link: " + b);
    const X = boot({ "/api/published/exams": LIST }, Object.assign({}, STAFF, { tabs: ["classes", "exams"], me: null }), cut);
    await X.tick();
    assert(!X.el("tabs").innerHTML.includes('data-tab="teachers"') && X.run("S.tab") === "classes", X.el("tabs").innerHTML);
  });
  await t("a teacher's Exams tab shows their own duties above the exams; none, no section", async () => {
    const STAFF = Object.assign({}, APP, { mode: "staff", tabs: ["classes", "teachers", "exams"], me: "Mr Ben Ong" });
    const cut = d => { d.teachers = d.teachers.map(r => [r[0], r[1], "", ""]); d.rooms = []; d.students = []; };
    const EL = [200, { schedules: [STUROW], banner: null }];
    const DU = { schedules: [{ id: "a1", name: "Sec 3 Exam", kind: "exam", duties: [
      { date: "2026-10-05", start: "09:45", end: "11:10", room: "3-01", label: "Sec 3 Pure Chemistry Paper 1", role: "Chief invigilator" },
      { date: "2026-10-05", start: "07:35", end: "09:00", room: "3-02", label: "Sec 3 English Paper 1 <b>", role: "Invigilate" }] }], lessons: [] };
    const P = boot({ "/api/published/exams": EL, "/api/exams/my-duties": [200, DU] }, STAFF, cut);
    await P.tick(); P.run("show('exams', null)");
    const v = P.view(), i = v.indexOf("Your duties");
    assert(i > 0 && i < v.indexOf("Science Centre"), "the duties come above the exam list: " + v);
    assert(v.includes("<td>07:35–09:00</td><td>3-02</td><td>Sec 3 English Paper 1 &lt;b&gt;</td><td>Invigilate</td>") && v.includes("<td>3-01</td><td>Sec 3 Pure Chemistry Paper 1</td><td>Chief invigilator</td>"), v);
    assert(v.indexOf("07:35") < v.indexOf("09:45"), "in time order");
    const N = boot({ "/api/published/exams": EL, "/api/exams/my-duties": [200, { schedules: [], lessons: [] }] }, STAFF, cut);
    await N.tick(); N.run("show('exams', null)");
    assert(!N.view().includes("Your duties") && N.view().includes("Science Centre"), N.view());
    const E = boot({ "/api/published/exams": EL, "/api/exams/my-duties": [403, { error: "x" }] }, STAFF, cut);
    await E.tick(); E.run("show('exams', null)");
    assert(!E.view().includes("Your duties"), "no section on an error");
    const F = boot({ "/api/published/exams": LIST }, APP);
    await F.tick(); assert(!F.fetched.includes("/api/exams/my-duties"), "only staff mode asks");
  });
  await t("a teacher-only period: a box on the teacher's own timetable, its line in the legend, nothing in the counts, none on a class, and the teacher busy in Who's free", async () => {
    const ROW = ["Mr Ben Ong", 1, 22, 4, "Zone computing class", "West Zone centre", "3.00", "5.30", false, true];   /* Odd Tue, periods 22 to 25, runs on to 5.30 */
    const LINE = "Zone computing class · Tue · 3.00 to 5.30 · West Zone centre";
    const withStaff = d => { d.staff = [ROW, ["Mr Ben Ong", 0, null, 0, "Briefing", "", "7.00", "7.30", true, false]]; d.staff_lines = { "Mr Ben Ong": [LINE, "Briefing · Mon · 7.00 to 7.30"] }; };
    const P = boot({ "/api/published/exams": LIST }, APP, withStaff), Q = boot({ "/api/published/exams": LIST }, APP);
    await P.tick(); await Q.tick();
    const tv = P.run('teacherView("Mr Ben Ong")'), tq = Q.run('teacherView("Mr Ben Ong")');
    assert.strictEqual(JSON.stringify(tv.stats), JSON.stringify(tq.stats)); assert.strictEqual(tv.rows.length, tq.rows.length);
    const boxes = tv.cells.filter(c => c.staff);
    assert.strictEqual(boxes.length, 1, "the period with no periods has no box"); assert.strictEqual(boxes[0].title, "Zone computing class");
    assert.strictEqual(JSON.stringify(boxes[0].lines), JSON.stringify(["3.00 (to 5.30)", "West Zone centre"])); assert.strictEqual(boxes[0].after, true);
    assert.strictEqual(JSON.stringify(tv.legend.filter(e => e.staff).map(e => e.text)), JSON.stringify([LINE, "Briefing · Mon · 7.00 to 7.30"]));
    assert.strictEqual(tv.cells.length, tq.cells.length + 1);
    P.run('show("teachers", "Mr Ben Ong")'); const h = P.view();
    const box = h.match(/<div class="cell staff cut-r"[^>]*>.*?<\/div>/)[0];
    assert(!box.includes("data-id") && box.includes("Zone computing class") && box.includes("to 5.30") && box.includes("West Zone centre"), box);
    assert(h.includes('<i class="sw staff"></i><span>Zone computing class · Tue · 3.00 to 5.30 · West Zone centre</span>'), "the legend line");
    assert(!Q.view().includes("staff"), "no staff data: as it was");
    const cv = P.run('classView("4A")'); assert(!cv.cells.some(c => c.staff) && !cv.legend.some(e => e.staff));
    P.run('S.ff = { d: 1, from: 22, to: 23 }; show("free", null)'); assert(!P.view().includes('data-key="Mr Ben Ong"'), "busy in the period: " + P.view());
    P.run('S.ff = { d: 1, from: 1, to: 3 }; show("free", null)'); assert(P.view().includes('data-key="Mr Ben Ong"'), "free at the start of the day");
    P.run('S.ff = { d: 0, from: 22, to: 23 }; show("free", null)'); assert(P.view().includes('data-key="Mr Ben Ong"'), "another day");
    P.run('S.ff = { d: 1, from: 18, to: 21 }; show("free", null)'); assert(P.view().includes('data-key="Mr Ben Ong"'), "the period has not begun");
  });

  await t("in staff mode a teacher's own periods come by a request of their own; a failed answer changes nothing", async () => {
    const STAFF = Object.assign({}, APP, { mode: "staff", tabs: ["classes", "teachers", "exams"], me: "Mr Ben Ong" });
    const cut = d => { d.teachers = d.teachers.map(r => [r[0], r[1], "", ""]); d.rooms = []; d.students = []; };
    const ROW = ["Mr Ben Ong", 1, 22, 4, "Zone computing class", "West Zone centre", "3.00", "5.30", false, true];
    const EL = [200, { schedules: [], banner: null }];
    const P = boot({ "/api/published/exams": EL, "/api/exams/my-duties": [200, { schedules: [], lessons: [] }], "/api/timetable/my-periods": [200, { staff: [ROW], lines: ["Zone computing class · Tue · 3.00 to 5.30 · West Zone centre"] }] }, STAFF, cut);
    await P.tick(); P.run('show("teachers", "Mr Ben Ong")'); await P.tick();
    const v = P.view(); assert(P.fetched.includes("/api/timetable/my-periods"));
    assert(v.includes('class="cell staff cut-r"') && v.includes("Zone computing class") && v.includes("Zone computing class · Tue · 3.00 to 5.30"), v);
    const F = boot({ "/api/published/exams": EL, "/api/timetable/my-periods": [403, { error: "x" }] }, STAFF, cut);
    await F.tick(); F.run('show("teachers", "Mr Ben Ong")'); assert(!F.view().includes("staff") && F.view().includes('class="cell'), "a refusal leaves the page as it was");
    const G = boot({ "/api/published/exams": EL }, STAFF, cut); await G.tick(); G.run('show("teachers", "Mr Ben Ong")'); assert(!G.view().includes("cell staff"), "no answer at all");
    const O = boot({ "/api/published/exams": LIST }, APP); await O.tick(); assert(!O.fetched.includes("/api/timetable/my-periods"), "only staff mode asks");
  });
})().then(() => console.log(`${n} published page tests passed`), e => { console.error(e); process.exit(1); });

"use strict";
/* Exams (/exams and /exams/<id>) for the exams committee and the timetable committee.
   /exams: the list of schedules and the small form that makes a new one.
   /exams/<id>: one schedule with tabs, one render function per tab (TABS). Every edit changes S.sched at once and is
   saved with PUT after 800 ms of no typing; the view (checks, counts) is fetched again after each save. */
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const NO_CALENDAR = "Set the school calendar in Relief settings first: exams need it to know which timetable day a date is.";
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const KINDS = { exam: "Exam", test: "Common test" };
  const S = {
    id: null, list: null, sched: null, view: null, levels: [], classes: [],
    tab: "when", timer: null, chain: Promise.resolve(), dirty: false, rev: 0, saving: false, msg: "", bad: false,
    nf: null, mk: null, accCls: "", note: ""
  };
  /* the tabs: tabs 4 to 7 are added to this list; each draw() gives the html of its tab body */
  const TABS = [
    { key: "when", name: "What and when", draw: () => tabWhen() },
    { key: "papers", name: "Papers", draw: () => tabPapers() },
    { key: "access", name: "Access arrangements", draw: () => tabAccess() }
  ];

  /* ---------------------------------------------------------------- small helpers */
  const at = (k, a, b) => `data-k="${k}"${a !== undefined ? ` data-a="${esc(a)}"` : ""}${b !== undefined ? ` data-b="${esc(b)}"` : ""} data-f="${esc([k, a, b].filter(x => x !== undefined).join("|"))}"`;
  const opt = (v, cur, label) => `<option value="${esc(v)}"${String(v) === String(cur) ? " selected" : ""}>${esc(label ?? v)}</option>`;
  const uniq = a => a.filter((x, i) => a.indexOf(x) === i);
  const newId = () => Array.from(crypto.getRandomValues(new Uint8Array(4)), b => b.toString(16).padStart(2, "0")).join("");

  function fmtDate(iso, year) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || ""); if (!m) return iso || "";
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return `${WEEK[d.getUTCDay()]} ${+m[3]} ${MONTHS[+m[2] - 1]}${year ? " " + m[1] : ""}`;
  }

  function fmtLen(n) {
    n = Number(n) || 0;
    const h = Math.floor(n / 60), m = n % 60;
    return h ? (m ? `${h} h ${m}` : `${h} h`) : `${m} min`;
  }

  /* ---------------------------------------------------------------- the server */
  async function homeLink() {
    let to = "/relief";
    try { const r = await fetch("/api/exams/me", { cache: "no-store" }), j = await r.json(); if (j && j.name === "Timetable committee") to = "/"; } catch (e) { /* keep the staff link */ }
    return to;
  }

  async function forbidden(text) {
    clearTimeout(S.timer); S.dirty = false;
    $("#main").innerHTML = `<div class="card"><h1>Exams</h1><p class="msg bad">${esc(text || "You cannot open exams.")}</p><p><a href="${await homeLink()}">Back</a></p></div>`;
  }

  /* -> {ok, status, j}; 401 goes to the sign-in page and 403 shows the server's sentence in place of the page */
  async function api(method, url, body, form) {
    let r, j = {};
    try {
      const o = { method, cache: "no-store" };
      if (form) o.body = form;
      else if (body !== undefined) { o.headers = { "Content-Type": "application/json" }; o.body = JSON.stringify(body); }
      r = await fetch(url, o);
      j = await r.json().catch(() => ({}));
    } catch (err) {
      return { ok: false, status: 0, j: { error: "Could not reach the server. Check the connection and try again." } };
    }
    if (r.status === 401) location.href = "/login";
    if (r.status === 403) forbidden(j.error);
    return { ok: r.ok, status: r.status, j };
  }

  function fail(text, back) {
    clearTimeout(S.timer); S.dirty = false;
    $("#main").innerHTML = `<div class="card"><h1>Exams</h1><p class="msg bad">${esc(text)}</p><p><a href="${back || "/exams"}">${back ? "Back" : "Back to Exams"}</a></p></div>`;
  }

  function links() {
    $("#links").innerHTML = `<a class="ghost filebtn" href="/exams">Exams</a><a class="ghost filebtn" href="/exams/settings">Exam settings</a><a class="ghost filebtn" href="/logout">Sign out</a>`;
  }

  /* ================================================================ the list */
  function blankForm() { return { kind: "exam", name: "", levels: [], classes: [], start: "", end: "", open: false }; }

  function drawList() {
    const L = S.list, nf = S.nf;
    const rows = L.schedules.map(s => `<div class="card scard"><div><span class="chip ${s.kind === "test" ? "test-kind" : "ex-kind"}">${esc(KINDS[s.kind] || s.kind)}</span>
      <a class="name" href="/exams/${esc(s.id)}">${esc(s.name)}</a><br>
      <span class="muted small">${esc(fmtDate(s.start))} to ${esc(fmtDate(s.end))}${(s.levels || []).length ? " · " + esc(s.levels.join(", ")) : ""} · ${s.papers} ${s.papers === 1 ? "paper" : "papers"}</span></div>
      <div><span class="chip draft">Draft</span></div></div>`).join("");
    const cal = L.calendar_ok ? "" : `<p class="notice">${esc(NO_CALENDAR)} <a href="/relief/settings">Relief settings</a></p>`;
    $("#main").innerHTML = `<div class="head"><h1>Exams and tests</h1>
      <div class="row"><button type="button" class="primary" data-act="newOpen" ${L.calendar_ok && !nf.open ? "" : "disabled"}>+ New exam or test</button></div></div>
      ${cal}${nf.open ? newForm() : ""}
      ${rows || `<div class="card"><p class="muted">No exams or tests yet.</p></div>`}`;
  }

  function newForm() {
    const nf = S.nf, L = S.list;
    const lv = L.levels.map(l => `<label class="tick"><input type="checkbox" data-nf="level" data-v="${esc(l)}" ${nf.levels.includes(l) ? "checked" : ""}> ${esc(l)}</label>`).join("");
    const cl = L.classes.map(([c, l]) => `<label class="tick" title="${esc(l)}"><input type="checkbox" data-nf="class" data-v="${esc(c)}" ${nf.classes.includes(c) ? "checked" : ""}> ${esc(c)}</label>`).join("");
    return `<div class="card form"><h2>New exam or test</h2>
      <div class="line"><b>What is it</b><select data-nf="kind" aria-label="Exam or common test">${opt("exam", nf.kind, "Exam")}${opt("test", nf.kind, "Common test")}</select></div>
      <div class="line"><b>Name</b><input type="text" data-nf="name" value="${esc(nf.name)}" maxlength="120" placeholder="e.g. Sec 3 End-of-Year Exam" aria-label="Name"></div>
      <div class="line"><b>Who</b><span class="chiprow">${lv || `<span class="muted small">The published timetable has no levels.</span>`}</span></div>
      <div class="line"><b></b><details class="pickc" ${nf.classes.length ? "open" : ""}><summary>Or pick classes</summary><div class="classes">${cl}</div></details></div>
      <div class="line"><b>Dates</b><input type="date" data-nf="start" value="${esc(nf.start)}" aria-label="First day"> to <input type="date" data-nf="end" value="${esc(nf.end)}" aria-label="Last day"></div>
      <div class="row"><button type="button" class="primary" data-act="newSave">Make it</button><button type="button" data-act="newCancel">Cancel</button><span class="msg bad" id="nfMsg" role="status"></span></div></div>`;
  }

  async function newSave() {
    const nf = S.nf, msg = $("#nfMsg"), btn = $('[data-act="newSave"]');
    const say = t => { if (msg) msg.textContent = t; };
    say(""); if (btn) btn.disabled = true;
    const ofClasses = uniq(S.list.classes.filter(([c]) => nf.classes.includes(c)).map(([, l]) => l));
    const r = await api("POST", "/api/exams", { kind: nf.kind, name: nf.name, levels: nf.levels.length ? nf.levels : ofClasses, start: nf.start, end: nf.end });
    if (!r.ok) { if (btn) btn.disabled = false; if (r.status !== 403) say(r.j.error || "That did not work. Try again."); return; }
    if (nf.classes.length) {   /* the server makes a schedule from levels; the classes go in with one more save */
      const s = r.j;
      const r2 = await api("PUT", "/api/exams/" + s.id, Object.assign({}, s, { levels: nf.levels, classes: nf.classes }));
      if (!r2.ok && r2.status === 403) return;
    }
    location.href = "/exams/" + r.j.id;
  }

  async function startList() {
    links();
    const r = await api("GET", "/api/exams");
    if (r.status === 401 || r.status === 403) return;
    if (!r.ok) { fail(r.j.error || "Something went wrong."); return; }
    S.list = r.j; S.nf = blankForm();
    drawList();
  }

  /* ================================================================ one schedule */
  const tab = () => TABS.find(t => t.key === S.tab) || TABS[0];

  function saveInner() {
    return `${S.dirty ? `<span class="dirty">Changes not saved.</span>` : ""}${S.msg ? `<span class="msg ${S.bad ? "bad" : "ok"}" role="status">${esc(S.msg)}</span>` : ""}`;
  }
  function paintSave() { const el = $("#saveline"); if (el) el.innerHTML = saveInner(); }

  function render() {
    const s = S.sched;
    $("#main").innerHTML = `<div class="head"><div><h1>${esc(s.name)}</h1>
      <div class="muted small"><a href="/exams">All exams</a> · ${esc(KINDS[s.kind] || s.kind)} · ${esc(fmtDate(s.start, true))} to ${esc(fmtDate(s.end, true))}</div></div>
      <div class="savebar" id="saveline">${saveInner()}</div></div>
      <div class="xtabs" role="tablist">${TABS.map(t => `<button type="button" role="tab" class="${t.key === S.tab ? "on" : ""}" aria-selected="${t.key === S.tab}" data-act="tab" data-a="${t.key}">${esc(t.name)}</button>`).join("")}</div>
      <div id="tabbody">${tab().draw()}</div>`;
  }

  /* draw the tab body again, keeping the cursor where it was */
  function paint() {
    const body = $("#tabbody"); if (!body) return;
    const a = document.activeElement, key = a && a.dataset ? a.dataset.f : null;
    let s0 = null, s1 = null;
    try { s0 = a.selectionStart; s1 = a.selectionEnd; } catch (e) { /* not a text box */ }
    body.innerHTML = tab().draw();
    if (key) {
      const el = Array.from(document.querySelectorAll("[data-f]")).find(x => x.dataset.f === key);
      if (el) { el.focus(); try { if (s0 != null) el.setSelectionRange(s0, s1); } catch (e) { /* not a text box */ } }
    }
  }

  /* change the schedule, then save it after a pause */
  function edit(fn, redraw) {
    fn();
    S.dirty = true; S.rev++; S.msg = ""; S.bad = false; paintSave();
    clearTimeout(S.timer); S.timer = setTimeout(flush, 800);
    if (redraw) paint();
  }

  function flush() {
    clearTimeout(S.timer); S.timer = null;
    S.chain = S.chain.then(saveNow, saveNow);
    return S.chain;
  }

  async function saveNow() {
    if (!S.dirty) return true;
    const rev = S.rev;
    S.saving = true;
    const r = await api("PUT", "/api/exams/" + S.id, S.sched);
    S.saving = false;
    if (r.status === 401 || r.status === 403) return false;
    if (!r.ok) { S.bad = true; S.msg = r.j.error || "Nothing was saved. Try again."; paintSave(); return false; }
    S.sched.saved_at = r.j.saved_at; S.sched.saved_by = r.j.saved_by;
    if (S.rev === rev) { S.dirty = false; S.bad = false; S.msg = "Saved"; }
    paintSave();
    await refreshView();
    return true;
  }

  async function refreshView() {
    const r = await api("GET", `/api/exams/${S.id}/view`);
    if (!r.ok) return;
    S.view = r.j;
    if (S.sched) paint();
  }

  /* an action the server does to the schedule (fill, upload): our own edits go first, the answer replaces the schedule */
  async function serverAction(method, url, body, form, done) {
    await flush();
    if (S.dirty) return;   /* the save was refused: its sentence is on the screen */
    S.msg = ""; S.bad = false;
    const r = await api(method, url, body, form);
    if (r.status === 401 || r.status === 403) return;
    if (!r.ok) { S.bad = true; S.msg = r.j.error || "That did not work. Try again."; paintSave(); return; }
    S.sched = r.j;
    if (done) done(r.j);
    paintSave();
    await refreshView();
    render();
  }

  /* ---------------------------------------------------------------- tab 1: what and when */
  const periods = () => (S.view && S.view.periods) || [];

  function dayState(date) {
    const d = ((S.view && S.view.summary.days) || []).find(x => x.date === date) || {};
    const e = (S.sched.days || {})[date] || {};
    const p = periods();
    return {
      levels: e.levels != null ? e.levels.slice() : (d.levels || S.sched.levels).slice(),
      whole: e.whole !== undefined ? !!e.whole : true,
      from: e.from || (p.length ? p[0][0] : null), to: e.to || (p.length ? p[Math.min(3, p.length - 1)][1] : null)
    };
  }

  function setDay(date, patch) {
    const cur = dayState(date), out = Object.assign({}, cur, patch);
    if (out.whole) { out.from = null; out.to = null; }
    S.sched.days = Object.assign({}, S.sched.days, { [date]: { levels: out.levels, whole: out.whole, from: out.from, to: out.to } });
  }

  function timeSelect(date, which, cur) {
    const p = periods(), i = which === "from" ? 0 : 1, vals = uniq(p.map(x => x[i]).concat(cur ? [cur] : []));
    return `<select ${at(which === "from" ? "dayFrom" : "dayTo", date)} aria-label="${which === "from" ? "From" : "To"} on ${esc(fmtDate(date))}">${vals.map(v => opt(v, cur)).join("")}</select>`;
  }

  function dayRow(d) {
    if (d.day == null) return `<tr><td>${esc(fmtDate(d.date))}</td><td class="muted" colspan="3">Not a school day</td></tr>`;
    const st = dayState(d.date), s = S.sched;
    const lv = s.levels.length ? s.levels.map(l => `<label class="tick"><input type="checkbox" ${at("dayLevel", d.date, l)} ${st.levels.includes(l) ? "checked" : ""}> ${esc(l)}</label>`).join(" ")
      : `<span class="muted small">The chosen classes</span>`;
    const part = st.whole ? "" : ` ${timeSelect(d.date, "from", st.from)} to ${timeSelect(d.date, "to", st.to)}`;
    return `<tr><td>${esc(fmtDate(d.date))}</td><td>${esc(d.day)}</td><td class="lv">${lv}</td>
      <td><span class="seg"><button type="button" class="${st.whole ? "on" : ""}" data-act="dayWhole" ${at("dayWholeBtn", d.date, "1")}>Whole day</button><button type="button" class="${st.whole ? "" : "on"}" data-act="dayWhole" ${at("dayWholeBtn", d.date, "0")}>Part</button></span>${part}</td></tr>`;
  }

  function tabWhen() {
    const s = S.sched, t = s.times || {};
    const lv = S.levels.map(l => `<label class="tick"><input type="checkbox" ${at("level", l)} ${s.levels.includes(l) ? "checked" : ""}> ${esc(l)}</label>`).join("");
    const cl = S.classes.map(([c, l]) => `<label class="tick" title="${esc(l)}"><input type="checkbox" ${at("class", c)} ${s.classes.includes(c) ? "checked" : ""}> ${esc(c)}</label>`).join("");
    const days = (S.view && S.view.summary.days) || [];
    const rows = S.view ? days.map(dayRow).join("") : `<tr><td colspan="4" class="muted">Loading…</td></tr>`;
    const sup = s.kind === "test" ? `<div class="line"><b>Supervised</b><select ${at("sup")} aria-label="Who supervises the test">${opt("lesson", s.supervision, "Supervised by the teacher whose lesson it would have been")}${opt("invigilators", s.supervision, "Supervised by invigilators")}</select></div>` : "";
    return `<div class="card form"><div class="line"><b>What is it</b><span>${esc(KINDS[s.kind] || s.kind)}</span></div>
      <div class="line"><b>Name</b><input type="text" ${at("name")} value="${esc(s.name)}" maxlength="120" aria-label="Name"></div>
      <div class="line"><b>Who</b><span class="chiprow">${lv}</span></div>
      <div class="line"><b></b><details class="pickc" ${s.classes.length ? "open" : ""}><summary>Or pick classes</summary><div class="classes">${cl}</div></details></div>
      <div class="line"><b>Dates</b><input type="date" ${at("start")} value="${esc(s.start)}" aria-label="First day"> to <input type="date" ${at("end")} value="${esc(s.end)}" aria-label="Last day"></div>
      ${sup}</div>
      <div class="card"><h2>Each day</h2><div class="tablewrap"><table class="daytable"><thead><tr><th>Date</th><th>Timetable day</th><th>Levels sitting</th><th>How much of the day</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="muted small">A level that is not sitting on a day keeps its full timetable that day. On a part day, lessons stop from the first time to the second and run as usual outside it.</p></div>
      <div class="card times"><h2>Exam-day times</h2>
      <div class="line">Students report at <input type="time" ${at("time", "report")} value="${esc(t.report || "")}" aria-label="Students report at"></div>
      <div class="line">At least <input type="number" min="0" max="240" step="1" ${at("time", "min_break")} value="${esc(t.min_break ?? "")}" aria-label="Minutes between papers"> minutes between two papers for one student</div>
      <div class="line">At most <input type="number" min="1" max="10" step="1" ${at("time", "max_papers")} value="${esc(t.max_papers ?? "")}" aria-label="Most papers a day"> papers a day for one student</div></div>`;
  }

  function setLevel(l, on) {
    const s = S.sched;
    s.levels = on ? uniq(s.levels.concat([l])) : s.levels.filter(x => x !== l);
    for (const e of Object.values(s.days || {})) {   /* days that name their levels follow the schedule's levels */
      if (!Array.isArray(e.levels)) continue;
      e.levels = on ? uniq(e.levels.concat([l])) : e.levels.filter(x => x !== l);
    }
  }

  function onWhenField(el, k, a, b) {
    const s = S.sched, v = el.value;
    if (k === "name") return edit(() => { s.name = v; });
    if (k === "start") return edit(() => { s.start = v; }, false);
    if (k === "end") return edit(() => { s.end = v; }, false);
    if (k === "sup") return edit(() => { s.supervision = v; });
    if (k === "level") return edit(() => setLevel(a, el.checked), true);
    if (k === "class") return edit(() => { s.classes = el.checked ? uniq(s.classes.concat([a])) : s.classes.filter(x => x !== a); }, true);
    if (k === "dayLevel") return edit(() => { const L = dayState(a).levels; setDay(a, { levels: el.checked ? uniq(L.concat([b])) : L.filter(x => x !== b) }); });
    if (k === "dayFrom") return edit(() => setDay(a, { from: v }), true);
    if (k === "dayTo") return edit(() => setDay(a, { to: v }), true);
    if (k === "time") {
      if (a === "report") return edit(() => { s.times = Object.assign({}, s.times, { report: v }); });
      const n = Number(v);
      if (v === "" || !Number.isInteger(n) || n < (a === "max_papers" ? 1 : 0)) return;   /* wait for a whole number */
      return edit(() => { s.times = Object.assign({}, s.times, { [a]: n }); });
    }
  }

  /* ---------------------------------------------------------------- tab 2: papers */
  const paperLevels = () => uniq(S.sched.levels.concat(S.classes.filter(([c]) => S.sched.classes.includes(c)).map(([, l]) => l)));
  const schoolDays = () => ((S.view && S.view.summary.days) || []).filter(d => d.day != null).map(d => d.date);

  function paperRow(p, i) {
    const n = S.view && S.view.counts ? S.view.counts[p.id] : null, count = n == null ? "" : ` <span class="muted">(${n})</span>`;
    const lvs = uniq(paperLevels().concat(p.level ? [p.level] : []));
    const days = uniq(schoolDays().concat(p.date ? [p.date] : []));
    const who = p.who === "students" ? `Picked students${count}`
      : `<select ${at("pwho", i)} aria-label="Who sits paper ${i + 1}">${opt("level", p.who, "All of " + (p.level || "the level"))}${opt("groups", p.who, "The subject's groups")}</select>${count}`;
    return `<tr><td><select ${at("plevel", i)} aria-label="Level of paper ${i + 1}">${lvs.map(l => opt(l, p.level)).join("")}</select></td>
      <td><input type="text" ${at("psubject", i)} value="${esc(p.subject)}" aria-label="Subject of paper ${i + 1}"></td>
      <td><input type="text" ${at("ppaper", i)} value="${esc(p.paper)}" aria-label="Paper name ${i + 1}"></td>
      <td><input type="number" min="1" step="5" ${at("pmin", i)} value="${esc(p.minutes)}" title="${esc(fmtLen(p.minutes))}" aria-label="Minutes of paper ${i + 1}"></td>
      <td class="who">${who}</td>
      <td><input type="text" ${at("ptog", i)} value="${esc(p.together || "")}" maxlength="80" aria-label="Sits with, paper ${i + 1}"></td>
      <td><select ${at("pdate", i)} aria-label="Date of paper ${i + 1}">${opt("", p.date || "", "date")}${days.map(d => opt(d, p.date, fmtDate(d))).join("")}</select></td>
      <td><input type="time" ${at("pstart", i)} value="${esc(p.start || "")}" aria-label="Start of paper ${i + 1}"></td>
      <td class="x"><button type="button" class="small danger" data-act="delPaper" data-a="${i}" title="Take this paper off" aria-label="Take paper ${i + 1} off">✕</button></td></tr>`;
  }

  function checksPanel() {
    const c = S.view && S.view.summary.checks;
    if (!c) return "";
    const lines = c.errors.map(t => `<div><span class="flag">●</span> ${esc(t)}</div>`).concat(c.warnings.map(t => `<div><span class="amber">●</span> ${esc(t)} <span class="muted">A warning, not a stop.</span></div>`));
    if (!lines.length) lines.push(S.sched.papers.length ? `<div><span class="okc">✓</span> No problems with the paper times.</div>` : `<div class="muted">Add papers to see the checks.</div>`);
    return `<div class="card checks"><h2>Checks on your times</h2>${lines.join("")}</div>`;
  }

  function makeupForm() {
    const m = S.mk, v = S.view, stu = v ? v.students : {};
    const classes = uniq(Object.values(stu).map(x => x[1])).sort();
    const cur = m.cls || classes[0] || "";
    const list = Object.entries(stu).filter(([, x]) => x[1] === cur).map(([id, x]) => `<label class="tick"><input type="checkbox" data-mk="pick" data-v="${esc(id)}" ${m.picked.includes(id) ? "checked" : ""}> ${esc(x[0])}</label>`).join("");
    return `<div class="mk"><h3 style="margin-top:0">A make-up paper</h3>
      <div class="line"><select data-mk="level" aria-label="Level">${paperLevels().map(l => opt(l, m.level)).join("")}</select>
        <input type="text" data-mk="subject" value="${esc(m.subject)}" placeholder="Subject" aria-label="Subject">
        <input type="text" data-mk="paper" value="${esc(m.paper)}" placeholder="Paper" aria-label="Paper">
        <input type="number" min="1" step="5" data-mk="minutes" value="${esc(m.minutes)}" aria-label="Minutes"> minutes</div>
      <div class="line">Pick students from <select data-mk="cls" aria-label="Class">${classes.map(c => opt(c, cur)).join("")}</select> <span class="muted small">${m.picked.length} picked</span></div>
      <div class="stu">${list || `<span class="muted small">No students in this class.</span>`}</div>
      <div class="row"><button type="button" class="primary small" data-act="mkAdd">Add the paper</button><button type="button" class="small" data-act="mkCancel">Cancel</button><span class="msg bad" id="mkMsg" role="status"></span></div></div>`;
  }

  function tabPapers() {
    const s = S.sched, ps = s.papers, withTime = ps.filter(p => p.date && p.start).length, need = ps.length - withTime;
    const of = s.levels.length ? s.levels.join(", ") : "the chosen classes";
    const rows = ps.map(paperRow).join("");
    return `<div class="row" style="justify-content:space-between;margin-bottom:10px">
      <div class="row"><button type="button" data-act="fill">Fill from the subjects of ${esc(of)}</button><button type="button" data-act="upload">Upload a paper list (Excel)</button>
        <button type="button" data-act="download">Download the paper list</button><button type="button" data-act="addPaper">+ Add a paper</button><button type="button" data-act="addMakeup">+ Add a make-up paper</button>
        <input type="file" id="paperFile" accept=".xlsx" hidden></div>
      <span class="muted small">${ps.length} ${ps.length === 1 ? "paper" : "papers"} · ${withTime} with a time${need ? ` · <span class="flag">${need} still ${need === 1 ? "needs" : "need"} one</span>` : ""}</span></div>
    ${S.note ? `<p class="msg ok" role="status">${esc(S.note)}</p>` : ""}
    ${S.mk ? makeupForm() : ""}
    <div class="tablewrap ptable"><table><thead><tr><th>Level</th><th>Subject</th><th>Paper</th><th>Minutes</th><th>Who sits</th><th>Sits with</th><th>Date</th><th>Start</th><th></th></tr></thead>
      <tbody>${rows || `<tr><td colspan="9" class="muted" style="padding:10px">No papers yet.</td></tr>`}</tbody></table></div>
    <p class="muted small">Papers with the same words under Sits with start together. Who sits comes from the subject groups of the published timetable.</p>
    ${checksPanel()}`;
  }

  function onPaperField(el, k, a) {
    const p = S.sched.papers[Number(a)], v = el.value;
    if (!p) return;
    if (k === "plevel") return edit(() => { p.level = v; }, true);
    if (k === "psubject") return edit(() => { p.subject = v; });
    if (k === "ppaper") return edit(() => { p.paper = v; });
    if (k === "pmin") { const n = Number(v); if (!Number.isInteger(n) || n < 1) return; return edit(() => { p.minutes = n; }); }
    if (k === "pwho") return edit(() => { p.who = v; }, true);
    if (k === "ptog") return edit(() => { p.together = v; });
    if (k === "pdate") return edit(() => { p.date = v || null; }, true);
    if (k === "pstart") return edit(() => { p.start = v || null; });
  }

  function onMakeup(el) {
    const m = S.mk, k = el.dataset.mk, v = el.value;
    if (!m) return;
    if (k === "pick") { m.picked = el.checked ? uniq(m.picked.concat([el.dataset.v])) : m.picked.filter(x => x !== el.dataset.v); paint(); return; }
    if (k === "cls") { m.cls = v; paint(); return; }
    if (k === "minutes") { m.minutes = v; return; }
    m[k] = v;
  }

  function mkAdd() {
    const m = S.mk, say = t => { const e = $("#mkMsg"); if (e) e.textContent = t; };
    const n = Number(m.minutes);
    if (!m.level || !m.subject.trim()) { say("Pick a level and give the paper a subject."); return; }
    if (!Number.isInteger(n) || n < 1) { say("Give the paper a length in minutes."); return; }
    if (!m.picked.length) { say("Pick at least one student."); return; }
    const paper = { id: newId(), level: m.level, subject: m.subject.trim(), paper: m.paper.trim(), minutes: n, date: null, start: null, who: "students", students: m.picked.slice(), together: "" };
    edit(() => { S.sched.papers.push(paper); S.mk = null; }, true);
  }

  function download() {
    flush().then(async () => {
      if (S.dirty) return;
      let r;
      try { r = await fetch(`/api/exams/${S.id}/papers.xlsx`, { cache: "no-store" }); } catch (e) { S.bad = true; S.msg = "Could not reach the server. Try again."; paintSave(); return; }
      if (r.status === 401) { location.href = "/login"; return; }
      if (r.status === 403) { forbidden((await r.json().catch(() => ({}))).error); return; }
      if (!r.ok) { S.bad = true; S.msg = (await r.json().catch(() => ({}))).error || "The file could not be made."; paintSave(); return; }
      const blob = await r.blob(), cd = r.headers.get("Content-Disposition") || "", m = /filename="?([^";]+)"?/.exec(cd);
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = m ? m[1] : "paper list.xlsx";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    });
  }

  /* ---------------------------------------------------------------- tab 3: access arrangements */
  function tabAccess() {
    const s = S.sched, stu = (S.view && S.view.students) || {};
    const classes = uniq(Object.values(stu).map(x => x[1])).sort();
    const cur = S.accCls && classes.includes(S.accCls) ? S.accCls : (classes[0] || "");
    const have = new Set(s.access.map(a => a.student));
    const free = Object.entries(stu).filter(([id, x]) => x[1] === cur && !have.has(id)).map(([id, x]) => `<button type="button" class="small" data-act="accAdd" data-a="${esc(id)}">+ ${esc(x[0])}</button>`).join(" ");
    const rows = s.access.map((a, i) => {
      const x = stu[a.student];
      return `<tr><td>${x ? esc(x[0]) : esc(a.student)}${x ? "" : ` <span class="muted small">(not in this exam)</span>`}</td><td>${x ? esc(x[1]) : ""}</td>
        <td><input type="number" min="0" max="100" step="5" ${at("aextra", i)} value="${esc(a.extra ?? 0)}" aria-label="Extra time percent for ${x ? esc(x[0]) : esc(a.student)}"></td>
        <td class="c"><input type="checkbox" ${at("aown", i)} ${a.own_room ? "checked" : ""} aria-label="Own room"></td>
        <td class="c"><input type="checkbox" ${at("aread", i)} ${a.reader ? "checked" : ""} aria-label="Reader"></td>
        <td class="c"><input type="checkbox" ${at("ascribe", i)} ${a.scribe ? "checked" : ""} aria-label="Scribe"></td>
        <td><input type="text" ${at("anote", i)} value="${esc(a.note || "")}" maxlength="200" aria-label="Note"></td>
        <td class="x"><button type="button" class="small danger" data-act="accDel" data-a="${i}" title="Take this student off" aria-label="Take this student off">✕</button></td></tr>`;
    }).join("");
    return `<div class="card"><h2>Access arrangements</h2>
      <p class="muted small">Students who need extra time, a room of their own, a reader or a scribe. Their extra time is added when the app checks the paper times.</p>
      ${S.view ? `<div class="line" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">Add a student from <select data-acc="cls" aria-label="Class">${classes.map(c => opt(c, cur)).join("")}</select></div>
      <div class="chiprow" style="margin:6px 0 12px">${free || `<span class="muted small">No one left to add in this class.</span>`}</div>` : `<p class="muted">Loading…</p>`}
      <div class="tablewrap ptable"><table><thead><tr><th>Student</th><th>Class</th><th>Extra time %</th><th>Own room</th><th>Reader</th><th>Scribe</th><th>Note</th><th></th></tr></thead>
      <tbody>${rows || `<tr><td colspan="8" class="muted" style="padding:10px">No one yet.</td></tr>`}</tbody></table></div></div>`;
  }

  function onAccessField(el, k, a) {
    const x = S.sched.access[Number(a)], v = el.value;
    if (!x) return;
    if (k === "aextra") { const n = Number(v); if (v === "" || !(n >= 0 && n <= 100)) return; return edit(() => { x.extra = n; }); }
    if (k === "aown") return edit(() => { x.own_room = el.checked; });
    if (k === "aread") return edit(() => { x.reader = el.checked; });
    if (k === "ascribe") return edit(() => { x.scribe = el.checked; });
    if (k === "anote") return edit(() => { x.note = v; });
  }

  /* ---------------------------------------------------------------- events */
  function onField(e) {
    const el = e.target;
    if (S.id && el.dataset.mk) { onMakeup(el); return; }
    if (S.id && el.dataset.acc === "cls") { S.accCls = el.value; paint(); return; }
    if (!S.id && el.dataset.nf) { onNewField(el); return; }
    if (!S.id || !S.sched) return;
    const k = el.dataset.k, a = el.dataset.a, b = el.dataset.b;
    if (!k) return;
    if (k === "name" || k === "start" || k === "end" || k === "sup" || k === "level" || k === "class" || k.startsWith("day") || k === "time") onWhenField(el, k, a, b);
    else if (k.startsWith("a")) onAccessField(el, k, a);
    else onPaperField(el, k, a);
  }

  /* text boxes are read as they are typed, the rest when they are changed */
  function onInput(e) {
    const el = e.target, ty = el.type;
    if (el.tagName === "SELECT" || ty === "checkbox" || ty === "date" || ty === "file") return;
    onField(e);
  }
  function onChange(e) {
    const el = e.target, ty = el.type;
    if (ty === "file") { onFile(el); return; }
    if (el.tagName === "SELECT" || ty === "checkbox" || ty === "date") onField(e);
  }

  function onNewField(el) {
    const nf = S.nf, k = el.dataset.nf, v = el.value;
    if (k === "level" || k === "class") {
      const key = k === "level" ? "levels" : "classes";
      nf[key] = el.checked ? uniq(nf[key].concat([el.dataset.v])) : nf[key].filter(x => x !== el.dataset.v);
    } else nf[k] = v;
  }

  function onFile(el) {
    const f = el.files && el.files[0]; if (!f || !S.id) return;
    const form = new FormData(); form.append("file", f);
    el.value = "";
    serverAction("POST", `/api/exams/${S.id}/papers.xlsx`, undefined, form, () => { S.note = "The paper list is in."; });
  }

  function onClick(e) {
    const b = e.target.closest("button[data-act]"); if (!b || b.matches(":disabled")) return;
    const act = b.dataset.act, a = b.dataset.a, s = S.sched;
    if (!S.id) {
      if (act === "newOpen") { S.nf.open = true; drawList(); const n = $('[data-nf="name"]'); if (n) n.focus(); }
      else if (act === "newCancel") { S.nf = blankForm(); drawList(); }
      else if (act === "newSave") newSave();
      return;
    }
    if (!s) return;
    if (act === "tab") { S.tab = a; S.note = ""; render(); return; }
    if (act === "dayWhole") {
      const date = a, on = b.dataset.b === "1", p = periods();
      edit(() => setDay(date, on ? { whole: true } : { whole: false, from: p.length ? p[0][0] : null, to: p.length ? p[Math.min(3, p.length - 1)][1] : null }), true);
      return;
    }
    if (act === "fill") {
      const before = s.papers.length;
      serverAction("POST", `/api/exams/${S.id}/fill`, {}, undefined, j => { const n = j.papers.length - before; S.note = n > 0 ? `Added ${n} ${n === 1 ? "paper" : "papers"}.` : "There is nothing new to add: every subject has a paper already."; });
      return;
    }
    if (act === "upload") { const f = $("#paperFile"); if (f) f.click(); return; }
    if (act === "download") { download(); return; }
    if (act === "addPaper") {
      const lv = paperLevels();
      edit(() => { s.papers.push({ id: newId(), level: lv[0] || "", subject: "", paper: "Paper 1", minutes: 60, date: null, start: null, who: "groups", students: [], together: "" }); }, true);
      return;
    }
    if (act === "addMakeup") { S.mk = { level: paperLevels()[0] || "", subject: "", paper: "Make-up", minutes: "60", cls: "", picked: [] }; paint(); return; }
    if (act === "mkCancel") { S.mk = null; paint(); return; }
    if (act === "mkAdd") { mkAdd(); return; }
    if (act === "delPaper") { edit(() => { s.papers.splice(Number(a), 1); }, true); return; }
    if (act === "accAdd") { edit(() => { s.access.push({ student: a, extra: 0, own_room: false, reader: false, scribe: false, note: "" }); }, true); return; }
    if (act === "accDel") { edit(() => { s.access.splice(Number(a), 1); }, true); return; }
  }

  async function startOne(id) {
    links();
    S.id = id;
    const [r, v, l] = await Promise.all([api("GET", "/api/exams/" + id), api("GET", `/api/exams/${id}/view`), api("GET", "/api/exams")]);
    for (const x of [r, v, l]) if (x.status === 401 || x.status === 403) return;
    for (const x of [r, v, l]) if (!x.ok) { fail(x.j.error || "Something went wrong."); return; }
    S.sched = r.j; S.view = v.j; S.levels = l.j.levels || []; S.classes = l.j.classes || [];
    document.title = r.j.name + " · Exams";
    render();
  }

  document.addEventListener("click", onClick);
  document.addEventListener("input", onInput);
  document.addEventListener("change", onChange);
  window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
  const m = /^\/exams\/([A-Za-z0-9]+)\/?$/.exec(location.pathname);
  if (m && m[1] !== "settings") startOne(m[1]); else startList();
})();

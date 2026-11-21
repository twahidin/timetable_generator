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
  const KINDS = { exam: "Exam", test: "Common test", event: "Event" };
  const NO_STUDENTS_YET = "The published timetable has no students yet: add them on the Students step and publish again to check clashes and seat students.";
  const S = {
    id: null, list: null, sched: null, view: null, levels: [], classes: [],
    base: "/api/exams", tabs: null, evl: null, me0: null, ne: null, ev: { dept: "", pick: "" },
    tab: "when", timer: null, chain: Promise.resolve(), dirty: false, rev: 0, saving: false, msg: "", bad: false,
    nf: null, mk: null, duties: null, accCls: "", note: "",
    busy: false, sit: "", room: "", mvCls: "", mvStu: "", duty: null, who: null, whoTok: 0, open: {},
    me: { can_approve: false }, label: "", rv: null, rvErr: "", rvTok: 0, abMsg: "", sbNote: "", aw: { duty: null, away: "", who: "", data: null, err: "", say: "", tok: 0 }
  };
  /* the tabs: tabs 4 to 7 are added to this list; each draw() gives the html of its tab body */
  const EX_TABS = [
    { key: "when", name: "What and when", draw: () => tabWhen() },
    { key: "papers", name: "Papers", draw: () => tabPapers() },
    { key: "access", name: "Access arrangements", draw: () => tabAccess() },
    { key: "schedule", name: "Schedule", draw: () => tabSchedule() },
    { key: "venues", name: "Venues and seats", draw: () => tabVenues() },
    { key: "invig", name: "Invigilators", draw: () => tabInvig() },
    { key: "lessons", name: "Lessons", draw: () => tabLessons() },
    { key: "approval", name: "Approval", draw: () => tabApproval() }
  ];
  /* an event has four tabs; the approval tab is the exams' own */
  const EV_TABS = [
    { key: "ewhen", name: "What and when", draw: () => tabEvWhen() },
    { key: "egoes", name: "Who goes", draw: () => tabEvGoes() },
    { key: "elessons", name: "Lessons", draw: () => tabEvLessons() },
    { key: "approval", name: "Approval", draw: () => tabApproval() }
  ];
  S.tabs = EX_TABS;
  const isEv = () => S.base === "/api/events";

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

  function links(member) {
    $("#links").innerHTML = `<a class="ghost filebtn" href="/exams">Exams</a>${member === false ? "" : `<a class="ghost filebtn" href="/exams/settings">Exam settings</a>`}<a class="ghost filebtn" href="/logout">Sign out</a>`;
  }

  /* ================================================================ the list */
  function blankForm() { return { kind: "exam", name: "", levels: [], classes: [], start: "", end: "", open: false }; }

  /* the chip's class from the server's label: draft, waiting, approved, ended or withdrawn */
  function chipClass(s) {
    const l = s.label || "";
    if (l === "Ended") return "ended";
    if (l === "Withdrawn") return "withdrawn";
    if (l.startsWith("Waiting")) return "waiting";
    if (l.startsWith("Approved")) return "approved";
    return "draft";
  }
  const sentOn = at => at ? fmtDate(String(at).slice(0, 10)) : "";

  /* who on an approved schedule is away in relief: the server's texts, as notices */
  const awayNotes = list => (list || []).length ? `<div class="notice" role="status" aria-label="Away (from relief)">${list.map(t => `<div>${esc(t)}</div>`).join("")}</div>` : "";

  /* the lines under a schedule's name in the list */
  function statusLines(s) {
    const out = [];
    (s.away || []).forEach(t => out.push(`<b>${esc(t)}</b>`));
    if (s.note && s.status === "approved") out.push(`Changes sent back: “${esc(s.note)}”`);
    else if (s.note && (s.status || "draft") === "draft") out.push(`Sent back: “${esc(s.note)}”`);
    if (s.status === "waiting" || s.status === "changes") out.push(`sent by ${esc(s.sent_by || "")}, ${esc(sentOn(s.sent_at))}`);
    if ((s.status === "approved" || s.status === "changes") && s.on_site) out.push(`on the main site ${esc(fmtDate(s.on_site[0]))} to ${esc(fmtDate(s.on_site[1]))}`);
    if (s.retimed) out.push("The timetable changed since this was made.");
    return out.map(x => `<br><span class="muted small">${x}</span>`).join("");
  }

  const dates = s => s.start === s.end ? esc(fmtDate(s.start)) : `${esc(fmtDate(s.start))} to ${esc(fmtDate(s.end))}`;

  function examCard(s) {
    return `<div class="card scard"><div><span class="chip ${s.kind === "test" ? "test-kind" : "ex-kind"}">${esc(KINDS[s.kind] || s.kind)}</span>
      <a class="name" href="/exams/${esc(s.id)}">${esc(s.name)}</a><br>
      <span class="muted small">${esc(fmtDate(s.start))} to ${esc(fmtDate(s.end))}${(s.levels || []).length ? " · " + esc(s.levels.join(", ")) : ""} · ${s.papers} ${s.papers === 1 ? "paper" : "papers"}</span>${statusLines(s)}</div>
      <div><span class="chip ${chipClass(s)}">${esc(s.label || "Draft")}</span></div></div>`;
  }

  function eventCard(s) {
    const who = (s.levels || []).length ? s.levels.join(", ") : (s.classes || []).join(", ");
    const line = [dates(s), esc(who), esc(s.where || ""), `${s.n_going} going`].filter(Boolean).join(" · ");
    return `<div class="card scard"><div><span class="chip ev-kind">Event</span>
      <a class="name" href="/events/${esc(s.id)}">${esc(s.name)}</a><span class="muted small"> · teacher in charge ${esc(s.in_charge || "")}</span><br>
      <span class="muted small">${line}</span>${statusLines(s)}</div>
      <div><span class="chip ${chipClass(s)}">${esc(s.label || "Draft")}</span></div></div>`;
  }

  function drawList() {
    const L = S.list, E = S.evl, nf = S.nf, ne = S.ne, use = !!L;
    const all = (L ? L.schedules.map(x => [x, examCard]) : []).concat(E.schedules.map(x => [x, eventCard]));
    all.sort((x, y) => String(y[0].saved_at || "9").localeCompare(String(x[0].saved_at || "9")));
    const rows = all.map(([x, f]) => f(x)).join("");
    const calOk = (!L || L.calendar_ok) && E.calendar_ok;
    const cal = calOk ? "" : `<p class="notice">${esc(NO_CALENDAR)} <a href="/relief/settings">Relief settings</a></p>`;
    $("#main").innerHTML = `<div class="head"><h1>${use ? "Exams, tests and events" : "Exams and events"}</h1>
      <div class="row">${use ? `<button type="button" class="primary" data-act="newOpen" ${L.calendar_ok && !nf.open ? "" : "disabled"}>+ New exam or test</button>` : ""}<button type="button" ${use ? "" : `class="primary"`} data-act="evOpen" ${E.calendar_ok && !ne.open ? "" : "disabled"}>+ New event</button></div></div>
      ${cal}${nf.open ? newForm() : ""}${ne.open ? newEvForm() : ""}${dutiesCard()}
      ${rows || `<div class="card"><p class="muted">${use ? "No exams, tests or events yet." : "You are not in charge of an event yet."}</p></div>`}${use ? "" : `<p><a href="/relief">Back to Relief</a></p>`}`;
  }

  function blankEv() { return { open: false, name: "", levels: [], classes: [], start: "", end: "", in_charge: "" }; }

  function newEvForm() {
    const ne = S.ne, E = S.evl;
    const lv = E.levels.map(l => `<label class="tick"><input type="checkbox" data-ne="level" data-v="${esc(l)}" ${ne.levels.includes(l) ? "checked" : ""}> ${esc(l)}</label>`).join("");
    const cl = E.classes.map(([c, l]) => `<label class="tick" title="${esc(l)}"><input type="checkbox" data-ne="class" data-v="${esc(c)}" ${ne.classes.includes(c) ? "checked" : ""}> ${esc(c)}</label>`).join("");
    const ppl = (E.people || []).length ? `<div class="line"><b>Teacher in charge</b><select data-ne="in_charge" aria-label="Teacher in charge"><option value="">Choose a teacher</option>${E.people.map(n => opt(n, ne.in_charge)).join("")}</select></div>` : "";
    return `<div class="card form"><h2>New event</h2>
      <div class="line"><b>Name</b><input type="text" data-ne="name" value="${esc(ne.name)}" maxlength="120" placeholder="e.g. Sec 2 Learning Journey" aria-label="Name"></div>
      <div class="line"><b>Who</b><span class="chiprow">${lv || `<span class="muted small">The published timetable has no levels.</span>`}</span></div>
      <div class="line"><b></b><details class="pickc" ${ne.classes.length ? "open" : ""}><summary>Or pick classes</summary><div class="classes">${cl}</div></details></div>
      <div class="line"><b>Dates</b><input type="date" data-ne="start" value="${esc(ne.start)}" aria-label="First day"> to <input type="date" data-ne="end" value="${esc(ne.end)}" aria-label="Last day"></div>
      ${ppl}
      <div class="row"><button type="button" class="primary" data-act="evSave">Make it</button><button type="button" data-act="evCancel">Cancel</button><span class="msg bad" id="neMsg" role="status"></span></div></div>`;
  }

  async function evSave() {
    const ne = S.ne, msg = $("#neMsg"), btn = $('[data-act="evSave"]');
    const say = t => { if (msg) msg.textContent = t; };
    say(""); if (btn) btn.disabled = true;
    const body = { name: ne.name, levels: ne.levels, classes: ne.classes, start: ne.start, end: ne.end };
    if ((S.evl.people || []).length) body.in_charge = ne.in_charge;
    const r = await api("POST", "/api/events", body);
    if (!r.ok) { if (btn) btn.disabled = false; if (r.status !== 403) say(r.j.error || "That did not work. Try again."); return; }
    location.href = "/events/" + r.j.id;
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
      if (r2.status === 401 || r2.status === 403) return;
      if (!r2.ok) {
        try { sessionStorage.setItem("examsNote", "The exam was made, but its classes were not saved: " + (r2.j.error || "Check the exam and try again.")); } catch (e) { /* no storage: the editor opens without the sentence */ }
      }
    }
    location.href = "/exams/" + r.j.id;
  }

  /* ---------------------------------------------------------------- my exam duties */
  const nTimes = (n, one, many) => `${n} ${n === 1 ? one : many}`;

  function dutyBlock(sc) {
    if (sc.kind === "event") {
      const er = sc.duties.map(d => `<tr><td>${esc(fmtDate(d.date))} · ${esc(d.start)}–${esc(d.end)}</td><td>At the event${sc.where ? " · " + esc(sc.where) : ""}</td>
        <td class="small">${d.duty ? "duty: " + esc(d.duty) : ""}</td></tr>`).join("");
      return `<h3>${esc(sc.name)}</h3><div class="tablewrap"><table><tbody>${er}</tbody></table></div>
        <p class="muted small">teacher in charge: ${esc(sc.in_charge || "")}</p>`;
    }
    const rows = sc.duties.map(d => `<tr><td>${esc(fmtDate(d.date))} · ${esc(d.start)}–${esc(d.end)}</td>
      <td>${esc(d.role)} ${esc(d.room)} · ${esc(d.label)} · ${nTimes(d.students, "student", "students")}</td>
      <td class="small">${[d.others.length ? "with " + esc(d.others.join(", ")) : "", d.chief ? "chief: " + esc(d.chief) : "", sc.scripts ? "scripts to " + esc(sc.scripts) : ""].filter(Boolean).join(" · ")}</td></tr>`).join("");
    return `<h3>${esc(sc.name)}</h3><div class="tablewrap"><table><tbody>${rows}</tbody></table></div>
      <p class="muted small">${nTimes(sc.duties.length, "duty", "duties")} · ${esc(fmtLen(sc.minutes))} this exam</p>`;
  }

  /* S.duties is null until /api/exams/my-duties answers; a member with no duties and no lesson that doesn't happen sees no
     card, someone else sees the sentence (and the lessons, when there are some) */
  function dutiesCard(alone) {
    const D = S.duties; if (!D) return "";
    if (!D.schedules.length && !(D.lessons || []).length && !alone) return "";
    const lessons = (D.lessons || []).length ? `<p class="small">Lessons that don't happen: ${D.lessons.map(l => `${esc(fmtDate(l.date))} ${esc(l.start)} ${esc((l.classes || []).join(", "))} ${esc(l.subject)}`).join(" · ")}</p>` : "";
    return `<div class="card"><h2>My exam and event duties</h2>${D.schedules.map(dutyBlock).join("") || `<p class="muted">You have no exam or event duties on the main site.</p>`}${lessons}</div>`;
  }

  async function startList() {
    const me = await api("GET", "/api/exams/me");
    if (me.status === 401 || me.status === 403) return;
    if (!me.ok) { links(); fail(me.j.error || "Something went wrong."); return; }
    links(me.j.can_use);
    const du = await api("GET", "/api/exams/my-duties");
    S.duties = du.ok ? du.j : null;
    const ev = await api("GET", "/api/events");
    if (ev.status === 401 || ev.status === 403) return;
    if (!ev.ok) { fail(ev.j.error || "Something went wrong.", me.j.can_use ? "" : "/relief"); return; }
    S.evl = ev.j; S.ne = blankEv(); S.nf = blankForm(); S.list = null;
    if (me.j.can_use) {
      const r = await api("GET", "/api/exams");
      if (r.status === 401 || r.status === 403) return;
      if (!r.ok) { fail(r.j.error || "Something went wrong."); return; }
      S.list = r.j;
    }
    drawList();
  }

  /* ================================================================ one schedule */
  const tab = () => S.tabs.find(t => t.key === S.tab) || S.tabs[0];

  function saveInner() {
    return `${S.dirty ? `<span class="dirty">Changes not saved.</span>` : ""}${S.msg ? `<span class="msg ${S.bad ? "bad" : "ok"}" role="status">${esc(S.msg)}</span>` : ""}`;
  }
  function paintSave() { const el = $("#saveline"); if (el) el.innerHTML = saveInner(); }

  function render() {
    const s = S.sched;
    $("#main").innerHTML = `<div class="head"><div><h1>${esc(s.name)} <span class="chip ${chipClass({ label: S.label })}" id="statchip">${esc(S.label)}</span></h1>
      <div class="muted small"><a href="/exams">${isEv() ? "All exams and events" : "All exams"}</a> · ${esc(KINDS[s.kind] || s.kind)} · ${esc(fmtDate(s.start, true))} to ${esc(fmtDate(s.end, true))}${isEv() ? " · teacher in charge " + esc(s.in_charge || "") : ""}</div></div>
      <div class="savebar" id="saveline">${saveInner()}</div></div>
      ${onSite() ? `<p class="notice">On the main site. Changes you make here wait for the timetable committee: send them from the Approval tab.</p>` : ""}
      <div class="xtabs" role="tablist">${S.tabs.map(t => `<button type="button" role="tab" class="${t.key === S.tab ? "on" : ""}" aria-selected="${t.key === S.tab}" data-act="tab" data-a="${t.key}">${esc(t.name)}</button>`).join("")}</div>
      <div id="tabbody">${tab().draw()}</div><input type="file" id="paperFile" accept=".xlsx" hidden>`;
  }

  /* draw the tab body again, keeping the cursor where it was */
  function paint() {
    const body = $("#tabbody"); if (!body) return;
    const a = document.activeElement, key = a && a.dataset ? a.dataset.f : null;
    let s0 = null, s1 = null;
    try { s0 = a.selectionStart; s1 = a.selectionEnd; } catch (e) { /* not a text box */ }
    const keep = {}; body.querySelectorAll("[data-keep]").forEach(x => { keep[x.dataset.keep] = x.scrollTop; });
    body.innerHTML = tab().draw();
    body.querySelectorAll("[data-keep]").forEach(x => { if (keep[x.dataset.keep] != null) x.scrollTop = keep[x.dataset.keep]; });
    if (key) {
      const el = Array.from(document.querySelectorAll("[data-f]")).find(x => x.dataset.f === key);
      if (el) { el.focus({ preventScroll: true }); try { if (s0 != null) el.setSelectionRange(s0, s1); } catch (e) { /* not a text box */ } }
    }
  }

  /* change the schedule, then save it after a pause */
  function edit(fn, redraw) {
    fn();
    S.dirty = true; S.rev++; S.msg = ""; S.bad = false; S.note = ""; paintSave();
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
    const r = await api("PUT", `${S.base}/${S.id}`, S.sched);
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
    const r = await api("GET", `${S.base}/${S.id}/view`);
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
      <div class="line"><b>Scripts go to</b><input type="text" ${at("scripts")} value="${esc(s.scripts || "")}" maxlength="120" placeholder="the staff room" aria-label="Scripts go to"></div>
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
    if (k === "scripts") return edit(() => { s.scripts = v; });
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
    if (S.view.students_missing) lines.unshift(`<div><span class="amber">●</span> ${esc(NO_STUDENTS_YET)}</div>`);   /* no clash can be found */
    else if (!lines.length) lines.push(S.sched.papers.length ? `<div><span class="okc">✓</span> No problems with the paper times.</div>` : `<div class="muted">Add papers to see the checks.</div>`);
    return `<div class="card checks"><h2>Checks on your times</h2>${lines.join("")}</div>`;
  }

  function makeupForm() {
    const m = S.mk, v = S.view, stu = v ? v.students : {};
    const classes = uniq(Object.values(stu).map(x => x[1])).sort();
    const cur = m.cls || classes[0] || "";
    const list = Object.entries(stu).filter(([, x]) => x[1] === cur).map(([id, x]) => `<label class="tick"><input type="checkbox" data-mk="pick" data-f="mk-pick-${esc(id)}" data-v="${esc(id)}" ${m.picked.includes(id) ? "checked" : ""}> ${esc(x[0])}</label>`).join("");
    return `<div class="mk"><h3 style="margin-top:0">A make-up paper</h3>
      <div class="line"><select data-mk="level" data-f="mk-level" aria-label="Level">${paperLevels().map(l => opt(l, m.level)).join("")}</select>
        <input type="text" data-mk="subject" data-f="mk-subject" value="${esc(m.subject)}" placeholder="Subject" aria-label="Subject">
        <input type="text" data-mk="paper" data-f="mk-paper" value="${esc(m.paper)}" placeholder="Paper" aria-label="Paper">
        <input type="number" min="1" step="5" data-mk="minutes" data-f="mk-minutes" value="${esc(m.minutes)}" aria-label="Minutes"> minutes</div>
      <div class="line">Pick students from <select data-mk="cls" data-f="mk-cls" aria-label="Class">${classes.map(c => opt(c, cur)).join("")}</select> <span class="muted small">${m.picked.length} picked</span></div>
      <div class="stu" data-keep="stu">${list || `<span class="muted small">No students in this class.</span>`}</div>
      <div class="row"><button type="button" class="primary small" data-act="mkAdd">Add the paper</button><button type="button" class="small" data-act="mkCancel">Cancel</button><span class="msg bad" id="mkMsg" role="status"></span></div></div>`;
  }

  function tabPapers() {
    const s = S.sched, ps = s.papers, withTime = ps.filter(p => p.date && p.start).length, need = ps.length - withTime;
    const of = s.levels.length ? s.levels.join(", ") : "the chosen classes";
    const rows = ps.map(paperRow).join("");
    return `<div class="row" style="justify-content:space-between;margin-bottom:10px">
      <div class="row"><button type="button" data-act="fill">Fill from the subjects of ${esc(of)}</button><button type="button" data-act="upload">Upload a paper list (Excel)</button>
        <button type="button" data-act="download">Download the paper list</button><button type="button" data-act="addPaper">+ Add a paper</button><button type="button" data-act="addMakeup">+ Add a make-up paper</button>
        </div>
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
      ${S.view && S.view.students_missing ? `<p class="notice">${esc(NO_STUDENTS_YET)}</p>` : S.view ? `<div class="line" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">Add a student from <select data-acc="cls" data-f="acc-cls" aria-label="Class">${classes.map(c => opt(c, cur)).join("")}</select></div>
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

  /* ---------------------------------------------------------------- tabs 4 to 7: the made schedule */
  const NO_STUDENTS = "The published timetable has no students. Add them on the Students step and publish again to seat them.";
  const STALE = "The exam changed since Make: press Make again.";
  const staleLine = () => (S.view && S.view.made && S.view.stale) ? `<p class="notice" role="status">${esc(STALE)}</p>` : "";
  const hhmm = n => `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
  const norm = t => { const m = /^(\d+):(\d+)/.exec(t || ""); return m ? `${m[1].padStart(2, "0")}:${m[2]}` : ""; };
  const letters = i => i < 26 ? String.fromCharCode(65 + i) : String.fromCharCode(64 + Math.floor(i / 26)) + String.fromCharCode(65 + i % 26);
  const madeOf = () => (S.view && S.view.made) || null;
  const seatsOf = key => ((madeOf() || {}).seats || {})[key] || {};
  const stuOf = sid => ((S.view && S.view.students) || {})[sid] || null;
  const nameOf = sid => { const x = stuOf(sid); return x ? x[0] : sid; };
  const sittingKeys = () => Object.keys((S.view && S.view.rooms_by_key) || {});
  const printLink = (what, label) => (S.view && S.view.stale) ? `<button type="button" class="small" disabled title="Press Make again first">${esc(label)}</button>`
    : `<a class="ghost filebtn small" href="/api/exams/${esc(S.id)}/print/${what}.pdf" target="_blank" rel="noopener">${esc(label)}</a>`;
  const clsColour = (list, cls) => `s${Math.max(0, uniq(list).sort().indexOf(cls)) % 6}`;

  function sitLabel(key) {
    const [d, t] = key.split(" ");
    const ps = S.sched.papers.filter(p => p.date === d && p.start && norm(p.start) === t);
    const what = uniq(ps.map(p => `${p.level} ${p.subject}${p.paper ? " " + p.paper : ""}`.trim()));
    return `${fmtDate(d)} · ${t}${what.length ? " · " + what.join(" + ") : ""}`;
  }

  /* what the page does at the server: our own edits go first, then the answer (the whole view) replaces S.view */
  async function viewAction(path, body, ok) {
    if (S.busy) return false;
    await flush();
    if (S.dirty) return false;   /* the save was refused: its sentence is on the screen */
    S.busy = true; S.msg = ""; S.bad = false; paintSave(); paint();
    const r = await api("POST", `/api/exams/${S.id}/${path}`, body);
    S.busy = false;
    if (r.status === 401 || r.status === 403) return false;
    if (!r.ok) { S.bad = true; S.msg = r.j.error || "That did not work. Try again."; paintSave(); paint(); return false; }
    S.view = r.j; S.msg = typeof ok === "function" ? ok(r.j) : (ok || ""); paintSave(); paint();
    return true;
  }

  async function loadWho(keep) {
    const d = S.duty; if (!d) return;
    const tok = ++S.whoTok;
    if (!keep) { S.who = null; paint(); }
    const r = await api("GET", `/api/exams/${S.id}/who?key=${encodeURIComponent(d.key)}&room=${encodeURIComponent(d.room)}`);
    if (tok !== S.whoTok || r.status === 401 || r.status === 403) return;
    S.who = r.ok ? r.j : { error: r.j.error || "Could not list who could take it." };
    paint();
  }

  const needMade = () => `<div class="card"><p class="muted">${S.view ? "Nothing is made yet. Press Make on the Schedule tab." : "Loading…"}</p></div>`;

  /* ---------------------------------------------------------------- tab 4: schedule */
  /* a part day that starts with the school day: "lessons from 09:00"; one in the middle of the day: "lessons outside 09:40–10:40" */
  const fromFirst = d => { const p = periods(); return !p.length || d.window[0] === p[0][0]; };
  const partWords = d => fromFirst(d) ? `lessons from ${esc(d.window[1])}` : `lessons outside ${esc(d.window[0])}–${esc(d.window[1])}`;

  function dayCells(d) {
    const levels = S.view.levels || [];
    return levels.map(l => {
      if (!(d.levels || []).includes(l)) return `<td><span class="pp norm">normal lessons</span></td>`;
      const ps = (d.papers || {})[l] || [];
      const blocks = ps.map(p => `<span class="pp ex"><b>${esc(p.label)}</b> ${esc(p.start)}–${esc(p.end)}</span>`).join("");
      const after = !d.whole && d.window ? `<span class="pp norm">${partWords(d)}</span>` : "";
      return `<td>${blocks || (d.whole ? `<span class="muted small">no paper</span>` : "")}${after}</td>`;
    }).join("");
  }

  function tabSchedule() {
    const v = S.view;
    if (!v) return `<div class="card"><p class="muted">Loading…</p></div>`;
    const sm = v.summary, c = sm.counts, levels = v.levels || [], made = v.made;
    const check = sm.checks.errors.length + sm.checks.warnings.length + c.short + c.unseated;
    const gone = (sm.gone || []).length ? `<div class="notice">${sm.gone.map(g => `<div>${esc(g)}</div>`).join("")}</div>` : "";
    const rows = sm.days.map(d => {
      if (d.day == null) return `<tr><td><b>${esc(fmtDate(d.date))}</b></td><td class="muted" colspan="${levels.length || 1}">Not a school day</td></tr>`;
      return `<tr><td><b>${esc(fmtDate(d.date))}</b><br><span class="muted small">${esc(d.day)} · ${d.whole ? "whole day" : fromFirst(d) ? "part, to " + esc(d.window[1]) : `part, ${esc(d.window[0])}–${esc(d.window[1])}`}</span></td>${dayCells(d)}</tr>
        <tr><td colspan="${levels.length + 1}" class="small muted dayline">Teachers: <b>${d.freed}</b> freed by the exam · <b>${d.on_duty}</b> on duty · <b>${d.teaching}</b> still teaching · <span class="${d.backups ? "amber" : ""}">${d.backups} ${d.backups === 1 ? "backup" : "backups"}</span></td></tr>`;
    }).join("");
    const make = v.students_missing ? `<span class="msg bad">${esc(NO_STUDENTS)}</span>`
      : `<button type="button" class="primary" data-act="make" ${S.busy ? "disabled" : ""}>${made ? "Make again" : "Make"}</button>`;
    const dl = made && !v.stale ? `<a class="ghost filebtn" href="/api/exams/${esc(S.id)}/download.xlsx" target="_blank" rel="noopener">Download (Excel)</a>` : `<button type="button" disabled>Download (Excel)</button>`;
    return `${gone}<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0">${esc(S.sched.name)}</h2><div class="row">${make}${dl}</div></div>
      ${staleLine()}<div class="kpi">
        <div><div class="k">Papers</div><div class="big">${c.papers}</div><div class="small muted">${c.with_time} with a time</div></div>
        <div><div class="k">Students with 2 papers in a day</div><div class="big">${c.two_a_day}</div></div>
        <div><div class="k">Invigilation duties</div><div class="big">${c.duties}</div>${c.short ? `<div class="small flag">${c.short} ${c.short === 1 ? "place" : "places"} not filled</div>` : ""}</div>
        <div><div class="k">Backups needed</div><div class="big ${c.backups ? "amber" : ""}">${c.backups}</div></div>
        <div><div class="k">To check</div><div class="big ${check ? "flag" : ""}">${check}</div>${c.unseated ? `<div class="small flag">${c.unseated} without a seat</div>` : ""}</div>
      </div>
      <div class="tablewrap"><table class="tl"><thead><tr><th style="width:130px">Day</th>${levels.map(l => `<th>${esc(l)}</th>`).join("")}</tr></thead><tbody>${rows || `<tr><td class="muted">No days yet.</td></tr>`}</tbody></table></div>
      <div style="margin-top:14px">${checksPanel()}</div>`;
  }

  /* ---------------------------------------------------------------- tab 5: venues and seats */
  /* the four "How to seat" choices: [key in sched.seating, label, [[value, words]]] */
  const SEAT_CHOICES = [
    ["home_rooms", "Classes", [[true, "Own class in own home room"], [false, "Mix classes"]]],
    ["shared", "A shared room", [["levels", "Alternate levels by column"], ["papers", "Alternate papers"], ["blocks", "One level per block"]]],
    ["order", "In a room", [["class", "Class, then Student ID"], ["name", "Name"]]],
    ["spacing", "Spacing", [["every", "Every seat"], ["gap", "A seat left between"]]]
  ];

  function seatChoices() {
    const st = S.sched.seating || {};
    const rows = SEAT_CHOICES.map(([k, label, opts]) => {
      const btns = opts.map(([v, words]) => {
        const on = String(st[k]) === String(v);
        return `<button type="button" class="${on ? "on" : ""}" aria-pressed="${on}" data-act="seatOpt" data-a="${esc(k)}" data-b="${esc(String(v))}">${esc(words)}</button>`;
      }).join("");
      return `<div class="line"><b>${esc(label)}</b><span class="seg wrap" role="group" aria-label="${esc(label)}">${btns}</span></div>`;
    }).join("");
    return `<div class="panel form"><h3 style="margin-top:0">How to seat</h3>${rows}<p class="muted small" style="margin:0">A change is used when you press Make again.</p></div>`;
  }

  function curSit() {
    const ks = sittingKeys();
    return ks.includes(S.sit) ? S.sit : (ks[0] || "");
  }

  function seatGrid(key, room) {
    const rs = ((S.view.rooms || {})[room]) || {}, list = seatsOf(key)[room] || [];
    const cls = uniq(list.map(([sid]) => (stuOf(sid) || [])[1]));
    const cell = (sid, seat) => { const x = stuOf(sid) || [sid, "?"]; return `<span class="seat ${clsColour(cls, x[1])}" title="${esc(seat + ": " + x[1] + " " + x[0])}">${esc(x[1])}<br>${esc(sid)}</span>`; };
    if (!rs.rows || !rs.cols) {
      const rows = list.slice().sort((a, b) => Number(a[1]) - Number(b[1])).map(([sid, seat]) => `<tr><td>${esc(seat)}</td><td>${esc((stuOf(sid) || [])[1] || "")}</td><td>${esc(sid)}</td><td>${esc(nameOf(sid))}</td></tr>`).join("");
      return `<p class="muted small">This room has no seat layout in Exam settings, so the seats are a numbered list.</p><div class="tablewrap"><table><thead><tr><th>Seat</th><th>Class</th><th>Student ID</th><th>Name</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    }
    const at2 = {}; list.forEach(([sid, seat]) => { at2[seat] = sid; });
    let out = `<span></span>` + Array.from({ length: rs.cols }, (_, i) => `<span class="seat lab">${letters(i)}</span>`).join(""), placed = 0;
    for (let r = 1; r <= rs.rows; r++) {
      out += `<span class="seat lab">${r}</span>`;
      for (let i = 0; i < rs.cols; i++) { const sid = at2[letters(i) + r]; if (sid) placed++; out += sid ? cell(sid, letters(i) + r) : `<span class="seat empty"></span>`; }
    }
    const stray = placed < list.length ? `<p class="flag small">${list.length - placed} ${list.length - placed === 1 ? "seat is" : "seats are"} outside this room's layout.</p>` : "";
    return `<p class="small muted">A seat shows the class and the Student ID. Hover to see the name. ${rs.rows} rows × ${rs.cols} columns.</p>
      <div class="seatwrap"><div class="seats" style="grid-template-columns:28px repeat(${rs.cols},minmax(46px,1fr))">${out}</div></div>${stray}`;
  }

  /* the class and student the move boxes show: the ones picked, else the first */
  function moveState(key) {
    const all = {};
    for (const list of Object.values(seatsOf(key))) for (const [sid] of list) { const x = stuOf(sid); if (x) (all[x[1]] = all[x[1]] || []).push(sid); }
    const classes = Object.keys(all).sort();
    const cur = classes.includes(S.mvCls) ? S.mvCls : (classes[0] || "");
    const mine = (all[cur] || []).slice().sort((a, b) => nameOf(a).localeCompare(nameOf(b)));
    return { classes, cur, mine, stu: mine.includes(S.mvStu) ? S.mvStu : (mine[0] || "") };
  }

  function moveBox(key, free) {
    const { classes, cur, mine, stu } = moveState(key);
    if (!classes.length) return "";
    const to = (name, label) => `<select data-x="${name}" data-f="x-${name}" aria-label="${esc(label)}" ${S.busy ? "disabled" : ""}><option value="">${esc(label)}</option>${free.map(r => `<option value="${esc(r[0])}">${esc(r[0])} (${r[1]} seats)</option>`).join("")}</select>`;
    return `<div class="mv"><b>Move students</b>
      <div class="line">Class <select data-x="mvCls" data-f="x-mvCls" aria-label="Class to move">${classes.map(c => opt(c, cur)).join("")}</select> ${to("mvClassTo", "Move class to…")}</div>
      <div class="line">Student <select data-x="mvStu" data-f="x-mvStu" aria-label="Student to move">${mine.map(s => opt(s, stu, nameOf(s))).join("")}</select> ${to("mvStuTo", "Move student to…")}</div></div>`;
  }

  function tabVenues() {
    const v = S.view, made = madeOf();
    if (!v || !made) return seatChoices() + needMade();
    const key = curSit();
    if (!key) return `${seatChoices()}<div class="card"><p class="muted">No paper has a date and a start time yet.</p></div>`;
    const seats = seatsOf(key), rooms = v.rooms_by_key[key] || [], duties = (made.duties || []).filter(d => d.key === key);
    const seated = Object.values(seats).reduce((n, l) => n + l.length, 0), left = (made.unseated || {})[key] || [];
    const room = seats[S.room] ? S.room : (Object.keys(seats)[0] || "");
    const trs = rooms.map(([name, cap, busy]) => {
      const list = seats[name] || [], d = duties.find(x => x.room === name);
      const by = {}; list.forEach(([sid]) => { const x = stuOf(sid); if (x) by[x[1]] = (by[x[1]] || 0) + 1; });
      const who = Object.keys(by).sort().map(c => `${esc(c)} (${by[c]})`).join(", ");
      const rain = busy.startsWith("rain room for");
      const first = list.length ? `<button type="button" class="linkb ${name === room ? "on" : ""}" data-act="pickRoom" data-a="${esc(name)}">${esc(name)}</button>` : esc(name);
      if (busy && !list.length) return `<tr class="busy"><td>${first}</td><td>0 / ${cap}</td><td class="muted" colspan="2">${esc(busy)} ${rain ? `<button type="button" class="small" data-act="useAnyway" data-a="${esc(key)}" data-b="${esc(name)}" ${S.busy ? "disabled" : ""}>Use it anyway</button>` : ""}</td></tr>`;
      if (!list.length) return `<tr class="muted"><td>${first}</td><td>0 / ${cap}</td><td class="small">Not needed for this sitting</td><td></td></tr>`;
      return `<tr><td>${first}</td><td>${list.length} / ${cap}${list.length > cap ? ` <span class="flag">+${list.length - cap}</span>` : ""}</td><td class="small">${who}</td>
        <td class="small">${d ? `${d.names.length}${d.chief ? " (1 chief)" : ""}` : ""}</td></tr>`;
    }).join("");
    const free = rooms.filter(r => !r[2]);
    const noSeat = left.length ? `<p class="flag small">${left.length} without a seat: ${left.map(s => esc(nameOf(s))).join(", ")}</p>` : "";
    return `${staleLine()}${seatChoices()}<div class="panel"><div class="line"><b>Sitting</b><select data-x="sit" data-f="x-sit" aria-label="Sitting">${sittingKeys().map(k => opt(k, key, sitLabel(k))).join("")}</select>
        <span class="chip ${left.length ? "bad" : "ok"}">${seated} seated</span></div>
      <div class="tablewrap"><table><thead><tr><th>Venue</th><th>Seats</th><th>Who</th><th>Invigilators</th></tr></thead><tbody>${trs}</tbody></table></div>${noSeat}</div>
      <div class="panel"><div class="row" style="justify-content:space-between"><h3 style="margin:0">${esc(room || "No room")} · seating plan</h3>
        <div class="row">${printLink("seating", "Seating plan")}${printLink("doors", "Door list")}${printLink("attendance", "Attendance sheet")}${printLink("classes", "Class lists")}</div></div>
        ${room ? seatGrid(key, room) : `<p class="muted">No one is seated in this sitting.</p>`}</div>
      ${moveBox(key, free)}`;
  }

  async function onVenue(el) {
    const x = el.dataset.x, v = el.value, key = curSit();
    if (x === "sit") { S.sit = v; S.room = ""; paint(); return; }
    if (x === "mvCls") { S.mvCls = v; S.mvStu = ""; paint(); return; }
    if (x === "mvStu") { S.mvStu = v; paint(); return; }
    if (!v || !key) return;
    const m = moveState(key);
    if (x === "mvClassTo" && m.mine.length) {
      const ids = m.mine.slice();
      if (await viewAction("move", { key, students: ids, room: v }, () => `Moved ${m.cur}, ${ids.length} ${ids.length === 1 ? "student" : "students"}, to ${v}.`)) { S.room = v; paint(); }
      return;
    }
    if (x === "mvStuTo" && m.stu) {
      const sid = m.stu;
      if (await viewAction("move", { key, students: [sid], room: v }, () => `Moved ${nameOf(sid)} to ${v}.`)) { S.room = v; paint(); }
    }
  }

  /* ---------------------------------------------------------------- tab 6: invigilators */
  const dutyEq = (d, p) => p && d.key === p.key && d.room === p.room;

  function dutyRow(d) {
    const flags = [];
    if (Object.keys(d.backup || {}).length) flags.push(`<span class="flag">Backup needed</span>`);
    if (d.short) flags.push(`<span class="flag">Short by ${d.short}</span>`);
    for (const [n, why] of Object.entries(d.not_free || {})) flags.push(`<span class="flag">Not free: ${esc(n)} ${esc(why)}</span>`);
    const names = d.names.map(n => `<div>${esc(n)}${d.chief === n ? ` <span class="chip">chief</span>` : ""}${(d.backup || {})[n] ? ` <span class="chip amber">backup</span>` : ""}
      <span class="muted small">${esc((d.reasons || {})[n] || "")}</span></div>`).join("");
    const sub = Object.keys((d.backup || {})).length ? `<div class="small muted">${Object.keys(d.backup).map(esc).join(", ")} teaches a lesson then</div>` : "";
    const n = (seatsOf(d.key)[d.room] || []).length;
    return `<tr class="${dutyEq(d, S.duty) ? "pick" : ""}"><td>${esc(fmtDate(d.date))}<br><span class="small muted">${hhmm(d.start)}–${hhmm(d.end)}</span></td>
      <td><b>${esc(d.room)}</b><br><span class="small muted">${esc(sitLabel(d.key).split(" · ").slice(2).join(" · "))}${n ? " · " + n : ""}</span></td>
      <td class="small">${names || `<span class="muted">No one yet</span>`}${d.locked ? ` <span class="chip">by hand</span>` : ""}</td>
      <td>${flags.length ? flags.join("<br>") + sub : `<span class="okc">✓</span>`}</td>
      <td><button type="button" class="small" data-act="duty" data-a="${esc(d.key)}" data-b="${esc(d.room)}">Who could take it</button></td></tr>`;
  }

  function whoPanel(made) {
    const p = S.duty;
    if (!p) return `<div class="panel"><h3>Who could take it</h3><p class="muted small">Press Who could take it on a duty.</p></div>`;
    const d = (made.duties || []).find(x => dutyEq(x, p));
    if (!d) return `<div class="panel"><h3>Who could take it</h3><p class="muted small">That duty is not there any more.</p></div>`;
    const head = `<h3>Who could take it</h3><p class="small"><b>${esc(d.room)}</b> · ${esc(fmtDate(d.date))} ${hhmm(d.start)}–${hhmm(d.end)}</p>
      <h4>Now</h4><div class="small">${d.names.map(n => `<div>${esc(n)}${(d.not_free || {})[n] ? ` <span class="flag">Not free: ${esc(d.not_free[n])}</span>` : ""} <button type="button" class="small danger" data-act="whoDrop" data-c="${esc(n)}" title="Take ${esc(n)} off" aria-label="Take ${esc(n)} off" ${S.busy ? "disabled" : ""}>✕</button></div>`).join("") || `<span class="muted">No one</span>`}</div>
      ${d.locked ? `<p class="small"><span class="muted">Chosen by hand: Make again keeps these names.</span> <button type="button" class="small" data-act="whoAuto" ${S.busy ? "disabled" : ""}>Let the app choose</button></p>` : ""}`;
    if (!S.who) return `<div class="panel">${head}<p class="muted small">Loading…</p></div>`;
    if (S.who.error) return `<div class="panel">${head}<p class="msg bad">${esc(S.who.error)}</p></div>`;
    const groups = [["freed", "Freed by the exam"], ["free", "Free then"], ["backups", "Backup invigilators"], ["need_backup", "Would need a backup"]];
    const body = groups.map(([k, title]) => {
      const list = (S.who[k] || []).filter(c => !d.names.includes(c.name));
      return `<h4>${title}</h4>${list.map(c => `<div class="small whorow"><div><b>${esc(c.name)}</b> <span class="muted">· ${c.minutes} min so far</span><br><span class="muted">${esc(c.reason)}</span></div>
        <button type="button" class="small" data-act="whoUse" data-c="${esc(c.name)}" ${S.busy ? "disabled" : ""}>Use</button></div>`).join("") || `<div class="small muted">No one</div>`}`;
    }).join("");
    return `<div class="panel">${head}${body}</div>`;
  }

  /* someone is away: the duty as it is on the main site, and who could take it (the approved copy, not the working one).
     The panel lists every duty of the approved copy, so a duty is reachable even when a change waiting for approval moved
     its sitting: the one picked here (S.aw.duty), else the approved duty of the duty picked in the table */
  const approvedDuties = () => onSite() ? ((S.sched.approved.made || {}).duties || []) : [];
  const approvedDuty = () => { const p = S.aw.duty || S.duty; return p ? approvedDuties().find(x => dutyEq(x, p)) || null : null; };

  async function loadAway(keep) {
    const d = approvedDuty(), tok = ++S.aw.tok;
    if (!d) { S.aw.data = null; return; }
    if (!keep) { S.aw.data = null; S.aw.err = ""; S.aw.say = ""; S.aw.away = d.names[0] || ""; S.aw.who = ""; paint(); }
    const r = await api("GET", `/api/exams/${S.id}/who?key=${encodeURIComponent(d.key)}&room=${encodeURIComponent(d.room)}&copy=approved`);
    if (tok !== S.aw.tok || r.status === 401 || r.status === 403) return;
    if (r.ok) { S.aw.data = r.j; S.aw.err = ""; } else { S.aw.data = null; S.aw.err = r.j.error || "Could not list who could take it."; }
    paint();
  }

  function awayPanel() {
    const list = approvedDuties(); if (!list.length) return "";
    const d = approvedDuty(), A = S.aw, G = A.data;
    const say = A.say ? `<p class="msg ok" role="status">${esc(A.say)}</p>` : "";
    const pick = `<div class="line"><b>Duty on the main site</b><select data-aw="duty" aria-label="Duty on the main site"><option value="">Choose a duty</option>${list.map(x => opt(`${x.key}|${x.room}`, d ? `${d.key}|${d.room}` : "", `${fmtDate(x.date)} ${hhmm(x.start)}–${hhmm(x.end)} · ${x.room}`)).join("")}</select></div>`;
    if (!d) return `<div class="panel"><h3>Someone is away</h3>${pick}<p class="muted small">Choose the duty on the main site that someone cannot do.</p>${say}</div>`;
    if (A.err) return `<div class="panel"><h3>Someone is away</h3>${pick}<p class="msg bad">${esc(A.err)}</p>${say}</div>`;
    if (!G) return `<div class="panel"><h3>Someone is away</h3>${pick}<p class="muted small">Loading…</p>${say}</div>`;
    const groups = [["freed", "Freed by the exam"], ["free", "Free then"], ["backups", "Backup invigilators"]];
    const names = groups.flatMap(([k]) => (G[k] || []).map(c => c.name));
    const who = names.includes(A.who) ? A.who : "";
    const sel = groups.map(([k, title]) => (G[k] || []).length ? `<optgroup label="${esc(title)}">${G[k].map(c => opt(c.name, who, `${c.name} · ${c.minutes} min so far`)).join("")}</optgroup>` : "").join("");
    return `${awayNotes((S.rv || {}).away)}<div class="panel"><h3>Someone is away</h3>${pick}<p class="muted small">This changes the duty on the main site now, without a new approval.</p>
      <div class="line"><b>Who is away</b><select data-aw="away" aria-label="Who is away">${d.names.map(n => opt(n, A.away)).join("")}</select></div>
      <div class="line"><b>Who takes it</b><select data-aw="who" aria-label="Who takes it"><option value="">Choose a name</option>${sel}</select></div>
      <div class="row"><button type="button" data-act="replace" ${S.busy ? "disabled" : ""}>Replace now</button></div>${say}</div>`;
  }

  async function replaceNow() {
    const d = approvedDuty(), A = S.aw;
    if (!d || !A.away || !A.who) { A.say = ""; S.bad = true; S.msg = "Choose who is away and who takes it."; paintSave(); return; }
    const name = A.who;
    const ok = await approvalAction("away", { key: d.key, room: d.room, away: A.away, name }, "");
    if (!ok) return;
    S.aw.say = `${name} takes the duty on the main site now. The timetable committee sees it under Done without approval.`;
    loadAway(false); S.aw.say = `${name} takes the duty on the main site now. The timetable committee sees it under Done without approval.`;
  }

  function loadList(made) {
    const mins = {};
    for (const d of made.duties || []) for (const n of d.names) { const m = mins[n] || (mins[n] = { n: 0, t: 0 }); m.n++; m.t += d.end - d.start; }
    const rows = Object.entries(mins).sort((a, b) => b[1].t - a[1].t || a[0].localeCompare(b[0]));
    const top = rows.length ? rows[0][1].t || 1 : 1;
    return `<div class="panel"><h3>Duty load · this exam</h3><table class="small">${rows.map(([n, m]) => `<tr><td>${esc(n)}</td><td style="width:40%"><div class="bar"><i style="width:${Math.round(100 * m.t / top)}%"></i></div></td><td>${m.n} · ${esc(fmtLen(m.t))}</td></tr>`).join("") || `<tr><td class="muted">No duties yet.</td></tr>`}</table></div>`;
  }

  function tabInvig() {
    const made = madeOf();
    if (!S.view || !made) return needMade();
    const duties = made.duties || [];
    return `${staleLine()}<div class="grid2"><div><div class="row" style="margin-bottom:10px">${printLink("roster-day", "Roster by day")}${printLink("roster-teacher", "Roster by teacher")}</div>
      <div class="tablewrap"><table><thead><tr><th>When</th><th>Venue</th><th>Invigilators</th><th>Check</th><th></th></tr></thead><tbody>${duties.map(dutyRow).join("") || `<tr><td colspan="5" class="muted" style="padding:10px">No duties.</td></tr>`}</tbody></table></div></div>
      <div>${whoPanel(made)}${awayPanel()}${loadList(made)}</div></div>`;
  }

  /* names: the names chosen by hand, or null to hand the duty back to the app */
  async function changeNames(names) {
    const p = S.duty; if (!p) return;
    const ok = await viewAction("invigilators", { key: p.key, room: p.room, names }, "Saved");
    if (ok) loadWho(true);
  }

  /* ---------------------------------------------------------------- tab 7: lessons */
  /* where one backup stands: the sentence for its state, and whether "Handled ourselves" can be ticked (not once it is stopped, past or sent by another schedule) */
  const BACKUP_STATE = {
    later: () => "Goes to the relief team when approved", sent: () => "Sent to the relief team", relief: l => `Relief: ${l.relief}`,
    handled: () => "Handled ourselves", stopped: l => `Not happening: ${l.stopped}`, past: () => "In the past", elsewhere: () => "Sent by another schedule"
  };
  const CAN_HANDLE = { later: 1, sent: 1, relief: 1, handled: 1 };
  function backupState(l) {
    const f = BACKUP_STATE[l.state]; if (!f) return "";
    const box = CAN_HANDLE[l.state] ? ` <label class="tick"><input type="checkbox" data-h="1" data-f="h:${esc(l.teacher)}|${esc(l.key)}" data-t="${esc(l.teacher)}" data-k="${esc(l.key)}" ${((S.hpend || {})[l.teacher + "|" + l.key] ?? l.state === "handled") ? "checked" : ""}> Handled ourselves</label>` : "";
    return `<div class="small muted">${esc(f(l))}${box}</div>`;
  }

  function lessonList(title, list, cls, extra, state) {
    const by = {}; list.forEach(l => { (by[l.date] = by[l.date] || []).push(l); });
    const days = Object.keys(by).sort().map(date => `<details data-d="${esc(title + date)}" ${S.open[title + date] ? "open" : ""}><summary>${esc(fmtDate(date))} · ${by[date].length}</summary>
      ${by[date].map(l => `<div class="small">${esc(l.start)}–${esc(l.end)} · ${esc((l.classes || []).join(", "))} ${esc(l.subject)}${(l.teachers || []).length ? " · " + esc(l.teachers.join(", ")) : ""}${l.note ? ` <span class="muted">· ${esc(l.note)}</span>` : ""}</div>${state ? state(l) : ""}`).join("")}</details>`).join("");
    return `<div class="panel ${cls}"><h3>${esc(title)} · ${list.length} ${list.length === 1 ? "lesson" : "lessons"}</h3>${days || `<div class="small muted">None.</div>`}${extra || ""}</div>`;
  }

  function tabLessons() {
    const L = S.view && S.view.lessons;
    if (!L) return `<div class="card"><p class="muted">Loading…</p></div>`;
    return `<div class="grid3">
      ${lessonList("No relief needed", L.none || [], "okbg")}
      ${lessonList("Backup needed", L.backup || [], "ambg", `<p class="muted small" style="margin-top:10px">Backups go to the relief team as planned relief when the schedule is approved.</p>`, backupState)}
      ${lessonList("Runs as usual", L.runs || [], "")}</div>`;
  }

  /* ---------------------------------------------------------------- the event editor */
  function tabEvWhen() {
    const s = S.sched, V = S.view;
    const lv = S.levels.map(l => `<label class="tick"><input type="checkbox" ${at("level", l)} ${s.levels.includes(l) ? "checked" : ""}> ${esc(l)}</label>`).join("");
    const cl = S.classes.map(([c, l]) => `<label class="tick" title="${esc(l)}"><input type="checkbox" ${at("class", c)} ${s.classes.includes(c) ? "checked" : ""}> ${esc(c)}</label>`).join("");
    const days = (V && V.summary.days) || [];
    const rows = V ? days.map(dayRow).join("") : `<tr><td colspan="4" class="muted">Loading…</td></tr>`;
    const rooms = ((V && V.rooms) || []).map(r => `<label class="tick"><input type="checkbox" ${at("venue", r)} ${(s.venues || []).includes(r) ? "checked" : ""}> ${esc(r)}</label>`).join("");
    const bad = l => `<div><span class="flag">●</span> ${esc(l)}</div>`;
    const clashes = V ? ((V.clashes || []).map(bad).join("") || `<div><span class="okc">✓</span> No clashes.</div>`) : `<p class="muted">Loading…</p>`;
    const flags = V && (V.flags || []).length ? `<h3>Lessons that use a venue taken</h3>${V.flags.map(bad).join("")}` : "";
    const cuts = V && (V.cuts || []).length ? V.cuts.map(bad).join("") : "";
    return `<div class="card form"><div class="line"><b>What is it</b><span>Event</span></div>
      <div class="line"><b>Name</b><input type="text" ${at("name")} value="${esc(s.name)}" maxlength="120" placeholder="e.g. Sec 2 Learning Journey" aria-label="Name"></div>
      <div class="line"><b>Who</b><span class="chiprow">${lv}</span></div>
      <div class="line"><b></b><details class="pickc" ${s.classes.length ? "open" : ""}><summary>Or pick classes</summary><div class="classes">${cl}</div></details></div>
      <div class="line"><b>Dates</b><input type="date" ${at("start")} value="${esc(s.start)}" aria-label="First day"> to <input type="date" ${at("end")} value="${esc(s.end)}" aria-label="Last day"></div>
      <div class="line"><b>Where</b><input type="text" ${at("where")} value="${esc(s.where || "")}" maxlength="120" placeholder="Off site (museum)" aria-label="Where"></div>
      <div class="line"><b>Venues in school</b><span class="chiprow">${rooms || `<span class="muted small">Loading…</span>`}</span></div>
      <p class="muted small">Venues ticked here are taken: exams and other events cannot use them then.</p></div>
      <div class="card"><h2>Each day</h2><div class="tablewrap"><table class="daytable"><thead><tr><th>Date</th><th>Timetable day</th><th>Levels going</th><th>How much of the day</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="muted small">A level that is not going on a day keeps its full timetable that day. On a part day, lessons stop from the first time to the second and run as usual outside it.</p></div>
      <div class="card"><h2>Clashes</h2>${clashes}${flags}${cuts ? `<h3>Where the time cuts a lesson</h3>${cuts}` : ""}</div>`;
  }

  const goingRows = () => (S.sched.going || []).map(n => {
    const g = ((S.view && S.view.going) || []).find(x => x.name === n);
    const text = g ? `<span class="${g.status === "free" ? "muted" : g.status === "backup" ? "amber" : "flag"} small">${esc(g.text)}</span>` : "";
    return `<tr><td>${esc(n)}${g && g.tag ? ` · ${esc(g.tag)}` : ""}</td><td>${text}</td>
      <td><button type="button" class="small danger" data-act="goDrop" data-a="${esc(n)}" title="Take ${esc(n)} off the list" aria-label="Take ${esc(n)} off the list">✕</button></td></tr>`;
  }).join("");

  function dutyEvRow(d, i) {
    const names = S.sched.going || [];
    const who = names.includes(d.who) || !d.who ? names : names.concat([d.who]);
    return `<tr><td><input type="text" ${at("evDuty", i)} value="${esc(d.duty)}" maxlength="120" placeholder="e.g. Bus captain" aria-label="Duty"></td>
      <td><select ${at("evWho", i)} aria-label="Who does the duty"><option value="">Choose a name</option>${who.map(n => opt(n, d.who)).join("")}</select></td>
      <td><input type="text" ${at("evTime", i)} value="${esc(d.time)}" maxlength="60" placeholder="e.g. 07:30 at the gate" aria-label="Time"></td>
      <td><button type="button" class="small danger" data-act="dutyDel" data-a="${i}" title="Take this duty off" aria-label="Take this duty off">✕</button></td></tr>`;
  }

  function awayEv() {
    const ap = onSite() ? (S.sched.approved.going || []) : [];
    if (!ap.length) return "";
    const A = S.aw, G = A.data;
    const say = A.say ? `<p class="msg ok" role="status">${esc(A.say)}</p>` : "";
    if (A.err) return `<div class="card"><h2>Someone is away</h2><p class="msg bad">${esc(A.err)}</p>${say}</div>`;
    if (!G) return `<div class="card"><h2>Someone is away</h2><p class="muted small">Loading…</p>${say}</div>`;
    const groups = [["freed", "Freed by the event"], ["free", "Free then"]];
    const names = groups.flatMap(([k]) => (G[k] || []).map(c => c.name));
    const who = names.includes(A.who) ? A.who : "";
    const sel = groups.map(([k, title]) => (G[k] || []).length ? `<optgroup label="${esc(title)}">${G[k].map(c => opt(c.name, who, `${c.name} · ${c.reason}`)).join("")}</optgroup>` : "").join("");
    return `${awayNotes((S.rv || {}).away)}<div class="card"><h2>Someone is away</h2><p class="muted small">This changes who goes on the main site now, without a new approval.</p>
      <div class="line"><b>Who is away</b><select data-aw="away" aria-label="Who is away">${ap.map(n => opt(n, A.away)).join("")}</select></div>
      <div class="line"><b>Who takes it</b><select data-aw="who" aria-label="Who takes it"><option value="">Choose a name</option>${sel}</select></div>
      <div class="row"><button type="button" data-act="evReplace" ${S.busy ? "disabled" : ""}>Replace now</button></div>${say}</div>`;
  }

  async function loadEvAway(keep) {
    if (!onSite()) return;
    const tok = ++S.aw.tok;
    if (!keep) { S.aw.data = null; S.aw.err = ""; S.aw.say = ""; S.aw.away = (S.sched.approved.going || [])[0] || ""; S.aw.who = ""; if (S.tab === "egoes") paint(); }
    const r = await api("GET", `${S.base}/${S.id}/who`);
    if (tok !== S.aw.tok || r.status === 401 || r.status === 403) return;
    if (r.ok) { S.aw.data = r.j; S.aw.err = ""; } else { S.aw.data = null; S.aw.err = r.j.error || "Could not list who could take it."; }
    if (S.tab === "egoes") paint();
  }

  async function evReplace() {
    const A = S.aw;
    if (!A.away || !A.who) { S.bad = true; S.msg = "Choose who is away and who takes it."; paintSave(); return; }
    const name = A.who, say = `${name} goes in their place on the main site now. The timetable committee sees it under Done without approval.`;
    const ok = await approvalAction("away", { away: A.away, name }, "");
    if (!ok) return;
    await loadEvAway(false); S.aw.say = say; if (S.tab === "egoes") paint();
  }

  function tabEvGoes() {
    const s = S.sched, V = S.view, going = s.going || [];
    const classes = V && (V.classes || []).length ? V.classes.join(", ") : "the classes";
    const notGoing = ((V && V.people) || []).filter(n => !going.includes(n));
    const depts = (V && V.depts) || [];
    const me = S.ev;
    const nB = going.filter(n => { const g = ((V && V.going) || []).find(x => x.name === n); return g && g.status === "backup"; }).length;
    const pick = (V && V.people) ? `<div class="line"><b>Pick people</b><select data-ev="pick" aria-label="Pick people"><option value="">Choose a name</option>${notGoing.map(n => opt(n, me.pick)).join("")}</select> <button type="button" data-act="goPick">Add</button></div>` : "";
    const dept = depts.length ? `<div class="line"><b>A department</b><select data-ev="dept" aria-label="A department"><option value="">Choose a department</option>${depts.map(d => opt(d, me.dept)).join("")}</select> <button type="button" data-act="goDept">Add</button></div>` : "";
    return `<div class="card"><h2>Who goes</h2>
      <div class="row"><button type="button" data-act="goFill" data-a="form teachers">Form teachers of ${esc(classes)}</button><button type="button" data-act="goFill" data-a="teachers then">Teachers who'd teach them then</button></div>
      ${dept}${pick}
      ${S.note ? `<p class="msg ok" role="status">${esc(S.note)}</p>` : ""}
      <div class="tablewrap"><table><tbody>${goingRows() || `<tr><td class="muted">No one yet.</td></tr>`}</tbody></table></div>
      <p class="small">${going.length} going · ${nB} with lessons that need backup</p></div>
      <div class="card"><h2>Duties at the event</h2><div class="tablewrap"><table><thead><tr><th>Duty</th><th>Who</th><th>Time</th><th></th></tr></thead><tbody>${(s.duties || []).map(dutyEvRow).join("")}</tbody></table></div>
      <div class="row"><button type="button" data-act="dutyAdd">+ Add a duty</button></div></div>${awayEv()}`;
  }

  function tabEvLessons() {
    const fr = (S.view && S.view.freed) || [];
    const freed = fr.length ? `<div class="card"><h2>Venues freed</h2>${fr.map(f => `<p class="small">Venues freed: ${esc(f.rooms.join(", "))} on ${esc(fmtDate(f.date))} ${esc(f.start)}–${esc(f.end)} (could be used for a make-up paper)</p>`).join("")}</div>` : "";
    return tabLessons() + freed;
  }

  function onEventField(el, k, a, b) {
    const s = S.sched, v = el.value;
    if (k === "where") return edit(() => { s.where = v; });
    if (k === "venue") return edit(() => { s.venues = el.checked ? uniq((s.venues || []).concat([a])) : (s.venues || []).filter(x => x !== a); });
    if (k === "evDuty") return edit(() => { s.duties[+a].duty = v; });
    if (k === "evTime") return edit(() => { s.duties[+a].time = v; });
    if (k === "evWho") return edit(() => { s.duties[+a].who = v; });
    return onWhenField(el, k, a, b);
  }

  /* an event's three ways of filling the list, and the two that add the chosen names */
  function goFill(way, dept, names) {
    const before = (S.sched.going || []).length;
    serverAction("POST", `${S.base}/${S.id}/fill`, { way, dept, names }, undefined, j => { const n = (j.going || []).length - before; S.note = n > 0 ? `Added ${n} ${n === 1 ? "person" : "people"}.` : "There is no one new to add."; });
  }

  /* ---------------------------------------------------------------- tab 8: approval */
  const onSite = () => !!(S.sched && S.sched.approved && (S.sched.status === "approved" || S.sched.status === "changes"));
  const CHECK_NAMES = { papers: "Paper times", seats: "Seats", free: "Invigilators free", others: "Other schedules", timetable: "Timetable", going: "People going", venues: "Venues" };
  const stamp = at => at ? `${fmtDate(String(at).slice(0, 10))} ${esc(String(at).slice(11, 16))}` : "";

  /* the review's answer is the page's: it also brings the status, which is kept on the schedule and the chip */
  function takeReview(j) {
    S.rv = j; S.rvErr = "";
    S.label = j.label || S.label; S.sched.status = j.status; S.sched.note = j.note;
  }

  async function loadReview(keep) {
    const tok = ++S.rvTok;
    if (!keep) { S.rv = null; S.rvErr = ""; if (S.tab === "approval") paint(); }
    await flush();
    const r = await api("GET", `${S.base}/${S.id}/review`);
    if (tok !== S.rvTok || r.status === 401 || r.status === 403) return;
    if (r.ok) takeReview(r.j); else { S.rv = null; S.rvErr = r.j.error || "Could not read the approval."; }
    const chip = $("#statchip"); if (chip) { chip.textContent = S.label; chip.className = "chip " + chipClass({ label: S.label }); }
    if (S.tab === "approval") paint();
  }

  /* send, approve, send back, withdraw: the schedule is read again afterwards, because the approved copy moves with them */
  async function approvalAction(path, body, ok) {
    if (S.busy) return false;
    await flush();
    if (S.dirty) return false;
    S.busy = true; S.msg = ""; S.bad = false; paintSave(); paint();
    const r = await api("POST", `${S.base}/${S.id}/${path}`, body);
    S.busy = false;
    if (r.status === 401 || r.status === 403) return false;
    if (!r.ok) { S.bad = true; S.msg = r.j.error || "That did not work. Try again."; S.abMsg = S.msg; paintSave(); paint(); return false; }
    S.abMsg = "";
    const g = await api("GET", `${S.base}/${S.id}`);
    if (g.ok) S.sched = g.j;
    takeReview(r.j); S.sbNote = ""; S.msg = ok || ""; paintSave();
    render(); refreshView();
    return true;
  }

  /* the same clash can be in both Invigilators free ("is on {schedule} then") and Other schedules ("takes {n} of these
     invigilators on {date}"): a "takes" line goes only when the free lines name that same schedule on that date for at least
     n people (not the own-duty "is on another duty then"), so a second person's clash never drops out of sight */
  function checkLines(c, all) {
    let lines = c.lines;
    if (c.key === "others" && !c.ok) {
      const free = (all.find(x => x.key === "free") || { lines: [] }).lines;
      lines = lines.filter(l => {
        const m = /^(.*) \([^()]*\) takes (\d+) of these invigilators on (.*)\.$/.exec(l); if (!m) return true;
        const named = uniq(free.filter(f => f.includes(` is on ${m[1]} then`) && f.includes(` on ${m[3]} `)).map(f => f.split(", ")[0]));
        return named.length < +m[2];
      });
    }
    return lines;
  }

  function checksBlock(rv) {
    const rows = rv.checks.map(c => {
      const lines = checkLines(c, rv.checks);
      if (!lines.length) return "";
      return `<div class="checks"><b>${esc(CHECK_NAMES[c.key] || c.key)}</b>${c.ok ? lines.map(l => `<div><span class="okc">✓</span> ${esc(l)}</div>`).join("") : lines.map(l => `<div><span class="flag">●</span> ${esc(l)}</div>`).join("")}</div>`;
    }).join("");
    return `<div class="card"><h2>Checks</h2>${rows}</div>`;
  }

  function whatBlock(w) {
    const part = w.days.filter(d => !d.whole), all = w.days.length;
    const when = !part.length ? "whole days" : part.length === all ? "part of the day" : `whole days, part day on ${part.map(d => esc(fmtDate(d.date))).join(", ")}`;
    const venues = w.venues.map(v => `${esc(v.room)} ${esc(v.start)}–${esc(v.end)} on ${nTimes(v.dates, "day", "days")}`).join("; ");
    if (w.kind === "event") {
      return `<div class="card"><h2>What changes on the main site</h2>
      <p>Classes ${esc(w.classes.join(", ") || "none")} (${esc(w.levels.join(", ") || "none")})${w.where ? " · " + esc(w.where) : ""} · ${when}</p>
      <p>Lessons that won't happen: ${w.stopped} (no relief needed)</p>
      <p>People going: ${w.going} · lessons that need backup: ${w.backups} (sent to the relief team when approved)</p>
      <p>Venues taken: ${venues || "none"}</p>
      <p>Lessons that use a venue taken: ${w.flagged}</p></div>`;
    }
    const anyway = (w.anyway || []).map(a => { const [d, t] = String(a.key).split(" "); return `${esc(a.room)} ${esc(fmtDate(d))} ${esc(t || "")}`.trim(); }).join("; ");
    return `<div class="card"><h2>What changes on the main site</h2>
      <p>Classes ${esc(w.classes.join(", ") || "none")} (${esc(w.levels.join(", ") || "none")}) · ${nTimes(w.papers, "paper", "papers")} · ${when}</p>
      <p>Lessons that won't happen: ${w.stopped} (no relief needed)</p>
      <p>Teachers with duties: ${w.teachers} · ${nTimes(w.duties, "duty", "duties")}${w.most ? ` · most: ${esc(w.most[0])}, ${w.most[1]}` : ""}</p>
      <p>Backups for the relief team: ${w.backups} (sent when approved)</p>
      <p>Venues taken: ${venues || "none"}</p>
      ${anyway ? `<p>Rain rooms used anyway: ${anyway}</p>` : ""}</div>`;
  }

  function sendBox(title, lead, label, path, why) {
    return `<div class="card"><h2>${title}</h2>${lead ? `<p>${lead}</p>` : ""}<div class="row"><button type="button" class="primary" data-act="approval" data-a="${path}" ${S.busy || why ? "disabled" : ""}>${label}</button>${why ? `<span class="muted small">${esc(why)}</span>` : ""}</div></div>`;
  }

  function tabApproval() {
    const rv = S.rv;
    if (S.rvErr) return `<div class="card"><p class="muted">${esc(S.rvErr)}</p></div>`;
    if (!rv) return `<div class="card"><p class="muted">Loading…</p></div>`;
    const st = rv.status, why = rv.can_send || "", unsent = rv.unsent || [], me = S.me.can_approve;
    const out = [`<div class="card"><h2>Approval</h2><p><span class="chip ${chipClass({ label: rv.label })}">${esc(rv.label)}</span></p>
      ${S.abMsg ? `<p class="msg bad" role="status">${esc(S.abMsg)}</p>` : ""}${rv.note ? `<p>Sent back by the timetable committee: “${esc(rv.note)}”</p>` : ""}</div>`];
    if ((rv.away || []).length) out.push(awayNotes(rv.away));
    if (st === "draft" || st === "withdrawn") out.push(sendBox("Send to the timetable committee", "", "Send to the timetable committee", "send", why));
    if ((st === "waiting" || st === "changes") && rv.changed) out.push(sendBox("Send again", "Changed since you sent it: send it again.", "Send again", "send", why));
    if (st === "approved" && unsent.length) out.push(`<div class="card"><h2>Changes not sent yet</h2>${unsent.map(c => `<p>${esc(c.text)}</p>`).join("")}<div class="row"><button type="button" class="primary" data-act="approval" data-a="send" ${S.busy || why ? "disabled" : ""}>Send the changes</button>${why ? `<span class="muted small">${esc(why)}</span>` : ""}</div></div>`);
    if (st === "approved" && !unsent.length) out.push(`<div class="card"><p class="muted">Nothing on the main site has changed since it was approved.</p></div>`);
    if (st === "changes" && rv.review.changes.length) out.push(`<div class="card"><h2>${me ? "Changes waiting for you" : "Changes waiting for the timetable committee"}</h2>${rv.review.changes.map(c => `<p>${esc(c.text)}</p>`).join("")}</div>`);
    out.push(whatBlock(rv.review.what), checksBlock(rv.review));
    if (me && (st === "waiting" || st === "changes")) {
      out.push(`<div class="card"><h2>${st === "waiting" ? "Approve: show on the main site" : "Approve the changes"}</h2><div class="row"><button type="button" class="primary" data-act="approval" data-a="approve" ${S.busy ? "disabled" : ""}>${st === "waiting" ? "Approve: show on the main site" : "Approve the changes"}</button></div></div>
        <div class="card"><h2>Send back with a note</h2><div class="line"><input type="text" data-sb="1" data-f="sb" value="${esc(S.sbNote)}" maxlength="300" placeholder="What ${isEv() ? "the teacher in charge" : "the exams committee"} should change" aria-label="Note for ${isEv() ? "the teacher in charge" : "the exams committee"}"></div>
        <div class="row"><button type="button" data-act="approval" data-a="send-back" ${S.busy ? "disabled" : ""}>Send back</button></div></div>`);
    }
    if (me && (st === "approved" || st === "changes")) out.push(`<div class="card"><h2>Withdraw from the main site</h2><div class="row"><button type="button" class="danger" data-act="approval" data-a="withdraw" ${S.busy ? "disabled" : ""}>Withdraw from the main site</button></div></div>`);
    const dw = rv.review.done_without || [];
    if (dw.length) out.push(`<div class="card"><h2>Done without approval</h2>${dw.map(e => `<p>${esc(e.detail)} · by ${esc(e.by)}, ${stamp(e.at)}</p>`).join("")}</div>`);
    return out.join("");
  }

  async function onApproval(a) {
    if (a === "send-back") return approvalAction("send-back", { note: S.sbNote }, "Sent back.");
    if (a === "withdraw") {
      if (!confirm(`Take ${S.sched.name} off the main site now?`)) return;
      return approvalAction("withdraw", {}, "Taken off the main site.");
    }
    return approvalAction(a, {}, a === "approve" ? "Approved." : "Sent.");
  }

  /* ---------------------------------------------------------------- events */
  function onField(e) {
    const el = e.target;
    if (S.id && el.dataset.x) { onVenue(el); return; }
    if (S.id && el.dataset.mk) { onMakeup(el); return; }
    if (S.id && el.dataset.aw === "duty") { const v = el.value, i = v.indexOf("|"); S.aw.duty = v ? { key: v.slice(0, i), room: v.slice(i + 1) } : null; loadAway(false); paint(); return; }
    if (S.id && el.dataset.aw) { S.aw[el.dataset.aw] = el.value; return; }
    if (S.id && el.dataset.sb) { S.sbNote = el.value; return; }
    if (S.id && el.dataset.acc === "cls") { S.accCls = el.value; paint(); return; }
    if (!S.id && el.dataset.nf) { onNewField(el); return; }
    if (!S.id && el.dataset.ne) { onNewEvField(el); return; }
    if (S.id && el.dataset.ev) { S.ev[el.dataset.ev] = el.value; return; }
    if (!S.id || !S.sched) return;
    const k = el.dataset.k, a = el.dataset.a, b = el.dataset.b;
    if (!k) return;
    if (isEv()) { onEventField(el, k, a, b); return; }
    if (k === "name" || k === "start" || k === "end" || k === "sup" || k === "scripts" || k === "level" || k === "class" || k.startsWith("day") || k === "time") onWhenField(el, k, a, b);
    else if (k.startsWith("a")) onAccessField(el, k, a);
    else onPaperField(el, k, a);
  }

  /* text boxes are read as they are typed, the rest when they are changed */
  function onInput(e) {
    const el = e.target, ty = el.type;
    if (el.tagName === "SELECT" || ty === "checkbox" || ty === "date" || ty === "file") return;
    onField(e);
  }
  /* "Handled ourselves": the answer is the schedule's view again (the Lessons tab reads it); the Approval counts are read again */
  async function onHandled(el) {
    if (S.busy) { el.checked = !el.checked; return; }
    const tag = el.dataset.t + "|" + el.dataset.k;
    S.busy = true; S.msg = ""; S.bad = false; S.hpend = { [tag]: !!el.checked }; paintSave();
    const r = await api("POST", `${S.base}/${S.id}/handled`, { teacher: el.dataset.t, key: el.dataset.k, handled: !!el.checked });
    S.busy = false; S.hpend = {};
    if (r.status === 401 || r.status === 403) { paint(); return; }
    if (!r.ok) { S.bad = true; S.msg = r.j.error || "That did not work. Try again."; paintSave(); paint(); return; }
    S.view = r.j; S.rv = null; paintSave(); paint();
  }

  function onChange(e) {
    const el = e.target, ty = el.type;
    if (ty === "checkbox" && el.dataset.h && S.id) { onHandled(el); return; }
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

  function onNewEvField(el) {
    const ne = S.ne, k = el.dataset.ne, v = el.value;
    if (k === "level" || k === "class") {
      const key = k === "level" ? "levels" : "classes";
      ne[key] = el.checked ? uniq(ne[key].concat([el.dataset.v])) : ne[key].filter(x => x !== el.dataset.v);
    } else {
      ne[k] = v;
      if (k === "start" && v && (!ne.end || ne.end < v)) { ne.end = v; const e = $('[data-ne="end"]'); if (e) e.value = v; }   /* the last day starts as the first */
    }
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
      else if (act === "evOpen") { S.ne.open = true; drawList(); const n = $('[data-ne="name"]'); if (n) n.focus(); }
      else if (act === "evCancel") { S.ne = blankEv(); drawList(); }
      else if (act === "evSave") evSave();
      return;
    }
    if (!s) return;
    if (act === "tab") { S.tab = a; S.note = ""; render(); if (a === "approval") { S.abMsg = ""; loadReview(false); } if (a === "egoes") loadEvAway(false); return; }
    if (isEv()) {
      if (act === "goFill") { goFill(a, "", []); return; }
      if (act === "goDept") { if (!S.ev.dept) { S.note = ""; S.bad = true; S.msg = "Pick a department."; paintSave(); return; } goFill("department", S.ev.dept, []); return; }
      if (act === "goPick") { if (!S.ev.pick) { S.bad = true; S.msg = "Pick a person."; paintSave(); return; } const n = S.ev.pick; S.ev.pick = ""; goFill("people", "", [n]); return; }
      if (act === "goDrop") { edit(() => { s.going = (s.going || []).filter(x => x !== a); (s.duties || []).forEach(d => { if (d.who === a) d.who = ""; }); }, true); return; }
      if (act === "dutyAdd") { edit(() => { s.duties = (s.duties || []).concat([{ duty: "", who: "", time: "" }]); }, true); return; }
      if (act === "dutyDel") { edit(() => { s.duties.splice(Number(a), 1); }, true); return; }
      if (act === "evReplace") { evReplace(); return; }
    }
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
    if (act === "make") { viewAction("make", {}, "Made."); return; }
    if (act === "pickRoom") { S.room = a; paint(); return; }
    if (act === "seatOpt") {
      const v = a === "home_rooms" ? b.dataset.b === "true" : b.dataset.b;
      edit(() => { s.seating = Object.assign({}, s.seating, { [a]: v }); }, true);
      return;
    }
    if (act === "useAnyway") { viewAction("use-anyway", { key: a, room: b.dataset.b }, "The room is in use for this sitting."); return; }
    if (act === "duty") { S.duty = { key: a, room: b.dataset.b }; S.aw.duty = null; loadWho(false); loadAway(false); return; }
    if (act === "approval") { onApproval(a); return; }
    if (act === "replace") { replaceNow(); return; }
    if (act === "whoAuto") { changeNames(null); return; }
    if (act === "whoDrop" || act === "whoUse") {
      const p = S.duty, d = p && ((madeOf() || {}).duties || []).find(x => dutyEq(x, p)), n = b.dataset.c;
      if (!d) return;
      changeNames(act === "whoDrop" ? d.names.filter(x => x !== n) : uniq(d.names.concat([n])));
      return;
    }
    if (act === "accDel") { edit(() => { s.access.splice(Number(a), 1); }, true); return; }
  }

  /* the sentence kept for the editor is dropped when the editor does not open, so it does not turn up on a later visit */
  function dropNote() { try { sessionStorage.removeItem("examsNote"); } catch (e) { /* no storage */ } }

  async function startOne(id, ev) {
    links();
    S.id = id;
    if (ev) { S.base = "/api/events"; S.tabs = EV_TABS; S.tab = "ewhen"; }
    const [r, v, l, me] = await Promise.all([api("GET", `${S.base}/${id}`), api("GET", `${S.base}/${id}/view`), api("GET", ev ? "/api/events" : "/api/exams"), api("GET", "/api/exams/me")]);
    for (const x of [r, v, l, me]) if (x.status === 401 || x.status === 403) { dropNote(); return; }
    for (const x of [r, v, l, me]) if (!x.ok) { dropNote(); fail(x.j.error || "Something went wrong."); return; }
    S.me = me.j; links(S.me.can_use); S.label = ((l.j.schedules || []).find(x => x.id === id) || {}).label || "Draft";
    S.sched = r.j; S.view = v.j; S.levels = l.j.levels || []; S.classes = l.j.classes || [];
    document.title = r.j.name + (ev ? " · Events" : " · Exams");
    render();
    try {
      const n = sessionStorage.getItem("examsNote");
      if (n) { sessionStorage.removeItem("examsNote"); S.bad = true; S.msg = n; paintSave(); }
    } catch (e) { /* no storage */ }
  }

  document.addEventListener("click", onClick);
  document.addEventListener("input", onInput);
  document.addEventListener("change", onChange);
  document.addEventListener("toggle", e => { const d = e.target; if (d && d.dataset && d.dataset.d) S.open[d.dataset.d] = d.open; }, true);
  window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
  const m = /^\/exams\/([A-Za-z0-9]+)\/?$/.exec(location.pathname), me2 = /^\/events\/([A-Za-z0-9]+)\/?$/.exec(location.pathname);
  if (me2) startOne(me2[1], true); else if (m && m[1] !== "settings") startOne(m[1], false); else startList();
})();

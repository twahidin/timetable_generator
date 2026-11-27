"use strict";
/* Term Relief Report (/relief#load), for the relief team (me.can_team): who has taken how much relief, from /api/relief/load. One row a
   teacher: teaching this week, relief this week, exams and events this week (periods more for exam duties and events, fewer
   for lessons that stop; the column shows only in a week that has any), week so far, relief this term, requests to change
   this term. This week lists whoever has teaching, relief or a duty this week; This term whoever has relief or a request to change this term. Filters:
   a department and "Flexi Adjunct only". Download gives the same rows as a spreadsheet (/api/relief/load.csv). A name opens
   their reliefs this term (/api/relief/load/<name>): date, lesson, whose class, the pick's reason and who approved it; a
   relief not yet approved is labelled "waiting" or "new pick" so it is not read as a relief taken, and one whose lesson an
   exam or event stops "not happening". */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day, enc = encodeURIComponent, say = R.say;
  const $ = (s, el = document) => el.querySelector(s);
  const L = { pane: null, data: null, err: null, seq: 0, loading: false, view: "week", dept: "", fat: false, open: null, one: null,
              oneErr: null, oneSeq: 0, msg: null };
  const BY = { ai: "AI", app: "the app's order", planner: "the planner", team: "the relief team" };
  const LABEL = { waiting: "waiting", "new pick": "new pick", "not happening": "not happening" };

  const query = () => (L.view === "term" && L.data && L.data.term ? `?term=${enc(L.data.term.name)}` : "");
  const rows = () => (L.data && Array.isArray(L.data.rows) ? L.data.rows : []);
  const shown = () => rows().filter(r => (L.view === "week" ? r.week > 0 || r.teaching > 0 || r.relief > 0 : r.term > 0 || r.changes > 0) && (!L.dept || (r.depts || []).includes(L.dept)) && (!L.fat || r.fat));
  const depts = () => [...new Set(rows().flatMap(r => r.depts || []))].sort();

  function reliefRow(v) {
    const lab = LABEL[v.state], by = BY[v.by] || "";
    const who = lab ? `<span class="chip st-amber">${esc(lab)}</span>` : v.approved_by ? `approved by ${esc(v.approved_by)}` : `<span class="muted">—</span>`;
    return `<tr class="${lab ? "ld-wait" : ""}"><td>${esc(day(v.date))}</td><td>${esc(v.lesson)}<div class="small muted">${esc(`${v.start}–${v.end}`)}</div></td>
      <td>${esc(v.absent)}</td><td>${by ? `<span class="td-by">${esc(by)}</span> ` : ""}${esc(v.reason || "")}</td><td>${who}</td></tr>`;
  }

  function oneHTML() {
    if (!L.open) return "";
    const close = `<button type="button" class="small" data-ld="close">Close</button>`, name = esc(L.open);
    if (L.oneErr) return `<div class="card ld-one"><div class="ab-top"><h3>${name}</h3>${close}</div><p>${say(L.oneErr)}</p></div>`;
    if (!L.one) return `<div class="card ld-one"><div class="ab-top"><h3>${name}</h3>${close}</div><p class="muted">Loading…</p></div>`;
    const list = L.one.reliefs || [], t = L.one.term;
    return `<div class="card ld-one" id="ldOne" tabindex="-1"><div class="ab-top"><div><h3>${name}: reliefs ${t ? `this term (${esc(t.name)})` : "this term"}</h3>
      <div class="small muted">A relief marked “waiting” or “new pick” is not approved yet: it is not a relief taken. One marked “not happening” was stopped by an exam or event and does not count.</div></div>${close}</div>
      ${list.length ? `<div class="tablewrap"><table class="rtable"><thead><tr><th>Date</th><th>Lesson</th><th>Whose class</th><th>Why they were picked</th><th>Approved</th></tr></thead>
        <tbody>${list.map(reliefRow).join("")}</tbody></table></div>` : `<p class="muted">No reliefs this term.</p>`}</div>`;
  }

  function paint() {
    const box = $("#ldBox", L.pane);
    if (!box) return;
    if (!L.data) {
      box.innerHTML = L.err ? `<div class="card"><p>${say(L.err)}</p><p><button type="button" data-ld="reload">Try again</button></p></div>` : `<div class="card"><p class="muted">Loading…</p></div>`;
      return;
    }
    const d = L.data, list = shown(), w = d.week || {}, t = d.term;
    const seg = [["week", "This week"], ["term", "This term"]].map(([k, l]) => `<button type="button" data-ld="view" data-v="${k}" class="${k === L.view ? "on" : ""}" aria-pressed="${k === L.view ? "true" : "false"}"${k === "term" && !t ? " disabled" : ""}>${l}</button>`).join("");
    const opts = [`<option value="">All departments</option>`].concat(depts().map(x => `<option value="${esc(x)}"${x === L.dept ? " selected" : ""}>${esc(x)}</option>`)).join("");
    const about = [w.start ? `Week of ${day(w.start)}` : "", t ? t.name : "no term set"].filter(Boolean).join(" · ");
    const exams = rows().some(r => Number(r.exams)), signed = v => Number(v) > 0 ? `+${v}` : Number(v) < 0 ? `−${-v}` : "0";
    const cols = [["Teaching this week", "teaching"], ["Relief this week", "relief"], ...(exams ? [["Exams and events this week", "exams"]] : []), ["Week so far", "week"], ["Relief this term", "term"], ["Requests to change this term", "changes"]];
    box.innerHTML = `<div class="card ld">
      <div class="ab-top"><div><h2>Term Relief Report</h2><div class="small muted">${esc(about)}</div></div>
        <div class="row"><button type="button" class="small" data-ld="reload" ${L.loading ? "disabled" : ""}>${L.loading ? "Reading…" : "Refresh"}</button><button type="button" class="small" data-ld="csv">Download</button></div></div>
      <div class="line ld-filters"><div class="seg" role="group" aria-label="Which period">${seg}</div>
        <span class="ld-dept"><label class="small muted" for="ldDept">Department</label><select id="ldDept" data-ld="dept">${opts}</select></span>
        <label class="small"><input type="checkbox" data-ld="fat" ${L.fat ? "checked" : ""}> Flexi Adjunct only</label></div>
      <div id="ldMsg" aria-live="polite">${L.msg ? say(L.msg) : ""}</div>
      ${L.err ? `<p>${say(L.err)}</p>` : ""}
      ${list.length ? `<div class="tablewrap"><table class="rtable ld-table"><thead><tr><th>Teacher</th>${cols.map(c => `<th class="num">${esc(c[0])}</th>`).join("")}</tr></thead>
        <tbody>${list.map(r => `<tr><td><button type="button" class="linkish" data-ld="open" data-name="${esc(r.name)}" aria-expanded="${L.open === r.name ? "true" : "false"}">${esc(r.name)}</button>${r.fat ? ` <span class="fat">Flexi Adjunct</span>` : ""}
          <div class="small muted">${esc((r.depts || []).join(", "))}</div></td>${cols.map(c => `<td class="num">${esc(c[1] === "exams" ? signed(r.exams) : r[c[1]])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`
        : `<p class="muted">${esc(L.view === "week" ? "Nobody matches this week." : "Nobody matches this term.")}</p>`}
      <div class="note">“Week so far” is teaching plus relief this week${exams ? ", with exam duties and events added and lessons they stop taken off" : ""}. Relief counts approved reliefs and picks still waiting.</div></div>${oneHTML()}`;
  }

  async function load() {
    const seq = ++L.seq;
    L.loading = true; paint();
    const r = await R.api(`/api/relief/load${query()}`);
    if (seq !== L.seq) return;
    L.loading = false;
    if (!r.ok) { L.err = { text: r.error, bad: true, status: r.status }; paint(); return; }
    L.err = null; L.data = r.data;
    if (L.dept && !depts().includes(L.dept)) L.dept = "";
    paint();
  }

  async function openOne(name) {
    const seq = ++L.oneSeq;
    L.open = name; L.one = null; L.oneErr = null; paint();
    const el = $("#ldOne", L.pane) || $(".ld-one", L.pane);
    if (el) el.scrollIntoView({ block: "nearest" });
    const r = await R.api(`/api/relief/load/${enc(name)}${L.data && L.data.term ? `?term=${enc(L.data.term.name)}` : ""}`);
    if (seq !== L.oneSeq || L.open !== name) return;
    if (!r.ok) L.oneErr = { text: r.error, bad: true, status: r.status }; else L.one = r.data;
    paint();
    const card = $("#ldOne", L.pane);
    if (card) card.focus();
  }

  async function download() {
    L.msg = { text: "Making the file…", bad: false }; paint();
    let r;
    try { r = await fetch(`/api/relief/load.csv${query()}`, { cache: "no-store" }); }
    catch (e) { L.msg = { text: "Could not reach the server. Check the connection and try again.", bad: true }; paint(); return; }
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      L.msg = { text: (j && j.error) || "The file could not be made.", bad: true, status: r.status }; paint(); return;
    }
    const blob = await r.blob(), cd = r.headers.get("Content-Disposition") || "", m = /filename="?([^";]+)"?/.exec(cd);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob); link.download = m ? m[1] : "relief load.csv";
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 10000);
    L.msg = null; paint();
  }

  function onClick(e) {
    const b = e.target.closest("[data-ld]");
    if (!b || b.disabled) return;
    const a = b.dataset.ld;
    if (a === "view") { if (b.dataset.v !== L.view) { L.view = b.dataset.v; paint(); load(); } const again = $(`[data-ld="view"][data-v="${L.view}"]`, L.pane); if (again) again.focus(); return; }
    if (a === "reload") { load(); if (L.open) openOne(L.open); return; }
    if (a === "csv") { download(); return; }
    if (a === "open") { openOne(b.dataset.name); return; }
    if (a === "close") {
      const name = L.open; L.open = null; L.one = null; paint();
      const back = [...L.pane.querySelectorAll('[data-ld="open"]')].find(x => x.dataset.name === name); if (back) back.focus();
    }
  }

  function onChange(e) {
    const el = e.target.closest("[data-ld]");
    if (!el) return;
    if (el.dataset.ld === "dept") { L.dept = el.value; paint(); const s = $("#ldDept", L.pane); if (s) s.focus(); }
    if (el.dataset.ld === "fat") { L.fat = el.checked; paint(); const c = $('[data-ld="fat"]', L.pane); if (c) c.focus(); }
  }

  R.tab("load", {
    init(pane) {
      L.pane = pane;
      pane.innerHTML = `<div id="ldBox"></div>`;
      pane.addEventListener("click", onClick);
      pane.addEventListener("change", onChange);
      paint();
      load();
    },
    shown() { load(); },
    dirty() { return false; },
  });
})();

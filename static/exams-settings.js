"use strict";
/* Exam settings (/exams/settings): the exams committee, the exam rooms, the invigilator lists and the rules.
   One form, one Save (top and bottom). The form is kept in S.f; a refused save shows the server's sentence and keeps
   everything typed. */
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const S = { d: null, f: null, dirty: false, busy: false, msg: "", bad: false, open: null, q: "" };
  const LISTS = { committee: "the exams committee", backups: "the backup invigilators", chiefs: "the chief invigilators", never: "the never list" };

  const clone = x => JSON.parse(JSON.stringify(x));
  const numOrNull = v => v === "" ? null : Number(v);
  const val = v => v == null ? "" : esc(v);

  function everyone() {
    return S.d.people.map(p => ({ name: p.name, about: (p.depts || []).join(", ") || (p.staff_only ? "Other staff" : "") }));
  }

  function matches(key) {
    const have = new Set(S.f[key]), words = S.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return everyone().filter(p => !have.has(p.name) && words.every(w => (p.name + " " + p.about).toLowerCase().includes(w)));
  }

  /* ---------------------------------------------------------------- drawing */
  function setting(k, sub, body) {
    return `<div class="setting"><div class="k">${k}${sub ? `<div class="small muted">${sub}</div>` : ""}</div><div class="v">${body}</div></div>`;
  }

  function chips(key) {
    if (key === "committee" && !S.d.committee_ok) {   /* staff see the exams committee but cannot change it */
      const names = S.f[key].map(n => `<span class="pchip">${esc(n)}</span>`).join("");
      return `<div class="chiprow">${names || `<span class="muted small">No one yet.</span>`}</div><div class="small muted">Only the timetable committee can change this list.</div>`;
    }
    const list = S.f[key].map((n, i) => `<span class="pchip">${esc(n)}<button type="button" data-unchip="${key}" data-i="${i}" title="Take ${esc(n)} off" aria-label="Take ${esc(n)} off ${LISTS[key]}">✕</button></span>`).join("");
    return `<div class="chiprow">${list || `<span class="muted small">No one yet.</span>`}<button type="button" class="small" data-pick="${key}">+ Add</button></div>${S.open === key ? picker(key) : ""}`;
  }

  function picker(key) {
    return `<div class="picker"><div class="row"><input id="pickQ" type="search" placeholder="Type a name or a department" value="${esc(S.q)}" autocomplete="off" aria-label="Find a person">
      <button type="button" class="small" data-pickdone="1">Done</button></div><ul id="pickList">${pickItems(key)}</ul></div>`;
  }

  function pickItems(key) {
    const m = matches(key);
    if (!m.length) return `<li class="muted small none">${S.q.trim() ? "No one matches." : "No one left to add."}</li>`;
    return m.map((p, i) => `<li><button type="button" class="${i === 0 && S.q.trim() ? "first" : ""}" data-add="${key}" data-name="${esc(p.name)}"><span>${esc(p.name)}</span><span class="muted">${esc(p.about)}</span></button></li>`).join("");
  }

  function roomRows() {
    const names = Object.keys(S.f.rooms);
    const rows = names.map(n => {
      const r = S.f.rooms[n];
      return `<tr><td>${esc(n)}</td>
        <td><input type="number" min="1" step="1" data-room="seats" data-n="${esc(n)}" value="${val(r.seats)}" aria-label="Exam seats in ${esc(n)}"></td>
        <td><input type="number" min="1" step="1" data-room="rows" data-n="${esc(n)}" value="${val(r.rows)}" aria-label="Rows in ${esc(n)}"></td>
        <td><input type="number" min="1" step="1" data-room="cols" data-n="${esc(n)}" value="${val(r.cols)}" aria-label="Columns in ${esc(n)}"></td>
        <td class="c"><input type="checkbox" data-room="hall" data-n="${esc(n)}" ${r.hall ? "checked" : ""} aria-label="${esc(n)} is a hall"></td>
        <td class="c"><input type="checkbox" data-room="access" data-n="${esc(n)}" ${r.access ? "checked" : ""} aria-label="${esc(n)} is for access arrangements"></td>
        <td><input type="text" data-room="note" data-n="${esc(n)}" value="${esc(r.note || "")}" maxlength="200" placeholder="Note (optional)" aria-label="Note for ${esc(n)}"></td>
        <td class="x"><button type="button" class="small danger" data-unroom="${esc(n)}" title="Take ${esc(n)} off" aria-label="Take ${esc(n)} off the exam rooms">✕</button></td></tr>`;
    }).join("");
    const left = S.d.rooms.filter(r => !(r[0] in S.f.rooms));
    const add = left.length ? `<select data-addroom="1" aria-label="Add an exam room"><option value="">+ Add a room</option>${left.map(r => `<option value="${esc(r[0])}">${esc(r[0])}${r[1] || r[2] ? ` (${esc([r[1], r[2] ? r[2] + " seats" : ""].filter(Boolean).join(", "))})` : ""}</option>`).join("")}</select>` : `<span class="muted small">Every room of the published timetable is here.</span>`;
    return (rows ? `<div class="tablewrap rooms"><table><thead><tr><th>Room</th><th>Exam seats</th><th>Rows</th><th>Columns</th><th>Hall</th><th>Access</th><th>Note</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
      : `<p class="muted small">No exam rooms yet.</p>`) + `<div style="margin-top:8px">${add}</div>
      <div class="small muted" style="margin-top:6px">Exam seats are how many students sit an exam in the room, which is usually fewer than the room holds. Hall: a big venue that needs a chief invigilator. Access: where access arrangements are sat.</div>`;
  }

  function rules() {
    const R = S.f.rules, n = (k, label, extra, min, max) => `<div class="line"><label for="r_${k}">${label}</label><input id="r_${k}" type="number" min="${min}" max="${max}" step="1" data-rule="${k}" value="${val(R[k])}"${extra || ""}></div>`;
    return n("per_classroom", "Invigilators per classroom", "", 1, 10)
      + n("hall_per", "In a hall, one invigilator for every this many students", "", 1, 500)
      + `<div class="line"><label><input type="checkbox" data-rule="hall_chief" ${R.hall_chief ? "checked" : ""}> A chief invigilator in the hall</label></div>`
      + n("arrive", "Arrive this many minutes before the paper", "", 0, 120)
      + n("stay", "Stay this many minutes after for scripts", "", 0, 120)
      + `<div class="line"><label for="r_max_per_day">Most duties a day for one teacher</label><input id="r_max_per_day" type="number" min="1" max="20" step="1" data-rule="max_per_day" value="${val(R.max_per_day)}" placeholder="none"><span class="muted small">empty: no limit</span></div>`
      + `<div class="line"><label><input type="checkbox" data-rule="not_own_subject" ${R.not_own_subject ? "checked" : ""}> Not in a paper of their own subject</label></div>
      <div class="small muted">Always true, whatever the rules say: only teachers who are free then, never someone who is away that day, never someone on another duty at the same time.</div>`;
  }

  function barInner() {
    const st = S.f;
    const saved = st.saved_at ? `Saved by ${esc(st.saved_by)}, ${esc(st.saved_at)}` : S.dirty ? "" : "Not saved yet.";
    return `<button type="button" class="primary" data-act="save" ${S.busy ? "disabled" : ""}>${S.busy ? "Saving…" : "Save"}</button>${saved ? `<span class="muted small">${saved}</span>` : ""}${S.dirty ? `<span class="dirty">Changes not saved.</span>` : ""}${S.msg ? `<span class="msg ${S.bad ? "bad" : "ok"}" role="status">${esc(S.msg)}</span>` : ""}`;
  }

  function bar(where) { return `<div class="savebar ${where}" data-bar="1">${barInner()}</div>`; }
  function paintBars() { document.querySelectorAll("[data-bar]").forEach(b => { b.innerHTML = barInner(); }); }

  function render() {
    const f = S.f, gone = (f.missing || []).concat((f.missing_rooms || []).map(r => r + " (room)"));
    $("#main").innerHTML = `<div class="card"><h1>Exam settings</h1>
      ${gone.length ? `<p class="notice">No longer on the timetable: ${esc(gone.join(", "))}. Saving removes them.</p>` : ""}
      ${bar("first")}
      ${setting("Exams committee", "<span>They can open Exams and change everything in it. The timetable committee always can.</span>", chips("committee"))}
      ${setting("Exam rooms", "<span>Picked from the rooms of the published timetable.</span>", roomRows())}
      ${setting("Backup invigilators", "<span>Used first when someone has to be replaced. They can include staff who do not teach.</span>", chips("backups"))}
      ${setting("Chief invigilators", "<span>Who may lead a hall.</span>", chips("chiefs"))}
      ${setting("Never invigilate", "<span>Never given a duty.</span>", chips("never"))}
      ${setting("Rules", "<span>The app follows these when it picks invigilators.</span>", rules())}
      <div style="margin-top:14px">${bar("last")}</div></div>`;
  }

  async function homeLink() {
    let to = "/relief";
    try { const r = await fetch("/api/exams/me", { cache: "no-store" }), j = await r.json(); if (j && j.name === "Timetable committee") to = "/"; } catch (e) { /* keep the staff link */ }
    return to;
  }

  async function fail(text, forbidden) {
    const back = forbidden ? `<a href="${await homeLink()}">Back</a>` : `<a href="/exams/settings">Try again</a>`;
    S.dirty = false;
    $("#main").innerHTML = `<div class="card"><h1>Exam settings</h1><p class="msg bad">${esc(text)}</p><p>${back}</p></div>`;
  }

  /* ---------------------------------------------------------------- changes */
  function changed() { S.dirty = true; S.msg = ""; S.bad = false; paintBars(); }
  function redraw(focus) { changed(); render(); if (focus) { const el = $(focus); if (el) el.focus(); } }

  function pickName(key, name) {
    if (name && !S.f[key].includes(name)) S.f[key].push(name);
    S.q = ""; redraw("#pickQ");
  }

  function onClick(e) {
    const b = e.target.closest("button"); if (!b || b.matches(":disabled")) return;
    const ds = b.dataset, f = S.f;
    if (!f) return;
    if (ds.act === "save") { save(); return; }
    if (ds.pick) { S.open = ds.pick; S.q = ""; render(); const q = $("#pickQ"); if (q) q.focus(); return; }
    if (ds.pickdone) { S.open = null; S.q = ""; render(); return; }
    if (ds.add) { pickName(ds.add, ds.name); return; }
    if (ds.unchip) { f[ds.unchip].splice(Number(ds.i), 1); redraw(); return; }
    if (ds.unroom !== undefined) { delete f.rooms[ds.unroom]; redraw(); return; }
  }

  function onInput(e) {
    const el = e.target, ds = el.dataset, f = S.f, v = el.value;
    if (!f) return;
    if (el.id === "pickQ") { S.q = v; const ul = $("#pickList"); if (ul && S.open) ul.innerHTML = pickItems(S.open); return; }
    if (el.type === "checkbox" || el.tagName === "SELECT") return;   /* those are handled on change */
    if (ds.room) {
      const r = f.rooms[ds.n]; if (!r) return;
      r[ds.room] = ds.room === "note" ? v : numOrNull(v);
      changed(); return;
    }
    if (ds.rule) { f.rules[ds.rule] = numOrNull(v); changed(); return; }
  }

  function onChange(e) {
    const el = e.target, ds = el.dataset, f = S.f;
    if (!f) return;
    if (ds.addroom) {
      const name = el.value, room = S.d.rooms.find(r => r[0] === name);
      if (!name || !room) return;
      f.rooms[name] = { seats: room[2] || 30, rows: null, cols: null, hall: false, access: false, note: "" };
      redraw(); return;
    }
    if (el.type === "checkbox" && ds.room) { const r = f.rooms[ds.n]; if (r) { r[ds.room] = el.checked; changed(); } return; }
    if (el.type === "checkbox" && ds.rule) { f.rules[ds.rule] = el.checked; changed(); return; }
  }

  function onKey(e) {
    if (e.target.id !== "pickQ") return;
    if (e.key === "Escape") { e.preventDefault(); S.open = null; S.q = ""; render(); return; }
    if (e.key === "Enter") {
      e.preventDefault();
      const m = S.q.trim() ? matches(S.open) : [];
      if (m.length) pickName(S.open, m[0].name);
    }
  }

  /* ---------------------------------------------------------------- the server */
  async function save() {
    if (S.busy) return;
    S.busy = true; S.msg = ""; S.bad = false; paintBars();
    let r, j = {};
    try {
      r = await fetch("/api/exams/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.f) });
      j = await r.json().catch(() => ({}));
    } catch (err) {
      S.busy = false; S.bad = true; S.msg = "Could not reach the server. Nothing was saved: try again."; paintBars(); return;
    }
    S.busy = false;
    if (r.status === 401) { location.href = "/login"; return; }
    if (r.status === 403) { fail(j.error || "You cannot change exam settings.", true); return; }
    if (!r.ok) { S.bad = true; S.msg = j.error || "Nothing was saved. Try again."; paintBars(); return; }
    S.d = j; S.f = clone(j.settings); S.dirty = false; S.bad = false; S.msg = "Saved"; S.open = null; S.q = "";
    render();
  }

  async function start() {
    let r, j = {};
    try { r = await fetch("/api/exams/settings", { cache: "no-store" }); j = await r.json().catch(() => ({})); }
    catch (err) { fail("Could not reach the server. Check the connection and try again."); return; }
    if (r.status === 401) { location.href = "/login"; return; }
    if (r.status === 403) { fail(j.error || "You cannot open exam settings.", true); return; }
    if (!r.ok) { fail(j.error || "Something went wrong."); return; }
    S.d = j; S.f = clone(j.settings);
    render();
  }

  document.addEventListener("click", onClick);
  document.addEventListener("input", onInput);
  document.addEventListener("change", onChange);
  document.addEventListener("keydown", onKey);
  window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
  start();
})();

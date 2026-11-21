"use strict";
/* The history page (/history): who changed what, and when, newest first. Every text in an entry (a name, a place, a
   sentence, a value, a room from a request) is untrusted, so the page is built with textContent only, never innerHTML. */
(function () {
  const $ = s => document.querySelector(s);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const AGAIN = "Please sign in again.";
  const WHERES = ["Step 1 · Venues", "Step 2 · Classes", "Step 3 · Subjects", "Step 4 · Teachers", "Step 5 · Teacher Deployment Editor",
    "Step 5 · Banding & TG Group Editor", "Step 6 · Configuration & constraints", "Students", "School & day", "Setup", "Step 8 · Upload and edit",
    "Step 9 · Publish", "Relief settings", "Exams and events", "Admin", "Sign-in"];
  const VIA = { password: "password", code: "code", shared: "shared code", personal: "personal code", app: "by itself", google: "Google" };
  const CUT = 120;
  const S = { who: "", where: "", dept: "", from: "", to: "", signins: false, entries: [], more: false, admin: false, depts: [], token: 0, busy: false };
  try { S.who = new URLSearchParams(location.search).get("who") || ""; } catch (e) { S.who = ""; }

  /* ---------------------------------------------------------------- small helpers */
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const k in attrs || {}) {
      if (k === "text") el.textContent = attrs[k];
      else if (k === "class") el.className = attrs[k];
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== false && attrs[k] != null) el.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    }
    for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
    return el;
  }
  const cut = s => (s.length <= CUT ? s : s.slice(0, CUT - 1) + "…");
  function plain(v) {
    if (v === null || v === undefined || v === "") return "(none)";
    if (Array.isArray(v)) return v.length ? v.map(plain).join(", ") : "(none)";
    if (typeof v === "object") {
      for (const k of ["label", "name", "room", "class", "subject", "block", "role", "target"]) if (typeof v[k] === "string" && v[k]) return v[k];
      return "(a whole row)";
    }
    return String(v);
  }
  function shown(v, cls) {
    const full = plain(v);
    return h("span", { class: cls, title: full.length > CUT ? full : null, text: cut(full) });
  }
  const pad = n => String(n).padStart(2, "0");
  function when(e) {
    const d = new Date(e.at || (e.ts || 0) * 1000);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const dayKey = d => (d ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` : "?");
  const dayName = d => (d ? `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}` : "Unknown day");
  function clock(d) {
    if (!d) return "";
    const hr = d.getHours();
    return `${hr % 12 || 12}:${pad(d.getMinutes())} ${hr < 12 ? "am" : "pm"}`;
  }
  function note(text) { const m = $("#msg"); m.replaceChildren(); if (text) m.append(h("div", { class: "msg", text })); }

  async function api(query) {
    let r, d = null;
    try { r = await fetch("/api/history?" + query, { credentials: "same-origin" }); }
    catch (e) { throw new Error("The server could not be reached. Try again."); }
    try { d = await r.json(); } catch (e) { d = null; }
    if (r.status === 401) throw new Error(AGAIN);
    if (!r.ok) throw new Error((d && d.error) || "Something went wrong. Reload the page and try again.");
    return d;
  }
  function query(before) {
    const p = new URLSearchParams();
    if (S.who.trim()) p.set("who", S.who.trim());
    if (S.where) p.set("where", S.where);
    if (S.dept) p.set("dept", S.dept);
    if (S.from) p.set("from", S.from);
    if (S.to) p.set("to", S.to);
    if (S.signins) p.set("signins", "1");
    if (before) p.set("before", before);
    return p.toString();
  }

  /* ---------------------------------------------------------------- loading */
  async function load(older) {
    const token = ++S.token;
    S.busy = true; drawMore();
    try {
      const d = await api(query(older && S.entries.length ? S.entries[S.entries.length - 1].id : ""));
      if (token !== S.token) return;
      S.entries = older ? S.entries.concat(d.entries || []) : (d.entries || []);
      S.more = !!d.more; S.admin = !!d.admin;
      if (Array.isArray(d.depts)) S.depts = d.depts;
      note("");
    } catch (e) {
      if (token !== S.token) return;
      note(e.message);
    }
    S.busy = false;
    drawFilters(); drawList(); drawMore();
  }

  /* ---------------------------------------------------------------- filters */
  let timer = null;
  function drawFilters() {
    const box = $("#filters");
    if (box.contains(document.activeElement) && box.dataset.drawn) { const sg = $("#fSign"); if (sg) { sg.textContent = "Sign-ins: " + (S.signins ? "shown" : "hidden"); sg.classList.toggle("on", S.signins); } fillDepts(); return; }
    box.dataset.drawn = "1";
    const who = h("input", { type: "search", id: "fWho", placeholder: "Anyone", "aria-label": "Who", value: S.who,
      oninput: ev => { S.who = ev.target.value; clearTimeout(timer); timer = setTimeout(() => load(false), 300); } });
    const where = h("select", { id: "fWhere", "aria-label": "Where", onchange: ev => { S.where = ev.target.value; load(false); } },
      h("option", { value: "", text: "All steps" }), WHERES.map(w => h("option", { value: w, text: w, selected: w === S.where })));
    const dept = h("select", { id: "fDept", "aria-label": "Department", onchange: ev => { S.dept = ev.target.value; load(false); } });
    const from = h("input", { type: "date", id: "fFrom", "aria-label": "From", value: S.from, onchange: ev => { S.from = ev.target.value; load(false); } });
    const to = h("input", { type: "date", id: "fTo", "aria-label": "To", value: S.to, onchange: ev => { S.to = ev.target.value; load(false); } });
    const sign = h("button", { id: "fSign", type: "button", class: S.signins ? "on" : "", text: "Sign-ins: " + (S.signins ? "shown" : "hidden"),
      onclick: () => { S.signins = !S.signins; load(false); } });
    box.replaceChildren(h("label", {}, "Who ", who), h("label", {}, "Where ", where), h("label", {}, "Department ", dept),
      h("label", {}, "From ", from), h("label", {}, "To ", to), sign);
    fillDepts();
  }
  function fillDepts() {
    const sel = $("#fDept"); if (!sel) return;
    const names = S.depts.slice();
    for (const e of S.entries) for (const d of e.depts || []) if (typeof d === "string" && !names.includes(d)) names.push(d);
    if (S.dept && !names.includes(S.dept)) names.push(S.dept);
    const key = names.join("\u0001") + "|" + S.dept;
    if (sel.dataset.key === key) return;
    sel.dataset.key = key;
    sel.replaceChildren(h("option", { value: "", text: "All departments" }), names.map(d => h("option", { value: d, text: d, selected: d === S.dept })));
  }

  /* ---------------------------------------------------------------- entries */
  function link(e) {
    const where = String(e.where || "");
    if (typeof e.link === "string" && /^\/(?![\/\\\s])/.test(e.link)) return [e.link, "Open " + where.replace(/^Exams and events$/, "exams and events")];
    if (e.kind === "exams") return ["/exams", "Open exams and events"];
    if (where.startsWith("Step 8")) return ["/", "Open the committee page (step 8)"];
    if (where.startsWith("Step 9")) return ["/", "Open the committee page (step 9)"];
    if (e.kind === "relief" || where.startsWith("Relief")) return ["/relief", "Open relief"];
    if (e.kind === "account" && S.admin && Array.isArray(e.people) && e.people.length) return ["/admin", "Open the admin page"];
    return null;
  }
  function body(e) {
    const where = e.where ? h("span", { class: "where", text: String(e.where) }) : null;
    const text = typeof e.text === "string" ? e.text : "";
    if (e.kind === "setup-refused") {
      const label = e.label ? String(e.label) + ": " : "";
      return [where, h("span", { text: "Refused: " + label + String(e.why || "") })];
    }
    const field = ["set", "school", "day", "top"].includes(e.op) && e.kind !== "account" && "was" in e && "now" in e;
    if (e.kind === "setup" && field) {
      return [where, h("span", { text: `${plain(e.label)}${e.field && !String(e.label || "").endsWith(String(e.field)) ? ": " + e.field : ""}: ` }),
        shown(e.was, "was"), " → ", shown(e.now, "now")];
    }
    return [where, h("span", { text })];
  }
  function row(e, extra) {
    const d = when(e);
    const via = VIA[e.via] || (e.via ? String(e.via) : "");
    const lk = link(e);
    const what = h("div", { class: "what" }, body(e));
    if (lk) what.append(h("div", { class: "why" }, h("a", { href: lk[0], text: lk[1] })));
    return h("div", { class: "e" + (e.kind === "app" ? " app" : "") + (e.kind === "setup-refused" ? " refused" : "") + (extra || ""), "data-id": e.id },
      h("span", { class: "t", text: clock(d) }),
      h("span", { class: "who" }, h("b", { text: String(e.as || "Unknown") }), via ? h("span", { text: via }) : null),
      what);
  }
  function drawList() {
    const box = $("#list");
    const have = new Set(S.entries.filter(e => e.kind !== "app" && e.batch != null).map(e => e.batch));
    const last = new Map();
    for (const e of S.entries) if (e.kind !== "app" && e.batch != null) last.set(e.batch, e.id);
    const under = new Map();
    for (const e of S.entries) if (e.kind === "app" && e.follows != null && have.has(e.follows)) {
      if (!under.has(e.follows)) under.set(e.follows, []);
      under.get(e.follows).push(e);
    }
    const out = [];
    let key = null;
    if (!S.entries.length) { box.replaceChildren(h("p", { class: "muted", text: "Nothing has been recorded for these filters." })); return; }
    for (const e of S.entries) {
      if (e.kind === "app" && e.follows != null && have.has(e.follows)) continue;
      const d = when(e), k = dayKey(d);
      if (k !== key) { key = k; out.push(h("div", { class: "day", text: dayName(d) })); }
      out.push(row(e));
      if (e.batch != null && last.get(e.batch) === e.id) for (const a of (under.get(e.batch) || []).slice().reverse()) out.push(row(a));
    }
    box.replaceChildren(...out);
  }
  function drawMore() {
    const box = $("#more");
    box.replaceChildren();
    if (S.busy) { box.append(h("span", { class: "muted", text: "Loading…" })); return; }
    if (S.more) box.append(h("button", { type: "button", id: "older", text: "Show older", onclick: () => load(true) }));
  }

  drawFilters();
  load(false);
})();

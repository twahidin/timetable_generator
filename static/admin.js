"use strict";
/* The admin page (/admin): Staff, Students and Ways in. Every check is the server's: this page shows its sentences.
   Names, notes and every server text are untrusted, so they go into the page through esc(). A one-time password is
   kept in S.once only: never stored, never logged, and cleared when the panel closes or another person is picked. */
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const AGAIN = "Please sign in again.";
  const EXTRAS = [["relief", "Relief team"], ["exams", "Exams and events"], ["admin", "Admin"]];
  const SEEN = "admin-moved-seen";
  const S = { tab: "staff", people: [], depts: [], groups: [], hints: {}, moved: [], me: "", students: null, ways: null,
              q: "", fg: "", fd: "", fe: "", sq: "", ticked: new Set(), sel: null, menu: null, once: null, examsOpen: null,
              confirmReset: null, pmsg: null, msg: null, out: false, token: 0 };

  /* ---------------------------------------------------------------- small helpers */
  const fmtDay = iso => { const m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(iso || ""); return m ? `${+m[3]} ${MONTHS[+m[2] - 1]} ${m[1]}` : String(iso || ""); };
  const dayStart = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  function fmtTime(t) {
    if (!t) return "Never";
    const d = new Date(t * 1000), now = new Date(), days = Math.round((dayStart(now) - dayStart(d)) / 864e5);
    const tm = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    if (days === 0) return "Today " + tm;
    if (days === 1) return "Yesterday";
    return `${d.getDate()} ${MONTHS[d.getMonth()]}` + (d.getFullYear() !== now.getFullYear() ? " " + d.getFullYear() : "");
  }
  const label = key => (S.groups.find(g => g[0] === key) || [key, key])[1];
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const person = name => S.people.find(p => p.name === name);
  const ticks = () => [...S.ticked];
  const slipsUrl = names => "/api/relief/code-slips.pdf?names=" + names.map(encodeURIComponent).join(",");

  async function api(path, body) {
    let r, d = null;
    try { r = await fetch(path, body === undefined ? { credentials: "same-origin" } : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
    catch (e) { throw new Error("The server could not be reached. Try again."); }
    try { d = await r.json(); } catch (e) { d = null; }
    if (r.status === 401) { S.out = true; S.once = null; drawMsg(); throw new Error(AGAIN); }
    if (!r.ok) throw new Error((d && d.error) || "Something went wrong. Reload the page and try again.");
    return d;
  }

  function note(text, bad) { S.msg = text ? { text, bad: !!bad } : null; drawMsg(); }

  /* ---------------------------------------------------------------- loading */
  async function loadPeople() {
    const d = await api("/api/admin/people");
    S.people = d.people; S.depts = d.departments; S.groups = d.groups; S.hints = d.hints || {}; S.moved = d.moved || []; S.me = d.me;
    for (const n of [...S.ticked]) if (!person(n)) S.ticked.delete(n);
    if (S.sel && !person(S.sel)) closePanel();
  }
  async function loadStudents() { S.students = await api("/api/admin/students"); }
  async function loadWays() { S.ways = await api("/api/admin/ways"); }

  async function reload(which) {
    try { await Promise.all([loadPeople(), which === "all" ? loadStudents() : null]); }
    catch (e) { if (!S.out) note(e.message, true); }
    drawAll();
  }

  /* ---------------------------------------------------------------- top: messages, moved lines, tabs */
  function drawMsg() {
    const el = $("#msg");
    if (S.out) { el.innerHTML = `<div class="msg bad">${esc(AGAIN)} <a href="/login">Sign in</a></div>`; return; }
    el.innerHTML = S.msg ? `<div class="msg ${S.msg.bad ? "bad" : "ok"}">${esc(S.msg.text)}</div>` : "";
  }

  function drawMoved() {
    let seen = null;
    try { seen = localStorage.getItem(SEEN); } catch (e) { seen = null; }
    const key = JSON.stringify(S.moved);
    const el = $("#moved");
    if (!S.moved.length || seen === key) { el.innerHTML = ""; return; }
    el.innerHTML = `<div class="hint"><b>Moved into the accounts:</b><ul style="margin:4px 0 6px 18px;padding:0">${S.moved.map(l => `<li>${esc(l)}</li>`).join("")}</ul>
      <button type="button" data-act="dismiss">Dismiss</button></div>`;
  }

  function drawTabs() {
    const ns = S.students ? S.students.length.toLocaleString() : "…";
    const t = (k, text) => `<button type="button" data-tab="${k}" class="${S.tab === k ? "on" : ""}" ${S.tab === k ? 'aria-current="page"' : ""}>${text}</button>`;
    $("#tabs").innerHTML = t("staff", `Staff (${S.people.length})`) + t("students", `Students (${ns})`) + t("ways", "Ways in") + `<a href="/history">History</a>`;
  }

  /* ---------------------------------------------------------------- staff */
  function extraOk(p) {
    if (!S.fe) return true;
    if (S.fe === "off") return !!p.off;
    if (S.fe === "none") return !p.extras.relief && !p.extras.exams && !p.extras.admin;
    return !!p.extras[S.fe];
  }
  function shown() {
    const q = S.q.trim().toLowerCase();
    return S.people.filter(p => (!q || p.name.toLowerCase().includes(q)) && (!S.fg || p.group === S.fg) && (!S.fd || (p.depts || []).includes(S.fd)) && extraOk(p));
  }

  function skeleton() {
    const opt = (v, cur, text) => `<option value="${esc(v)}"${v === cur ? " selected" : ""}>${esc(text)}</option>`;
    const depts = [...new Set([...S.depts, ...S.people.flatMap(p => p.depts || [])])].sort();
    $("#view").innerHTML = `<div id="hint"></div>
      <div class="row" style="justify-content:flex-end;margin:0 0 8px"><a class="filebtn" id="slipsAll" href="/api/relief/code-slips.pdf" target="_blank" rel="noopener">Print code slips</a><button type="button" class="primary" data-act="addopen">Add a person</button></div>
      <div id="addbox"></div>
      <div class="filters">
        <input type="search" id="q" placeholder="Search a name" aria-label="Search a name" value="${esc(S.q)}" autocomplete="off">
        <select id="fg" aria-label="Group">${opt("", S.fg, "Group: all")}${S.groups.map(g => opt(g[0], S.fg, g[1])).join("")}</select>
        <select id="fd" aria-label="Department">${opt("", S.fd, "Department: all")}${depts.map(d => opt(d, S.fd, d)).join("")}</select>
        <select id="fe" aria-label="Extra">${opt("", S.fe, "Extra: any")}${EXTRAS.map(e => opt(e[0], S.fe, e[1])).join("")}${opt("off", S.fe, "Switched off")}${opt("none", S.fe, "No extra")}</select>
        <button type="button" data-act="tickall" id="tickall"></button>
      </div>
      <div id="bar"></div><div id="menu"></div>
      <div class="wrap" id="wrap"><div class="tw" id="tbl"></div><div id="panel"></div></div>`;
  }

  function drawHint() {
    const heads = (S.hints.heads_on_step4 || []).filter(n => person(n) && person(n).group === "teacher");
    const nod = (S.hints.heads_no_dept || []).filter(n => person(n));
    let h = "";
    if (heads.length) h += `<div class="hint">Step 4 lists <b>${esc(plural(heads.length, "teacher", "teachers"))}</b> as HOD or SH who are still in the Teacher group. <button type="button" data-act="makemgmt">Make them management</button></div>`;
    if (nod.length) h += `<div class="hint">${esc(nod.join(", "))} ${nod.length === 1 ? "is" : "are"} HOD or SH with no department, so ${nod.length === 1 ? "they change" : "they change"} no rows of the map. Pick a person and tick their departments.</div>`;
    $("#hint").innerHTML = h;
  }

  function extrasOf(p) {
    const x = p.extras || {}, out = [];
    if (x.relief) out.push("Relief team");
    if (x.exams) out.push("Exams and events · to " + fmtDay(x.exams));
    if (x.admin) out.push("Admin");
    return out;
  }

  function drawTable() {
    const list = shown(), all = list.length && list.every(p => S.ticked.has(p.name));
    $("#tickall").textContent = `Tick all shown (${list.length})`;
    $("#slipsAll").hidden = !!S.ticked.size;
    const rows = list.map(p => `<tr data-row="${esc(p.name)}" class="${p.name === S.sel ? "sel" : ""}${p.off ? " off" : ""}">
      <td class="ck"><input type="checkbox" data-tick="${esc(p.name)}" aria-label="Tick ${esc(p.name)}" ${S.ticked.has(p.name) ? "checked" : ""}></td>
      <td><button type="button" class="linkbtn" data-act="pick" data-name="${esc(p.name)}">${esc(p.name)}</button></td>
      <td><span class="g ${esc(p.group)}">${esc(label(p.group))}</span></td>
      <td>${(p.depts || []).length ? esc(p.depts.join(", ")) : `<span class="w">–</span>`}</td>
      <td>${p.off ? `<span class="w">Switched off</span> ` : ""}${extrasOf(p).map(x => `<span class="x">${esc(x)}</span>`).join("")}</td>
      <td class="w">${esc(fmtTime(p.last))}</td></tr>`).join("");
    $("#tbl").innerHTML = `<table><thead><tr><th class="ck"><input type="checkbox" data-act="tickhead" aria-label="Tick everyone shown" ${all ? "checked" : ""}></th><th>Name</th><th>Group</th><th>Department</th><th>Extra</th><th>Last signed in</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="6" class="w" style="padding:14px">No one matches.</td></tr>`}</tbody></table>`;
  }

  /* ---- the dark bar and its menus (every action previews first) */
  function drawBar() {
    const n = S.ticked.size, bar = $("#bar");
    if (!n) { bar.innerHTML = ""; $("#menu").innerHTML = ""; return; }
    const k = S.menu && S.menu.kind, b = (kind, text, cls) => `<button type="button" data-act="menu" data-kind="${kind}" class="${k === kind ? "on " : ""}${cls || ""}">${text}</button>`;
    const anyOff = ticks().some(x => (person(x) || {}).off);
    bar.innerHTML = `<div class="bar"><b>${n} ticked</b>${b("give", "Give extra access ▾")}${b("take", "Take away extra access ▾")}${b("group", "Set group ▾")}
      <button type="button" data-act="slips">Print their code slips</button>${b("off", "Switch off", "warn")}${anyOff ? b("on", "Switch on") : ""}
      <button type="button" class="clr" data-act="clear">Clear ticks</button></div>`;
    drawMenu();
  }

  const VERB = { give: n => `Give it to ${plural(n, "person", "people")}`, take: n => `Take it away from ${plural(n, "person", "people")}`,
                 group: n => `Set the group for ${plural(n, "person", "people")}`, off: n => `Switch off ${plural(n, "person", "people")}`, on: n => `Switch on ${plural(n, "person", "people")}` };

  function menuSum() {
    const m = S.menu;
    const sum = m.err ? `<div class="sum bad">${esc(m.err)}</div>` : m.lines ? `<div class="sum">${m.lines.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : m.hold ? `<div class="sum">${esc(m.hold)}</div>` : `<div class="sum">Reading what it would do…</div>`;
    return `${sum}<div class="go"><button type="button" class="primary" data-act="apply" ${m.lines && !m.busy ? "" : "disabled"}>${esc(VERB[m.kind](S.ticked.size))}</button><button type="button" data-act="cancelmenu">Cancel</button></div>`;
  }

  /* full: rebuild the choices too; otherwise only the preview and buttons, so a date being typed keeps its focus */
  function drawMenu(full = true) {
    const m = S.menu, el = $("#menu");
    if (!m || !S.ticked.size) { el.innerHTML = ""; return; }
    if (!full && $("#msum")) { $("#msum").innerHTML = menuSum(); return; }
    let opts = "";
    if (m.kind === "give" || m.kind === "take") {
      opts = EXTRAS.map(([k, t]) => `<div class="it"><label><input type="radio" name="bx" data-bx="${k}" ${m.extra === k ? "checked" : ""}> ${esc(t)}</label>
        ${m.kind === "give" && k === "exams" && m.extra === "exams" ? `until <input type="date" data-until="1" value="${esc(m.until)}" aria-label="Last day of the exams and events access">` : ""}</div>`).join("");
    } else if (m.kind === "group") {
      opts = `<div class="it"><label>Group <select data-bgroup="1">${S.groups.map(g => `<option value="${esc(g[0])}"${g[0] === m.group ? " selected" : ""}>${esc(g[1])}</option>`).join("")}</select></label></div>`;
    } else {
      opts = `<div class="w">${m.kind === "off" ? "They are signed out and cannot sign in until switched on." : "They can sign in again."}</div>`;
    }
    el.innerHTML = `<div class="menu">${opts}<div id="msum">${menuSum()}</div></div>`;
  }

  function bulkBody(preview) {
    const m = S.menu, b = { names: ticks(), action: m.kind, preview };
    if (m.kind === "give" || m.kind === "take") b.extra = m.extra;
    if (m.kind === "give" && m.extra === "exams") b.until = m.until;
    if (m.kind === "group") b.group = m.group;
    return b;
  }

  async function previewMenu() {
    const m = S.menu; if (!m) return;
    const my = ++S.token;
    m.lines = null; m.err = null; m.hold = null;
    if (m.kind === "give" && m.extra === "exams" && !m.until) { m.hold = "Pick the last day first."; drawMenu(false); return; }
    drawMenu(false);
    try {
      const d = await api("/api/admin/bulk", bulkBody(true));
      if (my !== S.token || S.menu !== m) return;
      m.lines = d.lines;
    } catch (e) { if (my !== S.token || S.menu !== m) return; m.err = e.message; }
    drawMenu(false);
  }

  function openMenu(kind) {
    if (S.menu && S.menu.kind === kind) { S.menu = null; drawBar(); return; }
    const first = ticks().map(person).filter(Boolean)[0], r = first && String(first.role || "").trim().toLowerCase();
    S.menu = { kind, extra: "relief", until: "", group: r === "sh" ? "sh" : r === "hod" ? "hod" : "teacher", lines: null, err: null, hold: null, busy: false };
    drawBar(); previewMenu();
  }

  async function applyMenu() {
    const m = S.menu; if (!m || !m.lines || m.busy) return;
    m.busy = true; drawMenu(false);
    try {
      const d = await api("/api/admin/bulk", bulkBody(false));
      S.menu = null; S.ticked.clear(); S.token++;
      note(d.applied ? d.lines.join(" ") : "Nothing changed: " + d.lines.join(" "), false);
      await loadPeople();
      drawAll();
    } catch (e) { m.busy = false; m.err = e.message; m.lines = null; drawMenu(false); }
  }

  /* ---- one person's panel */
  function closePanel() { S.sel = null; S.once = null; S.confirmReset = null; S.pmsg = null; S.examsOpen = null; }

  function drawPanel() {
    const el = $("#panel"), p = S.sel && person(S.sel);
    $("#wrap").classList.toggle("nopanel", !p);
    if (!p) { el.innerHTML = ""; return; }
    const head = p.group === "hod" || p.group === "sh";
    const sub = p.staff_only ? "Added by name: not on the published timetable" : "On the published timetable" + (p.role ? ` · role ${p.role}` : "");
    const x = p.extras || {}, examsOn = !!x.exams || S.examsOpen === p.name;
    const map = head ? `<div class="r"><div class="l">Changes the map for</div>${S.depts.map(d => `<label class="ck2"><input type="checkbox" data-dept="${esc(d)}" ${(p.depts || []).includes(d) ? "checked" : ""}> ${esc(d)}</label>`).join("") || `<span class="w">The setup has no departments yet.</span>`}
      <div class="w">From step 4; tick more if they look after two.</div></div>` : "";
    const suggest = p.name.toLowerCase().replace(/\s+/g, ".").replace(/[^a-z0-9._-]/g, "").slice(0, 40);
    const acct = p.username
      ? `<div>Username <b>${esc(p.username)}</b> <span class="w">· ${p.has_password ? "password set" : "no password yet"}</span></div>`
      : `<div class="w" style="margin-bottom:4px">No username yet.</div><div class="row"><input id="uname" type="text" value="${esc(suggest)}" aria-label="Username" autocomplete="off" style="max-width:220px"></div>`;
    const resetBtn = p.username ? (S.confirmReset === p.name
      ? `<span class="w">Give ${esc(p.name)} a new one-time password and sign them out everywhere?</span> <button type="button" class="primary small" data-act="reset">Yes, reset it</button> <button type="button" class="small" data-act="resetno">Cancel</button>`
      : `<button type="button" data-act="resetask">Reset password</button>`)
      : `<button type="button" data-act="mkaccount">Make a password account</button>`;
    const once = S.once && S.once.name === p.name ? `<div class="once" role="status">Shown once. Give it to ${esc(p.name)}; they pick their own when they next sign in. They are signed out everywhere now.<code>${esc(S.once.value)}</code></div>` : "";
    el.innerHTML = `<div class="side"><div class="row" style="justify-content:space-between;flex-wrap:nowrap"><h2>${esc(p.name)}</h2><button type="button" class="small" data-act="closepanel" aria-label="Close">✕</button></div>
      <div class="sub">${esc(sub)}${p.off ? " · switched off" : ""}</div>
      ${S.pmsg ? `<div class="msg ${S.pmsg.bad ? "bad" : "ok"}" style="margin:8px 0">${esc(S.pmsg.text)}</div>` : ""}
      <div class="r"><div class="l">Group</div><select data-pgroup="1" aria-label="Group">${S.groups.map(g => `<option value="${esc(g[0])}"${g[0] === p.group ? " selected" : ""}>${esc(g[1])}</option>`).join("")}</select></div>
      ${map}
      <div class="r"><div class="l">Extra</div>
        <label class="ck2"><input type="checkbox" data-pextra="relief" ${x.relief ? "checked" : ""}> Relief team</label>
        <div class="ck2"><label><input type="checkbox" data-pextra="exams" ${examsOn ? "checked" : ""}> Exams and events</label>${examsOn ? ` <span class="w">until</span> <input type="date" data-puntil="1" value="${esc(x.exams || "")}" aria-label="Last day of the exams and events access">` : ""}</div>
        <label class="ck2"><input type="checkbox" data-pextra="admin" ${x.admin ? "checked" : ""}> Admin</label></div>
      <div class="r"><div class="l">Way in</div>${acct}</div>
      <div class="r"><div class="l">Note</div><input type="text" data-pnote="1" maxlength="200" value="${esc(p.note || "")}" aria-label="Note" style="width:100%" placeholder="Only admins see this"></div>
      <div class="btns">${resetBtn}<a class="filebtn" href="/history?who=${encodeURIComponent(p.name)}">Their changes</a>
        <button type="button" class="${p.off ? "" : "danger"}" data-act="${p.off ? "swon" : "swoff"}">${p.off ? "Switch on" : "Switch off"}</button></div>
      ${once}</div>`;
  }

  async function savePerson(body, ok) {
    S.pmsg = null;
    try {
      await api("/api/admin/person", body);
      S.pmsg = ok ? { text: ok, bad: false } : null;
      await loadPeople();
    } catch (e) { if (!S.out) S.pmsg = { text: e.message, bad: true }; }
    drawAll();
  }

  async function reset(body) {
    S.pmsg = null; S.confirmReset = null; S.once = null;
    try {
      const d = await api("/api/admin/reset", body);
      S.once = { name: body.name, value: d.once };
      await loadPeople();
    } catch (e) { if (!S.out) S.pmsg = { text: e.message, bad: true }; }
    drawAll();
  }

  /* ---- add a person */
  function drawAdd(open) {
    const el = $("#addbox");
    if (!open) { el.innerHTML = ""; return; }
    el.innerHTML = `<div class="menu add" style="margin-top:0"><div class="l">Add a person who is not on the timetable</div>
      <div class="row"><input id="addName" type="text" maxlength="100" placeholder="Their name" aria-label="Name" autocomplete="off">
      <select id="addGroup" aria-label="Group">${S.groups.map(g => `<option value="${esc(g[0])}"${g[0] === "executive" ? " selected" : ""}>${esc(g[1])}</option>`).join("")}</select>
      <button type="button" class="primary" data-act="addgo">Add</button><button type="button" data-act="addno">Cancel</button></div>
      <div id="addMsg" class="sum bad" hidden></div></div>`;
    $("#addName").focus();
  }

  async function addPerson() {
    const name = $("#addName").value.trim(), group = $("#addGroup").value, m = $("#addMsg");
    m.hidden = true;
    try {
      const item = await api("/api/admin/person", { name, group, added: true });
      await loadPeople();
      closePanel(); S.sel = item.name; S.q = ""; S.fg = ""; S.fd = ""; S.fe = "";
      note(`${item.name} is on the staff list.`, false);
      skeleton(); drawAll();
    } catch (e) { if (!S.out) { m.textContent = e.message; m.hidden = false; } }
  }

  /* ---------------------------------------------------------------- students and ways in */
  function drawStudents() {
    const q = S.sq.trim().toLowerCase(), all = S.students || [];
    const list = all.filter(s => !q || `${s.id} ${s.name} ${s.class}`.toLowerCase().includes(q));
    $("#view").innerHTML = `<div class="row" style="margin:0 0 10px"><input type="search" id="sq" placeholder="Search an ID, name or class" aria-label="Search students" value="${esc(S.sq)}" autocomplete="off" style="min-width:220px">
      <span class="w" id="sn"></span><span style="margin-left:auto"></span><a class="filebtn" href="/api/code-slips.pdf" target="_blank" rel="noopener">Print code slips</a></div>
      <div class="tw"><div id="stbl"></div></div>`;
    drawStudentRows(list, all.length);
  }
  function drawStudentRows(list, total) {
    $("#sn").textContent = `${list.length} of ${total}`;
    const shownRows = list.slice(0, 500);
    $("#stbl").innerHTML = `<table><thead><tr><th>ID</th><th>Name</th><th>Class</th></tr></thead><tbody>${shownRows.map(s => `<tr><td>${esc(s.id)}</td><td>${esc(s.name)}</td><td>${esc(s.class)}</td></tr>`).join("")
      || `<tr><td colspan="3" class="w" style="padding:14px">${total ? "No one matches." : "No students list is published yet."}</td></tr>`}</tbody></table>${list.length > shownRows.length ? `<div class="w" style="padding:8px">Showing the first 500. Search to narrow it.</div>` : ""}`;
  }

  const SHARED_NAMES = { committee: "Shared committee code", head: "Shared heads' code", teacher: "Shared teacher code", student: "Shared student code" };

  function drawWays() {
    const w = S.ways;
    if (!w) { $("#view").innerHTML = `<p class="muted">Loading…</p>`; return; }
    const sh = w.shared.map(r => {
      const off = r.off != null, used = plural(r.used_week, "time", "times");
      const state = !r.set ? `<span class="w">Not set</span>` : off ? `<span class="on">Off since ${esc(fmtDay(new Date(r.off * 1000).toISOString().slice(0, 10)))}</span>` : `<span class="stillon">Still on · used ${esc(used)} this week</span>`;
      const btn = !r.set ? "" : off ? `<button type="button" class="small" data-act="shared" data-code="${esc(r.code)}" data-off="0">Turn on</button>` : `<button type="button" class="small danger" data-act="shared" data-code="${esc(r.code)}" data-off="1">Turn off</button>`;
      return `<tr><td>${esc(SHARED_NAMES[r.code] || r.code)}</td><td>${state}</td><td>${btn}</td></tr>`;
    }).join("");
    $("#view").innerHTML = `${w.secret_key ? "" : `<div class="hint">Accounts need SECRET_KEY in Railway variables.</div>`}
      <div class="tw ways"><table><thead><tr><th style="width:34%">Way in</th><th>State</th><th></th></tr></thead><tbody>
      <tr><td><b>Personal codes</b> (staff and students)</td><td>${w.personal_codes ? "On" : "Off"}</td><td><a class="filebtn small" href="/api/relief/code-slips.pdf" target="_blank" rel="noopener">Print slips</a></td></tr>
      <tr><td><b>Username and password</b></td><td>${w.secret_key ? "On" : "Off"} · ${esc(plural(w.password_accounts, "account", "accounts"))}</td><td></td></tr>
      <tr><td><b>Recovery code</b></td><td>${w.recovery_set ? "Set in Railway variables" : "Not set"}</td><td></td></tr>
      ${sh}</tbody></table></div>
      <div class="w" style="margin-top:8px">"Used … times" counts sign-ins with the shared code in the last week, so you can see when it is safe to turn off.</div>`;
  }

  async function turnShared(code, off) {
    try { S.ways = await api("/api/admin/shared-off", { code, off }); note(`${SHARED_NAMES[code] || "The code"} is ${off ? "off" : "on"}.`, false); }
    catch (e) { if (!S.out) note(e.message, true); }
    drawWays();
  }

  /* ---------------------------------------------------------------- drawing it all */
  function drawStaff() { drawHint(); drawTable(); drawBar(); drawPanel(); }
  function drawAll() {
    drawMsg(); drawMoved(); drawTabs();
    if (S.tab === "staff") { if (!$("#tbl")) skeleton(); drawStaff(); }
    else if (S.tab === "students") drawStudents();
    else drawWays();
  }

  async function showTab(tab) {
    if (tab === S.tab) return;
    S.tab = tab; S.menu = null; note(null);
    if (tab === "staff") skeleton();
    if (tab === "ways") { S.ways = null; }
    drawAll();
    if (tab === "ways") { try { await loadWays(); } catch (e) { if (!S.out) note(e.message, true); } drawWays(); }
  }

  /* ---------------------------------------------------------------- events */
  function pick(name) {
    if (S.sel !== name) { S.once = null; S.confirmReset = null; S.pmsg = null; S.examsOpen = null; }
    S.sel = name; drawTable(); drawPanel();
    if (window.matchMedia("(max-width:900px)").matches && $("#panel .side")) $("#panel .side").scrollIntoView({ block: "start" });   /* the panel is under the table on a narrow screen */
  }

  document.addEventListener("click", e => {
    const t = e.target.closest("[data-act],[data-tab],tr[data-row]");
    if (!t || t.tagName === "INPUT" && !t.dataset.act) return;
    if (t.dataset.tab) return void showTab(t.dataset.tab);
    if (!t.dataset.act) { if (!e.target.closest("input,button,a")) pick(t.dataset.row); return; }
    const a = t.dataset.act, p = S.sel && person(S.sel);
    if (a === "pick") pick(t.dataset.name);
    else if (a === "closepanel") { closePanel(); drawTable(); drawPanel(); }
    else if (a === "dismiss") { try { localStorage.setItem(SEEN, JSON.stringify(S.moved)); } catch (x) { /* kept for this visit only */ } $("#moved").innerHTML = ""; }
    else if (a === "tickall") { const l = shown(); const all = l.every(x => S.ticked.has(x.name)); l.forEach(x => all ? S.ticked.delete(x.name) : S.ticked.add(x.name)); S.menu = null; drawTable(); drawBar(); }
    else if (a === "clear") { S.ticked.clear(); S.menu = null; drawTable(); drawBar(); }
    else if (a === "makemgmt") { (S.hints.heads_on_step4 || []).forEach(n => person(n) && S.ticked.add(n)); S.menu = null; drawTable(); openMenu("group"); }
    else if (a === "menu") openMenu(t.dataset.kind);
    else if (a === "cancelmenu") { S.menu = null; S.token++; drawBar(); }
    else if (a === "apply") applyMenu();
    else if (a === "slips") window.open(slipsUrl(ticks()), "_blank", "noopener");
    else if (a === "addopen") drawAdd(true);
    else if (a === "addno") drawAdd(false);
    else if (a === "addgo") addPerson();
    else if (a === "resetask") { S.confirmReset = p.name; drawPanel(); }
    else if (a === "resetno") { S.confirmReset = null; drawPanel(); }
    else if (a === "reset") reset({ name: p.name });
    else if (a === "mkaccount") reset({ name: p.name, username: ($("#uname") || {}).value || "" });
    else if (a === "swoff") savePerson({ name: p.name, off: true }, `${p.name} is switched off and signed out.`);
    else if (a === "swon") savePerson({ name: p.name, off: false }, `${p.name} is switched on.`);
    else if (a === "shared") turnShared(t.dataset.code, t.dataset.off === "1");
  });

  document.addEventListener("change", e => {
    const t = e.target, d = t.dataset, p = S.sel && person(S.sel);
    if (t.id === "fg") { S.fg = t.value; drawTable(); }
    else if (t.id === "fd") { S.fd = t.value; drawTable(); }
    else if (t.id === "fe") { S.fe = t.value; drawTable(); }
    else if (d.tick != null) { t.checked ? S.ticked.add(d.tick) : S.ticked.delete(d.tick); S.menu = null; drawTable(); drawBar(); }
    else if (d.act === "tickhead") { shown().forEach(x => t.checked ? S.ticked.add(x.name) : S.ticked.delete(x.name)); S.menu = null; drawTable(); drawBar(); }
    else if (d.bx) { S.menu.extra = d.bx; drawMenu(); previewMenu(); }
    else if (d.until) { S.menu.until = t.value; S.menu.lines = null; S.menu.err = null; S.menu.hold = "Reading what it would do…"; drawMenu(false); clearTimeout(S.wait); S.wait = setTimeout(previewMenu, 350); }
    else if (d.bgroup) { S.menu.group = t.value; previewMenu(); }
    else if (!p) return;
    else if (d.pgroup) savePerson({ name: p.name, group: t.value });
    else if (d.dept != null) savePerson({ name: p.name, depts: [...document.querySelectorAll("[data-dept]")].filter(c => c.checked).map(c => c.dataset.dept) });
    else if (d.pextra === "relief" || d.pextra === "admin") savePerson({ name: p.name, extras: { [d.pextra]: t.checked } });
    else if (d.pextra === "exams") { if (t.checked) { S.examsOpen = p.name; drawPanel(); } else { S.examsOpen = null; savePerson({ name: p.name, extras: { exams: null } }); } }
    else if (d.puntil) savePerson({ name: p.name, extras: { exams: t.value } }, "Saved.");
    else if (d.pnote) savePerson({ name: p.name, note: t.value }, "Note saved.");
  });

  document.addEventListener("input", e => {
    if (e.target.id === "q") { S.q = e.target.value; drawTable(); }
    else if (e.target.id === "sq") { S.sq = e.target.value; const q = S.sq.trim().toLowerCase(), all = S.students || []; drawStudentRows(all.filter(s => !q || `${s.id} ${s.name} ${s.class}`.toLowerCase().includes(q)), all.length); }
  });

  window.addEventListener("pagehide", () => { S.once = null; });

  (async function init() {
    drawTabs();
    try { await loadPeople(); } catch (e) { if (!S.out) note(e.message, true); }
    drawAll();
    try { await loadStudents(); } catch (e) { S.students = null; }
    drawTabs();
  })();
})();

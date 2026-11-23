"use strict";
/* Relief settings (/relief/settings) for the timetable committee and the relief team: one form, one Save (at the top
   and the bottom). The form is kept in S.f; a refused save shows the server's sentence and keeps everything typed.
   Under it, apart from the form and its Save, the Telegram card (TG). */
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const DAYS = [["Mon", "Monday"], ["Tue", "Tuesday"], ["Wed", "Wednesday"], ["Thu", "Thursday"], ["Fri", "Friday"]];
  const FIXED = "Always true, whatever the rules say: only teachers free at that time · never someone away that day · the relief team approves before anything is sent.";
  const NAMES = "Write people by their full name. The app replaces names with labels before the rules go to the AI.";
  const S = { data: null, f: null, dirty: false, busy: false, msg: "", bad: false, open: null, q: "" };

  const clone = x => JSON.parse(JSON.stringify(x));
  const listOf = key => S.f.limits.never;   /* the only list kept on this page: the never list */
  const opt = (v, cur, label) => `<option value="${esc(v)}"${v === cur ? " selected" : ""}>${esc(label ?? v)}</option>`;

  function everyone() {   /* who the pickers offer: the published timetable's teachers, then the other staff from the accounts */
    return S.data.people.map(p => ({ name: p.name, about: p.staff_only ? "Other staff" : (p.depts || []).join(", ") }));
  }

  function matches(key) {
    const have = new Set(listOf(key)), words = S.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return everyone().filter(p => !have.has(p.name) && words.every(w => (p.name + " " + p.about).toLowerCase().includes(w)));
  }

  /* ---------------------------------------------------------------- drawing */
  function setting(k, sub, body) {
    return `<div class="setting"><div class="k">${k}${sub ? `<div class="small muted">${sub}</div>` : ""}</div><div class="v">${body}</div></div>`;
  }

  function chips(key, what) {
    const names = listOf(key);
    const list = names.map((n, i) => `<span class="chip pchip">${esc(n)}<button type="button" data-unchip="${key}" data-i="${i}" title="Take ${esc(n)} off" aria-label="Take ${esc(n)} off ${what}">✕</button></span>`).join("");
    return `<div class="chiprow">${list || `<span class="muted small">No one yet.</span>`}<button type="button" class="small" data-pick="${key}">+ Add</button></div>${S.open === key ? picker(key) : ""}`;
  }

  function picker(key) {
    return `<div class="picker" id="picker"><div class="row"><input id="pickQ" type="search" placeholder="Type a name or a department" value="${esc(S.q)}" autocomplete="off" aria-label="Find a person">
      <button type="button" class="small" data-pickdone="1">Done</button></div><ul id="pickList">${pickItems(key)}</ul></div>`;
  }

  function pickItems(key) {
    const m = matches(key);
    if (!m.length) return `<li class="muted small none">${S.q.trim() ? "No one matches." : "No one left to add."}</li>`;
    return m.map((p, i) => `<li><button type="button" class="${i === 0 && S.q.trim() ? "first" : ""}" data-add="${key}" data-name="${esc(p.name)}"><span>${esc(p.name)}</span><span class="muted">${esc(p.about)}</span></button></li>`).join("");
  }

  function readOnly(names, what) {   /* a list kept on the admin page: shown here, never edited */
    const list = names.length ? names.map(n => `<span class="chip pchip" style="padding-right:10px">${esc(n)}</span>`).join("") : `<span class="muted small">No one yet.</span>`;
    return `<div class="chiprow" aria-label="${esc(what)}">${list}</div>`;
  }

  function changeNote() {
    return `<div class="small muted" style="margin-top:6px">${S.data.can_admin ? `<a href="/admin">Change these on the admin page.</a>` : "Ask an admin to change these."}</div>`;
  }

  function fatRole() {
    const roles = S.data.roles.slice(), cur = S.f.fat_role || "";
    if (cur && !roles.includes(cur)) roles.push(cur);
    return `<div class="line">Everyone whose role on step 4 is <select data-fat="1" aria-label="Flexi Adjunct Teachers' role">${opt("", cur, "None")}${roles.map(r => opt(r, cur)).join("")}</select>
      <span class="muted small" id="fatCount">${fatCount()}</span></div>`;
  }

  function fatCount() {
    if (!S.f.fat_role) return "";
    const n = S.data.people.filter(p => p.role === S.f.fat_role).length;
    return `(${n} ${n === 1 ? "teacher" : "teachers"})`;
  }

  function rules() {
    const R = S.f.rules, n = R.length;
    return R.map((r, i) => `<div class="rule"><span class="num">${i + 1}</span><textarea class="wrapbox" data-rule="${i}" maxlength="300" rows="2" aria-label="Rule ${i + 1}" placeholder="e.g. Never give relief to the Principal or Vice-Principals.">${esc(r)}</textarea>
      <span class="acts"><button type="button" class="small" data-up="${i}" ${i === 0 ? "disabled" : ""} title="Move up" aria-label="Move rule ${i + 1} up">↑</button><button type="button" class="small" data-down="${i}" ${i === n - 1 ? "disabled" : ""} title="Move down" aria-label="Move rule ${i + 1} down">↓</button><button type="button" class="small danger" data-unrule="${i}" title="Take this rule off" aria-label="Take rule ${i + 1} off">✕</button></span></div>`).join("")
      + `<button type="button" class="small add" data-act="addRule">+ Add a rule</button>
      <div class="small muted names">${esc(NAMES)}</div>
      <div class="small muted fixed">${esc(FIXED)}<span class="locked">fixed</span></div>`;
  }

  function limits() {
    const L = S.f.limits, num = v => v == null ? "" : esc(v);
    return `<div class="line"><label for="limFat">Most relief periods a day for a Flexi Adjunct Teacher</label><input id="limFat" type="number" min="1" max="20" step="1" data-lim="fat_per_day" value="${num(L.fat_per_day)}"></div>
      <div class="line"><label for="limOther">for anyone else</label><input id="limOther" type="number" min="1" max="20" step="1" data-lim="other_per_day" value="${num(L.other_per_day)}" placeholder="none"><span class="muted small">empty: no limit</span></div>
      <div class="line" style="margin-top:12px">Never give relief to</div>${chips("never", "the never list")}`;
  }

  function times() {
    const T = S.f.times, t = k => `<input type="time" data-t="${k}" value="${esc(T[k])}" aria-label="${k === "fill_at" ? "Fill open lessons at" : k === "remind_at" ? "Remind the absent teacher at" : "Weekly summary at"}">`;
    return `<div class="line">Fill open lessons at ${t("fill_at")} the school day before</div>
      <div class="line">Remind the absent teacher to acknowledge and set work at ${t("remind_at")} the school day before</div>
      <div class="line">Report "not yet acknowledged" every <input type="number" min="5" max="60" step="1" data-t="report_every" value="${T.report_every == null ? "" : esc(T.report_every)}" aria-label="Report every how many minutes"> minutes</div>
      <div class="line">Weekly summary on <select data-t="weekly_day" aria-label="Weekly summary day">${DAYS.map(([v, l]) => opt(v, T.weekly_day, l)).join("")}</select> at ${t("weekly_at")}</div>`;
  }

  function calendar() {
    const C = S.f.calendar, two = S.data.weeks === 2;
    const terms = C.terms.map((tm, i) => `<tr><td><input data-term="name" data-i="${i}" value="${esc(tm.name)}" placeholder="Term ${i + 1}" aria-label="Term name"></td>
      <td><input type="date" data-term="start" data-i="${i}" value="${esc(tm.start)}" aria-label="First day"></td>
      <td><input type="date" data-term="end" data-i="${i}" value="${esc(tm.end)}" aria-label="Last day"></td>
      ${two ? `<td><select data-term="starts_as" data-i="${i}" aria-label="Starts as">${opt("", tm.starts_as || "", "Choose")}${opt("Odd", tm.starts_as || "", "Odd")}${opt("Even", tm.starts_as || "", "Even")}</select></td>` : ""}
      <td class="x"><button type="button" class="small danger" data-unterm="${i}" title="Take this term off" aria-label="Take this term off">✕</button></td></tr>`).join("");
    const hols = C.holidays.map((h, i) => `<tr><td><input data-hol="name" data-i="${i}" value="${esc(h.name)}" placeholder="e.g. Deepavali" aria-label="Holiday name"></td>
      <td><input type="date" data-hol="start" data-i="${i}" value="${esc(h.start)}" aria-label="First day"></td>
      <td><input type="date" data-hol="end" data-i="${i}" value="${esc(h.end)}" aria-label="Last day"></td>
      <td class="x"><button type="button" class="small danger" data-unhol="${i}" title="Take this holiday off" aria-label="Take this holiday off">✕</button></td></tr>`).join("");
    const cols = two ? 5 : 4;
    return `<h3>Terms</h3><div class="tablewrap cal"><table><thead><tr><th>Name</th><th>First day</th><th>Last day</th>${two ? `<th title="The week of the term's first day">Starts as</th>` : ""}<th></th></tr></thead>
      <tbody>${terms || `<tr><td class="empty" colspan="${cols}">No terms yet.</td></tr>`}</tbody></table></div>
      <button type="button" class="small add" data-act="addTerm">+ Add a term</button>
      <h3 class="next">Holidays and no-school days</h3><div class="tablewrap cal"><table><thead><tr><th>Name</th><th>First day</th><th>Last day</th><th></th></tr></thead>
      <tbody>${hols || `<tr><td class="empty" colspan="4">No holidays yet.</td></tr>`}</tbody></table></div>
      <button type="button" class="small add" data-act="addHoliday">+ Add a holiday</button><span class="muted small"> A holiday of one day needs only its first day.</span>`;
  }

  function codes() {
    return `<div class="codes"><a class="filebtn" href="/api/relief/codes.csv" data-dl="personal relief codes.csv">Download codes (.csv)</a>
      <a class="filebtn" href="/api/relief/code-slips.pdf" data-dl="relief code slips.pdf">Print code slips (PDF)</a><span class="dlmsg" id="dlMsg"></span></div>
      <div class="small muted" style="margin-top:6px">A code for each teacher on the published timetable and each other staff member, as last saved.</div>`;
  }

  function bar(where) { return `<div class="savebar ${where}" data-bar="1">${barInner()}</div>`; }

  function barInner() {
    const st = S.f, d = S.data;
    const saved = st.saved_at ? `Saved by ${esc(st.saved_by)}, ${esc(st.saved_at)}` : S.dirty ? "" : "Not saved yet.";
    const btn = d.can_save ? `<button type="button" class="primary" data-act="save" ${S.busy ? "disabled" : ""}>${S.busy ? "Saving…" : "Save"}</button>`
      : `<span class="muted">Only the timetable committee and the relief team can change relief settings.</span>`;
    return `${btn}${saved ? `<span class="muted small">${saved}</span>` : ""}${S.dirty ? `<span class="dirty">Changes not saved.</span>` : ""}${S.msg ? `<span class="msg ${S.bad ? "bad" : "ok"}" role="status">${esc(S.msg)}</span>` : ""}`;
  }

  function paintBars() { document.querySelectorAll("[data-bar]").forEach(b => { b.innerHTML = barInner(); }); }

  function links() {
    const committee = S.data && S.data.can_codes;   /* only the committee may have the codes */
    const own = committee ? `<a class="ghost filebtn" href="/">Committee page</a><a class="ghost filebtn" href="/timetable" target="_blank">Published timetable</a>`
      : `<a class="ghost filebtn" href="/relief">Relief</a><a class="ghost filebtn" href="/timetable">Your timetable</a>`;
    $("#links").innerHTML = own + `<a class="ghost filebtn" href="/logout">Sign out</a>`;
  }

  function render() {
    const f = S.f, d = S.data, missing = f.missing || [];
    $("#main").innerHTML = `<div class="card">
      ${missing.length ? `<p class="notice">No longer on the timetable: ${esc(missing.join(", "))}. Saving removes them.</p>` : ""}
      ${bar("first")}
      <fieldset id="form" ${d.can_save ? "" : "disabled"}>
      ${setting("Management", "", readOnly(d.lists.management, "Management") + changeNote())}
      ${setting("Relief team", `<span>They can change these settings.</span>`, readOnly(d.lists.team, "Relief team") + changeNote())}
      ${setting("Other staff (no lessons)", `<span>Staff who are not on the timetable but take part in relief. Each gets a personal code.</span>`, readOnly(d.lists.added, "Other staff") + changeNote())}
      ${setting("Flexi Adjunct Teachers", "", fatRole())}
      ${setting("Relief rules", `<span>The AI follows these in order and quotes them in its reasons.</span>`, rules())}
      ${setting("Checked limits", `<span>The app checks these itself.</span>`, limits())}
      ${setting("Reporting officer", "", `Is told on Telegram, when they have linked it, when someone who names them asks for relief.`)}
      ${setting("Times", "", times())}
      ${setting("School calendar", `<span>So the app knows which day of the timetable each date is.</span>`, calendar())}
      ${d.can_codes ? setting("Personal codes", "", codes()) : ""}
      </fieldset>
      <div style="margin-top:14px">${bar("last")}</div></div>`;
    fitAll();
  }

  function fail(text) {
    $("#main").innerHTML = `<div class="card"><h1>Relief settings</h1><p class="msg bad">${esc(text)}</p><p><a href="/relief/settings">Try again</a></p></div>`;
  }

  /* textareas grow with their words where the browser cannot size them itself */
  const SIZES = typeof CSS !== "undefined" && CSS.supports && CSS.supports("field-sizing", "content");
  function fit(el) { if (SIZES || !el) return; el.style.height = "auto"; el.style.height = el.scrollHeight + 2 + "px"; }
  function fitAll() { document.querySelectorAll("textarea[data-rule]").forEach(fit); }

  /* ---------------------------------------------------------------- changes */
  function changed() {
    S.dirty = true;
    S.msg = ""; S.bad = false;
    paintBars();
  }

  function redraw(focus) {   /* a change to the shape of the form: draw it again and put the cursor back */
    changed(); render();
    if (focus) { const el = $(focus); if (el) el.focus(); }
  }

  function pickName(key, name) {
    const L = listOf(key);
    if (name && !L.includes(name)) L.push(name);
    S.q = ""; redraw("#pickQ");
  }

  function move(list, i, by) {
    const j = i + by; if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
  }

  function onClick(e) {
    const b = e.target.closest("button,a[data-dl]"); if (!b || b.matches(":disabled")) return;
    const ds = b.dataset, i = Number(ds.i), f = S.f;
    if (ds.act === "save") { save(); return; }
    if (ds.dl !== undefined) { e.preventDefault(); download(b); return; }
    if (ds.pick) { S.open = ds.pick; S.q = ""; render(); const q = $("#pickQ"); if (q) q.focus(); return; }
    if (ds.pickdone) { S.open = null; S.q = ""; render(); return; }
    if (ds.add) { pickName(ds.add, ds.name); return; }
    if (ds.unchip) { listOf(ds.unchip).splice(i, 1); redraw(); return; }
    if (ds.act === "addRule") { f.rules.push(""); redraw(`[data-rule="${f.rules.length - 1}"]`); return; }
    if (ds.up !== undefined) { move(f.rules, Number(ds.up), -1); redraw(`[data-up="${Number(ds.up) - 1}"]`); return; }
    if (ds.down !== undefined) { move(f.rules, Number(ds.down), 1); redraw(`[data-down="${Number(ds.down) + 1}"]`); return; }
    if (ds.unrule !== undefined) { f.rules.splice(Number(ds.unrule), 1); redraw(); return; }
    if (ds.act === "addTerm") { f.calendar.terms.push({ name: "", start: "", end: "", starts_as: null }); redraw(`[data-term="name"][data-i="${f.calendar.terms.length - 1}"]`); return; }
    if (ds.unterm !== undefined) { f.calendar.terms.splice(Number(ds.unterm), 1); redraw(); return; }
    if (ds.act === "addHoliday") { f.calendar.holidays.push({ name: "", start: "", end: "" }); redraw(`[data-hol="name"][data-i="${f.calendar.holidays.length - 1}"]`); return; }
    if (ds.unhol !== undefined) { f.calendar.holidays.splice(Number(ds.unhol), 1); redraw(); return; }
  }

  function onInput(e) {
    const el = e.target, ds = el.dataset, i = Number(ds.i), f = S.f, v = el.value;
    if (!f) return;
    if (el.id === "pickQ") { S.q = v; const ul = $("#pickList"); if (ul && S.open) ul.innerHTML = pickItems(S.open); return; }
    const num = x => x === "" ? null : Number(x);
    if (ds.fat) { f.fat_role = v; $("#fatCount").innerHTML = fatCount(); changed(); return; }
    if (ds.rule !== undefined) { f.rules[Number(ds.rule)] = v; fit(el); changed(); return; }
    if (ds.lim) { f.limits[ds.lim] = num(v); changed(); return; }
    if (ds.t) { f.times[ds.t] = ds.t === "report_every" ? num(v) : v; changed(); return; }
    if (ds.term) { f.calendar.terms[i][ds.term] = ds.term === "starts_as" ? (v || null) : v; changed(); return; }
    if (ds.hol) { f.calendar.holidays[i][ds.hol] = v; changed(); return; }
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
    if (S.busy || !S.data.can_save) return;
    S.busy = true; S.msg = ""; S.bad = false; paintBars();
    let r, j = {};
    try {
      r = await fetch("/api/relief/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.f) });
      j = await r.json().catch(() => ({}));
    } catch (err) {
      S.busy = false; S.bad = true; S.msg = "Could not reach the server. Nothing was saved: try again."; paintBars(); return;
    }
    S.busy = false;
    if (r.status === 401) { location.href = "/login"; return; }
    if (!r.ok) { S.bad = true; S.msg = j.error || "Nothing was saved. Try again."; paintBars(); return; }
    S.data = j; S.f = clone(j.settings); S.dirty = false; S.bad = false; S.msg = "Saved."; S.open = null; S.q = "";
    links(); render();
  }

  async function download(a) {
    const msg = $("#dlMsg"), say = (t, bad) => { if (msg) { msg.textContent = t; msg.className = "dlmsg" + (bad ? " msg bad" : ""); } };
    say("Making the file…");
    let r;
    try { r = await fetch(a.getAttribute("href"), { cache: "no-store" }); }
    catch (err) { say("Could not reach the server. Try again.", true); return; }
    if (r.status === 401) { location.href = "/login"; return; }
    if (!r.ok) {   /* the server's own words: JSON {error} (not the committee) or plain text (codes are off) */
      const t = await r.text().catch(() => "");
      let s = t; try { s = JSON.parse(t).error || t; } catch (err) { /* plain text */ }
      say(s || "The file could not be made.", true); return;
    }
    const blob = await r.blob(), cd = r.headers.get("Content-Disposition") || "", m = /filename="?([^";]+)"?/.exec(cd);
    const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = m ? m[1] : a.dataset.dl;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 10000);
    say("");
  }

  async function start() {
    let r, j = {};
    try { r = await fetch("/api/relief/settings", { cache: "no-store" }); j = await r.json().catch(() => ({})); }
    catch (err) { fail("Could not reach the server. Check the connection and try again."); return; }
    if (r.status === 401) { location.href = "/login"; return; }
    if (!r.ok) { fail(j.error || "Something went wrong."); return; }
    S.data = j; S.f = clone(j.settings);
    links(); render();
  }

  /* ================================================================ Telegram */
  /* The bot, for whoever may save the settings (a 401 or a 403 shows nothing): whether its token is set and it is connected, who is
     linked and who is not, from /api/relief/telegram/admin. Connect, Disconnect and Unlink are done at once, the last two after a
     question, and each answers with how things are now; after a refusal they are read again, under the server's sentence. The card
     draws itself only, and of itself only what changes: nothing typed in the form is lost, and the focus and an open list stay. */
  const WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const TG_URL = "/api/relief/telegram/", UNREACHABLE = "Could not reach the server. Check the connection and try again.";
  const NO_TOKEN = "Not set up yet. The bot's token goes in Railway's variables (TELEGRAM_BOT_TOKEN) of the copy the school uses; then come back here and press Connect. How to make the bot is in docs/DEPLOY.md.";
  const NOT_YET = "The token is set. Connect points Telegram at this copy of the app.";
  const ONE_COPY = "The bot works on one copy of the app only. Connect it on the copy the school uses.";
  /* data: how things are, as last read (null: nothing shows, or err does); ask: {what: "disconnect"} or {what: "unlink", name} while
     it is asked; busy: a step is on its way; msg: what the last one answered; drawn: part of the card -> its HTML */
  const TG = { box: $("#telegram"), data: null, err: null, ask: null, busy: false, msg: null, drawn: {} };

  const tgRows = v => (Array.isArray(v) ? v : []);

  function dayOf(iso) {   /* "Mon 12 Oct" */
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    return m ? `${WEEK[new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])).getUTCDay()]} ${+m[3]} ${MONTHS[+m[2] - 1]}` : String(iso || "");
  }

  function tgButton(act, label, cls, name) {
    return `<button type="button" class="${cls}" data-tg="${act}"${name === undefined ? "" : ` data-name="${esc(name)}"`}${TG.busy ? " disabled" : ""}>${esc(label)}</button>`;
  }

  function tgAsk(q, act, label, name) {
    return `<div class="ask" role="group" aria-label="${esc(q)}"><span class="q">${esc(q)}</span>${tgButton(act, label, "small danger", name)}${tgButton("keep", "Keep it", "small")}</div>`;
  }

  function tgSay(m) {   /* signed out: a way to sign in again without losing this page */
    const again = m.status === 401 ? ` <a href="/login" target="_blank" rel="noopener">Sign in again (opens a new tab)</a>, then try once more.` : "";
    return `<span class="msg ${m.bad ? "bad" : "ok"}">${esc(m.text)}${again}</span>`;
  }

  function tgState(d) {
    if (!d.connected) return esc(d.token_set ? NOT_YET : NO_TOKEN);
    return `<b>${esc(`Connected as @${d.bot}${d.at ? ` since ${dayOf(d.at)}` : ""}${d.base ? `: ${d.base}` : ""}`)}</b>`;
  }

  function tgCount(d) {
    const people = Number(d.people) || 0;
    return d.connected ? esc(`${people - tgRows(d.not_linked).length} of ${people} linked`) : "";
  }

  function tgActs(d) {
    if (!d.token_set) return "";
    if (!d.connected) return `<div class="codes">${tgButton("connect", "Connect the bot", "primary")}</div>`;
    const ask = TG.ask && TG.ask.what === "disconnect";
    return `<div class="codes">${tgButton("connect", "Connect again", "")}${ask ? "" : tgButton("ask-off", "Disconnect", "danger")}</div>`
      + (ask ? tgAsk("Disconnect? Nobody gets messages until it is connected again.", "disconnect", "Disconnect") : "");
  }

  function tgLinked(x) {
    const ask = TG.ask && TG.ask.what === "unlink" && TG.ask.name === x.name, about = [x.handle ? `@${x.handle}` : "", x.at ? `since ${dayOf(x.at)}` : ""].filter(Boolean).join(" · ");
    return `<li><span class="who">${esc(x.name)} <span class="muted">${esc(about)}</span></span>${ask ? tgAsk(`Stop relief messages to ${x.name}?`, "unlink", "Unlink", x.name) : tgButton("ask", "Unlink", "small", x.name)}</li>`;
  }

  function tgLists(d) {
    if (!d.connected) return "";
    const open = new Set([...TG.box.querySelectorAll("details")].filter(x => x.open).map(x => x.dataset.k));
    const list = (k, title, rows) => `<details data-k="${k}"${open.has(k) ? " open" : ""}><summary data-k="${k}">${esc(`${title} (${rows.length})`)}</summary><ul class="tg-${k}">${rows.join("") || `<li class="muted">Nobody.</li>`}</ul></details>`;
    return list("no", "Not linked", tgRows(d.not_linked).map(n => `<li>${esc(n)}</li>`)) + list("yes", "Linked", tgRows(d.linked).map(tgLinked));
  }

  function tgPut(id, html) {
    if ((TG.drawn[id] || "") !== html) $(`#${id}`, TG.box).innerHTML = TG.drawn[id] = html;
  }

  function tgFind(act, name) { return [...TG.box.querySelectorAll(`[data-tg="${act}"]`)].find(b => name === undefined || b.dataset.name === name); }

  function tgPaint() {
    const d = TG.data;
    TG.box.hidden = !d && !TG.err;   /* an empty one is no region of the page */
    if (TG.box.hidden) { TG.box.innerHTML = ""; TG.drawn = {}; return; }
    if (!TG.drawn.card) {   /* live: the lines that change, each on its own, so that one is not said with another */
      TG.drawn = { card: true };
      TG.box.innerHTML = `<div class="card tg"><h2>Telegram</h2><div id="tgTop"><div id="tgPractice"></div><p class="tg-state" id="tgState" aria-live="polite"></p><p class="tg-state" id="tgCount" aria-live="polite"></p>
        <div class="small muted" id="tgOne"></div></div><div id="tgActs"></div><div id="tgSay" aria-live="polite"></div><div id="tgLists"></div></div>`;
    }
    const a = document.activeElement, had = a && TG.box.contains(a) ? a : null;
    tgPut("tgPractice", d && d.practice ? `<p class="notice">Practice mode: nothing is sent to Telegram.</p>` : "");
    tgPut("tgState", d ? tgState(d) : tgSay(TG.err));
    tgPut("tgCount", d ? tgCount(d) : "");
    tgPut("tgOne", d && d.token_set ? esc(ONE_COPY) : "");
    tgPut("tgActs", d ? tgActs(d) : `<div class="codes">${tgButton("reload", "Try again", "small")}</div>`);
    tgPut("tgSay", TG.msg ? tgSay(TG.msg) : "");
    tgPut("tgLists", d ? tgLists(d) : "");
    if (!had || TG.box.contains(had)) return;
    const now = had.dataset.tg ? tgFind(had.dataset.tg, had.dataset.name) : had.dataset.k ? $(`summary[data-k="${had.dataset.k}"]`, TG.box) : null;
    if (now) now.focus({ preventScroll: true });
  }

  function tgFocus(...els) {   /* what had the focus is gone: the first of these there is. Focus that is somewhere stays there */
    const a = document.activeElement, el = els.find(Boolean);
    if (el && (!a || a === document.body)) el.focus({ preventScroll: true });
  }

  async function tgApi(path, body) {
    let r, j = {};
    try {
      r = await fetch(TG_URL + path, body === undefined ? { cache: "no-store" } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      j = await r.json().catch(() => ({}));
    } catch (err) { return { ok: false, status: 0, error: UNREACHABLE }; }
    return r.ok ? { ok: true, status: r.status, data: j } : { ok: false, status: r.status, error: (j && j.error) || "Something went wrong. Try again." };
  }

  function tgSet(d) {   /* how things are now; a question about what is no more goes */
    TG.data = d;
    if (TG.ask && !(d.connected && (TG.ask.what === "disconnect" || tgRows(d.linked).some(x => x.name === TG.ask.name)))) TG.ask = null;
  }

  async function tgRead() {
    const r = await tgApi("admin");
    TG.busy = false;
    if (r.ok) tgSet(r.data);
    else TG.err = r.status === 401 || r.status === 403 ? null : { text: r.error, bad: true };
    tgPaint();
  }

  async function tgStep(path, body, said) {
    TG.busy = true; TG.msg = null; tgPaint();
    const r = await tgApi(path, body);
    if (r.ok) { TG.ask = null; tgSet(r.data); TG.msg = said ? { text: said, bad: false } : null; }
    else {
      TG.msg = { text: r.error, bad: true, status: r.status };
      const now = await tgApi("admin");
      if (now.ok) tgSet(now.data);
    }
    TG.busy = false;
    tgPaint();
    tgFocus(tgFind("keep"), path === "unlink" && $(`summary[data-k="yes"]`, TG.box), tgFind("connect"));
  }

  function tgAsking(ask) {
    const was = TG.ask;
    TG.ask = ask; TG.msg = null; tgPaint();
    tgFocus(ask ? tgFind("keep") : was && was.what === "unlink" ? tgFind("ask", was.name) : tgFind("ask-off"));
  }

  function tgClick(e) {
    const b = e.target.closest("button[data-tg]");
    if (!b || b.disabled) return;
    switch (b.dataset.tg) {
      case "reload": TG.busy = true; tgPaint(); tgRead().then(() => tgFocus(tgFind("reload"), tgFind("connect"))); return;
      case "connect": tgStep("connect", {}, "Connected."); return;
      case "ask-off": tgAsking({ what: "disconnect" }); return;
      case "ask": tgAsking({ what: "unlink", name: b.dataset.name }); return;
      case "keep": tgAsking(null); return;
      case "disconnect": tgStep("disconnect", {}); return;
      case "unlink": tgStep("unlink", { name: b.dataset.name }); return;
    }
  }

  TG.box.addEventListener("click", tgClick);
  TG.box.addEventListener("keydown", e => { if (e.key === "Escape" && TG.ask && !TG.busy) { e.preventDefault(); tgAsking(null); } });

  document.addEventListener("click", onClick);
  document.addEventListener("input", onInput);
  document.addEventListener("keydown", onKey);
  window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
  start();
  tgRead();
})();

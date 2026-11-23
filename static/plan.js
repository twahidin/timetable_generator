"use strict";
/* Plan with AI (/plan, and /plan?exam=<id> to carry on with that exam at once), for the people who may change exams.
   The start screen: what is missing, the buttons that open a talk, and the box. The talk: its lines (one pure function draws
   each kind), Stop and the progress while the AI works (the page polls every second then, and not at all otherwise), the box
   with Paste a list and Add a file, and on the right "Filled in so far", read from the draft (on a phone a folded panel above
   the talk). Every text of the server goes through esc; nothing of it is put in as HTML, and a link is a link only when it is
   one of the app's own ("/..."). The buttons that change something come only from the app's fields: undo, buttons, quick. */
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const OFF = "Plan with AI is not set up on this server.";
  const CODES = "Teachers go as codes. A name the app does not know is sent as typed.";
  const NOTHING = "Nothing yet: say what you want to plan.";
  const TOUCH = "The page lost touch with the app. Reload to carry on.";
  const BAD_FILE = "Give an Excel or Word file, or paste the list.";
  const NEW_TALK = "Start a new talk? The exam stays as it is.";
  const LOST = "This talk was lost when the app restarted. Your exam is safe: press Carry on.";
  const EMPTY = "Type what you want to say first.";
  const NO_SERVER = "Could not reach the server. Check the connection and try again.";
  const WRONG = "Something went wrong. Try again.";
  const MOST_BYTES = 5 * 1024 * 1024, COUNT_FROM = 1800;
  const KEEP = "plan.talk";       /* sessionStorage: the id of the talk this tab is in, and nothing else of a talk */
  const P = {
    start: null, id: null, lines: [], view: null, last: 0, tok: 0, timer: null, fails: 0, needFull: false, sending: false,
    alert: "", alertTimer: null, file: "", touch: false, drawn: new WeakMap()
  };

  /* ---------------------------------------------------------------- pure helpers (tests/plan.test.js cuts them out) */
  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  /* a link of the app's own: one "/" and a path, never "//elsewhere" or "/\\elsewhere", and no space or control character
     anywhere (a browser drops a tab or a new line, so "/<tab>/host" would be "//host") */
  function isLocal(href) {
    return typeof href === "string" && /^\/(?![\/\\])[^\s\x00-\x1f\x7f]*$/.test(href);
  }

  /* a link when it is the app's own, opened in a new tab: every link the page draws leaves /plan, and the talk stays open in
     this tab. Anything else is its label as plain text; no link, nothing */
  function linkHtml(href, label) {
    if (!href) return "";
    return isLocal(href) ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(label)}</a>` : esc(label);
  }

  /* what the page opens on: a new talk on the exam the address names, the talk this tab was in (remembered: its id), or the
     start screen. -> {how: "exam", exam} | {how: "reopen", id} | {how: "start"} */
  function bootChoice(search, remembered) {
    const exam = new URLSearchParams(search || "").get("exam");
    if (exam) return { how: "exam", exam };
    if (typeof remembered === "string" && remembered) return { how: "reopen", id: remembered };
    return { how: "start" };
  }

  /* the table of a list line: the head it gives and its rows, or nothing */
  function readAsTable(table) {
    if (!table || !Array.isArray(table.head) || !Array.isArray(table.rows) || !table.rows.length) return "";
    const head = table.head.map(h => `<th scope="col">${esc(h)}</th>`).join("");
    const rows = table.rows.map(r => `<tr>${(Array.isArray(r) ? r : []).map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("");
    return `<div class="tablewrap pl-table"><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  /* one line of the talk. isLast: the talk's last line (its quick answers show there only); working: the AI is answering
     (no quick answers, and Take it back and a list's buttons wait); examLink: the exam page (view.exam.link), for a done
     step's "See it" */
  function lineHtml(line, isLast, working, examLink) {
    const l = line || {}, kind = ["me", "ai", "did", "sys", "list"].includes(l.kind) ? l.kind : "sys", off = working ? " disabled" : "";
    let body = `<div class="tx">${kind === "did" ? "✓ " : ""}${esc(l.text)}</div>`;
    if (kind === "did" && l.step) {
      const see = isLocal(examLink) ? linkHtml(examLink, "See it") : "";
      const back = l.undo === true ? `<button type="button" class="small" data-act="undo" data-a="${esc(l.step)}"${off}>Take it back</button>`
        : l.undo === false ? `<span class="muted small">Taken back</span>` : "";
      if (see || back) body += `<div class="acts">${see}${see && back ? " · " : ""}${back}</div>`;
    }
    if (kind === "list") {
      body += readAsTable(l.table);
      const left = Array.isArray(l.left) ? l.left : [];
      if (left.length) body += `<ul class="left">${left.map(r => `<li>${r && r.line != null ? `Row ${esc(r.line)}: ` : ""}${esc(r && r.text)}</li>`).join("")}</ul>`;
      const b = Array.isArray(l.buttons) ? l.buttons : [];
      if (b.length && typeof l.list === "string" && l.list)
        body += `<div class="row acts">${b.map((x, i) => `<button type="button" data-act="list" data-a="${esc(l.list)}" data-b="${i === 0 ? "yes" : "no"}"${off}>${esc(x)}</button>`).join("")}</div>`;
    }
    const quick = kind === "ai" && isLast && !working && Array.isArray(l.quick) ? l.quick.slice(0, 4) : [];
    if (quick.length) body += `<div class="row qk">${quick.map(q => `<button type="button" data-act="pick" data-a="${esc(q)}">${esc(q)}</button>`).join("")}</div>`;
    return `<div class="ln ${kind}" data-n="${esc(l.n)}">${body}</div>`;
  }

  /* the lines of "Filled in so far": a mark and words by state, the title, the text, and Open when the line has a link */
  function checklistHtml(items) {
    const WORDS = { done: "✓", check: "To check", todo: "Still to do", last: "As last time", form: "On the exam page" };
    const CHIP = { done: "ok", check: "amber", todo: "", last: "amber", form: "" };
    return `<ul class="pl-list">${(Array.isArray(items) ? items : []).map(it => {
      const x = it || {}, st = WORDS[x.state] ? x.state : "todo", open = linkHtml(x.link, "Open");
      const mark = st === "done" ? `✓<span class="sr"> Done</span>` : WORDS[st];
      return `<li><div class="ckhead"><b>${esc(x.title)}</b><span class="chip ${CHIP[st]}">${mark}</span></div>`
        + `<div class="muted small">${esc(x.text)}${open ? " " + open : ""}</div></li>`;
    }).join("")}</ul>`;
  }

  /* how long until the next poll: a second while the AI works, none when it is done; after a failed poll 3 s, five times, then none */
  function nextWait(working, fails) {
    if (fails > 5) return null;
    if (fails > 0) return 3000;
    return working ? 1000 : null;
  }

  function sizeText(bytes) {
    const b = Number(bytes) || 0;
    if (b < 1024) return `${b} B`;
    if (b < 1024 * 1024) return `${Math.round(b / 1024)} KB`;
    return `${(b / (1024 * 1024)).toFixed(1)} MB`;
  }

  /* the folded panel's summary on a phone: how many lines are done */
  function summaryText(items) {
    const all = Array.isArray(items) ? items : [];
    return all.length ? `Filled in so far: ${all.filter(x => x && x.state === "done").length} of ${all.length}` : "Filled in so far";
  }

  /* the talk's lines in order by n: a later copy of a line replaces it; full: the reply holds the whole talk */
  function mergeLines(old, incoming, full) {
    const by = new Map();
    if (!full) (old || []).forEach(l => by.set(l.n, l));
    (Array.isArray(incoming) ? incoming : []).forEach(l => { if (l && Number.isInteger(l.n)) by.set(l.n, l); });
    return Array.from(by.values()).sort((a, b) => a.n - b.n);
  }

  function counterText(n) {
    return `${Number(n).toLocaleString("en-US")} of 2,000 characters`;
  }

  /* the chip's class from the server's label */
  function chipClass(label) {
    const l = String(label || "");
    if (l === "Ended") return "ended";
    if (l === "Withdrawn") return "withdrawn";
    if (l.startsWith("Waiting")) return "waiting";
    if (l.startsWith("Approved")) return "approved";
    return "";
  }

  /* the talk this tab is in, by its id only; a browser may refuse the storage, and the page then works without it */
  function remember(id) { try { sessionStorage.setItem(KEEP, id); } catch (e) { /* no storage */ } }
  function forget() { try { sessionStorage.removeItem(KEEP); } catch (e) { /* no storage */ } }
  function remembered() { try { return sessionStorage.getItem(KEEP); } catch (e) { return null; } }

  /* ---------------------------------------------------------------- the server */
  /* -> {ok, status, j}; status 0 when the server could not be reached; 401 goes to the sign-in page */
  async function api(method, url, body, form) {
    let r, j = {};
    try {
      const o = { method, cache: "no-store" };
      if (form) o.body = form;
      else if (body !== undefined) { o.headers = { "Content-Type": "application/json" }; o.body = JSON.stringify(body); }
      r = await fetch(url, o);
      j = await r.json().catch(() => ({}));
    } catch (err) {
      return { ok: false, status: 0, j: { error: NO_SERVER } };
    }
    if (r.status === 401) location.href = "/login";
    return { ok: r.ok, status: r.status, j: j && typeof j === "object" ? j : {} };
  }
  function talkUrl(rest) { return `/api/plan/talks/${encodeURIComponent(P.id)}${rest || ""}`; }

  /* a reply that ends what the page shows: signed out, no AI on the server, or the talk lost. -> whether it was one */
  function ended(r) {
    if (r.status === 401) { stopPoll(); return true; }
    if (r.status === 404) { drawOff(); return true; }
    if (r.status === 410) { lost(r.j.error); return true; }
    return false;
  }

  function stopPoll() { P.tok++; clearTimeout(P.timer); P.timer = null; }

  function drawOff() {
    stopPoll(); P.id = null; forget();
    $("#main").innerHTML = `<div class="card"><p>${esc(OFF)}</p></div>`;
  }

  function drawFail(text) {
    stopPoll(); P.id = null;
    $("#main").innerHTML = `<div class="card"><p class="msg bad">${esc(text || WRONG)}</p><p><a href="/exams">Back to Exams</a></p></div>`;
  }

  async function loadStart() {
    const r = await api("GET", "/api/plan/start");
    if (r.status === 401) return false;
    if (r.status === 404) { drawOff(); return false; }
    if (!r.ok) { drawFail(r.j.error); return false; }
    P.start = r.j;
    return true;
  }

  /* ---------------------------------------------------------------- the start screen */
  /* lostText: the sentence of a talk that was lost (410), shown above the start screen with its Carry on buttons */
  function drawStart(lostText, alertText) {
    stopPoll(); P.id = null; P.lines = []; P.view = null; P.last = 0; P.alert = alertText || ""; P.file = ""; P.touch = false;
    document.title = "Plan with AI";
    const st = P.start || {}, missing = Array.isArray(st.missing) ? st.missing : [], exams = Array.isArray(st.exams) ? st.exams : [];
    const stops = missing.some(m => m && m.stops);
    const lines = missing.map(m => { const a = linkHtml(m && m.link, "Open"); return `<p class="pl-sys">${esc(m && m.text)}${a ? " " + a : ""}</p>`; }).join("");
    const carry = exams.map(x => `<button type="button" data-act="carry" data-a="${esc(x.id)}">Carry on: ${esc(x.name)}</button>`).join("");
    $("#main").innerHTML = `<div class="card">
      <h1>What would you like to plan?</h1>
      ${lostText ? `<p class="pl-sys" role="alert">${esc(lostText)}</p>` : ""}${lines}
      ${stops ? "" : `<div class="row pl-starts"><button type="button" data-act="plan" data-a="Plan an exam">Plan an exam</button><button type="button" data-act="plan" data-a="Plan a common test">Plan a common test</button>${carry}</div>
      <div class="pl-type"><textarea id="box" rows="2" aria-label="What you would like to plan" placeholder="Type here. For example: I would like to plan an exam timetable"></textarea><button type="button" class="primary" id="send" data-act="send">Send</button></div>
      <p id="count" class="muted small"></p>
      <p id="alert" class="msg bad" role="alert">${esc(P.alert)}</p>
      <p class="muted small">${esc(CODES)}</p>`}
    </div>`;
  }

  function startBusy(on) { document.querySelectorAll("#main button, #main textarea").forEach(el => { el.disabled = on; }); }

  /* a talk opens (on an exam for Carry on); text: the first message, said at once */
  async function openTalk(exam, text) {
    startBusy(true);
    const r = await api("POST", "/api/plan/talks", exam ? { exam } : {});
    if (r.status === 401 || r.status === 404 || r.status === 410) { ended(r); return; }
    if (!r.ok || !r.j.id) {
      if (!$("#box") && !$("[data-act=plan]")) { drawStart("", r.j.error || WRONG); return; }
      startBusy(false); setAlert(r.j.error || WRONG); return;
    }
    showTalk(r.j.id, r.j.view);
    if (text) { $("#box").value = text; paintCount(); await send(); } else focusBox();
  }

  /* the talk of this id is drawn from a whole view of it, and remembered */
  function showTalk(id, view) {
    P.id = id; P.tok++; P.lines = []; P.view = null; P.last = 0; P.fails = 0; P.needFull = false; P.alert = ""; P.file = ""; P.touch = false;
    remember(id);
    drawTalk();
    apply(view, true);
  }

  /* the talk this tab was in (a reload, or back from another page): shown again; gone (410) means the start screen, quietly */
  async function reopen(id) {
    const r = await api("GET", `/api/plan/talks/${encodeURIComponent(id)}?after=0`);
    if (r.status === 401) return;
    if (r.status === 404) { drawOff(); return; }
    if (r.status === 410) { forget(); drawStart(); focusBox(); return; }
    if (!r.ok) { drawStart("", r.j.error || WRONG); return; }
    showTalk(id, r.j);
    if (!(P.view && P.view.working)) focusBox();
    schedule();
  }

  /* ---------------------------------------------------------------- the talk */
  function drawTalk() {
    $("#main").innerHTML = `<details class="card pl-fold" id="sofar-fold"><summary id="sofar-sum">Filled in so far</summary><div id="sofar-fold-body"></div></details>
    <div class="pl-cols">
      <section class="card" aria-labelledby="talkhead">
        <div class="pl-head"><h2 id="talkhead">Plan with AI</h2><button type="button" id="newtalk" data-act="newtalk">New talk</button></div>
        <div id="log" class="pl-log" role="log" aria-live="polite" aria-label="The talk"></div>
        <p id="touch" class="pl-sys" role="alert" hidden>${esc(TOUCH)}</p>
        <div class="pl-work"><span id="progress" class="muted small" role="status"></span><button type="button" id="stop" data-act="stop" hidden>Stop</button></div>
        <div class="pl-type"><textarea id="box" rows="2" aria-label="Your answer" placeholder="Type your answer"></textarea><button type="button" class="primary" id="send" data-act="send">Send</button></div>
        <div class="row pl-more"><button type="button" id="pastelist" data-act="pasteopen" aria-expanded="false" aria-controls="pastebox">Paste a list</button><button type="button" id="addfile" data-act="file">Add a file</button><span id="fileline" class="muted small"></span><span id="count" class="muted small"></span></div>
        <div id="pastebox" class="pl-paste" hidden><textarea id="pastetext" rows="10" aria-label="The list of papers" placeholder="Paste the list of papers here"></textarea>
          <div class="row"><button type="button" class="primary" id="readlist" data-act="readlist">Read the list</button><button type="button" id="pasteback" data-act="pasteback">Back</button></div></div>
        <p id="alert" class="msg bad" role="alert"></p>
        <p id="why" class="muted small"></p>
        <p class="muted small">${esc(CODES)}</p>
        <input type="file" id="file" accept=".xlsx,.docx" hidden>
      </section>
      <aside class="card pl-side" id="sofar" aria-labelledby="sofarhead"><h2 id="sofarhead">Filled in so far</h2><div id="sofar-body"></div></aside>
    </div>`;
  }

  /* what a reply of the talk says. full: its lines are the whole talk */
  function apply(v, full) {
    if (!v || typeof v !== "object") return;
    const was = !!(P.view && P.view.working);
    P.lines = mergeLines(P.lines, v.lines, full);
    P.last = full ? (Number.isInteger(v.last) ? v.last : 0) : Math.max(P.last, Number.isInteger(v.last) ? v.last : 0);
    P.view = v;
    if (full) P.needFull = false;
    else if (was && !v.working) P.needFull = true;     /* an answer ended: the whole talk is read once more (Take it back, a list's buttons) */
    paint();
  }

  function paint() { paintHead(); paintLog(); paintControls(); paintPanel(); }

  function paintHead() {
    const ex = P.view && P.view.exam, h = $("#talkhead"); if (!h) return;
    const html = ex ? `${esc(ex.name)} <span class="chip ${chipClass(ex.status)}">${esc(ex.status)}</span>` : "Plan with AI";
    if (h.innerHTML !== html) h.innerHTML = html;
    document.title = ex && ex.name ? `${ex.name} · Plan with AI` : "Plan with AI";
  }

  /* only what changed is drawn again, so the log's reader does not say a line twice */
  function fromHtml(html) { const d = document.createElement("div"); d.innerHTML = html; return d.firstElementChild; }
  function paintLog() {
    const log = $("#log"); if (!log) return;
    const working = !!(P.view && P.view.working), have = new Map();
    Array.from(log.children).forEach(el => have.set(el.dataset.n, el));
    P.lines.forEach((l, i) => {
      const html = lineHtml(l, i === P.lines.length - 1, working, P.view && P.view.exam ? P.view.exam.link : null);
      let el = have.get(String(l.n));
      have.delete(String(l.n));
      if (!el) { el = fromHtml(html); P.drawn.set(el, html); }
      else if (P.drawn.get(el) !== html) {
        const nu = fromHtml(html);
        if (el.className !== nu.className) { el.replaceWith(nu); el = nu; }
        else {                                  /* the same line: only its parts that changed (Taken back, quick answers coming or going) */
          const parts = Array.from(nu.children);
          parts.forEach((c, k) => { const old = el.children[k]; if (!old) el.appendChild(c); else if (old.outerHTML !== c.outerHTML) old.replaceWith(c); });
          while (el.children.length > parts.length) el.lastElementChild.remove();
        }
        P.drawn.set(el, html);
      }
      if (log.children[i] !== el) log.insertBefore(el, log.children[i] || null);
    });
    have.forEach(el => el.remove());
  }

  function setText(sel, text) { const el = $(sel); if (el && el.textContent !== text) el.textContent = text; }
  /* the alert line is emptied, then filled a moment later, so the same refusal twice is said again */
  function setAlert(text) {
    P.alert = text || ""; clearTimeout(P.alertTimer); P.alertTimer = null;
    const el = $("#alert"); if (!el) return;
    el.textContent = "";
    if (P.alert) P.alertTimer = setTimeout(() => { const e = $("#alert"); if (e) e.textContent = P.alert; }, 60);
  }
  function paintCount() { const b = $("#box"); if (b && $("#count")) setText("#count", b.value.length > COUNT_FROM ? counterText(b.value.length) : ""); }

  function paintControls() {
    if (!$("#log")) return;
    const v = P.view || {}, can = v.can || {}, working = !!v.working, busy = working || P.sending;
    const noSay = busy || can.say === false, noList = busy || can.list === false;
    $("#box").disabled = noSay; $("#send").disabled = noSay;
    $("#pastelist").disabled = noList; $("#addfile").disabled = noList; $("#readlist").disabled = noList;
    $("#stop").hidden = !working; $("#stop").disabled = P.sending;
    $("#newtalk").disabled = P.sending;
    setText("#progress", working ? String(v.progress || "") : "");
    setText("#why", !working && can.why && can.why !== P.alert ? String(can.why) : "");
    setText("#fileline", P.file);
    $("#touch").hidden = !P.touch;
    paintCount();
  }

  function paintPanel() {
    const v = P.view || {}, ex = v.exam, items = ex && Array.isArray(v.checklist) ? v.checklist : [];
    const html = ex ? `<p class="pl-exam">${linkHtml(ex.link, ex.name) || esc(ex.name)} <span class="chip ${chipClass(ex.status)}">${esc(ex.status)}</span></p>${checklistHtml(items)}`
      : `<p class="muted">${esc(NOTHING)}</p>`;
    for (const sel of ["#sofar-body", "#sofar-fold-body"]) { const el = $(sel); if (el && el.innerHTML !== html) el.innerHTML = html; }
    setText("#sofar-sum", summaryText(items));
  }

  function focusBox() { const b = $("#box"); if (b && !b.disabled) b.focus(); }

  /* ---------------------------------------------------------------- polling */
  function schedule() {
    clearTimeout(P.timer); P.timer = null;
    if (!P.id) return;
    const working = !!(P.view && P.view.working);
    const wait = P.needFull && !P.fails ? 0 : nextWait(working || P.needFull, P.fails);
    if (wait === null) { if (P.fails > 5) { P.touch = true; paintControls(); } return; }
    const tok = P.tok;
    P.timer = setTimeout(() => poll(tok), wait);
  }

  async function poll(tok) {
    if (tok !== P.tok || !P.id) return;
    const full = P.needFull;
    const r = await api("GET", talkUrl(`?after=${full ? 0 : P.last}`));
    if (tok !== P.tok) return;
    if (r.status === 401 || r.status === 404 || r.status === 410) { ended(r); return; }
    if (!r.ok) { P.fails++; schedule(); return; }    /* quietly, and again after 3 s */
    P.fails = 0;
    apply(r.j, full);
    if (full && !(P.view && P.view.working)) focusBox();
    schedule();
  }

  /* one of the person's actions on the talk. full: the reply is the whole talk (after 0); fileText: "{name}, {size}" while a
     file is on its way (the line goes once the answer is back) */
  async function act(rest, body, full, form, fileText) {
    if (!P.id || P.sending) return false;
    stopPoll(); P.sending = true; P.file = fileText || ""; paintControls();
    const r = await api("POST", talkUrl(rest), body, form);
    P.sending = false; P.file = "";
    if (r.status === 401 || r.status === 404 || r.status === 410) { ended(r); return false; }
    if (!r.ok) { paintControls(); setAlert(r.j.error || WRONG); focusBox(); schedule(); return false; }
    setAlert(""); P.fails = 0; P.touch = false;
    apply(r.j, full);
    if (!(P.view && P.view.working)) focusBox();
    schedule();
    return true;
  }

  async function send() {
    const box = $("#box"); if (!box || box.disabled) return;
    const text = box.value;
    if (!P.id) {
      if (!text.trim()) { setAlert(EMPTY); box.focus(); return; }
      openTalk(null, text); return;
    }
    if (await act("/say", { text, after: P.last }, false)) { const b = $("#box"); if (b) { b.value = ""; paintCount(); } }
  }

  async function readList() {
    const t = $("#pastetext"); if (!t) return;
    if (await act("/list", { text: t.value, after: P.last }, false)) { t.value = ""; pasteBox(false, false); }
  }

  function pasteBox(open, focus) {
    const box = $("#pastebox"), b = $("#pastelist"); if (!box) return;
    box.hidden = !open; b.setAttribute("aria-expanded", String(open));
    if (focus) (open ? $("#pastetext") : b).focus();
  }

  function addFile(f) {
    if (!f) return;
    const text = `${f.name}, ${sizeText(f.size)}`;
    if (f.size > MOST_BYTES) { P.file = text; paintControls(); setAlert(BAD_FILE); return; }   /* the page says so itself and sends nothing */
    const form = new FormData(); form.append("file", f, f.name);
    act(`/list?after=${P.last}`, undefined, false, form, text);
  }

  async function newTalk() {
    if (!window.confirm(NEW_TALK)) return;
    if (P.sending) return;
    const id = P.id; stopPoll();
    P.sending = true; P.id = null; forget(); paintControls();    /* nothing more is sent to the talk being closed */
    if (id) { const r = await api("DELETE", `/api/plan/talks/${encodeURIComponent(id)}`); if (r.status === 401) return; if (r.status === 404) { P.sending = false; drawOff(); return; } }
    P.sending = false;
    if (location.search) history.replaceState(null, "", "/plan");
    if (await loadStart()) { drawStart(); focusBox(); }
  }

  /* 410: the talk is gone (the app restarted, or it was closed): the sentence, and the start screen with its Carry on buttons */
  async function lost(text) {
    stopPoll(); P.id = null; forget();
    if (location.search) history.replaceState(null, "", "/plan");
    if (await loadStart()) drawStart(text || LOST);
  }

  /* ---------------------------------------------------------------- events */
  function onClick(e) {
    const b = e.target.closest("button[data-act]"); if (!b || b.disabled) return;
    const a = b.dataset.act, v = b.dataset.a;
    if (a === "send") send();
    else if (a === "plan") openTalk(null, v);
    else if (a === "carry") openTalk(v, "");
    else if (a === "pick") act("/say", { pick: v, after: P.last }, false);
    else if (a === "undo") act("/undo", { step: v, after: 0 }, true);
    else if (a === "list") act(`/list/${encodeURIComponent(v)}`, { yes: b.dataset.b === "yes", after: 0 }, true);
    else if (a === "stop") act("/stop?after=0", undefined, true);
    else if (a === "newtalk") newTalk();
    else if (a === "pasteopen") pasteBox($("#pastebox").hidden, true);
    else if (a === "pasteback") pasteBox(false, true);
    else if (a === "readlist") readList();
    else if (a === "file") $("#file").click();
  }

  function onKey(e) {
    if (e.target.id !== "box" || e.key !== "Enter" || e.shiftKey || e.isComposing) return;
    e.preventDefault(); send();     /* Enter sends; Shift+Enter makes a new line */
  }

  document.addEventListener("click", onClick);
  document.addEventListener("keydown", onKey);
  document.addEventListener("input", e => { if (e.target.id === "box") paintCount(); });
  document.addEventListener("change", e => { if (e.target.id === "file") { const f = e.target.files && e.target.files[0]; e.target.value = ""; addFile(f); } });

  (async function boot() {
    if (!(await loadStart())) return;
    const go = bootChoice(location.search, remembered());
    if (go.how === "exam") openTalk(go.exam, "");      /* a new talk on that exam; it is remembered in place of the old one */
    else if (go.how === "reopen") reopen(go.id);
    else { drawStart(); focusBox(); }
  })();
})();

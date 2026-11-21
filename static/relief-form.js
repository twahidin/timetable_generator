"use strict";
/* Shared by the Relief pages (relief.js, relief-plan.js): the lesson list of a new absence and a person picker, plus the
   small helpers every relief page uses (escaping, dates, periods).

   ReliefForm.lessons(container, lessons, opts) draws the lessons (as /api/relief/lessons gives them), each with its work:
   a work box, a link box and "Add a file". A shared lesson (x.others: its other teachers who are not away then, as
   /api/relief/lessons gives them) shows "{others} is there: no relief needed" with "Ask for cover anyway"; with nobody
   there it is an ordinary lesson to cover. What is typed is kept for each lesson key, so calling it again (other dates,
   other periods) keeps the work of every lesson still listed, and a lesson whose cover the person has not chosen follows
   the new list's others. opts: workLabel (the work box's label), empty (the line when there are no lessons), side(lesson) and extra(lesson) (HTML beside the lesson's name and under its work; escape
   what goes in them with ReliefForm.esc), onChange() (called on every edit).
   ReliefForm.read(container) gives [{key, needed?, work: {text, link, files: []}}] for POST /api/relief/absences (needed is there only when the person chose it with "Ask for cover anyway" / "No relief needed"; left out, the server decides from who is away at Send);
   ReliefForm.needed(container, key) says whether one listed lesson is to be covered.
   ReliefForm.files(container) gives [{key, files: [File]}]: a file is sent after the absence is saved (POST
   …/files), then attached with PUT …/lessons/<key>/work.
   ReliefForm.person(container, opts) is a search-as-you-type picker of people [{name, depts}].
   ReliefForm.today() is the school's date: the page sets it once from /api/relief/me with ReliefForm.setToday(iso). */
window.ReliefForm = (function () {
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const KINDS = [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"];
  const MAX_FILE = 10 * 1024 * 1024, PER_LESSON = 5;
  const WRONG_KIND = "Send a PDF, Word, PowerPoint, Excel or picture file.", TOO_BIG = "A file can be at most 10 MB.";
  const TOO_MANY = "A lesson can have at most 5 files.";
  const ENTIRE = "Entire Class";
  const forms = new WeakMap(), pickers = new WeakMap();
  let made = 0;

  /* ---------------------------------------------------------------- helpers */
  function utc(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    return m ? new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))) : null;
  }
  const isoOf = d => `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;

  function day(iso) {   /* "Sat 17 Oct" */
    const d = utc(iso);
    return d ? `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}` : String(iso ?? "");
  }

  function addDays(iso, n) {
    const d = utc(iso);
    if (!d) return "";
    d.setUTCDate(d.getUTCDate() + n);
    return isoOf(d);
  }

  let schoolToday = "";
  function setToday(iso) { if (/^\d{4}-\d{2}-\d{2}$/.test(String(iso || ""))) schoolToday = iso; }

  function today() {   /* the school's date, as the server gave it (/api/relief/me's today); the device's own date only before that */
    if (schoolToday) return schoolToday;
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  function periods(x) {   /* 0-based p in the data: "P4", or "P4–P6" for three periods */
    const p = Number(x.p) || 0, n = Math.max(1, Number(x.n) || 1);
    return n === 1 ? `P${p + 1}` : `P${p + 1}–P${p + n}`;
  }

  const time = x => x.start && x.end ? `${x.start}–${x.end}` : (x.start || "");
  const others = x => (Array.isArray(x.others) ? x.others : []).join(" and ");

  function title(x) {   /* "1A, 1B Maths (G1)" */
    const g = x.group && x.group !== ENTIRE ? ` (${x.group})` : "";
    return [(x.classes || []).join(", "), x.subject || ""].filter(Boolean).join(" ") + g;
  }

  const when = x => [periods(x), time(x), x.room || ""].filter(Boolean).join(" · ");

  /* "Some periods": from and to over every period of the day ([{p, start, end}] from /api/relief/lessons), each with its
     time; nothing is chosen until the person chooses. The selects carry data-per="from" / "to". */
  function periodSelects(idp, list, from, to) {
    const opt = (p, label, cur) => `<option value="${p}"${p === cur ? " selected" : ""}>${esc(label)}</option>`;
    const pick = `<option value=""${from === null ? " selected" : ""}>Choose…</option>`, pickTo = `<option value=""${to === null ? " selected" : ""}>Choose…</option>`;
    const froms = list.map(x => opt(Number(x.p), `P${Number(x.p) + 1}${x.start ? ` (${x.start})` : ""}`, from)).join("");
    const tos = list.filter(x => from === null || Number(x.p) >= from).map(x => opt(Number(x.p), `P${Number(x.p) + 1}${x.end ? ` (till ${x.end})` : ""}`, to)).join("");
    return `<div class="line"><label for="${esc(idp)}From">from</label><select id="${esc(idp)}From" data-per="from">${pick}${froms}</select>
      <label for="${esc(idp)}To">to</label><select id="${esc(idp)}To" data-per="to">${pickTo}${tos}</select></div>`;
  }

  function size(n) {
    n = Number(n) || 0;
    if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
    return `${Math.max(1, Math.round(n / 1024))} KB`;
  }

  function checkFile(file, have) {   /* the server's own sentences, before anything is sent */
    const name = String(file && file.name || ""), dot = name.lastIndexOf(".");
    if (dot < 0 || !KINDS.includes(name.slice(dot).toLowerCase())) return WRONG_KIND;
    if (!file.size) return WRONG_KIND;
    if (file.size > MAX_FILE) return TOO_BIG;
    if (have >= PER_LESSON) return TOO_MANY;
    return "";
  }

  const SIZES = typeof CSS !== "undefined" && CSS.supports && CSS.supports("field-sizing", "content");
  function fit(el) { if (SIZES || !el) return; el.style.height = "auto"; el.style.height = el.scrollHeight + 2 + "px"; }
  function fitAll(root) { if (!SIZES && root) root.querySelectorAll("textarea.wrapbox").forEach(fit); }

  /* ---------------------------------------------------------------- the lesson list */
  function lessons(container, list, opts) {
    let f = forms.get(container);
    if (!f) { f = { id: ++made, st: new Map(), list: [], opts: {} }; forms.set(container, f); bind(container, f); }
    f.list = Array.isArray(list) ? list : [];
    f.opts = opts || {};
    for (const x of f.list) {
      const shared = Array.isArray(x.others) && x.others.length > 0, s = f.st.get(x.key);
      if (!s) f.st.set(x.key, { needed: !shared, chosen: false, text: "", link: "", files: [], err: "" });
      else if (!s.chosen) s.needed = !shared;   /* until the person says, it follows whether someone is there */
    }
    draw(container, f);
  }

  function draw(container, f) {
    if (!f.list.length) {
      container.innerHTML = f.opts.empty === "" ? "" : `<p class="muted small rf-none">${esc(f.opts.empty || "No lessons then.")}</p>`;
      return;
    }
    const many = new Set(f.list.map(x => x.date)).size > 1;
    let html = "", last = null;
    f.list.forEach((x, i) => {
      if (many && x.date !== last) { html += `<div class="rf-date">${esc(day(x.date))}</div>`; last = x.date; }
      html += row(f, x, i);
    });
    container.innerHTML = html;
    fitAll(container);
  }

  function row(f, x, i) {
    const s = f.st.get(x.key), id = `rf${f.id}-${i}`, o = others(x), side = f.opts.side ? f.opts.side(x) || "" : "";
    const head = `<div class="rf-head"><div><b>${esc(title(x))}</b> <span class="muted">· ${esc(when(x))}</span></div>${side ? `<div class="rf-side small">${side}</div>` : ""}</div>`;
    let body;
    if (o && !s.needed) {
      body = `<div class="rf-shared"><span class="muted">${esc(o + " is there: no relief needed")}</span><button type="button" class="small" data-rf="cover">Ask for cover anyway</button></div>`;
    } else {
      const files = s.files.map((file, j) => `<span class="chip rf-file">${esc(file.name)} <span class="muted">${esc(size(file.size))}</span><button type="button" data-rf="unfile" data-j="${j}" title="Take this file off" aria-label="Take ${esc(file.name)} off">✕</button></span>`).join("");
      body = (o ? `<div class="rf-shared"><span class="muted small">${esc(o)} is there too.</span><button type="button" class="small" data-rf="nocover">No relief needed</button></div>` : "")
        + `<div class="rf-work"><label class="small muted" for="${id}-t">${esc(f.opts.workLabel || "Work for this lesson")}</label>
        <textarea id="${id}-t" class="wrapbox" data-rf="text" rows="2" maxlength="2000" placeholder="e.g. Textbook p. 112, Q1–10. Collect at the end.">${esc(s.text)}</textarea>
        <input type="url" data-rf="link" maxlength="500" value="${esc(s.link)}" placeholder="A link, if any (SLS, Google Drive): https://…" aria-label="A link for this lesson">
        <div class="rf-files">${files}<button type="button" class="small" data-rf="add">Add a file</button><input type="file" data-rf="file" multiple accept="${KINDS.join(",")}" hidden></div>
        <div class="rf-err" role="status">${esc(s.err)}</div></div>`;
    }
    const extra = f.opts.extra ? f.opts.extra(x) || "" : "";
    return `<div class="rl" data-key="${esc(x.key)}" data-i="${i}">${head}${body}${extra}</div>`;
  }

  function redrawRow(container, f, el, focus) {
    const i = Number(el.dataset.i), x = f.list[i];
    if (!x) return;
    el.outerHTML = row(f, x, i);
    const now = [...container.querySelectorAll(".rl")].find(r => r.dataset.key === x.key);
    if (now) { fitAll(now); if (focus) { const t = now.querySelector(focus); if (t) t.focus(); } }
  }

  function bind(container, f) {
    const at = el => { const r = el.closest(".rl"); return r && container.contains(r) ? [r, f.st.get(r.dataset.key)] : [null, null]; };
    const changed = () => { if (f.opts.onChange) f.opts.onChange(); };
    container.addEventListener("input", e => {
      const el = e.target, [r, s] = at(el);
      if (!r || !s) return;
      if (el.dataset.rf === "text") { s.text = el.value; fit(el); changed(); }
      else if (el.dataset.rf === "link") { s.link = el.value; changed(); }
    });
    container.addEventListener("change", e => {
      const el = e.target, [r, s] = at(el);
      if (!r || !s || el.dataset.rf !== "file") return;
      const bad = [];
      for (const file of el.files || []) {
        const why = checkFile(file, s.files.length);
        if (why) bad.push(`${file.name}: ${why}`); else s.files.push(file);
      }
      s.err = bad.join(" ");
      el.value = "";
      changed();
      redrawRow(container, f, r, '[data-rf="add"]');
    });
    container.addEventListener("click", e => {
      const b = e.target.closest("button[data-rf]"), [r, s] = b ? at(b) : [null, null];
      if (!r || !s) return;
      const what = b.dataset.rf;
      if (what === "add") { const input = r.querySelector('input[data-rf="file"]'); if (input) input.click(); return; }
      if (what === "unfile") { s.files.splice(Number(b.dataset.j), 1); s.err = ""; changed(); redrawRow(container, f, r, '[data-rf="add"]'); return; }
      if (what === "cover") { s.needed = true; s.chosen = true; changed(); redrawRow(container, f, r, '[data-rf="text"]'); return; }
      if (what === "nocover") { s.needed = false; s.chosen = true; changed(); redrawRow(container, f, r, '[data-rf="cover"]'); return; }
    });
  }

  function read(container) {
    const f = forms.get(container);
    if (!f) return [];
    return f.list.map(x => {
      const s = f.st.get(x.key);
      const row = { key: x.key, work: s.needed ? { text: s.text.trim(), link: s.link.trim(), files: [] } : { text: "", link: "", files: [] } };
      if (s.chosen) row.needed = !!s.needed;   /* only what the person chose: left out, the server decides from its records at Send */
      return row;
    });
  }

  function needed(container, key) {   /* is this lesson to be covered (a shared lesson is not, until "Ask for cover anyway")? */
    const f = forms.get(container), st = f && f.st.get(key);
    return !!(st && st.needed);
  }

  function files(container) {
    const f = forms.get(container);
    if (!f) return [];
    return f.list.map(x => [x.key, f.st.get(x.key)]).filter(([, s]) => s.needed && s.files.length).map(([key, s]) => ({ key, files: s.files.slice() }));
  }

  function redraw(container) { const f = forms.get(container); if (f) draw(container, f); }

  function reset(container) {   /* forget everything typed (after the absence is sent) */
    const f = forms.get(container);
    if (f) { f.st.clear(); f.list = []; }
    container.innerHTML = "";
  }

  /* ---------------------------------------------------------------- a person picker */
  /* opts: people [{name, depts}], value (a name or ""), exclude (names not offered), placeholder, label, onPick(name) */
  function person(container, opts) {
    let p = pickers.get(container);
    if (!p) { p = { q: "", open: false, opts: {} }; pickers.set(container, p); bindPicker(container, p); }
    p.opts = Object.assign({}, opts);
    p.open = p.open || !p.opts.value;
    drawPicker(container, p);
  }

  function matches(p) {
    const no = new Set(p.opts.exclude || []), words = p.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return (p.opts.people || []).filter(x => !no.has(x.name) && words.every(w => `${x.name} ${(x.depts || []).join(" ")}`.toLowerCase().includes(w)));
  }

  function items(p) {
    const m = matches(p);
    if (!m.length) return `<li class="muted small none">${p.q.trim() ? "No one matches." : "No one to choose."}</li>`;
    return m.map((x, i) => `<li><button type="button" class="${i === 0 && p.q.trim() ? "first" : ""}" data-pp="pick" data-name="${esc(x.name)}"><span>${esc(x.name)}</span><span class="muted">${esc((x.depts || []).join(", "))}</span></button></li>`).join("");
  }

  function drawPicker(container, p) {
    const v = p.opts.value;
    if (v && !p.open) {
      container.innerHTML = `<div class="row"><span class="chip pp-chosen">${esc(v)}</span><button type="button" class="small" data-pp="open">Change</button></div>`;
      return;
    }
    container.innerHTML = `<div class="picker"><div class="row"><input type="search" data-pp="q" value="${esc(p.q)}" placeholder="${esc(p.opts.placeholder || "Type a name or a department")}" autocomplete="off" aria-label="${esc(p.opts.label || "Find a person")}">
      ${v ? `<button type="button" class="small" data-pp="close">Keep ${esc(v)}</button>` : ""}</div><ul>${items(p)}</ul></div>`;
  }

  function bindPicker(container, p) {
    const pick = name => { p.q = ""; p.open = false; p.opts.value = name; drawPicker(container, p); if (p.opts.onPick) p.opts.onPick(name); const b = container.querySelector('[data-pp="open"]'); if (b) b.focus(); };
    container.addEventListener("input", e => {
      if (e.target.dataset.pp !== "q") return;
      p.q = e.target.value;
      const ul = container.querySelector("ul");
      if (ul) ul.innerHTML = items(p);
    });
    container.addEventListener("keydown", e => {
      if (e.target.dataset.pp !== "q") return;
      if (e.key === "Enter") { e.preventDefault(); const m = p.q.trim() ? matches(p) : []; if (m.length) pick(m[0].name); }
      if (e.key === "Escape" && p.opts.value) { e.preventDefault(); p.q = ""; p.open = false; drawPicker(container, p); }
    });
    container.addEventListener("click", e => {
      const b = e.target.closest("button[data-pp]");
      if (!b) return;
      if (b.dataset.pp === "pick") { pick(b.dataset.name); return; }
      if (b.dataset.pp === "open") { p.open = true; p.q = ""; drawPicker(container, p); const q = container.querySelector('[data-pp="q"]'); if (q) q.focus(); return; }
      if (b.dataset.pp === "close") { p.open = false; p.q = ""; drawPicker(container, p); }
    });
  }

  return { lessons, read, files, needed, redraw, reset, person, esc, day, addDays, today, setToday, periods, periodSelects, time, title, when, size, checkFile, fit, fitAll, KINDS };
})();

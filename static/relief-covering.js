"use strict";
/* Reliefs I'm covering (/relief#covering), for everyone: the reliefs a member of the relief team has approved to me, from
   the Monday of this week on, from /api/relief/covering, grouped by date: the lesson, its periods and times, the room,
   whose class it is (the absent teacher), the work set with its link (opened in a new tab) and its files (downloads), and
   Acknowledge / Request to change (a line saying why, which the relief team reads; until they act the relief stays mine).
   A past lesson is shown without its buttons, and so is one an approved exam or event stops ("Not happening", with why).
   Nothing waiting for the relief team is here, and never an absence's reason
   (the server sends none). After each step the list is read again; a refusal shows the server's sentence beside it. */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day, enc = encodeURIComponent, say = R.say;
  const $ = (s, el = document) => el.querySelector(s);
  const CHANGE_WHY = "Say in a line why you cannot take it.";
  /* ask: the cover whose "why" box is open, why: what is typed in it; msg: a line beside a cover; busy: covers with a step on its way */
  const C = { pane: null, list: null, err: null, seq: 0, loading: false, ask: null, why: "", msg: new Map(), busy: new Set() };
  const cid = c => c.id + "\n" + c.ckey;
  const keyOf = el => { const it = el && el.closest(".cv"); return it ? it.dataset.id + "\n" + it.dataset.ckey : null; };
  const find = k => (C.list || []).find(c => cid(c) === k) || null;
  const itemEl = k => [...C.pane.querySelectorAll(".cv")].find(el => keyOf(el) === k) || null;

  function clock(at) {   /* "07:20" today, else "Mon 23 Nov, 07:20" */
    const s = String(at || ""), d = s.slice(0, 10), t = s.slice(11, 16);
    if (!/^\d{2}:\d{2}$/.test(t)) return "";
    return d === RF.today() ? t : `${day(d)}, ${t}`;
  }

  function work(c) {
    const w = c.work || {}, link = /^https?:\/\//i.test(w.link || "") ? w.link : "", files = Array.isArray(w.files) ? w.files : [];
    const parts = [w.text ? `<div class="ab-work">${esc(w.text)}</div>` : "",
      link ? `<div class="ab-link small"><a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(link)}</a></div>` : "",
      files.length ? `<div class="ab-files small">${files.map(f => `<span class="chip rf-file"><a href="/api/relief/files/${esc(enc(c.id))}/${esc(enc(f.id))}" download>${esc(f.name)}</a> <span class="muted">${esc(RF.size(f.size))}</span></span>`).join("")}</div>` : ""].join("");
    return `<div class="cv-work"><div class="small muted">Work from ${esc(c.absent)}</div>${parts || `<div class="small muted ab-work">No work set yet.</div>`}</div>`;
  }

  function chip(c) {
    if (c.stopped) return `<span class="chip st-off">Not happening</span>`;
    if (c.state === "acknowledged") return `<span class="chip st-ok">✓ Acknowledged${c.ack && clock(c.ack.at) ? ` ${esc(clock(c.ack.at))}` : ""}</span>`;
    if (c.state === "change") return `<span class="chip st-blue">You asked to change</span>`;
    return `<span class="chip st-amber">Please acknowledge</span>`;
  }

  function acts(c) {
    const k = cid(c), off = C.busy.has(k) ? " disabled" : "", m = C.msg.get(k);
    const line = m ? `<div class="bar">${say(m)}</div>` : "";
    if (c.date < RF.today()) return line;   /* a past lesson: nothing to do */
    if (c.stopped) return `<div class="small">${esc(c.stopped)}: there is no lesson to cover then.</div>${line}`;
    if (C.ask === k) {
      return `<div class="ab-ask"><label for="cvWhy">${esc(CHANGE_WHY)}</label><input id="cvWhy" data-cv="why" maxlength="200" value="${esc(C.why)}" autocomplete="off" required>
        <button type="button" class="small primary" data-cv="ask-go"${off}>Send to the relief team</button><button type="button" class="small" data-cv="ask-off">Back</button></div>${line}`;
    }
    const b = [];
    if (c.state === "approved" || c.state === "change") b.push(`<button type="button" class="small primary" data-cv="ack"${off}>Acknowledge</button>`);
    if (c.state === "approved" || c.state === "acknowledged") b.push(`<button type="button" class="small" data-cv="ask"${off}>Request to change</button>`);
    const asked = c.state === "change" && c.change
      ? `<div class="small cv-asked">You asked to change${c.change.why ? `: “${esc(c.change.why)}”` : "."}<br>Until the relief team replies, this relief is still yours.</div>` : "";
    return `${asked}${b.length ? `<div class="bar">${b.join("")}</div>` : ""}${line}`;
  }

  function item(c) {
    return `<div class="rl cv${c.date < RF.today() || c.stopped ? " cv-past" : ""}" data-id="${esc(c.id)}" data-ckey="${esc(c.ckey)}" tabindex="-1">
      <div class="rf-head"><div><b>${esc(RF.title(c))}</b> <span class="muted">· ${esc(RF.when(c))}</span></div><div class="rf-side small">${chip(c)}</div></div>
      <div class="small">${esc(c.absent)}'s class</div>
      ${work(c)}${acts(c)}</div>`;
  }

  function paint() {
    const box = $("#cvBox", C.pane);
    if (!box) return;
    const f = focusNow();
    const top = `<div class="ab-top"><h2>Reliefs I'm covering</h2><button type="button" class="small" data-cv="reload"${C.loading ? " disabled" : ""}>${C.loading ? "Reading…" : "Refresh"}</button></div>`;
    let body;
    if (!C.list) body = C.err ? `<p>${say(C.err)} <button type="button" class="small" data-cv="reload">Try again</button></p>` : `<p class="muted">Loading…</p>`;
    else if (!C.list.length) body = (C.err ? `<p>${say(C.err)}</p>` : "") + `<p class="muted">No relief for you right now.</p>`;
    else {
      let last = null;
      body = (C.err ? `<p>${say(C.err)}</p>` : "") + C.list.map(c => {
        const head = c.date !== last ? `<div class="rf-date">${esc(c.date === RF.today() ? `Today, ${day(c.date)}` : day(c.date))}</div>` : "";
        last = c.date;
        return head + item(c);
      }).join("");
    }
    box.innerHTML = `<div class="card">${top}<p class="small muted ab-sub">The reliefs the relief team has given you, from this Monday on. Acknowledge each, or ask to change one, saying why.</p>${body}</div>`;
    if (f) refocus(f);
  }

  function focusNow() {
    const a = document.activeElement, k = a && C.pane.contains(a) ? keyOf(a) : null;
    return k && a.dataset && a.dataset.cv ? { k, cv: a.dataset.cv } : null;
  }

  function refocus(f, any) {   /* the same button again; any: else the relief itself (never another button: a second Return must not acknowledge) */
    const el = f && itemEl(f.k);
    if (!el) return;
    const b = el.querySelector(`[data-cv="${f.cv}"]`);
    if (b && !b.disabled) b.focus({ preventScroll: true });
    else if (any) el.focus({ preventScroll: true });
  }

  async function load() {
    const seq = ++C.seq;
    C.loading = true; paint();
    const r = await R.api("/api/relief/covering");
    if (seq !== C.seq) return;
    C.loading = false;
    if (!r.ok) { C.err = { text: r.error, bad: true, status: r.status }; paint(); return; }
    C.err = null; C.list = Array.isArray(r.data.covers) ? r.data.covers : [];
    for (const [k, m] of [...C.msg]) if (!find(k)) C.msg.delete(k);
    if (C.ask && !find(C.ask)) { C.ask = null; C.why = ""; }
    paint();
  }

  async function step(k, url, body, said) {
    const f = focusNow();
    C.busy.add(k); C.msg.delete(k); paint();
    const res = await R.api(url, R.json("POST", body));
    C.busy.delete(k);
    if (!res.ok) C.msg.set(k, { text: res.error, bad: true, status: res.status });
    else { C.msg.set(k, { text: said, bad: false }); if (C.ask === k) { C.ask = null; C.why = ""; } }
    await load();
    if (f && !focusNow()) refocus(f, true);
  }

  function send(k) {
    const c = find(k);
    if (!c) return;
    const why = C.why.trim();
    if (!why) { C.msg.set(k, { text: CHANGE_WHY, bad: true }); paint(); const w = $("#cvWhy", C.pane); if (w) w.focus(); return; }
    step(k, `/api/relief/absences/${enc(c.id)}/covers/${enc(c.ckey)}/ask-change`, { why }, "Sent to the relief team.");
  }

  function onClick(e) {
    const b = e.target.closest("button[data-cv]");
    if (!b || b.disabled) return;
    if (b.dataset.cv === "reload") { load(); return; }
    const k = keyOf(b), c = k && find(k);
    if (!c) return;
    switch (b.dataset.cv) {
      case "ack": step(k, `/api/relief/absences/${enc(c.id)}/covers/${enc(c.ckey)}/acknowledge`, {}, "Acknowledged."); return;
      case "ask": C.ask = k; C.why = ""; C.msg.delete(k); paint(); { const w = $("#cvWhy", C.pane); if (w) w.focus(); } return;
      case "ask-off": C.ask = null; C.why = ""; C.msg.delete(k); paint(); refocus({ k, cv: "ask" }, true); return;
      case "ask-go": send(k); return;
    }
  }

  function onInput(e) { if (e.target.dataset.cv === "why") C.why = e.target.value; }

  function onKey(e) {
    if (e.target.dataset.cv !== "why" || !C.ask) return;
    if (e.key === "Enter") { e.preventDefault(); if (!C.busy.has(C.ask)) send(C.ask); }
    if (e.key === "Escape") { e.preventDefault(); const k = C.ask; C.ask = null; C.why = ""; paint(); refocus({ k, cv: "ask" }, true); }
  }

  R.tab("covering", {
    init(pane) {
      C.pane = pane;
      pane.innerHTML = `<div id="cvBox"></div>`;
      pane.addEventListener("click", onClick);
      pane.addEventListener("input", onInput);
      pane.addEventListener("keydown", onKey);
      load();
    },
    shown() { load(); },
    dirty() { return !!(C.ask && C.why.trim()); },
  });
})();

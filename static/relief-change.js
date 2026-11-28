"use strict";
/* "Change the dates or times" of an absence, with what the change does lesson by lesson: on the absence cards of My absences and
   Planned by me (relief.js). Loaded after relief-form.js and relief-dates.js and before relief.js (window.Relief is read only inside
   functions).

   ReliefChange.mount(box, rec, opts) draws the controls into box: Dates (Today / Tomorrow / Pick dates, the calendar keyed
   "change:" + rec.id) and Away for (Whole day / Some periods, from and to over every period of the day, as the preview answers
   them), then "What this change does": POST …/change/preview is read again on each change, and only the newest answer is
   shown ("Nothing changes yet." while the change is none; a refusal's sentence in its place). The reason is optional (200
   characters at most). Save the change sends the dates and times with the keys the preview showed added and gone, so a request
   changed meanwhile is refused (its sentence shows and the preview is read again). opts: onDone(record | null, said): after a
   save (the answered record, "Changed.") or Close (null, ""). It gives {attach(box, rec), dirty(), busy(), stop()}: attach draws
   the same editor, as it is, into a new box (its card was drawn again), reading the preview again when the record has changed;
   stop ends it without onDone. initial, body and lines are pure, for the tests.

   opts.lessons (the relief team's Edit on All Relief Requests): "Or change one lesson", each lesson dated today or later as
   "{day} · {periods} · {title} · {relief}" (relief in Today's words, each part of a split lesson with its periods): Relief not
   needed opens "Why? (optional)" with Mark relief not needed and Back (one at a time); a lesson a person marked not needed has
   Needed again (one the app marked, a co-teacher being there, has none). opts.cancel: "Or cancel the whole request", a reason
   needed (Cancel the request is off while it is empty) and Keep it, which empties it. Each step done calls onDone(the answered
   record, what was done in a line); a refusal shows its sentence beside it. While any step is on its way, nothing else is sent. */
window.ReliefChange = (function () {
  const RF = window.ReliefForm, esc = RF.esc, enc = encodeURIComponent;
  const LOOKED = "The request has changed since you looked: look again before saving.";
  const KINDS = [["kept", "✔", "Kept"], ["added", "➕", "Added"], ["gone", "✖", "No longer needed"]];
  const owners = new WeakMap(), bound = new WeakSet();   /* box -> the editor drawn in it; the boxes listened to */
  const rel = () => window.Relief;
  const SAID = { open: "no relief teacher yet", waiting: "waiting for you", approved: "approved", acknowledged: "acknowledged", change: "asked to change" };   /* Today's words */

  /* the record's dates today or later, as Ask for relief's controls hold them */
  function initial(rec, today) {
    const dates = [...new Set(((rec && rec.dates) || []).map(String))].filter(d => d >= today).sort();
    const one = dates.length === 1 ? dates[0] : "";
    const day = one === today ? "today" : one && one === RF.addDays(today, 1) ? "tomorrow" : "pick";
    const p = rec && rec.periods, some = Array.isArray(p) && p.length === 2;
    return { day, picked: dates, away: some ? "some" : "whole", from: some ? Number(p[0]) : null, to: some ? Number(p[1]) : null };
  }

  function body(s, today) {
    const dates = s.day === "today" ? [today] : s.day === "tomorrow" ? [RF.addDays(today, 1)] : (s.picked || []).slice().sort();
    return { dates, periods: s.away === "some" ? [s.from, s.to] : null };
  }

  function lines(p) {
    const out = [];
    for (const [k, mark, label] of KINDS) for (const x of (p && p[k]) || []) out.push({ mark, text: `${label}: ${RF.day(x.date)} ${x.periods}, ${x.title} · ${x.line}` });
    const n = Number(p && p.earlier) || 0;
    if (n > 0) out.push({ mark: "", text: n === 1 ? "1 earlier lesson stays as it was." : `${n} earlier lessons stay as they were.` });
    return out;
  }

  /* who relieves lesson x, in Today's words: "Mr Sam Tan, approved", "no relief teacher yet", "relief not needed"; a split lesson's
     parts each with its periods ("P10: Mr Sam Tan, approved; P11–P12: no relief teacher yet") */
  function relief(x) {
    if (!x.needed) return "relief not needed";
    if (x.stopped) return "not happening";
    const one = c => { const w = SAID[c.state] || (c.state ? String(c.state) : SAID.open); return c.relief && c.state !== "open" ? `${c.relief}, ${w}` : w; };
    const cs = Array.isArray(x.covers) && x.covers.length ? x.covers : [{ state: "open" }];
    return cs.length === 1 ? one(cs[0]) : cs.map(c => `${RF.periods(c)}: ${one(c)}`).join("; ");
  }
  const byPerson = x => !x.needed && !!x.not_needed && x.not_needed.by !== "app";   /* a person marked it not needed (not the app, for a co-teacher there) */

  function lineHTML(l) {   /* "✔ <b>Kept:</b> …" */
    if (!l.mark) return `<div class="small muted rc-l">${esc(l.text)}</div>`;
    const i = l.text.indexOf(": ");
    return `<div class="small rc-l${l.mark === "✖" ? " rc-gone" : ""}">${l.mark} <b>${esc(l.text.slice(0, i + 1))}</b> ${esc(l.text.slice(i + 2))}</div>`;
  }

  const segBtn = (what, v, on, label) => `<button type="button" data-rc="${what}" data-v="${esc(v)}" class="${on ? "on" : ""}" aria-pressed="${on ? "true" : "false"}">${esc(label)}</button>`;

  function bind(box) {   /* once per box; the events go to the editor drawn in it */
    if (bound.has(box)) return;
    bound.add(box);
    for (const type of ["click", "input", "change", "keydown"]) box.addEventListener(type, e => { const ed = owners.get(box); if (ed) ed.on(type, e); });
  }

  function mount(box, rec, opts) {
    const o = opts || {}, t0 = RF.today();
    const S = Object.assign(initial(rec, t0), { rec, key: "change:" + rec.id, why: "", per: [], prev: null, err: null, loading: false, seq: 0, busy: false, msg: null, box: null, gone: false,
      nn: null, nnWhy: "", cwhy: "", lmsg: null, cmsg: null, drawn: {}, stepping: false });   /* nn: the lesson key whose Why? line is open; lmsg {key, text…}, cmsg: a refusal; stepping: busy with a step of these parts, not a save */
    const start = JSON.stringify(body(S, t0));
    const $ = sel => S.box.querySelector(sel);
    const idp = () => "rc-" + S.rec.id;

    function waiting() {   /* why nothing can be read yet, in a line; "" when it can */
      if (!body(S, RF.today()).dates.length) return "Choose the dates first.";
      if (S.away === "some" && (S.from === null || S.to === null)) return "Choose the periods first: from and to.";
      return "";
    }
    const ready = () => !waiting() && !S.loading && !S.err && !!S.prev && !S.prev.unchanged;

    function keep(el, paint) {   /* paint el again, the focus where it was (a button or select by its data-rc / data-per and data-v) */
      const a = document.activeElement, had = a && el.contains(a) && a !== el ? [a.dataset.rc, a.dataset.per, a.dataset.v] : null;
      paint();
      if (!had) return;
      const sel = had[1] ? `[data-per="${had[1]}"]` : had[0] ? `[data-rc="${had[0]}"]${had[2] !== undefined ? `[data-v="${had[2]}"]` : ""}` : "";
      const now = sel && el.querySelector(sel);
      if (now) now.focus();
    }

    function draw() {
      const me = (rel().me || {}).name, id = idp();
      const told = S.rec.teacher && S.rec.teacher !== me ? `<p class="small muted rc-told">${esc(`${S.rec.teacher} is told on Telegram what changed.`)}</p>` : "";
      S.box.innerHTML = `<div class="rc"><h3>Change the dates or times</h3>
        <div class="field"><div class="flabel">Dates</div><div class="rc-day"></div></div>
        <div class="field"><div class="flabel">Away for</div><div class="rc-away"></div></div>
        <div class="rc-does"><div class="rc-h">What this change does</div><div class="rc-lines"></div>
          <div class="rc-why"><label for="${esc(id)}-why">Reason for the change (optional)</label><input id="${esc(id)}-why" data-rc="why" maxlength="200" value="${esc(S.why)}" autocomplete="off"></div>
          <div class="rc-save"></div>${told}</div>${o.lessons ? `<div class="rc-one"></div>` : ""}${o.cancel ? `<div class="rc-cancel"></div>` : ""}</div>`;
      S.drawn = {};
      paintDay(); paintAway(); paintLines(); paintSave();
    }

    function paintDay() {   /* Pick dates is the calendar (relief-dates.js), which draws itself again on each change */
      const t = RF.today(), el = $(".rc-day");
      let under;
      if (S.day === "today") under = `<div class="small muted under">${esc(RF.day(t))}</div>`;
      else if (S.day === "tomorrow") under = `<div class="small muted under">${esc(RF.day(RF.addDays(t, 1)))}</div>`;
      else under = `<div class="rd-box"></div>`;
      keep(el, () => { el.innerHTML = `<div class="seg" role="group" aria-label="Which day">${segBtn("day", "today", S.day === "today", "Today")}${segBtn("day", "tomorrow", S.day === "tomorrow", "Tomorrow")}${segBtn("day", "pick", S.day === "pick", "Pick dates")}</div>${under}`; });
      if (S.day === "pick") window.ReliefDates.mount(el.querySelector(".rd-box"), { key: S.key, picked: S.picked, max: 20, onChange: list => { S.picked = list; changed(); reread(); } });
    }

    function paintAway() {
      const el = $(".rc-away");
      let under = "";
      if (S.away === "some") {
        if (!body(S, RF.today()).dates.length) under = `<div class="small muted under">Choose the dates first.</div>`;
        else if (S.per.length) under = RF.periodSelects(idp(), S.per, S.from, S.to);
        else if (S.loading) under = `<div class="small muted under">Reading the periods…</div>`;
        else if (!S.err) under = `<div class="small muted under">The published timetable has no periods to choose.</div>`;
      }
      keep(el, () => { el.innerHTML = `<div class="seg" role="group" aria-label="Away for">${segBtn("away", "whole", S.away === "whole", "Whole day")}${segBtn("away", "some", S.away === "some", "Some periods")}</div>${under}`; });
    }

    function paintLines() {
      const el = $(".rc-lines"), wait = waiting();
      let html;
      if (wait) html = `<p class="small muted rc-l">${esc(wait)}</p>`;
      else if (S.err) html = `<p class="rc-l">${rel().say(S.err)}${S.err.status === 0 ? ` <button type="button" class="small" data-rc="again">Try again</button>` : ""}</p>`;
      else if (S.loading || !S.prev) html = `<p class="small muted rc-l">Reading what this change does…</p>`;
      else if (S.prev.unchanged) html = `<p class="small muted rc-l">Nothing changes yet.</p>`;
      else html = lines(S.prev).map(lineHTML).join("") || `<p class="small muted rc-l">Nothing changes yet.</p>`;
      keep(el, () => { el.innerHTML = html; });
    }

    function paintSave() {
      const el = $(".rc-save");
      keep(el, () => {
        el.innerHTML = `<div class="bar"><button type="button" class="primary" data-rc="save"${S.busy || !ready() ? " disabled" : ""}>${S.busy && !S.stepping ? "Saving…" : "Save the change"}</button>`
          + `<button type="button" data-rc="close"${S.busy ? " disabled" : ""}>Close</button>${rel().say(S.msg)}</div>`;
      });
      paintMore();
    }

    /* ---- Or change one lesson; Or cancel the whole request (each drawn again only when what it shows has changed) */
    function paintPart(sel, html) {
      const el = $(sel);
      if (!el || S.drawn[sel] === html) return;
      S.drawn[sel] = html;
      keep(el, () => { el.innerHTML = html; });
    }

    function paintMore() {
      if (o.lessons) paintPart(".rc-one", oneHTML());
      if (o.cancel) paintPart(".rc-cancel", cancelHTML());
    }

    function oneHTML() {   /* each button names its lesson by its place in rec.lessons (data-v), never by its key in a selector */
      const t = RF.today(), off = S.busy ? " disabled" : "", list = (S.rec.lessons || []).map((x, i) => [x, i]).filter(([x]) => String(x.date) >= t)
        .sort(([a], [b]) => String(a.date).localeCompare(String(b.date)) || Number(a.p) - Number(b.p));
      const rows = list.map(([x, i]) => {
        const open = S.nn === x.key && x.needed && !x.stopped, btn = (act, label, cls) => `<button type="button" class="small${cls ? " " + cls : ""}" data-rc="${act}" data-v="${i}"${off}>${esc(label)}</button>`;
        let acts = "";
        if (open) acts = `<div class="rc-nn"><label for="${esc(idp())}-nn">Why? (optional)</label><input id="${esc(idp())}-nn" data-rc="nn-why" maxlength="200" value="${esc(S.nnWhy)}" autocomplete="off">${btn("nn-go", "Mark relief not needed", "primary")}${btn("nn-off", "Back")}</div>`;
        else if (x.needed && !x.stopped) acts = btn("nn", "Relief not needed");
        else if (byPerson(x)) acts = btn("needed", "Needed again");
        const m = S.lmsg && S.lmsg.key === x.key ? `<div class="bar">${rel().say(S.lmsg)}</div>` : "";
        return `<div class="rc-ll" data-key="${esc(x.key)}"><div class="rc-lt"><b>${esc(`${RF.day(x.date)} · ${RF.periods(x)}`)}</b> · ${esc(RF.title(x))} <span class="muted">${esc(`· ${relief(x)}`)}</span></div>${acts ? `<div class="bar">${acts}</div>` : ""}${m}</div>`;
      }).join("");
      return `<h3>Or change one lesson</h3><div class="rc-does">${rows || `<p class="small muted rc-l">No lessons today or later.</p>`}</div>`;
    }

    function cancelHTML() {
      const id = idp() + "-cwhy", off = S.busy ? " disabled" : "";
      return `<h3>Or cancel the whole request</h3><div class="rc-does"><label class="small" for="${esc(id)}">Say why in a line <b>(needed)</b></label>
        <div class="bar"><input id="${esc(id)}" data-rc="cwhy" maxlength="200" value="${esc(S.cwhy)}" autocomplete="off"><button type="button" class="small danger" data-rc="cancel"${S.busy || !S.cwhy.trim() ? " disabled" : ""}>Cancel the request</button><button type="button" class="small" data-rc="keep"${off}>Keep it</button>${rel().say(S.cmsg)}</div>
        <p class="small muted rc-told">${esc(`Everyone already told (the relief teachers and ${S.rec.teacher}) gets a message that it is cancelled.`)}</p></div>`;
    }

    /* one step on the request: Mark relief not needed, Needed again, Cancel the request; where: the lesson's key, or "cancel" */
    async function step(path, body, said, where) {
      if (S.busy || S.gone) return;
      S.busy = S.stepping = true; S.msg = null; S.lmsg = null; S.cmsg = null; paintSave();
      const r = await rel().api(`/api/relief/absences/${enc(S.rec.id)}/${path}`, rel().json("POST", body));
      S.busy = S.stepping = false;
      if (r.ok) { finish(r.data, said); return; }   /* done: said even when the editor was stopped meanwhile */
      if (S.gone) return;
      const m = { text: r.error, bad: true, status: r.status };
      if (where === "cancel") S.cmsg = m; else S.lmsg = Object.assign({ key: where }, m);
      paintSave();
      const again = () => [...S.box.querySelectorAll('[data-rc="needed"]')].find(b => (lessonAt(b.dataset.v) || {}).key === where);
      const back = where === "cancel" ? $('[data-rc="cwhy"]') : $('[data-rc="nn-why"]') || again();   /* where to try again */
      if (back) back.focus();
    }

    const lessonAt = v => (S.rec.lessons || [])[Number(v)] || null;
    function notNeeded(x) { if (x) step(`lessons/${enc(x.key)}/not-needed`, { why: S.nnWhy.trim() }, `${RF.title(x)}: relief not needed.`, x.key); }
    function cancelGo() { const why = S.cwhy.trim(); if (why) step("cancel", { why }, "Cancelled.", "cancel"); }

    function more(a, v) {   /* a click of the lesson and cancel parts; true when it was theirs */
      const x = lessonAt(v), focus = sel => { const el = $(sel); if (el) el.focus(); };
      switch (a) {
        case "nn": if (x) { S.nn = x.key; S.nnWhy = ""; S.lmsg = null; paintMore(); focus('[data-rc="nn-why"]'); } return true;
        case "nn-off": S.nn = null; S.lmsg = null; paintMore(); focus(`[data-rc="nn"][data-v="${Number(v)}"]`); return true;
        case "nn-go": notNeeded(x); return true;
        case "needed": if (x) step(`lessons/${enc(x.key)}/needed`, {}, `${RF.title(x)}: relief needed again.`, x.key); return true;
        case "cancel": cancelGo(); return true;
        case "keep": S.cwhy = ""; S.cmsg = null; delete S.drawn[".rc-cancel"]; paintMore(); focus('[data-rc="cwhy"]'); return true;   /* drawn again: the box holds what was typed */
      }
      return false;
    }

    const paintRead = () => { if (S.box && !S.gone) { paintAway(); paintLines(); paintSave(); } };

    function changed() { if (S.msg) S.msg = null; }

    /* what the change does, read again; an answer to an older read is dropped. With Some periods and no periods known yet (an
       earlier read refused), the whole day is read only for its periods */
    async function reread() {
      const b = body(S, RF.today()), seq = ++S.seq, wait = waiting(), learn = !!wait && b.dates.length > 0 && S.away === "some" && !S.per.length;
      S.prev = null; S.err = null;
      if (wait && !learn) { S.loading = false; paintRead(); return; }
      S.loading = true; paintRead();
      const r = await rel().api(`/api/relief/absences/${enc(S.rec.id)}/change/preview`, rel().json("POST", { dates: b.dates, periods: learn ? null : b.periods }));
      if (seq !== S.seq || S.gone) return;
      S.loading = false;
      if (!r.ok) { if (!learn) S.err = { text: r.error, bad: true, status: r.status }; paintRead(); return; }
      if (Array.isArray(r.data.day_periods)) S.per = r.data.day_periods;
      if (!learn) S.prev = r.data;
      paintRead();
    }

    async function save() {
      if (S.busy || !ready()) return;
      const b = body(S, RF.today()), keys = k => (S.prev[k] || []).map(x => x.key);
      S.busy = true; S.msg = null; paintSave();
      const r = await rel().api(`/api/relief/absences/${enc(S.rec.id)}/change`, rel().json("POST", { dates: b.dates, periods: b.periods, why: S.why.trim(), shown: { added: keys("added"), gone: keys("gone") } }));
      S.busy = false;
      if (r.ok) { finish(r.data, "Changed."); return; }   /* saved: said even when the editor was stopped meanwhile */
      if (S.gone) return;
      S.msg = { text: r.error, bad: true, status: r.status };
      if (r.error === LOOKED) reread(); else paintSave();
    }

    function stop() {
      S.gone = true;
      window.ReliefDates.forget(S.key);
    }

    function finish(got, said) {
      stop();
      if (o.onDone) o.onDone(got, said);
    }

    function on(type, e) {
      if (S.gone) return;
      const el = e.target;
      if (type === "click") {
        const b = el.closest("button");
        if (!b || b.disabled || !b.dataset.rc || S.busy) return;
        const a = b.dataset.rc, v = b.dataset.v;
        if (a === "day" && v !== S.day) { S.day = v; changed(); paintDay(); reread(); if (v === "pick") window.ReliefDates.focusFirst($(".rc-day .rd-box")); return; }
        if (a === "away" && v !== S.away) { S.away = v; changed(); paintAway(); reread(); return; }
        if (a === "again") { reread(); return; }
        if (a === "save") { save(); return; }
        if (more(a, v)) return;
        if (a === "close") finish(null, "");
        return;
      }
      if (type === "input") {
        if (el.dataset.rc === "why") S.why = el.value;
        else if (el.dataset.rc === "nn-why") S.nnWhy = el.value;
        else if (el.dataset.rc === "cwhy") { S.cwhy = el.value; const b = $('[data-rc="cancel"]'); if (b) b.disabled = S.busy || !S.cwhy.trim(); }
        return;
      }
      if (type === "keydown") {
        const rc = el.dataset.rc, enter = e.key === "Enter";
        if (rc === "why" && enter) { e.preventDefault(); save(); }
        else if (rc === "nn-why" && enter) { e.preventDefault(); if (!S.busy) notNeeded((S.rec.lessons || []).find(x => x.key === S.nn)); }
        else if (rc === "nn-why" && e.key === "Escape" && !S.busy) { e.preventDefault(); const i = (S.rec.lessons || []).findIndex(x => x.key === S.nn); more("nn-off", String(i)); }
        else if (rc === "cwhy" && enter) { e.preventDefault(); if (!S.busy) cancelGo(); }
        return;
      }
      const per = el.dataset.per;   /* change: from and to */
      if ((per !== "from" && per !== "to") || S.busy) return;
      const v = el.value === "" ? null : Number(el.value);
      if (per === "from") { S.from = v; if (S.from !== null && S.to !== null && S.to < S.from) S.to = null; }
      else S.to = v;
      changed(); paintAway(); reread();
    }

    function attach(b, r) {
      const again = !!r && JSON.stringify(r) !== JSON.stringify(S.rec);
      if (b === S.box && !again) return;   /* drawn there already, as it is */
      if (r) S.rec = r;
      if (S.box && owners.get(S.box) === ed) owners.delete(S.box);
      S.box = b;
      bind(b);
      owners.set(b, ed);
      draw();
      if (again && !S.busy) reread();
    }

    const ed = { on, attach, stop, busy: () => S.busy, dirty: () => !S.gone && (S.why.trim() !== "" || S.cwhy.trim() !== "" || (!!S.nn && S.nnWhy.trim() !== "") || JSON.stringify(body(S, RF.today())) !== start) };
    attach(box);
    reread();
    return { attach, stop, busy: ed.busy, dirty: ed.dirty };
  }

  return { initial, body, lines, mount };
})();

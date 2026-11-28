"use strict";
/* The Relief home (/relief) for a member of staff signed in by name (their own code or password). Tabs: My absences and Ask for relief
   (this file); Reliefs I'm covering, Relief Planning, All Relief Requests, Today's Relief Assignments, Planned Relief Assignments, Term Relief Report and Weekly summary come from relief-covering.js,
   relief-plan.js, relief-inbox.js, relief-today.js, relief-ahead.js, relief-load.js and relief-summary.js, which call
   Relief.tab(name, {init(pane, me), shown(pane), dirty()}). A tab shows only when the person may open it and its code is
   loaded. Each tab keeps its own part of the page, so moving between tabs loses nothing typed; leaving the page with
   something unsent or unsaved asks first. A refusal shows the server's sentence and keeps everything typed.
   At the top of My absences is the Link Telegram card: relief-telegram.js calls Relief.linkCard({init(box), shown()}).
   For those files, Relief also gives api, json, people, say, absences (the absence cards of My absences, for
   Planned by me), attach (a form's files, after the absence is saved), span, reason and plural; relief-plan.js adds
   freeList (the "free then" list, for Today's Change). */
(function () {
  const RF = window.ReliefForm, esc = RF.esc, day = RF.day, enc = encodeURIComponent;
  const $ = (s, el = document) => el.querySelector(s);
  const TABS = [["mine", () => true], ["ask", () => true], ["covering", () => true], ["plan", me => !!me.can_plan], ["inbox", me => !!me.can_team],
                ["today", me => !!me.can_team], ["ahead", me => !!me.can_team], ["load", me => !!me.can_team], ["summary", me => !!me.can_team]];
  const UNREACHABLE = "Could not reach the server. Check the connection and try again.";
  const mods = {};
  const plural = (n, one) => `${n} ${one}${n === 1 ? "" : "s"}`;
  const R = window.Relief = { me: null, cur: null, tab, linkCard, go, api, json, people, say, dirtyAny, absences, attach, span, reason, plural, reliefLines, approvedOf, sentSays };

  /* The relief line of a lesson to cover, read cover by cover (x.covers, in time order, never x.parts[i]): the relief teacher
     once approved (approved, acknowledged or asked to change) and the name is sent ("Being arranged" while it is not: the absent
     teacher sees it once that teacher has acknowledged), the planner's own choice still waiting ("Planned: name, waiting for the
     relief team"), else "The relief team will assign". The app's own pick is never shown as a relief. */
  const SENT = ["approved", "acknowledged", "change"];
  function approvedOf(x) { return (x.covers || []).filter(c => SENT.includes(c.state) && c.relief); }
  function reliefLines(x) {
    const covers = Array.isArray(x.covers) && x.covers.length ? x.covers : [{ state: "open", relief: x.relief || null, planned: x.planned || null }];
    const split = covers.length > 1;
    return covers.map(c => {
      const at = split ? `<span class="muted">P${Number(c.p) + 1}${Number(c.n) > 1 ? `–P${Number(c.p) + Number(c.n)}` : ""}</span> ` : "";
      if (SENT.includes(c.state) && c.relief) return `<div>${at}Relief: <b>${esc(c.relief)}</b></div>`;
      if (SENT.includes(c.state)) return `<div>${at}<span class="muted">Being arranged</span></div>`;
      if (c.planned) return `<div>${at}Planned: <b>${esc(c.planned)}</b>, waiting for the relief team</div>`;
      return `<div>${at}<span class="muted">The relief team will assign</span></div>`;
    }).join("");
  }

  /* ---------------------------------------------------------------- the server */
  async function api(url, opts) {
    let r, j = {};
    try {
      r = await fetch(url, Object.assign({ cache: "no-store" }, opts || {}));
      j = await r.json().catch(() => ({}));
    } catch (e) { return { ok: false, status: 0, error: UNREACHABLE }; }
    if (!r.ok) return { ok: false, status: r.status, error: (j && j.error) || "Something went wrong. Try again." };
    return { ok: true, status: r.status, data: j };
  }

  function json(method, body) { return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }; }

  let peopleOnce = null;
  function people() {   /* everyone relief knows [{name, depts}], read once */
    if (!peopleOnce) peopleOnce = api("/api/relief/people").then(r => { if (!r.ok) peopleOnce = null; return r; });
    return peopleOnce;
  }

  /* a message line: the server's sentence; signed out, a way to sign in again without losing this page */
  function say(m) {
    if (!m || !m.text) return "";
    const again = m.status === 401 ? ` <a href="/login" target="_blank" rel="noopener">Sign in again (opens a new tab)</a>, then try once more.` : "";
    return `<span class="msg ${m.bad ? "bad" : "ok"}" role="status">${esc(m.text)}${again}</span>`;
  }

  /* ---------------------------------------------------------------- tabs */
  const allowed = k => { const t = TABS.find(x => x[0] === k); return !!(t && R.me && t[1](R.me) && mods[k]); };

  function tab(name, mod) {   /* a tab's code registers itself; it shows if the person may open it */
    mods[name] = mod;
    if (!R.me) return;
    paintTabs();
    if (location.hash === "#" + name && allowed(name)) go(name);
  }

  function paintTabs() {
    for (const [k] of TABS) {
      const b = $(`#tab-${k}`);
      if (!b) continue;
      b.hidden = !allowed(k);
      b.classList.toggle("on", k === R.cur);
      b.setAttribute("aria-selected", k === R.cur ? "true" : "false");
    }
    $("#tabs").hidden = false;
  }

  function go(k) {
    if (!allowed(k)) k = "mine";
    R.cur = k;
    for (const [n] of TABS) { const p = $(`#pane-${n}`); if (p) p.hidden = n !== k; }
    $("#main").classList.toggle("wide", k === "inbox" || k === "today" || k === "ahead" || k === "load" || k === "summary");   /* All Relief Requests, Today's Relief Assignments, Planned Relief Assignments, Term Relief Report and Weekly summary are wide tables */
    const m = mods[k], pane = $(`#pane-${k}`);
    if (!m.started) { m.started = true; m.init(pane, R.me); }
    else if (m.shown) m.shown(pane);
    paintTabs();
    if (location.hash !== "#" + k) history.replaceState(null, "", "#" + k);
  }

  function dirtyAny() { return Object.values(mods).some(m => m.started && m.dirty && m.dirty()); }

  /* ================================================================ absences, as cards */
  /* R.absences(opts) draws absences as cards in a box: each with its lessons, their relief teacher and their work. The
     work of an absence that is not cancelled can be changed by its absent teacher or its planner, on lessons dated today
     or later (a past lesson is shown as it was, without its buttons; an absence whose dates are all past can only be
     acknowledged): what is typed is kept in drafts (absence id -> lesson key -> work, with known: the file ids the
     lesson had when the draft began) until it is saved, so a redraw never loses it. A save sends known, so a file
     someone else added meanwhile is kept. A file is sent at once and attached when the work is saved. My absences and
     Planned by me (relief-plan.js) each have one. A request still to come (not a backup for an exam or event) has Change dates
     or times: the editor (relief-change.js) opens under the card's lessons, one at a time in each box, kept in M.change while the
     card is drawn again. opts: load() -> {ok, data: [records]} or a refusal as api() gives it; empty (HTML when there are none); show(r) (which records are drawn;
     all when left out); side(r, x) (HTML beside a lesson to cover, in place of "Relief: …"; escape what goes in it);
     extra(r, x) (HTML under that lesson); painted() (after each drawing). It gives {mount(box), load(), dirty(), list(),
     error(), find(id), put(record), paint(id, focus), paintAll()}. */
  const who = n => n === R.me.name ? "you" : n;
  const owner = r => r.teacher === R.me.name || (r.how === "planned" && r.by === R.me.name);
  const lessonOf = (r, key) => r && (r.lessons || []).find(x => x.key === key);
  const lkey = (id, key) => id + "\n" + key;

  function needAck(r) { return r.how === "planned" && !r.acknowledged && !r.cancelled && r.teacher === R.me.name; }

  function status(r) {
    if (r.cancelled) return [`Cancelled${r.cancelled.by === "app" ? "" : ` by ${who(r.cancelled.by)}`}: ${r.cancelled.why}`, "st-off"];   /* by the app: a takeover, a duty changed */
    if (r.how === "planned" && !r.acknowledged) return [r.teacher === R.me.name ? "Please acknowledge and set work" : "Not acknowledged yet", "st-warn"];
    if (r.how === "planned") return ["Acknowledged", "st-ok"];
    return ["With the relief team", "st-ok"];
  }

  function span(r) {
    const p = r.periods;
    if (!Array.isArray(p) || p.length !== 2) return "whole day";
    const a = Number(p[0]) + 1, b = Number(p[1]) + 1;
    return a === b ? `P${a}` : `P${a}–P${b}`;
  }

  function reason(r) {
    const t = r.reason_text || "";
    if (r.reason === "Other") return t || "Other";
    return t ? `${r.reason}: ${t}` : (r.reason || "");
  }

  function absences(opts) {
    const M = { box: null, list: null, err: null, seq: 0, drafts: new Map(), msg: new Map(), lerr: new Map(), busy: new Set(), up: new Map(), ask: null, change: null };
    const open = r => !r.cancelled && owner(r);
    const live = r => (r.dates || []).some(d => d >= RF.today());   /* every date past: nothing left to change, only to acknowledge */
    const changeable = r => open(r) && live(r) && !r.exams && !!window.ReliefChange;   /* a backup follows its exam or event: change the duty instead */
    const changing = r => !!(M.change && M.change.id === r.id && changeable(r));
    const find = id => (M.list || []).find(r => r.id === id);
    const painted = () => { if (opts.painted) opts.painted(); };

    function draftOf(r, x) {
      const d = M.drafts.get(r.id), w = x.work || {};
      return (d && d.get(x.key)) || { text: w.text || "", link: w.link || "", files: (w.files || []).slice(), known: (w.files || []).map(f => f.id) };
    }

    function editDraft(r, x) {   /* the draft of one lesson, made from its saved work on the first change */
      let d = M.drafts.get(r.id);
      if (!d) { d = new Map(); M.drafts.set(r.id, d); }
      if (!d.has(x.key)) d.set(x.key, draftOf(r, x));
      return d.get(x.key);
    }

    function changedWork(r, k, w) {   /* a draft that differs from the saved work, on a lesson that still needs relief, today or later */
      const x = lessonOf(r, k), s = (x && x.work) || {}, ids = f => (f || []).map(o => o.id).join(" ");
      return !!(x && x.needed && x.date >= RF.today() && (w.text !== (s.text || "") || w.link !== (s.link || "") || ids(w.files) !== ids(s.files)));
    }

    function dirtyOf(r) {
      const d = M.drafts.get(r.id);
      return !!(d && !r.cancelled && [...d.entries()].some(([k, w]) => changedWork(r, k, w)));
    }

    function card(r) {
      const [chip, tone] = status(r), mine = r.teacher === R.me.name, editable = open(r), busy = M.busy.has(r.id) || (M.up.get(r.id) || 0) > 0;
      const head = [mine ? "" : `<b>${esc(r.teacher)}</b>`, `<b>${esc(RF.dayRuns(r.dates))}</b>`, esc(span(r)), esc(reason(r))].filter(Boolean);
      const sub = [r.how === "planned" ? `Planned by ${who(r.by)}` : `Asked by ${who(r.by)}`, plural((r.lessons || []).length, "lesson")];
      if (r.remarks) sub.push(`Remarks: ${r.remarks}`);
      const many = new Set((r.lessons || []).map(x => x.date)).size > 1;
      let last = null;
      const lessons = (r.lessons || []).map((x, i) => {
        const date = many && x.date !== last ? `<div class="rf-date">${esc(day(x.date))}</div>` : "";
        last = x.date;
        return date + lessonRow(r, x, i, editable);
      }).join("");
      let acts = "";
      const later = live(r), edit = changing(r);
      const change = changeable(r) && !edit ? `<button type="button" data-act="change" ${busy ? "disabled" : ""}>Change dates or times</button>` : "";
      if (editable && (later || needAck(r))) {
        const asking = later && M.ask && M.ask.id === r.id && M.ask.key === null;
        const cancel = !later ? "" : asking
          ? `<div class="ab-ask"><label for="why-${esc(r.id)}">Cancel this absence? Say why in a line.</label><input id="why-${esc(r.id)}" data-why="1" maxlength="200" value="${esc(M.ask.why)}" autocomplete="off">
              <button type="button" class="danger" data-act="cancel-go" ${busy ? "disabled" : ""}>Cancel the absence</button><button type="button" data-act="ask-off">Keep it</button></div>`
          : `<button type="button" class="danger" data-act="cancel-ask" ${busy ? "disabled" : ""}>Not needed at all: cancel</button>`;
        const main = needAck(r)
          ? `<button type="button" class="primary" data-act="ack" ${busy ? "disabled" : ""}>${later ? "Acknowledge and save the work" : "Acknowledge"}</button>`
          : `<button type="button" class="primary" data-act="save" ${busy || !dirtyOf(r) ? "disabled" : ""}>Save the work</button>`;
        acts = asking ? `${cancel}<div class="bar">${change}${main}${say(M.msg.get(r.id))}</div>` : `<div class="bar">${cancel}${change}<span class="grow"></span>${main}</div><div class="bar">${say(M.msg.get(r.id))}</div>`;
      } else if (M.msg.get(r.id)) acts = `<div class="bar">${say(M.msg.get(r.id))}</div>`;
      return `<div class="card ab${r.cancelled ? " cancelled" : ""}" data-id="${esc(r.id)}">
        <div class="ab-top"><div>${head.join(" · ")}</div><span class="chip ${tone}">${esc(chip)}</span></div>
        <div class="small muted ab-sub">${esc(sub.join(" · "))}</div>
        ${lessons || `<p class="muted small">No lessons.</p>`}${edit ? `<div class="rc-box"></div>` : ""}${acts}</div>`;
    }

    function lessonRow(r, x, i, editable) {
      const cover = x.needed && !x.stopped && !r.cancelled, now = editable && x.date >= RF.today();   /* a past lesson keeps what it has */
      const side = !cover ? "" : opts.side ? opts.side(r, x) || ""
        : reliefLines(x);
      const changed = x.changed && !r.cancelled && x.date >= RF.today() ? `<div class="ab-changed">The lesson has changed since this was planned</div>` : "";
      const stop = x.stopped && !r.cancelled ? `<div class="ab-changed">${esc("Not happening: " + x.stopped)}</div>` : "";   /* an approved exam or event stops it */
      const head = `<div class="rf-head"><div><b>${esc(RF.title(x))}</b> <span class="muted">· ${esc(RF.when(x))}</span></div>${side ? `<div class="rf-side small">${side}</div>` : ""}</div>`;
      let body;
      if (!x.needed) {
        const nn = x.not_needed || {}, line = nn.by === "app" ? `${nn.why}: no relief needed` : (nn.why ? `Relief not needed: ${nn.why}` : "Relief not needed");
        body = `<div class="ab-nn"><span class="muted">${esc(line)}</span>${now && !r.cancelled ? `<button type="button" class="small" data-act="needed" ${M.busy.has(r.id) ? "disabled" : ""}>Needed after all</button>` : ""}</div>`;
      } else body = now ? workEdit(r, x, i) : workRead(r, x);
      const extra = cover && opts.extra ? opts.extra(r, x) || "" : "";
      return `<div class="rl" data-key="${esc(x.key)}">${head}${changed}${stop}${body}${extra}</div>`;
    }

    function fileLink(r, f) {
      return `<a href="/api/relief/files/${esc(enc(r.id))}/${esc(enc(f.id))}" download>${esc(f.name)}</a>`;
    }

    function workEdit(r, x, i) {
      const d = draftOf(r, x), id = `ab-${r.id}-${i}`, e = M.lerr.get(lkey(r.id, x.key)), up = M.up.get(r.id) || 0;
      const files = d.files.map((f, j) => `<span class="chip rf-file">${fileLink(r, f)} <span class="muted">${esc(RF.size(f.size))}</span><button type="button" data-act="unfile" data-j="${j}" title="Take this file off" aria-label="Take ${esc(f.name)} off">✕</button></span>`).join("");
      const asking = M.ask && M.ask.id === r.id && M.ask.key === x.key;
      const nn = asking
        ? `<div class="ab-ask"><label for="why-${esc(id)}">Why is relief not needed? (optional)</label><input id="why-${esc(id)}" data-why="1" maxlength="200" value="${esc(M.ask.why)}" autocomplete="off">
            <button type="button" class="small primary" data-act="nn-go" ${M.busy.has(r.id) ? "disabled" : ""}>Mark relief not needed</button><button type="button" class="small" data-act="ask-off">Back</button></div>`
        : "";
      return `<div class="rf-work"><label class="small muted" for="${esc(id)}-t">Work for this lesson</label>
        <textarea id="${esc(id)}-t" class="wrapbox" data-w="text" rows="2" maxlength="2000" placeholder="What the class does in this lesson">${esc(d.text)}</textarea>
        <input type="url" data-w="link" maxlength="500" value="${esc(d.link)}" placeholder="A link, if any (SLS, Google Drive): https://…" aria-label="A link for this lesson">
        <div class="rf-files">${files}<button type="button" class="small" data-act="addfile" ${up ? "disabled" : ""}>Add a file</button><input type="file" data-w="file" multiple accept="${RF.KINDS.join(",")}" hidden>${asking ? "" : `<button type="button" class="small ab-nn-btn" data-act="nn-ask">Relief not needed</button>`}</div>
        <div class="rf-err${e && !e.bad ? " say" : ""}" role="status">${e ? esc(e.text) : ""}</div></div>${nn}`;
    }

    function workRead(r, x) {
      const w = x.work || {}, link = /^https?:\/\//i.test(w.link || "") ? w.link : "";
      const parts = [w.text ? `<div class="ab-work">${esc(w.text)}</div>` : "",
        link ? `<div class="ab-link small"><a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(link)}</a></div>` : "",
        (w.files || []).length ? `<div class="ab-files small">${w.files.map(f => `<span class="chip rf-file">${fileLink(r, f)}</span>`).join("")}</div>` : ""].join("");
      return parts || `<div class="small muted ab-work">No work set.</div>`;
    }

    function paintAll() {
      const box = M.box;
      if (!box) return;
      if (!M.list) {
        box.innerHTML = M.err ? `<div class="card"><p>${say(M.err)}</p><p><button type="button" data-act="reload">Try again</button></p></div>` : `<div class="card"><p class="muted">Loading…</p></div>`;
        painted();
        return;
      }
      const list = M.list.filter(r => !opts.show || opts.show(r));
      box.innerHTML = (M.err ? `<div class="card"><p>${say(M.err)}</p></div>` : "") + (M.list.length ? list.map(card).join("") : (opts.empty || ""));
      placeChange();
      RF.fitAll(box);
      painted();
    }

    /* the open editor, into its card's box once the card is drawn: the same editor, as it was; it ends when its record can no
       longer be changed (cancelled, its dates past, gone from the list) or its card is no longer drawn. A save refused as stale
       reads the list again (onStale), so the card shows the request as it is now */
    function placeChange() {
      if (!M.change) return;
      const id = M.change.id, r = find(id);
      if (!r || !changeable(r)) { if (M.change.ed) M.change.ed.stop(); M.change = null; return; }
      const c = M.box && [...M.box.querySelectorAll(".ab")].find(el => el.dataset.id === id), box = c && c.querySelector(".rc-box");
      if (!c) { if (M.change.ed) M.change.ed.stop(); M.change = null; return; }   /* its card left the view (Planned by me shows one): closed, so nothing hidden counts as unsaved */
      if (!box) return;   /* its card is drawn, the editor's box not yet (it is being opened) */
      if (M.change.ed) M.change.ed.attach(box, r);
      else M.change.ed = window.ReliefChange.mount(box, r, { onDone: (rec, said) => changeDone(id, rec, said), onStale: () => load() });
    }

    function openChange(r) {
      if (M.change && M.change.ed && M.change.ed.busy()) return;   /* one being saved: it finishes first */
      const old = M.change;
      if (old && old.ed) old.ed.stop();
      M.change = { id: r.id, ed: null };
      M.msg.delete(r.id);
      if (old && old.id !== r.id) paintCard(old.id);
      paintCard(r.id, ".rc .seg button.on");
    }

    function changeDone(id, rec, said) {   /* saved (the answered record) or closed (null) */
      if (M.change && M.change.id === id) M.change = null;
      if (rec) { put(rec); M.msg.set(id, { text: said, bad: false }); }
      paintCard(id, '[data-act="change"]');
    }

    function paintCard(id, focus) {
      const r = find(id), el = r && M.box && [...M.box.querySelectorAll(".ab")].find(c => c.dataset.id === id);
      if (!el) { paintAll(); return; }
      el.outerHTML = card(r);
      placeChange();
      const now = [...M.box.querySelectorAll(".ab")].find(c => c.dataset.id === id);
      if (now) { RF.fitAll(now); if (focus) { const t = now.querySelector(focus); if (t) t.focus(); } }
      painted();
    }

    function put(rec) {   /* the record the server answered, in place of the one shown */
      if (!M.list) M.list = [];
      const i = M.list.findIndex(r => r.id === rec.id);
      if (i >= 0) M.list[i] = rec; else M.list.unshift(rec);
    }

    async function load() {
      const seq = ++M.seq, r = await opts.load();
      if (seq !== M.seq) return r;
      if (!r.ok) { M.err = { text: r.error, bad: true, status: r.status }; paintAll(); return r; }
      M.err = null; M.list = Array.isArray(r.data) ? r.data : [];
      for (const id of [...M.drafts.keys()]) { const rec = find(id); if (!rec || rec.cancelled) M.drafts.delete(id); }
      paintAll();
      return r;
    }

    async function act(r, steps) {   /* run the server steps for one absence in turn; the first refusal stops them */
      M.busy.add(r.id); M.msg.delete(r.id); paintCard(r.id);
      let done = null;
      for (const step of steps) {
        const res = await step();
        if (!res) continue;
        if (!res.ok) { M.busy.delete(r.id); M.msg.set(r.id, { text: res.error, bad: true, status: res.status }); paintCard(r.id, M.ask && M.ask.id === r.id ? "[data-why]" : null); return null; }
        put(res.data); done = res.data;
      }
      M.busy.delete(r.id);
      return done || find(r.id);
    }

    function workSteps(r) {   /* one PUT for each lesson with unsaved work */
      const d = M.drafts.get(r.id);
      if (!d) return [];
      return [...d.entries()].filter(([k, w]) => changedWork(r, k, w)).map(([k, w]) => async () => {
        const res = await api(`/api/relief/absences/${enc(r.id)}/lessons/${enc(k)}/work`, json("PUT", { text: w.text, link: w.link, files: w.files.map(f => ({ id: f.id, name: f.name })), known: (w.known || []).slice() }));
        if (res.ok) { d.delete(k); M.lerr.delete(lkey(r.id, k)); if (!d.size) M.drafts.delete(r.id); }
        else M.lerr.set(lkey(r.id, k), { text: res.error, bad: true });   /* the refusal shows on its lesson too */
        return res;
      });
    }

    async function save(r, ack) {
      const steps = workSteps(r), had = steps.length;
      if (ack) steps.push(() => api(`/api/relief/absences/${enc(r.id)}/acknowledge`, json("POST", {})));
      if (!steps.length) return;
      const got = await act(r, steps);
      if (!got) return;
      M.msg.set(r.id, { text: ack ? (had ? "Acknowledged. The work is saved." : "Acknowledged.") : "Saved.", bad: false });
      paintCard(r.id);
    }

    async function addFiles(r, x, input) {
      const chosen = [...(input.files || [])];
      input.value = "";
      if (!chosen.length) return;
      const k = lkey(r.id, x.key), bad = [];
      if (M.msg.has(r.id) && !M.msg.get(r.id).bad) M.msg.delete(r.id);
      M.up.set(r.id, (M.up.get(r.id) || 0) + 1);
      M.lerr.set(k, { text: `Sending ${chosen.map(f => f.name).join(", ")}…`, bad: false });
      paintCard(r.id);
      for (const file of chosen) {
        const why = RF.checkFile(file, draftOf(find(r.id) || r, x).files.length);
        if (why) { bad.push(`${file.name}: ${why}`); continue; }
        const fd = new FormData();
        fd.append("file", file, file.name);
        const res = await api(`/api/relief/absences/${enc(r.id)}/files`, { method: "POST", body: fd });
        if (res.ok) editDraft(find(r.id) || r, x).files.push({ id: res.data.id, name: res.data.name, size: res.data.size });
        else bad.push(`${file.name}: ${res.error}`);
      }
      M.up.set(r.id, Math.max(0, (M.up.get(r.id) || 1) - 1));
      if (bad.length) M.lerr.set(k, { text: bad.join(" "), bad: true });
      else M.lerr.set(k, { text: "Added. Save the work to keep it.", bad: false });
      paintCard(r.id, '[data-act="save"],[data-act="ack"]');
    }

    function onClick(e) {
      const b = e.target.closest("button,a[data-go]");
      if (!b || b.disabled) return;
      if (b.dataset.go) { go(b.dataset.go); return; }
      if (b.dataset.act === "reload") { M.err = null; paintAll(); load(); return; }
      const c = b.closest(".ab"), r = c && find(c.dataset.id);
      if (!r) return;
      const row = b.closest(".rl"), x = row ? lessonOf(r, row.dataset.key) : null;
      switch (b.dataset.act) {
        case "save": save(r, false); return;
        case "ack": save(r, true); return;
        case "cancel-ask": M.ask = { id: r.id, key: null, why: "" }; paintCard(r.id, "[data-why]"); return;
        case "nn-ask": if (x) { M.ask = { id: r.id, key: x.key, why: "" }; paintCard(r.id, "[data-why]"); } return;
        case "ask-off": M.ask = null; paintCard(r.id); return;
        case "cancel-go": cancel(r); return;
        case "nn-go": if (x) notNeeded(r, x); return;
        case "change": openChange(r); return;
        case "needed": if (x) act(r, [() => api(`/api/relief/absences/${enc(r.id)}/lessons/${enc(x.key)}/needed`, json("POST", {}))]).then(got => { if (got) paintCard(r.id); }); return;
        case "addfile": if (row) { const input = row.querySelector('input[data-w="file"]'); if (input) input.click(); } return;
        case "unfile": if (x) { editDraft(r, x).files.splice(Number(b.dataset.j), 1); M.lerr.delete(lkey(r.id, x.key)); paintCard(r.id); } return;
      }
    }

    async function cancel(r) {
      const why = (M.ask && M.ask.why || "").trim();
      const got = await act(r, [() => api(`/api/relief/absences/${enc(r.id)}/cancel`, json("POST", { why }))]);
      if (!got) return;
      M.ask = null; M.drafts.delete(r.id);
      M.msg.set(r.id, { text: "Cancelled.", bad: false });
      paintCard(r.id);
    }

    async function notNeeded(r, x) {
      const why = (M.ask && M.ask.why || "").trim();
      const got = await act(r, [() => api(`/api/relief/absences/${enc(r.id)}/lessons/${enc(x.key)}/not-needed`, json("POST", { why }))]);
      if (!got) return;
      M.ask = null;
      paintCard(r.id);
    }

    function onInput(e) {
      const el = e.target, c = el.closest(".ab"), r = c && find(c.dataset.id);
      if (!r) return;
      if (el.dataset.why) { if (M.ask) M.ask.why = el.value; return; }
      const row = el.closest(".rl"), x = row && lessonOf(r, row.dataset.key);
      if (!x || (el.dataset.w !== "text" && el.dataset.w !== "link")) return;
      editDraft(r, x)[el.dataset.w] = el.value;
      if (el.dataset.w === "text") RF.fit(el);
      if (M.msg.has(r.id) && !M.msg.get(r.id).bad) { M.msg.delete(r.id); c.querySelectorAll(".msg.ok").forEach(m => m.remove()); }
      const btn = c.querySelector('[data-act="save"]');
      if (btn && !M.busy.has(r.id) && !(M.up.get(r.id) || 0)) btn.disabled = !dirtyOf(r);
    }

    function onChange(e) {
      const el = e.target;
      if (el.dataset.w !== "file") return;
      const c = el.closest(".ab"), r = c && find(c.dataset.id), row = el.closest(".rl"), x = row && lessonOf(r, row.dataset.key);
      if (r && x) addFiles(r, x, el);
    }

    function onKey(e) {
      if (!e.target.dataset.why) return;
      const c = e.target.closest(".ab"), r = c && find(c.dataset.id);
      if (!r || !M.ask || M.busy.has(r.id)) return;
      if (e.key === "Escape") { e.preventDefault(); M.ask = null; paintCard(r.id); return; }
      if (e.key === "Enter") {
        e.preventDefault();
        if (M.ask.key === null) cancel(r);
        else { const x = lessonOf(r, M.ask.key); if (x) notNeeded(r, x); }
      }
    }

    function mount(box) {
      M.box = box;
      box.addEventListener("click", onClick);
      box.addEventListener("input", onInput);
      box.addEventListener("change", onChange);
      box.addEventListener("keydown", onKey);
      paintAll();
    }

    return {
      mount, load, find, put, paint: paintCard, paintAll, list: () => M.list, error: () => M.err,
      dirty() { return (M.list || []).some(dirtyOf) || [...M.up.values()].some(n => n > 0) || !!(M.change && M.change.ed && (M.change.ed.dirty() || M.change.ed.busy())); },
    };
  }

  /* ================================================================ My absences */
  /* The Link Telegram card, then every absence of mine, newest first, as cards (R.absences). */
  const mine = absences({
    load: () => api("/api/relief/absences/mine").then(r => r.ok ? { ok: true, status: r.status, data: r.data.absences || [] } : r),
    empty: `<div class="card"><p class="muted">No absences yet. When you ask for relief, or someone plans relief for you, it shows here.</p><button type="button" class="primary" data-go="ask">Ask for relief</button></div>`,
    painted: paintCount,
  });

  function paintCount() {
    const n = (mine.list() || []).filter(needAck).length, el = $("#mineN");
    if (el) { el.textContent = n ? String(n) : ""; el.title = n ? `${plural(n, "absence")} to acknowledge` : ""; }
  }

  let link = null;
  function linkCard(mod) {   /* the card's code, ready before the tab is or after it */
    link = mod;
    if (mods.mine.started) mod.init($("#mineTelegram"));
  }

  tab("mine", {
    init(pane) {
      pane.innerHTML = `<div id="mineTelegram"></div><div id="mineList"></div>`;
      mine.mount($("#mineList", pane));
      mine.load();
      if (link) link.init($("#mineTelegram", pane));
    },
    shown() { mine.load(); if (link) link.shown(); },
    dirty() { return mine.dirty(); },
    reload() { mine.load(); },
  });

  /* ================================================================ Ask for relief */
  /* The form is kept in A; the lessons and their work are kept by ReliefForm. The lessons are read again whenever the
     dates or the periods change; each answer also gives every period of the day, which "Some periods" offers. Nothing is
     sent while the lessons are being read or could not be read, or while "Some periods" has no from and to. */
  const REASONS = ["Medical", "Child sick", "Course", "Other"];
  const A = { pane: null, day: "today", picked: [], away: "whole", from: null, to: null, reason: "", text: "", ro: "", people: null, perr: null,
              periods: [], readFor: "", lessons: [], lerr: null, loading: false, seq: 0, busy: false, msg: null, dirty: false };

  /* the reporting officer is remembered on this device for each person (a staffroom computer is shared) */
  const roRemembered = () => { try { return localStorage.getItem("relief.ro:" + R.me.name) || ""; } catch (e) { return ""; } };
  const roRemember = v => { try { localStorage.setItem("relief.ro:" + R.me.name, v); } catch (e) { /* private window: not remembered */ } };

  function dates() {
    const t = RF.today();
    if (A.day === "today") return [t];
    if (A.day === "tomorrow") return [RF.addDays(t, 1)];
    return A.picked.slice().sort();
  }

  const someWaiting = () => A.away === "some" && (A.from === null || A.to === null);

  function askBlock() {   /* why Send cannot be pressed yet, in a line; "" when it can */
    if (!dates().length) return "Choose the dates first.";
    if (someWaiting()) return "Choose the periods first: from and to.";
    if (A.lerr) return "Nothing can be sent until your lessons are read.";
    return "";
  }

  const segBtn = (what, v, on, label) => `<button type="button" data-a="${what}" data-v="${esc(v)}" class="${on ? "on" : ""}" aria-pressed="${on ? "true" : "false"}">${esc(label)}</button>`;

  function paintDay() {   /* Pick dates is the calendar (relief-dates.js), which draws itself again on each change */
    const t = RF.today(), box = $("#askDay", A.pane);
    let under;
    if (A.day === "today") under = `<div class="small muted under">${esc(day(t))}</div>`;
    else if (A.day === "tomorrow") under = `<div class="small muted under">${esc(day(RF.addDays(t, 1)))}</div>`;
    else under = `<div class="rd-box"></div>`;
    box.innerHTML = `<div class="seg" role="group" aria-label="Which day">${segBtn("day", "today", A.day === "today", "Today")}${segBtn("day", "tomorrow", A.day === "tomorrow", "Tomorrow")}${segBtn("day", "pick", A.day === "pick", "Pick dates")}</div>${under}`;
    if (A.day === "pick") window.ReliefDates.mount($(".rd-box", box), { key: "ask", picked: A.picked, max: 20, onChange: list => { A.picked = list; changed(); reread(); } });
  }

  function paintAway() {
    const box = $("#askAway", A.pane);
    let under = "";
    if (A.away === "some") {
      if (!dates().length) under = `<div class="small muted under">Choose the dates first.</div>`;
      else if (A.periods.length) under = RF.periodSelects("ask", A.periods, A.from, A.to);
      else if (A.loading) under = `<div class="small muted under">Reading the periods…</div>`;
      else if (!A.lerr) under = `<div class="small muted under">The published timetable has no periods to choose.</div>`;   /* with a refusal, its sentence under the lessons says why */
    }
    const had = box.contains(document.activeElement) ? document.activeElement.dataset.per : "";   /* the selects are drawn again when the lessons come back */
    box.innerHTML = `<div class="seg" role="group" aria-label="Away for">${segBtn("away", "whole", A.away === "whole", "Whole day")}${segBtn("away", "some", A.away === "some", "Some periods")}</div>${under}`;
    if (had) { const el = $(`[data-per="${had}"]`, box); if (el) el.focus(); }
  }

  function paintReason() {
    $("#askReason", A.pane).innerHTML = `<div class="seg" role="group" aria-label="Reason">${REASONS.map(x => segBtn("reason", x, A.reason === x, x)).join("")}</div>`
      + (A.reason === "Other" ? `<div><input id="askWhy" class="reason-line" maxlength="200" value="${esc(A.text)}" placeholder="Say why in a line" aria-label="The reason, in a line" autocomplete="off"></div>` : "");
  }

  function paintLessons() {
    const sayBox = $("#askLessonsSay", A.pane), list = $("#askLessonList", A.pane);
    const empty = A.loading || A.lerr ? "" : !dates().length ? "Choose the dates first." : someWaiting() ? "Choose the periods first." : "You have no lessons then.";
    sayBox.innerHTML = A.lerr ? `<p>${say(A.lerr)}${A.lerr.status === 0 ? ` <button type="button" class="small" data-a="reread">Try again</button>` : ""}</p>` : A.loading ? `<p class="small muted">Reading your lessons…</p>` : "";
    const shown = A.lerr ? [] : A.lessons, stopped = shown.filter(x => x.stopped), duties = A.lerr ? {} : A.duties || {};
    const lines = Object.keys(duties).sort().flatMap(d => (duties[d] || []).map(u => `<p class="small">${esc(`${day(d)}: ${u.what}, ${u.start}–${u.end}: ${u.replaces} replaces you.`)}</p>`));
    $("#askStopped", A.pane).innerHTML = stopped.map(x => `<p class="small muted"><b>${esc(RF.title(x))}</b> · ${esc(RF.when(x))}: ${esc("Not happening: " + x.stopped + " · no relief needed")}</p>`).join("") + lines.join("");
    RF.lessons(list, shown.filter(x => !x.stopped), { empty: stopped.length || lines.length ? "" : empty, onChange: changed });   /* with a refusal, nothing is listed (and nothing is sent), but what was typed is kept */
  }

  function paintRO() {
    const box = $("#askRO", A.pane);
    if (!A.people) { box.innerHTML = A.perr ? `${say(A.perr)} <button type="button" class="small" data-a="people">Try again</button>` : `<span class="small muted">Loading…</span>`; return; }
    RF.person(box, { people: A.people, value: A.ro, exclude: [R.me.name], label: "Find your reporting officer", onPick: name => { A.ro = name; changed(); } });
  }

  function paintSend() {
    const box = $("#askSend", A.pane), why = A.busy || A.loading ? "" : askBlock(), line = A.msg && !A.msg.bad ? "" : why;   /* beside "Sent.", no reason line */
    box.innerHTML = `<div class="bar"><button type="button" class="primary" data-a="send" ${A.busy || A.loading || why ? "disabled" : ""}>${A.busy ? "Sending…" : "Send to the relief team"}</button>${line ? `<span class="small muted">${esc(line)}</span>` : ""}${say(A.msg)}
      ${A.msg && A.msg.sent ? `<button type="button" class="small" data-go="mine">Open My absences</button>` : ""}</div>${A.msg && A.msg.files ? `<div class="bar">${say(A.msg.files)}</div>` : ""}`;
  }

  function changed() {
    A.dirty = true;
    if (A.msg && !A.busy) { A.msg = null; paintSend(); }
  }

  async function reread() {
    const ds = dates(), key = ds.join(","), seq = ++A.seq, some = A.away === "some", both = A.from !== null && A.to !== null;
    if (!ds.length) {
      A.readFor = ""; A.lessons = []; A.lerr = null; A.loading = false;
      paintAway(); paintLessons(); paintSend(); return;
    }
    A.loading = true; A.lerr = null;
    if (A.readFor !== key) A.lessons = [];   /* other dates: the old lessons are not shown while the new ones are read */
    paintAway(); paintLessons(); paintSend();
    const r = await api(`/api/relief/lessons?dates=${enc(key)}${some && both ? `&from=${A.from}&to=${A.to}` : ""}`);
    if (seq !== A.seq) return;
    A.loading = false;
    if (!r.ok) { A.readFor = ""; A.lessons = []; A.lerr = { text: r.error, bad: true, status: r.status }; paintAway(); paintLessons(); paintSend(); return; }
    if (Array.isArray(r.data.periods)) A.periods = r.data.periods;
    A.readFor = key;
    A.duties = r.data.duties || {};
    A.lessons = some && !both ? [] : r.data.lessons || [];   /* "Some periods" lists nothing until from and to are chosen */
    paintAway(); paintLessons(); paintSend();
  }

  async function loadPeople() {
    A.perr = null; paintRO();
    const r = await people();
    if (!r.ok) { A.perr = { text: r.error, bad: true, status: r.status }; paintRO(); return; }
    A.people = r.data || [];
    const kept = roRemembered();
    if (!A.ro && kept && A.people.some(p => p.name === kept) && kept !== R.me.name) A.ro = kept;
    paintRO();
  }

  async function attach(rec, list) {   /* the files chosen in a ReliefForm, sent once the absence is saved, then attached to their lessons: -> what failed, in words */
    const failed = [];
    for (const { key, files } of RF.files(list)) {
      const got = [];
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file, file.name);
        const u = await api(`/api/relief/absences/${enc(rec.id)}/files`, { method: "POST", body: fd });
        if (u.ok) got.push({ id: u.data.id, name: u.data.name }); else failed.push(`${file.name}: ${u.error}`);
      }
      if (!got.length) continue;
      const w = ((rec.lessons || []).find(x => x.key === key) || {}).work || {};
      const p = await api(`/api/relief/absences/${enc(rec.id)}/lessons/${enc(key)}/work`, json("PUT", { text: w.text || "", link: w.link || "", files: got, known: [] }));   /* known none: whatever the lesson has is kept */
      if (!p.ok) failed.push(`${got.map(f => f.name).join(", ")}: ${p.error}`);
    }
    return failed;
  }

  /* what the ask form says once sent: the officer's line from the server is added only when it is a non-empty string */
  function sentSays(d) { const n = d && d.officer_not_told; return "Sent. The relief team can see it." + (typeof n === "string" && n ? " " + n : ""); }
  async function send() {
    if (A.busy || A.loading || askBlock()) return;
    const list = $("#askLessonList", A.pane);
    A.busy = true; A.msg = null; paintSend();
    const body = { dates: dates(), periods: A.away === "some" ? [A.from, A.to] : null, reason: A.reason,
                   reason_text: A.reason === "Other" ? A.text.trim() : "", reporting_officer: A.ro, lessons: RF.read(list) };
    const res = await api("/api/relief/absences", json("POST", body));
    if (!res.ok) { A.busy = false; A.msg = { text: res.error, bad: true, status: res.status }; paintSend(); return; }
    const failed = await attach(res.data, list);
    roRemember(A.ro);
    window.ReliefDates.forget("ask");   /* Pick dates opens on the first school day's month again */
    Object.assign(A, { day: "today", picked: [], away: "whole", from: null, to: null, reason: "", text: "", busy: false, dirty: false });
    A.msg = { text: sentSays(res.data), bad: false, sent: true,
              files: failed.length ? { text: `Not added: ${failed.join(" ")} Add them in My absences.`, bad: true } : null };
    RF.reset(list);
    paintDay(); paintAway(); paintReason(); paintSend(); reread();
    if (mods.mine.started) mods.mine.reload();
  }

  function askClick(e) {
    const b = e.target.closest("button");
    if (!b || b.disabled) return;
    if (b.dataset.go) { go(b.dataset.go); return; }
    const a = b.dataset.a, v = b.dataset.v;
    if (a === "day" && v !== A.day) { A.day = v; changed(); paintDay(); reread(); if (v === "pick") window.ReliefDates.focusFirst($("#askDay .rd-box", A.pane)); return; }
    if (a === "away" && v !== A.away) { A.away = v; changed(); paintAway(); reread(); return; }
    if (a === "reason") { A.reason = v; changed(); paintReason(); if (v === "Other") { const w = $("#askWhy", A.pane); if (w) w.focus(); } return; }
    if (a === "people") { loadPeople(); return; }
    if (a === "reread") { reread(); return; }
    if (a === "send") { send(); return; }
  }

  function askInput(e) {
    if (e.target.id === "askWhy") { A.text = e.target.value; changed(); }
  }

  function askChange(e) {
    const per = e.target.dataset.per;
    if (per !== "from" && per !== "to") return;
    const v = e.target.value === "" ? null : Number(e.target.value);
    if (per === "from") { A.from = v; if (A.from !== null && A.to !== null && A.to < A.from) A.to = null; }
    else A.to = v;
    changed(); paintAway(); reread();
  }

  tab("ask", {
    init(pane) {
      A.pane = pane;
      pane.innerHTML = `<div class="card"><h2>Ask for relief</h2>
        <div class="field"><div class="flabel">Which day?</div><div id="askDay"></div></div>
        <div class="field"><div class="flabel">Away for</div><div id="askAway"></div></div>
        <div class="field"><div class="flabel">Reason</div><div id="askReason"></div></div>
        <div class="field"><div class="flabel">Your lessons then, and work for each</div><div id="askLessonsSay"></div><div id="askStopped"></div><div id="askLessonList"></div></div>
        <div class="field"><div class="flabel">Reporting officer</div><div id="askRO"></div></div>
        <div id="askSend"></div></div>`;
      pane.addEventListener("click", askClick);
      pane.addEventListener("input", askInput);
      pane.addEventListener("change", askChange);
      paintDay(); paintAway(); paintReason(); paintRO(); paintSend();
      loadPeople(); reread();
    },
    shown() { if (A.day !== "pick" && !A.busy) { paintDay(); if (dates().join(",") !== A.readFor) reread(); } },
    dirty() { return A.dirty || A.busy; },
  });

  /* ================================================================ the page */
  function paint(me) {
    R.me = me;
    RF.setToday(me.today);
    document.title = `Relief · ${me.name}`;
    $("#title").textContent = `Relief · ${me.name}`;
    $("#ttLink").href = `/timetable#teachers/${enc(me.name)}`;
    $("#settingsLink").hidden = !me.can_settings;
    const note = me.published === false ? `<p class="muted small">The timetable is not published yet.</p>` : "";
    const about = [(me.depts || []).join(", "), me.on_management ? "Management" : "", me.on_team ? "Relief team" : ""].filter(Boolean).join(" · ");
    const w = $("#who"); w.textContent = about; w.hidden = !about;
    if (note) w.insertAdjacentHTML("afterend", note);
    $("#loading").remove();
    const want = (location.hash || "").slice(1);
    go(allowed(want) ? want : "mine");
  }

  function fail(text) {
    $("#loading").innerHTML = `<p class="msg bad">${esc(text)}</p><p><a href="/relief">Try again</a></p>`;
  }

  async function start() {
    const r = await api("/api/relief/me");
    if (r.status === 401) { location.href = "/login"; return; }
    if (!r.ok) { fail(r.error); return; }
    paint(r.data);
  }

  $("#tabs").addEventListener("click", e => { const b = e.target.closest("button[data-tab]"); if (b && !b.hidden) go(b.dataset.tab); });
  window.addEventListener("hashchange", () => { const k = location.hash.slice(1); if (R.me && k !== R.cur && allowed(k)) go(k); });
  window.addEventListener("beforeunload", e => { if (dirtyAny()) { e.preventDefault(); e.returnValue = ""; } });
  start();
})();

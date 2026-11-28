"use strict";
/* All Relief Requests (/relief#inbox), for the relief team (me.can_team), read-only: every absence, newest first, with when it came
   in, who sent it and how, for whom and when, the reason, whether the absent teacher has acknowledged (when someone else
   planned it), how many lessons have work and how many reliefs are approved, waiting or open (from the server's cover
   counts); cancelled ones dimmed. Views: Coming up, Not acknowledged (planned by someone else, not acknowledged, and past
   the time to remind them; or with a relief of today that has reached its relief teacher and is not acknowledged, the server's
   unacked, each named in its row), Today, Earlier (every date past, not cancelled), Cancelled: every absence is in one of them (Not acknowledged only picks some of Coming up's and Today's). "new" = came in since this
   person last looked, counted over the absences the views show, and each view says how many of its own are new. The
   list is read with a GET, which never writes; once it is shown, the page posts the list's as_of to
   /api/relief/absences/seen. A request still to come (not cancelled, a date today or later, not a backup for an exam or event)
   has Edit in its last column: the editor (ReliefChange, with its lessons and cancel parts) opens under the table, the whole
   width of the card (never in the table's own scroller: on a phone every control is in reach), named by the request's teacher
   and dates, its row marked; one at a time, kept while the list is drawn again with its row, the focus where it was (a view
   without its row closes it, so nothing hidden counts as unsaved: when it holds unsaved choices the view button asks first). A
   lesson's step (Relief not needed, Needed again, Ask for relief anyway) keeps it open and reads the list again; Save the
   change and Cancel the request close it, what was done is said above the table and the list is read again, as it is after a
   save refused because the request changed meanwhile (onStale). A request that can no longer be changed when the list is read
   again (cancelled, every date past, gone) closes its Edit and says so above the table. The Submitted cell names the
   request's last change (Changed by …). */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day;
  const $ = (s, el = document) => el.querySelector(s);
  const I = { pane: null, list: null, err: null, asOf: "", view: "coming", seq: 0, loading: false, edit: null, said: null };   /* edit: {id, teacher, ed} the open Edit; said: what it did */
  const COLS = 9;
  const lastDate = r => (r.dates || []).slice().sort().pop() || "";
  const VIEWS = [
    ["coming", "Coming up", r => !r.cancelled && lastDate(r) >= RF.today(), "Nothing coming up."],
    ["nudge", "Not acknowledged", r => !!r.nudge || (Array.isArray(r.unacked) && r.unacked.length > 0), "Everyone has acknowledged."],
    ["today", "Today", r => !r.cancelled && (r.dates || []).includes(RF.today()), "No one is away today."],
    ["earlier", "Earlier", r => !r.cancelled && lastDate(r) < RF.today(), "Nothing earlier."],
    ["cancelled", "Cancelled", r => !!r.cancelled, "Nothing cancelled."],
  ];
  const hasWork = x => { const w = x.work || {}; return !!(w.text || w.link || (w.files || []).length); };
  const editable = r => !r.cancelled && lastDate(r) >= RF.today() && !r.exams && !!window.ReliefChange;   /* a backup follows its exam or event: change the duty instead */
  const find = id => (I.list || []).find(r => r.id === id);
  function lastChange(r) {   /* "Changed by Mr Hugo Ong, Today, 08:15" for the record's last change, else "" */
    const c = Array.isArray(r.changes) ? r.changes[r.changes.length - 1] : null;
    return c && typeof c === "object" && c.by ? `Changed by ${c.by}${stamp(c.at) ? `, ${stamp(c.at)}` : ""}` : "";
  }

  function stamp(iso, plain) {   /* "Mon 12 Oct, 09:30" from a school-time stamp; "Today, 09:30" unless plain */
    const s = String(iso || ""), d = s.slice(0, 10), t = s.slice(11, 16);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return "";
    return `${d === RF.today() && !plain ? "Today" : day(d)}${/^\d{2}:\d{2}$/.test(t) ? `, ${t}` : ""}`;
  }

  function status(r) {   /* "3 of 5 approved", "2 waiting", "1 open" from the server's cover counts */
    const c = r.cover || { total: 0, approved: 0, waiting: 0, open: 0 };
    if (!c.total) return `<span class="muted">—</span>`;
    const bits = [c.approved === c.total ? `${c.approved} approved` : `${c.approved} of ${c.total} approved`];
    if (c.waiting) bits.push(`${c.waiting} waiting`);
    if (c.open) bits.push(`${c.open} open`);
    return `<span class="${c.approved === c.total ? "chip st-ok" : c.open ? "chip st-amber" : "chip"}">${esc(bits.join(" · "))}</span>`;
  }

  function row(r) {
    const all = r.lessons || [], cover = all.filter(x => x.needed && !x.stopped), n = cover.length;
    const work = cover.filter(hasWork).length;
    const changed = !r.cancelled && all.some(x => x.changed && x.date >= RF.today());
    const when = RF.dayRuns(r.dates, d => (d === RF.today() ? "Today" : day(d)));
    const how = r.via === "telegram" ? "asked on Telegram" : r.how === "planned" ? "planned · app" : "for themselves · app";
    let tail;
    if (r.cancelled) {
      const c = r.cancelled;
      tail = `<td colspan="4"><span class="chip st-off">${esc(`Cancelled${c.by === "app" ? "" : ` by ${c.by}`}${c.at ? `, ${stamp(c.at)}` : ""}: “${c.why}”`)}</span></td>`;
    } else {
      const ack = r.how !== "planned" ? `<span class="small muted">their own request</span>`
        : r.acknowledged ? `<span class="chip st-ok">✓ ${esc(stamp(r.acknowledged.at) || "acknowledged")}</span>` : `<span class="chip st-amber">not acknowledged yet</span>`;
      const w = n ? `<span class="${work === n ? "chip st-ok" : ""}">${work} of ${n}</span>` : `<span class="muted">none to cover</span>`;
      const un = (Array.isArray(r.unacked) ? r.unacked : []).map(u => `<div class="small pl-changed">${esc(`Relief not acknowledged: ${u.who}, ${RF.periods(u)}${u.started ? " · started" : ""}`)}</div>`).join("");
      const rel = status(r) + un;
      const open = !!I.edit && I.edit.id === r.id, edit = editable(r)
        ? `<button type="button" class="small" data-in="edit" data-id="${esc(r.id)}" aria-expanded="${open ? "true" : "false"}">Edit</button>` : "";
      tail = `<td>${ack}</td><td>${w}</td><td>${rel}</td><td class="act">${edit}</td>`;
    }
    const ch = lastChange(r);
    return `<tr class="${[r.new ? "new" : "", r.cancelled ? "off" : "", I.edit && I.edit.id === r.id && editable(r) ? "editing" : ""].filter(Boolean).join(" ")}">
      <td>${r.new ? `<span class="chip new">new</span><br>` : ""}${esc(stamp(r.at))}${ch ? `<div class="small muted">${esc(ch)}</div>` : ""}</td>
      <td>${esc(r.by)}<div class="small muted">${esc(how)}</div></td>
      <td>${esc(r.teacher)}</td>
      <td>${esc(when)}<div class="small muted">${esc(`${R.span(r)} · ${R.plural(n, "lesson")}`)}</div>${changed ? `<div class="small pl-changed">The lesson has changed since this was planned</div>` : ""}</td>
      <td>${esc(R.reason(r))}</td>${tail}</tr>`;
  }

  function editHTML(rows) {   /* the open Edit, under the table: which request it is, then the editor's box */
    const r = I.edit && rows.find(x => x.id === I.edit.id);
    if (!r || !editable(r)) return "";
    const when = RF.dayRuns(r.dates, d => (d === RF.today() ? "Today" : day(d)));
    return `<div class="in-edit" role="group" aria-label="${esc(`Edit ${r.teacher}'s request`)}"><div class="in-for"><b>${esc(`Edit: ${r.teacher}'s request`)}</b> <span class="muted">${esc(`· ${when} · ${R.span(r)}`)}</span></div><div class="in-box"></div></div>`;
  }

  function paint() {
    const box = $("#inBox", I.pane);
    if (!box) return;
    const a = document.activeElement, had = a && box.contains(a) && a.dataset && a.dataset.in ? [a.dataset.in, a.dataset.id || a.dataset.v || ""] : null;
    const eb = $(".in-box", box), inEd = a && eb && eb.contains(a) && a !== eb && a.dataset ? [a.dataset.rc, a.dataset.per, a.dataset.v] : null;   /* the focus in the open Edit */
    checkEdit();
    if (!I.list) {
      box.innerHTML = I.err ? `<div class="card"><p>${R.say(I.err)}</p><p><button type="button" data-in="reload">Try again</button></p></div>` : `<div class="card"><p class="muted">Loading…</p></div>`;
      return;
    }
    const v = VIEWS.find(x => x[0] === I.view) || VIEWS[0], rows = I.list.filter(v[2]);
    const fresh = I.list.filter(r => r.new && VIEWS.some(w => w[2](r))).length;   /* only what a view shows counts as new */
    const count = f => { const all = I.list.filter(f), n = all.filter(r => r.new).length; return n ? `${all.length} · ${n} new` : String(all.length); };
    const seg = VIEWS.map(([k, label, f]) => `<button type="button" data-in="view" data-v="${k}" class="${k === v[0] ? "on" : ""}" aria-pressed="${k === v[0] ? "true" : "false"}">${esc(label)} (${esc(count(f))})</button>`).join("");
    const about = [I.asOf ? `As of ${stamp(I.asOf, true)}` : "", fresh ? `${fresh} new since you last looked` : ""].filter(Boolean).join(" · ");
    box.innerHTML = `<div class="card">
      <div class="ab-top"><div><h2>All Relief Requests</h2><div class="small muted">${esc(about)}</div></div>
        <div class="row"><div class="seg" role="group" aria-label="Which absences">${seg}</div><button type="button" class="small" data-in="reload" ${I.loading ? "disabled" : ""}>${I.loading ? "Reading…" : "Refresh"}</button></div></div>
      ${I.err ? `<p>${R.say(I.err)}</p>` : ""}
      ${I.said ? `<p class="in-said">${R.say(I.said)}</p>` : ""}
      ${rows.length ? `<div class="tablewrap"><table class="rtable inbox"><thead><tr><th>Submitted</th><th>By</th><th>For</th><th>When</th><th>Reason</th><th>Absent teacher</th><th>Work</th><th>Relief status</th><th><span class="vh">Edit</span></th></tr></thead>
        <tbody>${rows.map(row).join("")}</tbody></table></div>` : `<p class="muted">${esc(v[3])}</p>`}
      ${editHTML(rows)}</div>`;
    placeEdit();
    if (had) focusBtn(had[0], had[1]);
    if (inEd) focusEdit(inEd);
  }

  function focusEdit([rc, per, v]) {   /* the same control of the Edit, drawn again (by its data-rc or data-per, and data-v) */
    const eb = $("#inBox .in-box", I.pane), sel = per ? `[data-per="${per}"]` : rc ? `[data-rc="${rc}"]${v !== undefined ? `[data-v="${v}"]` : ""}` : "";
    const el = eb && sel && eb.querySelector(sel);
    if (el) el.focus();
  }

  function focusBtn(what, v) {   /* a button of the list by its data-in and its absence (or view) */
    const b = [...I.pane.querySelectorAll(`[data-in="${what}"]`)].find(x => (x.dataset.id || x.dataset.v || "") === v);
    if (b && !b.disabled) b.focus();
  }

  /* before the list is drawn: an open Edit whose request can no longer be changed (cancelled, every date past, gone from the
     list) ends, and the line above the table says so */
  function checkEdit() {
    if (!I.edit || !I.list) return;
    const r = find(I.edit.id);
    if (r && editable(r)) return;
    if (I.edit.ed) I.edit.ed.stop();
    I.said = { text: `${(r && r.teacher) || I.edit.teacher}'s request can no longer be changed.`, bad: true };
    I.edit = null;
  }

  /* the open Edit, into its row once the list is drawn: the same editor, as it was; closed when its row is not in the view shown */
  function placeEdit() {
    if (!I.edit || !I.list) return;
    const r = find(I.edit.id), box = $("#inBox .in-edit .in-box", I.pane);
    if (!r || !box) { if (I.edit.ed) I.edit.ed.stop(); I.edit = null; return; }   /* nothing hidden counts as unsaved */
    const id = r.id;
    if (I.edit.ed) I.edit.ed.attach(box, r);
    else I.edit.ed = window.ReliefChange.mount(box, r, { lessons: true, cancel: true, onDone: (rec, said) => editDone(id, rec, said), onStep: rec => stepDone(rec), onStale: () => load() });
  }

  function openEdit(id) {
    const old = I.edit;
    if (old && old.ed && old.ed.busy()) return;   /* one on its way: it finishes first */
    if (old && old.ed) old.ed.stop();
    I.edit = old && old.id === id ? null : { id, teacher: (find(id) || {}).teacher || "", ed: null };   /* Edit again closes it */
    I.said = null;
    paint();
    if (I.edit) { const first = $("#inBox .in-edit .rc .seg button.on", I.pane); if (first) first.focus(); }
    else focusBtn("edit", id);
  }

  function stepDone(rec) {   /* a lesson's step: the list holds the answered record at once (the Edit is drawn from it), then is read again */
    const i = rec && rec.id ? (I.list || []).findIndex(x => x.id === rec.id) : -1;
    if (i >= 0) I.list[i] = Object.assign({}, I.list[i], rec);
    load();
  }

  function editDone(id, rec, said) {   /* done (the answered record and what was done) or closed (null) */
    if (I.edit && I.edit.id === id) I.edit = null;
    if (rec && said) I.said = { text: said, bad: false };
    paint();
    focusBtn("edit", id);
    if (rec) load().then(() => { if (!document.activeElement || document.activeElement === document.body) focusBtn("edit", id); });
  }

  async function load() {
    const seq = ++I.seq;
    I.loading = true; paint();
    const r = await R.api("/api/relief/absences");
    if (seq !== I.seq) return;
    I.loading = false;
    if (!r.ok) { I.err = { text: r.error, bad: true, status: r.status }; paint(); return; }
    I.err = null; I.list = r.data.absences || []; I.asOf = r.data.as_of || "";
    paint();
    /* shown: what came in up to as_of is seen (only while this tab is the one on screen; a refusal here is not shown) */
    if (I.asOf && R.cur === "inbox") R.api("/api/relief/absences/seen", R.json("POST", { at: I.asOf }));
  }

  /* another view; when it does not show the open Edit's row, the Edit closes, and asks first when it holds unsaved choices */
  function view(k) {
    const f = (VIEWS.find(x => x[0] === k) || VIEWS[0])[2], r = I.edit && find(I.edit.id), ed = I.edit && I.edit.ed;
    if (r && !f(r) && ed && (ed.dirty() || ed.busy()) && !window.confirm(`Close the Edit of ${r.teacher}'s request? What you chose there is not saved.`)) return;
    I.view = k; paint();
    const again = $(`[data-in="view"][data-v="${I.view}"]`, I.pane);
    if (again) again.focus();
  }

  function onClick(e) {
    const b = e.target.closest("button[data-in]");
    if (!b || b.disabled) return;
    if (b.dataset.in === "view") { view(b.dataset.v); return; }
    if (b.dataset.in === "reload") { load(); return; }
    if (b.dataset.in === "edit") { openEdit(b.dataset.id); return; }
  }

  R.tab("inbox", {
    init(pane) {
      I.pane = pane;
      pane.innerHTML = `<div id="inBox"></div>`;
      pane.addEventListener("click", onClick);
      load();
    },
    shown() { load(); },
    dirty() { return !!(I.edit && I.edit.ed && (I.edit.ed.dirty() || I.edit.ed.busy())); },
  });
})();

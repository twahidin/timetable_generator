"use strict";
/* Planned Relief Assignments (/relief#ahead), for the relief team (me.can_team), read-only: every relief on the school days after
   today, one block a day (the teachers away, the lessons, what is waiting, open or approved and not sent out) over a table of its
   covers with the relief teacher and a status in the words Today uses. Next 2 weeks or This term; the list is read with a GET,
   which never writes, and read again each time the tab is shown. "Open this day" hands the date to Today's Relief Assignments
   (Relief.showDay), where Approve, Change and Split already are: nothing on this tab changes a record. */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day;
  const $ = (s, el = document) => el.querySelector(s);
  const A = { pane: null, data: null, err: null, span: "weeks", seq: 0, loading: false, keep: "" };
  const SPANS = [["weeks", "Next 2 weeks"], ["term", "This term"]];
  const EMPTY = { weeks: "No relief on the school days after today.", term: "No relief for the rest of the term." };
  const num = v => Number(v) || 0;

  function stamp(iso) {   /* "Mon 12 Oct, 09:00" from a school-time stamp */
    const s = String(iso || ""), d = s.slice(0, 10), t = s.slice(11, 16);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return "";
    return `${day(d)}${/^\d{2}:\d{2}$/.test(t) ? `, ${t}` : ""}`;
  }

  function status(r) {   /* [words, chip class, small line under it] */
    switch (r.state) {
      case "open": return ["No relief teacher yet", "st-amber"];
      case "waiting": return ["Waiting for you", "st-amber"];
      case "approved":
        if (r.out === "unsent") return ["Approved · not sent out", ""];
        if (r.out === "held" && stamp(r.goes_at)) return [`Approved · will be sent ${stamp(r.goes_at)}`, ""];
        return ["Approved · sent out", ""];
      case "acknowledged": return ["✓ Acknowledged", "st-ok"];
      case "change": return ["Asked to change", "st-blue"];
      case "stopped": return ["Not happening", "st-off", "stopped"];
      default: return null;
    }
  }

  function teacher(r) {
    const who = r.pick && r.pick.who, planned = r.planned_by ? `<div class="small muted">${esc(`Planned by ${r.planned_by}`)}</div>` : "";
    if (r.state === "change") {
      const np = r.change && r.change.pick && r.change.pick.who;
      return `${who ? `<s class="muted">${esc(who)}</s>` : `<span class="muted">—</span>`}${np ? `<div><b>${esc(`New pick: ${np}`)}</b></div>` : ""}${planned}`;
    }
    if (r.state === "open" || r.state === "cancelled" || !who) return `<span class="muted">—</span>`;
    return `<b>${esc(who)}</b>${planned}`;
  }

  function row(r) {
    const s = status(r), time = RF.time(r);
    const state = s ? `<span class="chip ${s[1]}">${esc(s[0])}</span>${s[2] ? `<div class="small muted">${esc(s[2])}</div>` : ""}` : `<span class="muted">—</span>`;
    return `<tr><td><b>${esc(RF.periods(r))}</b>${time ? `<div class="small muted">${esc(time)}</div>` : ""}</td>
      <td><b>${esc(RF.title(r))}</b>${r.room ? ` <span class="small muted">· ${esc(r.room)}</span>` : ""}</td>
      <td>${esc(r.absent)}</td><td>${teacher(r)}</td><td>${state}</td></tr>`;
  }

  function block(d) {
    const c = d.counts || {}, rows = Array.isArray(d.rows) ? d.rows : [];
    const chips = [num(c.waiting) ? `<span class="chip st-amber">${esc(`${num(c.waiting)} waiting for you`)}</span>` : "", num(c.open) ? `<span class="chip st-amber">${esc(`${num(c.open)} no relief teacher yet`)}</span>` : "",
      num(c.unsent) ? `<span class="chip">${esc(`${num(c.unsent)} approved, not sent out`)}</span>` : "",
      num(c.need) > 0 && !num(c.waiting) && !num(c.open) && !num(c.unsent) && !num(c.change) ? `<span class="chip st-ok">all approved</span>` : ""].filter(Boolean).join(" ");
    return `<div class="ah-day"><div class="ah-h"><b>${esc(day(d.date))}</b> <span class="small muted">${esc(`${R.plural(num(d.away), "teacher")} away · ${R.plural(typeof c.need === "number" ? c.need : rows.length, "lesson")}`)}</span> ${chips}</div>
      <button type="button" class="small" data-ah="open" data-date="${esc(d.date)}">Open this day</button></div>
      <div class="tablewrap"><table class="rtable ah"><thead><tr><th>Time</th><th>Lesson</th><th>For</th><th>Relief teacher</th><th>Status</th></tr></thead><tbody>${rows.map(row).join("")}</tbody></table></div>`;
  }

  const sel = b => (b.dataset.ah === "span" ? `[data-ah="span"][data-v="${b.dataset.v}"]` : b.dataset.ah === "reload" ? `[data-ah="reload"]` : "");
  function focused() {   /* the selector of the span button or Refresh that has the focus, if it is in this pane */
    const a = typeof document !== "undefined" ? document.activeElement : null;
    return a && a.dataset && A.pane && A.pane.contains && A.pane.contains(a) ? sel(a) : "";
  }

  function paint() {
    const box = $("#ahBox", A.pane);
    if (!box) return;
    const D = A.data, days = D && Array.isArray(D.days) ? D.days : [];
    const seg = SPANS.map(([k, label]) => `<button type="button" data-ah="span" data-v="${k}" class="${k === A.span ? "on" : ""}" aria-pressed="${k === A.span ? "true" : "false"}">${esc(label)}</button>`).join("");
    const body = (A.err ? `<p>${R.say(A.err)} <button type="button" data-ah="reload">Try again</button></p>` : "")
      + (D ? (days.length ? days.map(block).join("") : A.err ? "" : `<p class="muted">${esc(EMPTY[A.span] || EMPTY.weeks)}</p>`) : A.err ? "" : `<p class="muted">Loading…</p>`);
    box.innerHTML = `<div class="card">
      <div class="ab-top"><div><h2>Planned Relief Assignments</h2><div class="small muted">${esc(`Every relief on the school days after today${D && stamp(D.as_of) ? ` · as of ${stamp(D.as_of)}` : ""}`)}</div></div>
        <div class="row"><div class="seg" role="group" aria-label="How far ahead">${seg}</div><button type="button" class="small" data-ah="reload" ${A.loading ? "disabled" : ""}>${A.loading ? "Reading…" : "Refresh"}</button></div></div>
      ${body}
      </div>`;
    if (A.keep && !A.loading) { const el = $(A.keep, A.pane); A.keep = ""; if (el && el.focus) el.focus(); }
  }

  async function load() {
    const seq = ++A.seq;
    A.keep = A.keep || focused();   /* a repaint rewrites the box: the control in use is given the focus again once the read is in */
    A.loading = true; paint();
    const r = await R.api(`/api/relief/ahead?span=${A.span}`);
    if (seq !== A.seq) return;
    A.loading = false;
    if (!r.ok) { A.err = { text: r.error, bad: true, status: r.status }; paint(); return; }   /* the last list stays under the sentence */
    A.err = null; A.data = r.data || {};
    paint();
  }

  function onClick(e) {
    const b = e.target.closest("button[data-ah]");
    if (!b || b.disabled) return;
    const a = b.dataset.ah;
    if (a === "span") {
      if (!SPANS.some(s => s[0] === b.dataset.v) || b.dataset.v === A.span) return;
      A.span = b.dataset.v; A.data = null; A.err = null; A.keep = sel(b);   /* the other span's list is not kept: it would be under the wrong name */
      load();
      return;
    }
    if (a === "reload") { A.keep = sel(b) || `[data-ah="reload"]`; load(); return; }
    if (a === "open") R.showDay(b.dataset.date);
  }

  R.tab("ahead", {
    init(pane) {
      A.pane = pane;
      pane.innerHTML = `<div id="ahBox"></div>`;
      pane.addEventListener("click", onClick);
      load();
    },
    shown() { load(); },
    dirty() { return false; },
  });
})();

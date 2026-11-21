"use strict";
/* What's in (/relief#inbox), for the relief team (me.can_team), read-only: every absence, newest first, with when it came
   in, who sent it and how, for whom and when, the reason, whether the absent teacher has acknowledged (when someone else
   planned it), how many lessons have work and how many have a relief teacher; cancelled ones dimmed. Views: Coming up,
   Today, Cancelled. "new" = came in since this person last looked. The list is read with a GET, which never writes;
   once it is shown, the page posts the list's as_of to /api/relief/absences/seen. */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day;
  const $ = (s, el = document) => el.querySelector(s);
  const I = { pane: null, list: null, err: null, asOf: "", view: "coming", seq: 0, loading: false };
  const lastDate = r => (r.dates || []).slice().sort().pop() || "";
  const VIEWS = [
    ["coming", "Coming up", r => !r.cancelled && lastDate(r) >= RF.today(), "Nothing coming up."],
    ["today", "Today", r => !r.cancelled && (r.dates || []).includes(RF.today()), "No one is away today."],
    ["cancelled", "Cancelled", r => !!r.cancelled, "Nothing cancelled."],
  ];
  const hasWork = x => { const w = x.work || {}; return !!(w.text || w.link || (w.files || []).length); };

  function stamp(iso, plain) {   /* "Mon 12 Oct, 09:30" from a school-time stamp; "Today, 09:30" unless plain */
    const s = String(iso || ""), d = s.slice(0, 10), t = s.slice(11, 16);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return "";
    return `${d === RF.today() && !plain ? "Today" : day(d)}${/^\d{2}:\d{2}$/.test(t) ? `, ${t}` : ""}`;
  }

  function row(r) {
    const all = r.lessons || [], cover = all.filter(x => x.needed), n = cover.length;
    const work = cover.filter(hasWork).length, chosen = cover.filter(x => x.relief).length;
    const changed = !r.cancelled && all.some(x => x.changed && x.date >= RF.today());
    const when = (r.dates || []).map(d => d === RF.today() ? "Today" : day(d)).join(", ");
    const how = r.how === "planned" ? "planned · app" : "for themselves · app";
    let tail;
    if (r.cancelled) {
      const c = r.cancelled;
      tail = `<td colspan="3"><span class="chip st-off">${esc(`Cancelled by ${c.by}${c.at ? `, ${stamp(c.at)}` : ""}: “${c.why}”`)}</span></td>`;
    } else {
      const ack = r.how !== "planned" ? `<span class="small muted">their own request</span>`
        : r.acknowledged ? `<span class="chip st-ok">✓ ${esc(stamp(r.acknowledged.at) || "acknowledged")}</span>` : `<span class="chip st-amber">not acknowledged yet</span>`;
      const w = n ? `<span class="${work === n ? "chip st-ok" : ""}">${work} of ${n}</span>` : `<span class="muted">none to cover</span>`;
      const rel = n ? `<span class="${chosen === n ? "chip st-ok" : "chip"}">${chosen} chosen · ${n - chosen} open</span>` : `<span class="muted">—</span>`;
      tail = `<td>${ack}</td><td>${w}</td><td>${rel}</td>`;
    }
    return `<tr class="${[r.new ? "new" : "", r.cancelled ? "off" : ""].filter(Boolean).join(" ")}">
      <td>${r.new ? `<span class="chip new">new</span><br>` : ""}${esc(stamp(r.at))}</td>
      <td>${esc(r.by)}<div class="small muted">${esc(how)}</div></td>
      <td>${esc(r.teacher)}</td>
      <td>${esc(when)}<div class="small muted">${esc(`${R.span(r)} · ${R.plural(n, "lesson")}`)}</div>${changed ? `<div class="small pl-changed">The lesson has changed since this was planned</div>` : ""}</td>
      <td>${esc(R.reason(r))}</td>${tail}</tr>`;
  }

  function paint() {
    const box = $("#inBox", I.pane);
    if (!box) return;
    if (!I.list) {
      box.innerHTML = I.err ? `<div class="card"><p>${R.say(I.err)}</p><p><button type="button" data-in="reload">Try again</button></p></div>` : `<div class="card"><p class="muted">Loading…</p></div>`;
      return;
    }
    const v = VIEWS.find(x => x[0] === I.view) || VIEWS[0], rows = I.list.filter(v[2]), fresh = I.list.filter(r => r.new).length;
    const seg = VIEWS.map(([k, label, f]) => `<button type="button" data-in="view" data-v="${k}" class="${k === v[0] ? "on" : ""}" aria-pressed="${k === v[0] ? "true" : "false"}">${esc(label)} (${I.list.filter(f).length})</button>`).join("");
    const about = [I.asOf ? `As of ${stamp(I.asOf, true)}` : "", fresh ? `${fresh} new since you last looked` : ""].filter(Boolean).join(" · ");
    box.innerHTML = `<div class="card">
      <div class="ab-top"><div><h2>What's in</h2><div class="small muted">${esc(about)}</div></div>
        <div class="row"><div class="seg" role="group" aria-label="Which absences">${seg}</div><button type="button" class="small" data-in="reload" ${I.loading ? "disabled" : ""}>${I.loading ? "Reading…" : "Refresh"}</button></div></div>
      ${I.err ? `<p>${R.say(I.err)}</p>` : ""}
      ${rows.length ? `<div class="tablewrap"><table class="rtable inbox"><thead><tr><th>Submitted</th><th>By</th><th>For</th><th>When</th><th>Reason</th><th>Absent teacher</th><th>Work</th><th>Relief</th></tr></thead>
        <tbody>${rows.map(row).join("")}</tbody></table></div>` : `<p class="muted">${esc(v[3])}</p>`}
      <div class="note">Picking and approving relief teachers come in the next stage.</div></div>`;
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

  function onClick(e) {
    const b = e.target.closest("button[data-in]");
    if (!b || b.disabled) return;
    if (b.dataset.in === "view") { I.view = b.dataset.v; paint(); const again = $(`[data-in="view"][data-v="${I.view}"]`, I.pane); if (again) again.focus(); return; }
    if (b.dataset.in === "reload") { load(); return; }
  }

  R.tab("inbox", {
    init(pane) {
      I.pane = pane;
      pane.innerHTML = `<div id="inBox"></div>`;
      pane.addEventListener("click", onClick);
      load();
    },
    shown() { load(); },
    dirty() { return false; },
  });
})();

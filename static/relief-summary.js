"use strict";
/* Weekly summary (/relief#summary), for the relief team (me.can_team): one week's relief in numbers, from /api/relief/summary (the
   same numbers as the weekly message on Telegram). The heading is the week, as the server names it, with ‹ and › for the week before
   and after and "This week" when away from it. Opened with ?week=YYYY-MM-DD in the address (the message's button) it starts at that
   week; with anything that is no date, at this week. Counters (relief periods, absences, the share covered by Flexi Adjuncts, left out
   when no such role is set, and never acknowledged), planned ahead or on the day, how reliefs were acknowledged, requests to change,
   relief periods by day and by department of the absent teacher as bars (the number is always written), who had the most, and every
   relief of the week with how it was acknowledged. */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day, enc = encodeURIComponent, say = R.say;
  const $ = (s, el = document) => el.querySelector(s);
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
  const S = { pane: null, week: "", data: null, err: null, seq: 0 };   /* week: the Monday shown (ISO) */

  const num = v => Number(v) || 0;
  const isDate = v => /^\d{4}-\d{2}-\d{2}$/.test(String(v || "")) && RF.addDays(v, 0) === v;
  const mondayOf = iso => RF.addDays(iso, -((new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7));
  const thisWeek = () => mondayOf(RF.today());
  const pairs = v => (Array.isArray(v) ? v : []).map(x => [String(x[0]), num(x[1])]);

  function asked() {   /* the week in the address, else this week */
    const v = new URLSearchParams(location.search).get("week");
    return mondayOf(isDate(v) ? v : RF.today());
  }

  /* ---------------------------------------------------------------- the numbers */
  function counter(label, n, tone, under) {
    return `<div class="counter${tone ? " " + tone : ""}"><span class="small muted">${esc(label)}</span><b>${esc(n)}</b>${under ? `<span class="small muted">${esc(under)}</span>` : ""}</div>`;
  }

  function counters(d) {
    return `<div class="td-counts">${[counter("Relief periods", num(d.periods)), counter("Absences", num(d.absences)),
      d.fat_role ? counter("By Flexi Adjuncts", `${num(d.fat_percent)}%`, "", R.plural(num(d.fat_periods), "period")) : "",
      counter("Never acknowledged", num(d.never), num(d.never) ? "bad" : "")].join("")}</div>`;
  }

  function facts(d) {
    const line = (what, text) => `<div><dt>${esc(what)}</dt><dd>${esc(text)}</dd></div>`, n = num(d.asked);
    return `<dl class="sm-facts">${line("Arranged", `${num(d.ahead)} planned ahead · ${num(d.on_day)} on the day`)}
      ${line("Acknowledged", `${num(d.on_time)} on time · ${num(d.late)} late · ${num(d.never)} never · ${num(d.waiting)} waiting`)}
      ${line("Asked to change", n ? `${n} (${num(d.moved)} moved, ${num(d.kept)} kept)` : "0")}</dl>`;
  }

  function bars(title, list, cls) {
    const most = Math.max(1, ...list.map(x => x[1]));
    return `<section><h3>${esc(title)}</h3><dl class="sm-bars${cls ? " " + cls : ""}">${list.map(([k, n]) => `<div><dt>${esc(k)}</dt>
      <dd><span class="sm-bar" aria-hidden="true"><i style="width:${Math.round(100 * n / most)}%"></i></span><b>${n}</b></dd></div>`).join("")}</dl></section>`;
  }

  function ack(v) {   /* "never" and "late 09:30" say so in words, and in colour */
    const s = String(v || ""), tone = s === "never" ? "st-warn" : s.startsWith("late ") ? "st-amber" : s === "waiting" ? "" : "st-ok";
    return `<span class="chip${tone ? " " + tone : ""}">${esc(s)}</span>`;
  }

  function table(rows) {
    return `<h3>Every relief this week</h3><div class="tablewrap"><table class="rtable sm-table"><thead><tr><th>Date</th><th>Lesson</th><th>For</th><th>Relief</th><th>Acknowledged</th></tr></thead>
      <tbody>${rows.map(r => `<tr><td class="sm-date">${esc(day(r.date))}</td><td>${esc(r.lesson)}</td><td>${esc(r.absent)}</td><td>${esc(r.relief)}</td><td>${ack(r.ack)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function numbers(d) {
    if (!num(d.periods)) return `<p class="muted">No relief this week.</p>${num(d.asked) ? facts(d) : ""}`;
    const byDay = d.by_day || {}, top = pairs(d.top);
    return `${counters(d)}${facts(d)}
      <div class="sm-two">${bars("Relief periods by day", DAYS.map(k => [k, num(byDay[k])]), "days")}${bars("By department of the absent teacher", pairs(d.by_dept))}</div>
      <h3>Most relief this week</h3><p class="sm-top">${top.map(([k, n]) => `${esc(k)} <b>${n}</b>`).join(" · ")}</p>
      ${table(Array.isArray(d.rows) ? d.rows : [])}
      <div class="note">Counted in periods; absences and requests to change are counted one by one. A lesson stopped by an exam or event is left out.</div>`;
  }

  /* ---------------------------------------------------------------- the page */
  function paint() {
    const d = S.data;
    $("#smTitle", S.pane).textContent = d ? d.label : `Week of ${day(S.week)}`;
    $("#smNow", S.pane).hidden = S.week === thisWeek();
    const again = `<button type="button" class="small" data-sm="reload">Try again</button>`;
    $("#smBody", S.pane).innerHTML = (S.err ? `<p>${say(S.err)} ${again}</p>` : "") + (d ? numbers(d) : S.err ? "" : `<p class="muted">Loading…</p>`);
  }

  async function load() {
    const seq = ++S.seq;
    S.err = null;
    paint();
    const r = await R.api(`/api/relief/summary?week=${enc(S.week)}`);
    if (seq !== S.seq) return;   /* another week was asked for since */
    if (r.ok) S.data = r.data;
    else S.err = { text: r.error, bad: true, status: r.status };
    paint();
  }

  function setWeek(iso) {
    S.week = iso;
    S.data = null;
    load();
  }

  function onClick(e) {
    const b = e.target.closest("[data-sm]");
    if (!b || b.disabled) return;
    switch (b.dataset.sm) {
      case "before": setWeek(RF.addDays(S.week, -7)); return;
      case "after": setWeek(RF.addDays(S.week, 7)); return;
      case "now": setWeek(thisWeek()); break;
      case "reload": load(); break;
    }
    $("#smTitle", S.pane).focus();   /* the button pressed is not there any more */
  }

  R.tab("summary", {
    init(pane) {
      S.pane = pane;
      S.week = asked();
      pane.innerHTML = `<div class="card sm"><div class="ab-top"><div class="sm-nav">
        <button type="button" class="small" data-sm="before" aria-label="Week before">‹</button><h2 id="smTitle" tabindex="-1" aria-live="polite"></h2>
        <button type="button" class="small" data-sm="after" aria-label="Week after">›</button></div><button type="button" class="small" data-sm="now" id="smNow" hidden>This week</button></div>
        <div id="smBody"></div></div>`;
      pane.addEventListener("click", onClick);
      load();
    },
    shown() { load(); },
    dirty() { return false; },
  });
})();

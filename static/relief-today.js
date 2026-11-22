"use strict";
/* Today (/relief#today), for the relief team (me.can_team). Every lesson that needs relief on a date (today until another
   is chosen), from /api/relief/today, one row a cover (each part of a split lesson its own row), in time order: the
   periods and times, the class and subject, the room, the absent teacher and whether work is set, the relief teacher with
   who picked them and why, and the state in plain words. Buttons: Approve; Choose or Change, which opens the "free then"
   list (Relief.freeList, drawn as Plan relief's) and approves the one chosen at once; Split (a cover of two periods or
   more that is not approved: the person chooses after which period); Join again (a split lesson none of whose parts is
   approved); Keep (on a request to change, where Approve reads "Approve the new pick"). At the top: Approve all waiting
   and Fill now. While the server says picks are being made (filling), the day is read again every 3 seconds, only while
   this tab is on screen. After every action the day is read again; a refusal shows the server's sentence beside its row.
   Approve sends the name it shows (who), and Approve all the waiting rows it shows ({id, ckey, who} each): the server
   refuses or skips a pick that has changed since this page read it ("The pick has changed since you looked…"), and the
   re-read shows the new one. A lesson an approved exam or event stops is shown as "Not happening", with why, out of the
   counts and with no buttons; the teacher of a backup is in school, so the row says which duty they are on. A row is known by its absence id and cover key together (two absent co-teachers of one
   lesson share a cover key). */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day, enc = encodeURIComponent, say = R.say;
  const $ = (s, el = document) => el.querySelector(s);
  const EVERY = 3000, SENT = ["approved", "acknowledged", "change"];
  /* top: the lines above the rows ({text, bad, fill}); msg: a line beside a row (row key -> {text, bad}); busy: rows with
     a step on its way; all: Approve all or Fill now on its way; open: the row whose "free then" list is open, free: each
     list's answer; split: the row whose split choice is open */
  const T = { pane: null, date: "", data: null, err: null, seq: 0, loading: false, timer: 0, wait: 0, top: [], msg: new Map(),
              busy: new Set(), all: false, open: null, free: new Map(), split: null };

  const rid = r => r.id + "\n" + r.ckey;
  const rows = () => (T.data && Array.isArray(T.data.rows) ? T.data.rows : []);
  const findRow = k => rows().find(r => rid(r) === k) || null;
  const keyOf = el => { const row = el && el.closest(".td-row"); return row ? row.dataset.id + "\n" + row.dataset.ckey : null; };
  const rowEl = k => [...T.pane.querySelectorAll(".td-row[data-ckey]")].find(el => keyOf(el) === k) || null;
  const past = () => T.date < RF.today();
  const onScreen = () => R.cur === "today" && document.visibilityState !== "hidden";
  const lessonName = r => `${RF.title(r)} ${RF.periods(r)}`;

  function clock(at) {   /* "07:20" today, else "Mon 23 Nov, 07:20" */
    const s = String(at || ""), d = s.slice(0, 10), t = s.slice(11, 16);
    if (!/^\d{2}:\d{2}$/.test(t)) return "";
    return d === RF.today() ? t : `${day(d)}, ${t}`;
  }

  /* ---------------------------------------------------------------- a row */
  function byLine(pk) {   /* who picked them and why: "AI" or "the app's order" with the reason; a planner's or the team's reason names them */
    if (!pk) return "";
    const tag = pk.by === "ai" ? "AI" : pk.by === "app" ? "the app's order" : "";
    const reason = pk.reason || (pk.by === "planner" ? "Planned." : pk.by === "team" ? "Chosen by the relief team." : "");
    return `<div class="why">${tag ? `<span class="td-by">${esc(tag)}</span> ` : ""}${esc(reason)}</div>`;
  }

  function relief(r) {
    const filling = !!(T.data && T.data.filling), warn = r.warn ? `<div class="td-warn">${esc(r.warn)}</div>` : "";
    const picking = `<span class="td-busy">Being picked…</span>`;
    if (r.state === "cancelled" || r.state === "stopped") return `<span class="muted">${r.pick ? esc(r.pick.who) : "—"}</span>`;
    if (r.state === "open") return warn || (filling ? picking : `<span class="muted">Not picked yet.</span>`);   /* warn: nobody free, or only people over a limit */
    const p = r.pick || {};
    if (r.state === "change") {
      const ch = r.change || {}, np = ch.pick;
      const first = `<div><s class="muted">${esc(p.who)}</s> asked to change${ch.why ? `: <i>“${esc(ch.why)}”</i>` : ""}</div>${warn}`;
      const next = np
        ? `<div class="td-new"><b>New pick: ${esc(np.who)}</b>${byLine(np)}${ch.stale ? `<div class="td-warn">${esc(`${np.who} is no longer free then. Choose someone else.`)}</div>` : ""}</div>`
        : `<div class="td-new">${filling ? picking : `<span class="muted">No new pick yet.</span>`}</div>`;
      return first + next;
    }
    return `<div><b>${esc(p.who)}</b>${r.over_now ? ` <span class="mark">over a limit</span>` : ""}</div>${byLine(p)}${warn}`;
  }

  function chip(r) {
    const c = (text, tone) => `<span class="chip td-chip${tone ? " " + tone : ""}">${esc(text)}</span>`;
    switch (r.state) {
      case "open": return c("No relief teacher yet", "");
      case "waiting": return c("Waiting for you", "st-amber");
      case "approved": return c("Approved: they see it in Reliefs I'm covering", "st-sent")
        + (r.approved && r.approved.by ? `<div class="small muted">by ${esc(r.approved.by)}${clock(r.approved.at) ? `, ${esc(clock(r.approved.at))}` : ""}</div>` : "");
      case "acknowledged": return c(`✓ Acknowledged${r.ack && clock(r.ack.at) ? ` ${clock(r.ack.at)}` : ""}`, "st-ok");
      case "change": return c(`Asked to change${r.change && clock(r.change.at) ? ` ${clock(r.change.at)}` : ""}`, "st-blue");
      case "cancelled": return c("The absence is cancelled", "st-off");
      case "stopped": return c("Not happening", "st-off") + (r.stopped ? `<div class="small muted">${esc(r.stopped)}</div>` : "");
      default: return c(String(r.state || ""), "");
    }
  }

  function buttons(r) {
    if (r.state === "cancelled" || r.state === "stopped" || past()) return "";
    const k = rid(r), off = T.busy.has(k) || T.all ? " disabled" : "", out = [];
    const b = (act, label, cls, more) => `<button type="button" class="small${cls ? " " + cls : ""}" data-td="${act}"${more || ""}${off}>${esc(label)}</button>`;
    if (r.state === "waiting" && !r.stale) out.push(b("approve", "Approve", "primary"));
    if (r.state === "change" && r.change && r.change.pick && !r.change.stale) out.push(b("approve", "Approve the new pick", "primary"));
    const listOpen = T.open === k;
    out.push(b(listOpen ? "close" : "free", listOpen ? "Close the list" : r.state === "open" ? "Choose" : "Change", "", ` aria-expanded="${listOpen ? "true" : "false"}"`));
    if (r.state === "change" && r.pick) out.push(b("keep", `Keep ${r.pick.who}`));
    if (Number(r.n) >= 2 && (r.state === "open" || r.state === "waiting")) {
      const on = T.split === k;
      out.push(b(on ? "split-off" : "split", "Split", "", ` aria-expanded="${on ? "true" : "false"}"`));
    }
    if (r.split && !rows().some(o => o.id === r.id && o.key === r.key && SENT.includes(o.state))) out.push(b("join", "Join again"));
    return `<div class="bar td-btns">${out.join("")}</div>`;
  }

  function splitHTML(r) {   /* "Split after P3": the second part starts at the next period (0-based at = the 1-based period before it) */
    const p = Number(r.p) || 0, n = Number(r.n) || 1, off = T.busy.has(rid(r)) || T.all ? " disabled" : "", opts = [];
    for (let k = p + 1; k < p + n; k++) opts.push(`<button type="button" class="small" data-td="split-go" data-at="${k}"${off}>Split after P${k}</button>`);
    return `<div class="td-split" role="group" aria-label="${esc(`Split ${lessonName(r)}`)}"><span class="small">Split ${esc(lessonName(r))} into two parts, each with its own relief teacher:</span>
      ${opts.join("")}<button type="button" class="small" data-td="split-off">Back</button></div>`;
  }

  function freeArea(r) {
    const k = rid(r), s = T.free.get(k) || {}, close = `<button type="button" class="small" data-pl="close">Close the list</button>`;
    if (s.loading) return `<div class="pl-list"><p class="small muted">Finding who is free…</p></div>`;
    if (s.err) return `<div class="pl-list"><p>${say(s.err)}</p><div class="bar"><button type="button" class="small" data-td="free">Try again</button>${close}</div></div>`;
    const mark = r.state === "waiting" ? "Picked" : r.state === "change" ? "Asked to change" : "Chosen";
    return R.freeList({ data: s.data, x: Object.assign({}, r, { date: T.date }), chosen: r.state === "open" ? "" : (r.pick && r.pick.who) || "",
                        busy: !!s.busy || T.busy.has(k) || T.all, teaching: s.teaching, duty: s.duty, mark });
  }

  function row(r) {
    const k = rid(r), m = T.msg.get(k), under = [];
    if (m) under.push(`<div class="bar">${say(m)}</div>`);
    if (T.split === k && Number(r.n) >= 2) under.push(splitHTML(r));
    if (T.open === k) under.push(freeArea(r));
    const work = r.work_set ? `<span class="td-yes">work set</span>` : `<span class="td-no">no work yet</span>`;
    return `<div class="td-row${r.state === "cancelled" || r.state === "stopped" ? " off" : ""}${r.state === "change" ? " ask" : ""}" role="listitem" data-id="${esc(r.id)}" data-ckey="${esc(r.ckey)}">
      <div class="td-when"><b>${esc(RF.periods(r))}</b>${r.start ? `<div class="small muted">${esc(RF.time(r))}</div>` : ""}</div>
      <div class="td-lesson"><b>${esc(RF.title(r))}</b>${r.room ? ` <span class="small muted">· ${esc(r.room)}</span>` : ""}
        <div class="small">for ${esc(r.absent)}${r.duty ? ` <span class="muted">(${esc(r.duty)})</span>` : ""} · ${work}</div>${r.split ? `<div class="small muted">part of a split lesson</div>` : ""}</div>
      <div class="td-relief">${relief(r)}</div>
      <div class="td-state">${chip(r)}${buttons(r)}</div>
      ${under.length ? `<div class="td-under">${under.join("")}</div>` : ""}</div>`;
  }

  /* ---------------------------------------------------------------- the page */
  function paintDay() {
    const t = RF.today(), tm = RF.addDays(t, 1);
    const seg = (v, d, label) => `<button type="button" data-td="day" data-v="${v}" class="${T.date === d ? "on" : ""}" aria-pressed="${T.date === d ? "true" : "false"}">${esc(label)}</button>`;
    $("#tdSeg", T.pane).innerHTML = seg("today", t, "Today") + seg("tomorrow", tm, "Tomorrow");
    const input = $("#tdDate", T.pane);
    if (input && input.value !== T.date && document.activeElement !== input) input.value = T.date;
  }

  function paintHead() {
    const t = RF.today(), d = T.date, live = rows().filter(r => r.state !== "cancelled" && r.state !== "stopped"), away = new Set(live.map(r => r.absent)).size;
    $("#tdTitle", T.pane).textContent = d === t ? "Relief today" : `Relief on ${day(d)}`;
    const when = d === t ? `Today, ${day(d)}` : d === RF.addDays(t, 1) ? `Tomorrow, ${day(d)}` : day(d);
    $("#tdSub", T.pane).textContent = [when, T.data ? `${R.plural(away, "teacher")} away` : "", past() ? "past: shown as it was" : ""].filter(Boolean).join(" · ");
    const c = T.data && T.data.counts;
    const counter = (label, n, tone) => `<div class="counter${tone ? " " + tone : ""}"><span class="small muted">${esc(label)}</span><b>${esc(Number(n) || 0)}</b></div>`;
    $("#tdCounts", T.pane).innerHTML = !c ? "" : [counter("Lessons to cover", c.need), counter("Waiting for you", c.waiting, "amber"),
      counter("Approved, not acknowledged", c.approved), counter("Acknowledged", c.acknowledged, "ok"), counter("Asked to change", c.change, "blue"),
      counter("No relief teacher yet", c.open), Number(c.nobody) ? counter("Nobody free then", c.nobody, "bad") : ""].join("");
  }

  function paintActs() {
    const c = (T.data && T.data.counts) || {}, w = Number(c.waiting) || 0, off = !T.data || past() || T.all;
    $("#tdActs", T.pane).innerHTML = `<button type="button" class="primary" data-td="all"${off || !w ? " disabled" : ""}>${esc(w ? `Approve all ${w} waiting` : "Approve all waiting")}</button>
      <button type="button" data-td="fill"${off ? " disabled" : ""}>Fill now</button>
      <button type="button" class="small" data-td="reload"${T.loading ? " disabled" : ""}>${T.loading ? "Reading…" : "Refresh"}</button>`;
  }

  function paintTop() {
    const lines = T.top.map(m => `<p class="td-top">${say(m)}</p>`);
    if (T.data && T.data.filling) lines.push(`<p class="td-top small td-busy">Being picked… The page reads the day again every 3 seconds.</p>`);
    if (T.err && T.data) lines.push(`<p class="td-top">${say(T.err)} <button type="button" class="small" data-td="reload">Try again</button></p>`);
    $("#tdTop", T.pane).innerHTML = lines.join("");
  }

  function focusNow() {   /* the focused button of a row, as {k, sel, extra}, or null */
    const a = document.activeElement, k = a && a !== document.body && T.pane.contains(a) ? keyOf(a) : null;
    if (!k || !a.dataset) return null;
    const sel = a.dataset.td ? `[data-td="${a.dataset.td}"]` : a.dataset.pl ? `[data-pl="${a.dataset.pl}"]` : "";
    return sel ? { k, sel, extra: a.dataset.name || a.dataset.at || "" } : null;
  }

  function refocus(f, any) {   /* the same button of the same row again; any: else the row's first button */
    const el = f && rowEl(f.k);
    if (!el) return;
    let b = [...el.querySelectorAll(f.sel)].find(x => !f.extra || x.dataset.name === f.extra || x.dataset.at === f.extra);
    if ((!b || b.disabled) && any) b = [...el.querySelectorAll("button")].find(x => !x.disabled);
    if (b && !b.disabled) b.focus({ preventScroll: true });
  }

  function paintRows() {   /* the rows, keeping the focus on the same button of the same row when it is still there */
    const box = $("#tdRows", T.pane), f = focusNow();
    if (!T.data) box.innerHTML = T.err ? `<p>${say(T.err)} <button type="button" class="small" data-td="reload">Try again</button></p>` : `<p class="muted">Loading…</p>`;
    else if (!rows().length) box.innerHTML = `<p class="muted">No lessons need relief on ${esc(day(T.date))}.</p>`;
    else box.innerHTML = `<div class="td-list" role="list"><div class="td-row td-cols" aria-hidden="true"><span>Time</span><span>Lesson</span><span>Relief teacher and why</span><span>Status</span></div>${rows().map(row).join("")}</div>`;
    if (f) refocus(f, false);
  }

  function paint() { paintHead(); paintActs(); paintTop(); paintRows(); }

  function focusIn(k, sel) { const el = rowEl(k), b = el && el.querySelector(sel); if (b) b.focus(); }

  /* ---------------------------------------------------------------- the server */
  function schedule() {
    clearTimeout(T.timer); T.timer = 0;
    if (T.data && T.data.filling && onScreen()) T.timer = setTimeout(() => { T.timer = 0; if (onScreen()) load(true); }, EVERY);
  }

  async function load(quiet) {   /* quiet: a fetch while picks are made, drawn again only when something changed */
    const seq = ++T.seq, date = T.date;
    clearTimeout(T.timer); T.timer = 0;
    T.loading = true;
    if (!quiet) paintActs();
    const res = await R.api(`/api/relief/today?date=${enc(date)}`);
    if (seq !== T.seq) return;
    T.loading = false;
    if (!res.ok) { T.err = { text: res.error, bad: true, status: res.status }; paint(); return; }   /* no more fetches until Try again */
    const same = quiet && !T.err && T.data && JSON.stringify(T.data) === JSON.stringify(res.data);
    T.err = null; T.data = res.data;
    for (const [k, m] of [...T.msg]) if (!findRow(k)) { T.msg.delete(k); T.top.push(m); }   /* its row is gone (split, joined): said above the rows */
    if (T.open && !findRow(T.open)) T.open = null;
    if (T.split && !findRow(T.split)) T.split = null;
    if (!T.data.filling) T.top = T.top.filter(m => !m.fill);
    if (same) paintActs(); else paint();
    schedule();
  }

  async function act(k, method, url, body, done) {   /* one step on one row; then the day is read again */
    const f = focusNow();
    T.busy.add(k); T.msg.delete(k); paintRows();
    const res = await R.api(url, R.json(method, body));
    T.busy.delete(k);
    if (!res.ok) T.msg.set(k, { text: res.error, bad: true, status: res.status });
    else { const text = done ? done(res.data) : ""; if (text) T.msg.set(k, { text, bad: false }); }
    await load();
    if (f && !focusNow()) refocus(f, true);
  }

  async function openFree(k) {
    const r = findRow(k);
    if (!r) return;
    const s = { loading: true, err: null, data: null, teaching: false, busy: false };
    T.open = k; T.split = null; T.free.set(k, s); T.msg.delete(k);
    paintRows();
    focusIn(k, '[data-td="close"]');
    const res = await R.api(`/api/relief/absences/${enc(r.id)}/covers/${enc(r.ckey)}/free`);
    if (T.free.get(k) !== s) return;   /* opened again since */
    s.loading = false;
    if (res.ok) s.data = res.data; else s.err = { text: res.error, bad: true, status: res.status };
    paintRows();
  }

  function closeFree(k) {
    T.open = null;
    paintRows();
    if (k) focusIn(k, '[data-td="free"]');
  }

  async function choose(k, name) {   /* Change: the cover to this person, approved at once */
    const r = findRow(k), s = T.free.get(k);
    if (!r || !name) return;
    if (s) s.busy = true;
    await act(k, "PUT", `/api/relief/absences/${enc(r.id)}/covers/${enc(r.ckey)}/relief`, { relief: name }, () => {
      T.open = null; T.free.delete(k);
      return `${name} chosen and approved: they see it in Reliefs I'm covering.`;
    });
    if (s) s.busy = false;
  }

  async function approveAll() {
    if (T.all || !T.data) return;
    const before = rows(), covers = before.filter(o => o.state === "waiting" && o.pick && o.pick.who).map(o => ({ id: o.id, ckey: o.ckey, who: o.pick.who }));
    T.all = true; T.top = []; paint();
    const res = await R.api("/api/relief/today/approve-all", R.json("POST", { date: T.date, covers }));
    T.all = false;
    if (!res.ok) T.top = [{ text: res.error, bad: true, status: res.status }];
    else {
      const got = res.data || {}, skipped = Array.isArray(got.skipped) ? got.skipped : [];
      T.top = [{ text: `Approved ${R.plural(Number(got.approved) || 0, "relief")}.${skipped.length ? ` Not approved: ${skipped.length}.` : ""}`, bad: false }];
      for (const s of skipped) {   /* a skipped one is matched by its absence id and cover key */
        const r = before.find(o => o.id === s.id && o.ckey === s.ckey);
        T.top.push({ text: `${r ? `${lessonName(r)}, ${s.name}` : s.name}: ${s.why}`, bad: true });
        if (r) T.msg.set(rid(r), { text: s.why, bad: true });
      }
    }
    await load();
  }

  async function fillNow() {
    if (T.all || !T.data) return;
    T.all = true; T.top = []; paint();
    const res = await R.api("/api/relief/today/fill", R.json("POST", { date: T.date }));
    T.all = false;
    if (!res.ok) T.top = [{ text: res.error, bad: true, status: res.status }];
    else if (!res.data || !res.data.started) T.top = [{ text: "The picks could not be started. Try again in a minute.", bad: true }];
    else T.top = [{ text: "Picking for the open lessons.", bad: false, fill: true }];
    await load();
  }

  function setDate(v) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(v || "")) || v === T.date) return;
    T.date = v; T.data = null; T.err = null; T.top = []; T.msg.clear(); T.open = null; T.free.clear(); T.split = null;
    paintDay(); paint(); load();
  }

  /* ---------------------------------------------------------------- events */
  function onClick(e) {
    const b = e.target.closest("button[data-td],button[data-pl]");
    if (!b || b.disabled || !T.pane.contains(b)) return;
    const a = b.dataset.td || "pl-" + b.dataset.pl;
    switch (a) {
      case "day": setDate(b.dataset.v === "tomorrow" ? RF.addDays(RF.today(), 1) : RF.today()); return;
      case "reload": T.err = null; load(); return;
      case "all": approveAll(); return;
      case "fill": fillNow(); return;
    }
    const k = keyOf(b), r = k && findRow(k);
    if (!r) return;
    const cover = `/api/relief/absences/${enc(r.id)}/covers/${enc(r.ckey)}`, lesson = `/api/relief/absences/${enc(r.id)}/lessons/${enc(r.key)}`;
    switch (a) {
      case "approve": {
        const who = (r.state === "change" ? r.change && r.change.pick && r.change.pick.who : r.pick && r.pick.who) || "";
        act(k, "POST", `${cover}/approve`, { who }, () => `${who} approved: they see it in Reliefs I'm covering.`);   /* the name shown: refused if it changed */
        return;
      }
      case "free": openFree(k); return;
      case "close": case "pl-close": closeFree(k); return;
      case "pl-choose": choose(k, b.dataset.name || ""); return;
      case "pl-teaching": { const s = T.free.get(k); if (s) { s.teaching = !s.teaching; paintRows(); focusIn(k, '[data-pl="teaching"]'); } return; }
      case "pl-duty": { const s = T.free.get(k); if (s) { s.duty = !s.duty; paintRows(); focusIn(k, '[data-pl="duty"]'); } return; }
      case "keep": act(k, "POST", `${cover}/keep`, {}, () => `${r.pick.who} kept: the relief stays with them.`); return;
      case "split": T.split = k; T.open = null; T.msg.delete(k); paintRows(); focusIn(k, '[data-td="split-go"]'); return;
      case "split-off": T.split = null; paintRows(); focusIn(k, '[data-td="split"]'); return;
      case "split-go": {
        const at = Number(b.dataset.at);
        T.split = null;
        act(k, "POST", `${lesson}/split`, { at }, () => `${lessonName(r)} split after P${at}: each part needs its own relief teacher.`);
        return;
      }
      case "join": act(k, "POST", `${lesson}/join`, {}, () => `${RF.title(r)}: joined again as one lesson.`); return;
    }
  }

  function onChange(e) {
    if (e.target.id !== "tdDate") return;
    const v = e.target.value;
    clearTimeout(T.wait);   /* a date typed in digit by digit is read once it settles */
    T.wait = setTimeout(() => setDate(v), 350);
  }

  function onKey(e) {
    if (e.key === "Escape" && T.open && e.target.closest && e.target.closest(".pl-list")) { e.preventDefault(); closeFree(T.open); }
  }

  document.addEventListener("visibilitychange", () => { if (T.pane && onScreen() && T.data && T.data.filling && !T.timer) load(true); });

  R.tab("today", {
    init(pane) {
      T.pane = pane;
      T.date = RF.today();
      pane.innerHTML = `<div class="card td">
        <div class="ab-top"><div><h2 id="tdTitle">Relief today</h2><div class="small muted" id="tdSub"></div></div><div class="row td-acts" id="tdActs"></div></div>
        <div class="line td-day"><div class="seg" role="group" aria-label="Which day" id="tdSeg"></div>
          <label class="small muted" for="tdDate">or a date</label><input type="date" id="tdDate" value="${esc(T.date)}"></div>
        <div class="td-counts" id="tdCounts"></div>
        <div id="tdTop" aria-live="polite"></div>
        <div id="tdRows"></div>
        <div class="note">Nothing reaches a relief teacher until someone on the relief team approves it.</div></div>`;
      pane.addEventListener("click", onClick);
      pane.addEventListener("change", onChange);
      pane.addEventListener("keydown", onKey);
      paintDay(); paint();
      load();
    },
    shown() { paintDay(); load(); },
    dirty() { return false; },
  });
})();

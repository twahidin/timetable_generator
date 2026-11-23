"use strict";
/* Today (/relief#today), for the relief team (me.can_team). Every lesson that needs relief on a date (today until another
   is chosen), from /api/relief/today, one row a cover (each part of a split lesson its own row), in time order: the
   periods and times, the class and subject, the room, the absent teacher and whether work is set, the relief teacher with
   who picked them and why, and the state in plain words. Buttons: Approve; Send out (an approved relief not sent out yet:
   nothing reaches its teacher until it is, and one sent out outside school hours goes at the earliest send-out time); Choose
   or Change, which opens the "free then" list (Relief.freeList, drawn as Plan relief's) and approves the one chosen at once; Split (a cover of two periods or
   more that is not approved: the person chooses after which period); Join again (a split lesson none of whose parts is
   approved); Keep (on a request to change, where Approve reads "Approve the new pick"). At the top: Approve all waiting,
   Send out all approved and Fill now. While the server says picks are being made (filling), the day is read again every 3 seconds, only while
   this tab is on screen. After every action the day is read again; a refusal shows the server's sentence beside its row.
   The page opens on the day the server says (no date asked: today, or the next school day once today's cut-off has come), and its
   second day button is the next school day (hours.next_day; "Tomorrow" when it is). An approved row says "Approved · not sent out",
   "Will be sent at 06:45" (held) or what its teacher was sent; a waiting row asked after the cut-off says so; above the rows, a
   line for the reliefs held and, on the next school day past the cut-off, one for what sending out now does.
   Approve sends the name it shows (who), and Approve all the waiting rows it shows ({id, ckey, who} each); Send out and Send
   out all the same, with the approval shown ({id, ckey, who, approved_at}): the server
   refuses or skips a pick that has changed since this page read it ("The pick has changed since you looked…"), and the
   re-read shows the new one. A lesson an approved exam or event stops is shown as "Not happening", with why, out of the
   counts and with no buttons; the teacher of a backup is in school, so the row says which duty they are on. A row is known by its absence id and cover key together (two absent co-teachers of one
   lesson share a cover key).
   While the bot is connected (telegram in the answer; nothing of this shows while it is not): an approved row says what was sent
   on Telegram (told) or that its teacher is not there (linked); Remind on a row, for whoever can be reached once the relief has
   reached them (sentOut: a row's out, or "sent" for an approved row of an answer without it), and Remind all not
   acknowledged, first of the buttons at the top (its place is kept when it is not there, so that no other button moves under the
   pointer), which answers above the rows (both only while the day they were pressed on is shown). While a row says
   "Being sent…" the day is read again every 3 seconds, 5 times at most, only on screen; so it is for a row sent out or reminded here
   (not one only approved), until its teacher is told (a message is made after the step that asks for it). What came of it is said in a live line of its own
   too (tdSaid, not seen). */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day, enc = encodeURIComponent, say = R.say;
  const $ = (s, el = document) => el.querySelector(s);
  const EVERY = 3000, SENT = ["approved", "acknowledged", "change"];
  const READS = 5;   /* how often the day is read again by itself for what is being sent */
  /* top: the lines above the rows ({text, bad, fill}); msg: a line beside a row (row key -> {text, bad}); busy: rows with
     a step on its way; all: Approve all, Fill now or Remind all on its way; open: the row whose "free then" list is open, free: each
     list's answer; split: the row whose split choice is open; bot: a bot was connected when the day was last read; follow: the rows a
     step was taken on whose teacher is not told yet; reads: how often the day was read again for what is being sent; said: what came
     of that; lines, acts: the lines above the rows and the buttons at the top as drawn; date: the day shown, empty until the first
     answer (the page asks for none: the server says which day it opens on); hours: the times of the last answer (its hours) */
  const T = { pane: null, date: "", hours: null, data: null, err: null, seq: 0, loading: false, timer: 0, wait: 0, top: [], msg: new Map(),
              busy: new Set(), all: false, open: null, free: new Map(), split: null, bot: false, follow: new Set(), reads: 0, said: "", lines: "", acts: "" };

  const rid = r => r.id + "\n" + r.ckey;
  const rows = () => (T.data && Array.isArray(T.data.rows) ? T.data.rows : []);
  const findRow = k => rows().find(r => rid(r) === k) || null;
  const keyOf = el => { const row = el && el.closest(".td-row"); return row ? row.dataset.id + "\n" + row.dataset.ckey : null; };
  const rowEl = k => [...T.pane.querySelectorAll(".td-row[data-ckey]")].find(el => keyOf(el) === k) || null;
  const past = () => !!T.date && T.date < RF.today();
  const onScreen = () => R.cur === "today" && document.visibilityState !== "hidden";
  const lessonName = r => `${RF.title(r)} ${RF.periods(r)}`;

  function clock(at) {   /* "07:20" today, else "Mon 23 Nov, 07:20" */
    const s = String(at || ""), d = s.slice(0, 10), t = s.slice(11, 16);
    if (!/^\d{2}:\d{2}$/.test(t)) return "";
    return d === RF.today() ? t : `${day(d)}, ${t}`;
  }

  const sameDay = d => d === T.date;
  function goes(r) {   /* "06:45" on the day shown, else "Tue 13 Oct, 06:45"; "" when the time is not known */
    const s = String(r.goes_at || ""), d = s.slice(0, 10), t = s.slice(11, 16);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || !/^\d{2}:\d{2}$/.test(t)) return "";
    return sameDay(d) ? t : `${day(d)}, ${t}`;
  }
  const heldRows = () => rows().filter(r => r.state === "approved" && sentOut(r) === "held" && goes(r));

  /* ---------------------------------------------------------------- Telegram */
  const bot = () => !!T.data && T.data.telegram === true;
  /* "unsent" | "held" | "sent" (it has reached its teacher) for an approved row, null for the others; a row of an answer without out: as before, "sent" */
  const sentOut = r => (typeof r.out === "string" ? r.out : r.out === null ? null : SENT.includes(r.state) ? "sent" : null);
  const toRemind = () => (bot() ? rows().filter(r => r.state === "approved" && r.linked && sentOut(r) === "sent") : []);   /* approved, reached them, not acknowledged, and can be reached */
  const isWrong = r => r.linked && !!r.told && (r.told.state === "unsure" || r.told.state === "failed");
  const untold = r => !r.told || r.told.state === "dropped";
  const isComing = r => r.state === "approved" && r.linked && sentOut(r) === "sent" && (untold(r) ? T.follow.has(rid(r)) : r.told.state === "queued");   /* being sent, or about to be */
  const again = () => !!T.data && (T.data.filling || (bot() && T.reads < READS && rows().some(isComing)));   /* the day is to be read again by itself */

  function told(r) {   /* an approved row's line: what its teacher was sent */
    const s = r.told ? r.told.state : "", sent = s === "sent" ? `Sent ${clock(r.told.at)}`.trim() : "";
    if (!r.linked) return sent ? `${sent} · not on Telegram now` : "Not on Telegram: they see it in Reliefs I'm covering";
    if (sent) return sent;
    const them = past() ? "" : ": remind them";   /* a date past: nobody can be */
    return s === "unsure" ? `May not have been sent${them}` : s === "queued" ? "Being sent…" : s === "failed" ? `Could not be sent${them}` : past() ? "Not sent" : "Not sent yet";
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

  const by = r => (r.approved && r.approved.by ? `<div class="small muted">by ${esc(r.approved.by)}${clock(r.approved.at) ? `, ${esc(clock(r.approved.at))}` : ""}</div>` : "");

  function chip(r) {
    const c = (text, tone) => `<span class="chip td-chip${tone ? " " + tone : ""}">${esc(text)}</span>`;
    switch (r.state) {
      case "open": return c("No relief teacher yet", "");
      case "waiting": return c("Waiting for you", "st-amber") + (r.asked_after ? `<div class="small muted">${esc(`Asked at ${r.asked_after}, after the cut-off: nobody was pinged`)}</div>` : "");
      case "approved": if (sentOut(r) !== "sent") return c("Approved", "st-sent") + `<div class="small muted">${esc(sentOut(r) === "held" && goes(r) ? `Will be sent at ${goes(r)}` : "Approved · not sent out")}</div>` + by(r);
        return (bot() ? c("Approved", "st-sent") + `<div class="${isWrong(r) ? "td-warn" : "small muted"}">${esc(told(r))}</div>` : c("Approved: they see it in Reliefs I'm covering", "st-sent"))
        + by(r);
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
    if (r.state === "approved" && sentOut(r) === "unsent" && !r.stale) out.push(b("send-out", "Send out", "primary"));
    if (r.state === "change" && r.change && r.change.pick && !r.change.stale) out.push(b("approve", "Approve the new pick", "primary"));
    const listOpen = T.open === k;
    out.push(b(listOpen ? "close" : "free", listOpen ? "Close the list" : r.state === "open" ? "Choose" : "Change", "", ` aria-expanded="${listOpen ? "true" : "false"}"`));
    if (bot() && r.state === "approved" && r.linked && sentOut(r) === "sent") out.push(b("remind", "Remind"));   /* after Change, where the focus goes when Approve is gone */
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
    const t = RF.today(), h = T.hours, tm = RF.addDays(t, 1), next = h ? h.next_day : tm;   /* no hours (an old answer): tomorrow */
    const seg = (d, label) => `<button type="button" data-td="day" data-v="${esc(d)}" class="${T.date === d ? "on" : ""}" aria-pressed="${T.date === d ? "true" : "false"}">${esc(label)}</button>`;
    $("#tdSeg", T.pane).innerHTML = seg(t, "Today") + (next ? seg(next, next === tm ? "Tomorrow" : day(next)) : "");
    const input = $("#tdDate", T.pane);
    if (input && input.value !== T.date && document.activeElement !== input) input.value = T.date;
  }

  function paintHead() {
    const t = RF.today(), d = T.date, live = rows().filter(r => r.state !== "cancelled" && r.state !== "stopped"), away = new Set(live.map(r => r.absent)).size;
    $("#tdTitle", T.pane).textContent = !d || d === t ? "Relief today" : `Relief on ${day(d)}`;
    const when = !d ? "" : d === t ? `Today, ${day(d)}` : d === RF.addDays(t, 1) ? `Tomorrow, ${day(d)}` : day(d), h = T.hours;
    $("#tdSub", T.pane).textContent = [when, T.data ? `${R.plural(away, "teacher")} away` : "", past() ? "past: shown as it was" : "", h && h.past_cut_off ? `After ${h.cut_off} the page opens on the next school day` : ""].filter(Boolean).join(" · ");
    const c = T.data && T.data.counts;
    const counter = (label, n, tone) => `<div class="counter${tone ? " " + tone : ""}"><span class="small muted">${esc(label)}</span><b>${esc(Number(n) || 0)}</b></div>`;
    $("#tdCounts", T.pane).innerHTML = !c ? "" : [counter("Lessons to cover", c.need), counter("Waiting for you", c.waiting, "amber"),
      counter("Approved, not sent out", c.unsent), counter("Approved, not acknowledged", c.approved), counter("Acknowledged", c.acknowledged, "ok"), counter("Asked to change", c.change, "blue"),
      counter("No relief teacher yet", c.open), Number(c.nobody) ? counter("Nobody free then", c.nobody, "bad") : ""].join("");
  }

  function paintActs() {
    const c = (T.data && T.data.counts) || {}, w = Number(c.waiting) || 0, u = Number(c.unsent) || 0, off = !T.data || past() || T.all;
    const all = "Remind all not acknowledged";
    const first = toRemind().length ? `<button type="button" data-td="remind-all"${off || T.busy.size ? " disabled" : ""}>${all}</button> ` : T.bot ? `<span class="td-gap" aria-hidden="true">${all}</span> ` : "";
    const html = `${first}<button type="button" class="primary" data-td="all"${off || !w ? " disabled" : ""}>${esc(w ? `Approve all ${w} waiting` : "Approve all waiting")}</button>
      <button type="button" class="primary" data-td="send-all"${off || !u ? " disabled" : ""}>${esc(u ? `Send out ${u} approved` : "Send out approved")}</button>
      <button type="button" data-td="fill"${off ? " disabled" : ""}>Fill now</button>
      <button type="button" class="small" data-td="reload"${T.loading ? " disabled" : ""}>${T.loading ? "Reading…" : "Refresh"}</button>`;
    $("#tdActs", T.pane).classList.toggle("tg", !!T.bot);   /* room under the buttons only while a bot is connected: Remind all keeps its place */
    if (html === T.acts) return;
    const box = $("#tdActs", T.pane), a = document.activeElement, had = a && box.contains(a) ? a.dataset.td : "";
    box.innerHTML = T.acts = html;
    if (had) focusAct(had);
  }

  function focusAct(...acts) {   /* the first of these buttons at the top that can be pressed */
    const b = acts.map(x => $(`#tdActs [data-td="${x}"]`, T.pane)).find(x => x && !x.disabled);
    if (b) b.focus({ preventScroll: true });
  }

  function paintTop() {
    const h = T.hours, held = heldRows(), lines = [];
    if (h && h.past_cut_off && T.date && T.date === h.next_day) lines.push({ text: `Past the cut-off (${h.cut_off}). Nobody on the team is pinged until the morning message at ${h.morning}. What you send out now is sent at ${h.send_from} on ${day(T.date)}.` });
    if (held.length) {
      const first = held.map(r => String(r.goes_at)).sort()[0], at = first.slice(11, 16), d = first.slice(0, 10), one = held.length === 1;
      lines.push({ text: `${one ? "1 relief sent out: it" : `${held.length} reliefs sent out: they`} will be sent at ${at} on ${day(d)}. You can still change ${one ? "it" : "them"} until then.` });
    }
    lines.push(...T.top);
    lines.forEach((m, i) => { lines[i] = `<p class="td-top">${say(m)}</p>`; });
    if (T.data && T.data.filling) lines.push(`<p class="td-top small td-busy">Being picked… The page reads the day again every 3 seconds.</p>`);
    if (T.err && T.data) lines.push(`<p class="td-top">${say(T.err)} <button type="button" class="small" data-td="reload">Try again</button></p>`);
    if (lines.join("") !== T.lines) $("#tdTop", T.pane).innerHTML = T.lines = lines.join("");   /* a live region: what is there already is not said again */
  }

  function paintSaid() {   /* a live line of its own, so that nothing else is said with it; not there while no bot is connected */
    let el = $("#tdSaid", T.pane);
    if (!bot()) { if (el) el.remove(); return; }
    if (!el) {
      $(".td", T.pane).insertAdjacentHTML("beforeend", `<p class="vh" id="tdSaid" aria-live="polite"></p>`);
      el = $("#tdSaid", T.pane);
    }
    if (el.textContent !== T.said) el.textContent = T.said;
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

  function paint() { paintHead(); paintActs(); paintTop(); paintRows(); paintSaid(); }

  function focusIn(k, sel) { const el = rowEl(k), b = el && el.querySelector(sel); if (b) b.focus(); }

  /* ---------------------------------------------------------------- the server */
  function schedule() {
    clearTimeout(T.timer); T.timer = 0;
    if (T.reads >= READS) T.follow.clear();
    if (again() && onScreen()) T.timer = setTimeout(() => { T.timer = 0; if (onScreen()) load(true); }, EVERY);
  }

  async function load(quiet) {   /* quiet: a fetch while picks are made or something is being sent, drawn again only when something changed */
    const seq = ++T.seq, date = T.date;
    clearTimeout(T.timer); T.timer = 0;
    T.loading = !(quiet && bot());
    T.reads = quiet && !(T.data && T.data.filling) ? T.reads + 1 : 0;
    if (!quiet) paintActs();
    const res = await R.api(`/api/relief/today?${date ? `date=${enc(date)}` : ""}`);
    if (seq !== T.seq) return;
    T.loading = false;
    if (!res.ok) { T.err = { text: res.error, bad: true, status: res.status }; paint(); return; }   /* no more fetches until Try again */
    const same = quiet && !T.err && T.data && JSON.stringify(T.data) === JSON.stringify(res.data);
    const was = new Set(rows().filter(isComing).map(rid));
    T.err = null; T.data = res.data; T.bot = bot();
    if (res.data && res.data.hours && typeof res.data.hours === "object") T.hours = res.data.hours;
    if (!T.date) { T.date = /^\d{4}-\d{2}-\d{2}$/.test(String(res.data && res.data.date)) ? res.data.date : RF.today(); paintDay(); }   /* the day the server opened on */
    T.said = !bot() ? "" : rows().filter(r => was.has(rid(r)) && r.state === "approved" && !isComing(r)).map(r => `${r.pick ? `${r.pick.who}, ` : ""}${lessonName(r)}: ${told(r)}`).join(". ");
    for (const k of [...T.follow]) { const r = findRow(k); if (!r || r.state !== "approved" || sentOut(r) !== "sent" || !untold(r)) T.follow.delete(k); }   /* held: it goes later, nothing to wait for */
    for (const [k, m] of [...T.msg]) if (!findRow(k)) { T.msg.delete(k); T.top.push(m); }   /* its row is gone (split, joined): said above the rows */
    const live = k => { const r = findRow(k); return r && r.state !== "cancelled" && r.state !== "stopped"; };
    if (T.open && !live(T.open)) T.open = null;
    if (T.split && !live(T.split)) T.split = null;
    if (!T.data.filling) T.top = T.top.filter(m => !m.fill);
    if (same) { paintActs(); paintSaid(); } else { paintDay(); paint(); }
    schedule();
  }

  async function act(k, method, url, body, done, here, follow = true) {   /* one step on one row; then the day is read again. done(answer): what is said, or {text, bad}; here: said only while the day it was asked on is shown; follow: its teacher is to be told now (not after Approve or Change) */
    const f = focusNow(), date = T.date;
    T.busy.add(k); T.msg.delete(k); if (bot()) paintActs(); paintRows();
    const res = await R.api(url, R.json(method, body));
    T.busy.delete(k);
    if (here && T.date !== date) { paint(); return; }
    if (!res.ok) T.msg.set(k, { text: res.error, bad: true, status: res.status });
    else { const m = done ? done(res.data) : ""; if (m) T.msg.set(k, typeof m === "string" ? { text: m, bad: false } : m); if (follow) T.follow.add(k); }
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
      return `${name} chosen and approved: press Send out to tell them.`;
    }, false, false);
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
      saySkipped(before, skipped);
    }
    await load();
  }

  function saySkipped(before, skipped) {   /* a line above the rows for each skipped one, and its sentence beside its row: matched by its absence id and cover key */
    for (const s of skipped) {
      const r = before.find(o => o.id === s.id && o.ckey === s.ckey);
      T.top.push({ text: `${r ? `${lessonName(r)}, ${s.name}` : s.name}: ${s.why}`, bad: true });
      if (r) T.msg.set(rid(r), { text: s.why, bad: true });
    }
  }

  async function sendAll() {   /* Send out all approved: the approved rows not sent out that the page shows, as it shows them */
    if (T.all || !T.data) return;
    const before = rows(), date = T.date, list = before.filter(o => o.state === "approved" && sentOut(o) === "unsent" && o.pick && o.pick.who);
    const covers = list.map(o => ({ id: o.id, ckey: o.ckey, who: o.pick.who, approved_at: (o.approved && o.approved.at) || null }));
    T.all = true; T.top = []; paint();
    const res = await R.api("/api/relief/today/send-out", R.json("POST", { date, covers }));
    T.all = false;
    if (!res.ok) T.top = [{ text: res.error, bad: true, status: res.status }];
    else {
      const got = res.data || {}, skipped = Array.isArray(got.skipped) ? got.skipped : [], at = String(got.at || "").slice(11, 16);
      covers.forEach(o => T.follow.add(rid(o)));
      T.top = [{ text: `Sent out ${R.plural(Number(got.sent) || 0, "relief")} for ${day(date)}.${/^\d{2}:\d{2}$/.test(at) ? ` They will be sent at ${at}.` : ""}`, bad: false }];
      saySkipped(before, skipped);
    }
    await load();
  }

  /* ---- Remind: the server sends the reliefs again that still wait to be acknowledged, and says why not for the others */
  const asked = list => ({ date: T.date, covers: list.map(r => ({ id: r.id, ckey: r.ckey })) });
  const notSent = got => (got && Array.isArray(got.skipped) ? got.skipped : []).filter(s => s && s.why);

  function remind(k, r) {
    act(k, "POST", "/api/relief/today/remind", asked([r]), got => {
      if (got && Number(got.sent)) return "Reminded.";
      const s = notSent(got)[0];
      return s ? { text: s.why, bad: true } : "";
    }, true);
  }

  async function remindAll() {
    const list = toRemind(), date = T.date;
    T.all = true; T.top = []; paint();
    const res = await R.api("/api/relief/today/remind", R.json("POST", asked(list)));
    T.all = false;
    if (T.date !== date) { paint(); return; }   /* another day is shown: nothing of it is said there */
    if (!res.ok) T.top = [{ text: res.error, bad: true, status: res.status }];
    else {
      list.forEach(r => T.follow.add(rid(r)));
      const n = Number(res.data && res.data.sent) || 0;
      T.top = n ? [{ text: `Reminded ${n}.`, bad: false }] : [];
      for (const s of notSent(res.data)) if (s.name || !T.top.some(m => m.text === s.why)) T.top.push({ text: s.name ? `${s.name}: ${s.why}` : s.why, bad: true });   /* a reason with no name is said once */
      if (!T.top.length) T.top = [{ text: "Nobody to remind.", bad: true }];
    }
    await load();
    if (R.cur === "today" && (!document.activeElement || document.activeElement === document.body)) focusAct("remind-all", "reload");
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
    T.date = v; T.data = null; T.err = null; T.top = []; T.msg.clear(); T.open = null; T.free.clear(); T.split = null; T.follow.clear();
    paintDay(); paint(); load();
  }

  /* ---------------------------------------------------------------- events */
  function onClick(e) {
    const b = e.target.closest("button[data-td],button[data-pl]");
    if (!b || b.disabled || !T.pane.contains(b)) return;
    const a = b.dataset.td || "pl-" + b.dataset.pl;
    switch (a) {
      case "day": setDate(b.dataset.v); return;
      case "reload": T.err = null; load(); return;
      case "all": approveAll(); return;
      case "send-all": sendAll(); return;
      case "fill": fillNow(); return;
      case "remind-all": remindAll(); return;
    }
    const k = keyOf(b), r = k && findRow(k);
    if (!r) return;
    const cover = `/api/relief/absences/${enc(r.id)}/covers/${enc(r.ckey)}`, lesson = `/api/relief/absences/${enc(r.id)}/lessons/${enc(r.key)}`;
    switch (a) {
      case "approve": {
        const who = (r.state === "change" ? r.change && r.change.pick && r.change.pick.who : r.pick && r.pick.who) || "";
        act(k, "POST", `${cover}/approve`, { who }, () => `${who} approved: press Send out to tell them.`, false, false);   /* the name shown: refused if it changed */
        return;
      }
      case "send-out":   /* the relief and the approval shown: refused if either changed */
        act(k, "POST", `${cover}/send-out`, { who: (r.pick && r.pick.who) || "", approved_at: (r.approved && r.approved.at) || null }, () => "Sent out.");
        return;
      case "free": openFree(k); return;
      case "close": case "pl-close": closeFree(k); return;
      case "pl-choose": choose(k, b.dataset.name || ""); return;
      case "pl-teaching": { const s = T.free.get(k); if (s) { s.teaching = !s.teaching; paintRows(); focusIn(k, '[data-pl="teaching"]'); } return; }
      case "pl-duty": { const s = T.free.get(k); if (s) { s.duty = !s.duty; paintRows(); focusIn(k, '[data-pl="duty"]'); } return; }
      case "remind": remind(k, r); return;
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

  document.addEventListener("visibilitychange", () => { if (T.pane && onScreen() && again() && !T.timer) load(true); });

  R.tab("today", {
    init(pane) {
      T.pane = pane;
      T.date = "";
      pane.innerHTML = `<div class="card td">
        <div class="ab-top"><div><h2 id="tdTitle">Relief today</h2><div class="small muted" id="tdSub"></div></div><div class="row td-acts" id="tdActs"></div></div>
        <div class="line td-day"><div class="seg" role="group" aria-label="Which day" id="tdSeg"></div>
          <label class="small muted" for="tdDate">or a date</label><input type="date" id="tdDate" value=""></div>
        <div class="td-counts" id="tdCounts"></div>
        <div id="tdTop" aria-live="polite"></div>
        <div id="tdRows"></div>
        <div class="note">Nothing reaches a relief teacher until someone on the relief team approves it and sends it out.</div></div>`;
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

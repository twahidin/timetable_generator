"use strict";
/* Plan relief (/relief#plan), for management and the relief team (me.can_plan). The form plans relief for a colleague:
   the dates, the absent teacher, the whole day or some periods, a reason and remarks for the relief team; then that
   teacher's lessons, each with its work box (optional here: the absent teacher is asked to set it) and "Choose a relief
   teacher", which opens that lesson's "free then" list from /api/relief/free. Choosing fills the lesson; a lesson left
   open goes to the relief team. Planned by me lists what this person planned; Open shows an absence as the same card as
   My absences (R.absences), with Choose on its open lessons, and Download gives the relief sheet for a range of dates.
   The form is kept in P and the lessons' work by ReliefForm; the "free then" lists are kept in F. A refusal shows the
   server's sentence and keeps everything typed and chosen. The list itself is drawn by Relief.freeList, which Today's
   Change (relief-today.js) uses too. */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day, enc = encodeURIComponent, say = R.say;
  const $ = (s, el = document) => el.querySelector(s);
  const REASONS = ["Medical", "Child sick", "Course", "Other"];
  const P = { pane: null, day: "today", picked: [], teacher: "", people: null, perr: null, away: "whole", from: null, to: null,
              reason: "", text: "", remarks: "", periods: [], readFor: "", lessons: [], lerr: null, loading: false, seq: 0,
              chosen: new Map(), busy: false, msg: null, dirty: false, label: "" };
  /* "free then" lists, one open at a time: in the form the list of "new\n{absent}\n{lesson key}", on an opened absence
     "{id}\n{lesson key}"; st holds each list's answer, msg a refused choice on an opened absence */
  const F = { open: null, st: new Map(), msg: new Map() };
  const Pl = { open: null, msg: null, dl: null };   /* Planned by me: the absence opened, a line about opening it, the download's line */

  const who = n => n === R.me.name ? "you" : n;
  const hasWork = x => { const w = x.work || {}; return !!(w.text || w.link || (w.files || []).length); };
  const chosenKey = key => P.teacher + "\n" + key;
  const formCtx = key => "new\n" + P.teacher + "\n" + key;
  const cardCtx = (id, key) => id + "\n" + key;
  const listEl = () => $("#plLessonList", P.pane);

  /* ---------------------------------------------------------------- Planned by me: the absence cards */
  const view = R.absences({
    load: () => R.api("/api/relief/absences/planned").then(r => r.ok ? { ok: true, status: r.status, data: r.data.absences || [] } : r),
    show: r => r.id === Pl.open,
    empty: "",
    side: (r, x) => mayChoose(x) ? sideHTML(cardCtx(r.id, x.key), x.planned || "") : plainSide(x),
    extra: (r, x) => mayChoose(x) ? `<div class="pl-free">${freeArea(cardCtx(r.id, x.key))}</div>` : "",
    painted: paintPlanned,
  });

  /* a lesson gone from the timetable, stopped by an exam or event, or past, keeps what it has; a lesson with a cover approved, or split, is the relief team's, unless it is still this head's own choice; the server's may_choose (also false once the lesson has started) decides when it is sent */
  const mayChoose = x => !x.changed && !x.stopped && x.date >= RF.today() && (typeof x.may_choose === "boolean" ? x.may_choose : !R.approvedOf(x).length) && (x.covers || []).length < 2;
  const plainSide = x => R.reliefLines(x);

  /* ---------------------------------------------------------------- the "free then" list */
  function info(ctx) {   /* -> {x: the lesson, absent, chosen (a name or ""), r: the absence when it is saved} or null */
    if (!ctx) return null;
    const parts = ctx.split("\n");
    if (parts[0] === "new") {
      const key = parts.slice(2).join("\n"), x = parts[1] === P.teacher ? P.lessons.find(l => l.key === key) : null;
      return x ? { x, absent: P.teacher, chosen: P.chosen.get(chosenKey(key)) || "", r: null } : null;
    }
    const r = view.find(parts[0]), key = parts.slice(1).join("\n"), x = r && (r.lessons || []).find(l => l.key === key);
    return x ? { x, absent: r.teacher, chosen: x.planned || "", r } : null;
  }

  function ctxOf(el) {   /* the list an element belongs to: by its lesson row, and the absence card around it */
    const row = el && el.closest(".rl"), card = row && row.closest(".ab");
    if (!row) return null;
    return card ? cardCtx(card.dataset.id, row.dataset.key) : formCtx(row.dataset.key);
  }

  const rowOf = ctx => [...P.pane.querySelectorAll(".rl")].find(r => ctxOf(r) === ctx) || null;

  function sideHTML(ctx, chosen) {
    const on = F.open === ctx, busy = !!(F.st.get(ctx) || {}).busy;
    const toggle = `<button type="button" class="small" data-pl="${on ? "close" : "free"}" aria-expanded="${on ? "true" : "false"}">${on ? "Close the list" : chosen ? "Change" : "Choose a relief teacher"}</button>`;
    if (!chosen) return toggle;
    const lead = ctx.startsWith("new\n") ? "Relief:" : "Planned:";   /* on a saved absence it waits for the relief team */
    return `${lead} <span class="chip st-ok pl-chosen">${esc(chosen)}<button type="button" data-pl="clear" title="Take ${esc(chosen)} off" aria-label="Take ${esc(chosen)} off" ${busy ? "disabled" : ""}>✕</button></span>${lead === "Planned:" ? ` <span class="small muted">waiting for the relief team</span>` : ""} ${toggle}`;
  }

  function alsoChosen(x) {   /* in the form: who is chosen for another lesson that day -> that lesson's name */
    const list = listEl(), m = new Map();
    for (const o of P.lessons) {
      if (o.key === x.key || o.date !== x.date || !RF.needed(list, o.key)) continue;
      const name = P.chosen.get(chosenKey(o.key));
      if (name && !m.has(name)) m.set(name, RF.title(o));
    }
    return m;
  }

  function freeArea(ctx) {
    const m = F.msg.get(ctx);
    return (m ? `<p class="pl-msg">${say(m)}</p>` : "") + freeHTML(ctx);
  }

  function freeHTML(ctx) {
    const inf = info(ctx);
    if (F.open !== ctx || !inf) return "";
    const s = F.st.get(ctx) || {}, x = inf.x, close = `<button type="button" class="small" data-pl="close">Close the list</button>`;
    if (s.loading) return `<div class="pl-list"><p class="small muted">Finding who is free…</p></div>`;
    if (s.err) return `<div class="pl-list"><p>${say(s.err)}</p><div class="bar"><button type="button" class="small" data-pl="free">Try again</button>${close}</div></div>`;
    return freeList({ data: s.data, x, chosen: inf.chosen, also: inf.r ? new Map() : alsoChosen(x), busy: s.busy, teaching: s.teaching, duty: s.duty });
  }

  /* the "free then" list as HTML, from a free route's answer; Today's Change (relief-today.js) draws the same list through
     Relief.freeList. o: data ({groups, teaching}), x (the lesson, or a cover with its date: classes, subject, group, p, n,
     date), chosen (the name chosen now, or ""), also (Map: name -> the lesson they are chosen for here), busy (Choose
     disabled), teaching (the names teaching then shown), mark (the chosen person's chip, "Chosen" when left out). Its
     buttons carry data-pl: "choose" with data-name, "teaching" and "close". */
  function freeList(o) {
    const d = o.data || {}, x = o.x, groups = Array.isArray(d.groups) ? d.groups : [], teaching = Array.isArray(d.teaching) ? d.teaching : [], onDuty = Array.isArray(d.busy) ? d.busy : [];
    const n = groups.reduce((a, g) => a + (g.people || []).length, 0), also = o.also || new Map(), close = `<button type="button" class="small" data-pl="close">Close the list</button>`;
    const lead = groups.length && (groups[0].people || []).length && !groups[0].people[0].over ? groups[0].people[0].name : "";
    const person = p => {
      const what = [(p.depts || []).join(", "), (p.subjects || []).join(", ")].filter(Boolean).join(": ");
      const marks = (p.marks || []).concat(also.has(p.name) ? [`chosen for ${also.get(p.name)} here`] : []);
      const on = !!o.chosen && p.name === o.chosen;
      const pick = on ? `<span class="chip st-ok">${esc(o.mark || "Chosen")}</span>`
        : `<button type="button" class="small${p.name === lead ? " primary" : ""}" data-pl="choose" data-name="${esc(p.name)}" ${o.busy ? "disabled" : ""}>Choose</button>`;
      return `<div class="cand${p.over ? " dim" : ""}${on ? " on" : ""}"><div class="cand-who"><b>${esc(p.name)}</b>${p.fat ? ` <span class="fat">Flexi Adjunct</span>` : ""}${what ? ` <span class="why">${esc(what)}</span>` : ""}${marks.map(t => ` <span class="mark">${esc(t)}</span>`).join("")}</div>
        <span class="small cand-n">week ${esc(p.week)}</span><span class="small muted cand-n">${esc(p.today)} relief today</span>${pick}</div>`;
    };
    const fold = teaching.length ? ` · <button type="button" class="linkish" data-pl="teaching" aria-expanded="${o.teaching ? "true" : "false"}">${o.teaching ? "Hide" : "Show"} the ${teaching.length} teaching then</button>` : "";
    const dutyFold = onDuty.length ? ` · <button type="button" class="linkish" data-pl="duty" aria-expanded="${o.duty ? "true" : "false"}">${o.duty ? "Hide" : "Show"} the ${onDuty.length} on an exam duty or at an event then</button>` : "";
    return `<div class="pl-list" role="group" aria-label="${esc(`Who is free for ${RF.title(x)}`)}">
      <div class="small muted">Free at ${esc(RF.periods(x))} on ${esc(day(x.date))}: ${esc(R.plural(n, "teacher"))}${fold}${dutyFold}</div>
      ${o.teaching && teaching.length ? `<div class="small pl-teaching">${esc(teaching.join(", "))}</div>` : ""}
      ${o.duty && onDuty.length ? `<div class="small pl-teaching">${esc(onDuty.map(b => `${b.name} (${b.why})`).join(", "))}</div>` : ""}
      ${n ? groups.map(g => `<div class="tier">${esc(g.title)}</div>${(g.people || []).map(person).join("")}`).join("") : `<p class="small muted">No one is free then.</p>`}
      <div class="small muted pl-foot">"week" = teaching periods plus relief periods so far this week, lightest first in each group. A dimmed teacher is over a limit and can still be chosen.</div>
      <div class="bar">${close}</div></div>`;
  }
  R.freeList = freeList;

  function repaint(ctx, withSide = true) {   /* one lesson's choice and list, in place: what is being typed elsewhere keeps its place */
    const row = rowOf(ctx), inf = info(ctx);
    if (!row || !inf) return;
    const side = row.querySelector(".rf-side"), area = row.querySelector(".pl-free");
    if (withSide && side) side.innerHTML = sideHTML(ctx, inf.chosen);
    if (area) area.innerHTML = freeArea(ctx);
  }

  function focusIn(ctx, sel) { const row = rowOf(ctx), el = row && row.querySelector(sel); if (el) el.focus(); }

  async function openFree(ctx) {
    const inf = info(ctx);
    if (!inf) return;
    const was = F.open, s = { loading: true, err: null, data: null, teaching: false, busy: false };
    F.open = ctx; F.st.set(ctx, s); F.msg.delete(ctx);
    if (was && was !== ctx) repaint(was);
    repaint(ctx);
    focusIn(ctx, '.rf-side [data-pl="close"]');
    const r = await R.api(`/api/relief/free?absent=${enc(inf.absent)}&key=${enc(inf.x.key)}`);
    if (F.st.get(ctx) !== s) return;   /* opened again since */
    s.loading = false;
    if (r.ok) s.data = r.data; else s.err = { text: r.error, bad: true, status: r.status };
    repaint(ctx, false);
  }

  function closeFree() {
    const ctx = F.open;
    F.open = null;
    if (ctx) { repaint(ctx); focusIn(ctx, '.rf-side [data-pl="free"]'); }
  }

  async function choose(ctx, name) {   /* name "" takes the choice off */
    const inf = info(ctx);
    if (!inf) return;
    if (!inf.r) {   /* the form: kept here until Send */
      const key = inf.x.key;
      if (name) P.chosen.set(chosenKey(key), name); else P.chosen.delete(chosenKey(key));
      F.open = null; changed(); repaint(ctx); paintSend();
      focusIn(ctx, '.rf-side [data-pl="free"]');
      return;
    }
    const s = F.st.get(ctx) || {};
    F.st.set(ctx, s);
    s.busy = true; F.msg.delete(ctx); repaint(ctx);
    const res = await R.api(`/api/relief/absences/${enc(inf.r.id)}/lessons/${enc(inf.x.key)}/relief`, R.json("PUT", { relief: name || null }));
    s.busy = false;
    if (!res.ok) { F.msg.set(ctx, { text: res.error, bad: true, status: res.status }); repaint(ctx); return; }
    view.put(res.data);
    if (F.open === ctx) F.open = null;
    view.paint(inf.r.id);
    focusIn(ctx, '.rf-side [data-pl="free"]');
  }

  /* ---------------------------------------------------------------- the form */
  function dates() {
    const t = RF.today();
    if (P.day === "today") return [t];
    if (P.day === "tomorrow") return [RF.addDays(t, 1)];
    return P.picked.slice().sort();
  }

  const someWaiting = () => P.away === "some" && (P.from === null || P.to === null);

  function planBlock() {   /* why Send cannot be pressed yet, in a line; "" when it can */
    if (!dates().length) return "Choose the dates first.";
    if (!P.teacher) return "Choose the absent teacher first.";
    if (someWaiting()) return "Choose the periods first: from and to.";
    if (P.lerr) return "Nothing can be sent until the lessons are read.";
    return "";
  }

  function counts() {   /* [chosen, for the relief team] over the listed lessons to cover */
    const list = listEl();
    let k = 0, m = 0;
    if (P.loading || P.lerr) return [0, 0];
    for (const x of P.lessons) {
      if (!RF.needed(list, x.key)) continue;
      if (P.chosen.get(chosenKey(x.key))) k++; else m++;
    }
    return [k, m];
  }

  const sendLabel = () => { const [k, m] = counts(); return `Send: ${k} chosen, ${m} for the relief team`; };

  const segBtn = (what, v, on, label) => `<button type="button" data-pl="${what}" data-v="${esc(v)}" class="${on ? "on" : ""}" aria-pressed="${on ? "true" : "false"}">${esc(label)}</button>`;

  function paintDay() {
    const t = RF.today(), box = $("#plDay", P.pane);
    let under;
    if (P.day === "today") under = `<div class="small muted under">${esc(day(t))}</div>`;
    else if (P.day === "tomorrow") under = `<div class="small muted under">${esc(day(RF.addDays(t, 1)))}</div>`;
    else {
      const full = P.picked.length >= 10;
      under = `<div class="line"><input type="date" id="plDate" min="${esc(t)}" ${full ? "disabled" : ""} aria-label="A date to add"><button type="button" class="small" data-pl="adddate" ${full ? "disabled" : ""}>Add this date</button>
        <span class="small muted">${full ? "That is 10 dates, the most at one time." : "Up to 10 dates."}</span></div>
        <div class="chiprow">${P.picked.length ? P.picked.map(d => `<span class="chip dchip">${esc(day(d))}<button type="button" data-pl="undate" data-v="${esc(d)}" title="Take this date off" aria-label="Take ${esc(day(d))} off">✕</button></span>`).join("") : `<span class="small muted">No dates yet.</span>`}</div>`;
    }
    box.innerHTML = `<div class="seg" role="group" aria-label="Which day">${segBtn("day", "today", P.day === "today", "Today")}${segBtn("day", "tomorrow", P.day === "tomorrow", "Tomorrow")}${segBtn("day", "pick", P.day === "pick", "Pick dates")}</div>${under}`;
  }

  function paintWho() {
    const box = $("#plWho", P.pane);
    if (!P.people) { box.innerHTML = P.perr ? `${say(P.perr)} <button type="button" class="small" data-pl="people">Try again</button>` : `<span class="small muted">Loading…</span>`; return; }
    RF.person(box, { people: P.people, value: P.teacher, exclude: [R.me.name], label: "Find the absent teacher", onPick: pickTeacher });
  }

  function pickTeacher(name) {
    if (name === P.teacher) return;
    if (F.open && F.open.startsWith("new\n")) F.open = null;
    P.teacher = name;
    changed(); paintLessonsLabel(); reread();
  }

  function paintAway() {
    const box = $("#plAway", P.pane);
    let under = "";
    if (P.away === "some") {
      if (!P.teacher) under = `<div class="small muted under">Choose the absent teacher first.</div>`;
      else if (!dates().length) under = `<div class="small muted under">Choose the dates first.</div>`;
      else if (P.periods.length) under = RF.periodSelects("pl", P.periods, P.from, P.to);
      else if (P.loading) under = `<div class="small muted under">Reading the periods…</div>`;
      else if (!P.lerr) under = `<div class="small muted under">The published timetable has no periods to choose.</div>`;
    }
    const had = box.contains(document.activeElement) ? document.activeElement.dataset.per : "";   /* the selects are drawn again when the lessons come back */
    box.innerHTML = `<div class="seg" role="group" aria-label="Away for">${segBtn("away", "whole", P.away === "whole", "Whole day")}${segBtn("away", "some", P.away === "some", "Some periods")}</div>${under}`;
    if (had) { const el = $(`[data-per="${had}"]`, box); if (el) el.focus(); }
  }

  function paintReason() {
    $("#plReason", P.pane).innerHTML = `<div class="seg" role="group" aria-label="Reason">${REASONS.map(x => segBtn("reason", x, P.reason === x, x)).join("")}</div>`
      + (P.reason === "Other" ? `<div><input id="plWhy" class="reason-line" maxlength="200" value="${esc(P.text)}" placeholder="Say why in a line" aria-label="The reason, in a line" autocomplete="off"></div>` : "");
  }

  function paintLessonsLabel() {
    $("#plLessonsLabel", P.pane).textContent = P.teacher ? `${P.teacher}'s lessons then, from the published timetable` : "The lessons then, from the published timetable";
  }

  function paintLessons() {
    const sayBox = $("#plLessonsSay", P.pane), list = listEl();
    const empty = P.loading || P.lerr ? "" : !P.teacher ? "Choose the absent teacher first." : !dates().length ? "Choose the dates first."
      : someWaiting() ? "Choose the periods first." : `${P.teacher} has no lessons then.`;
    sayBox.innerHTML = P.lerr ? `<p>${say(P.lerr)}${P.lerr.status === 0 ? ` <button type="button" class="small" data-pl="reread">Try again</button>` : ""}</p>` : P.loading ? `<p class="small muted">Reading the lessons…</p>` : "";
    const shown = P.lerr ? [] : P.lessons, stopped = shown.filter(x => x.stopped), duties = P.lerr ? {} : P.duties || {};
    const lines = Object.keys(duties).sort().flatMap(d => (duties[d] || []).map(u => `<p class="small">${esc(`${day(d)}: ${u.what}, ${u.start}–${u.end}: ${u.replaces} replaces them.`)}</p>`));
    $("#plStopped", P.pane).innerHTML = stopped.map(x => `<p class="small muted"><b>${esc(RF.title(x))}</b> · ${esc(RF.when(x))}: ${esc("Not happening: " + x.stopped + " · no relief needed")}</p>`).join("") + lines.join("");
    RF.lessons(list, shown.filter(x => !x.stopped), {   /* with a refusal, nothing is listed (and nothing is sent), but what was typed is kept */
      empty: stopped.length || lines.length ? "" : empty, workLabel: `Work for this lesson (optional: ${P.teacher || "the absent teacher"} is asked to set it)`, onChange: lessonEdited,
      side: x => RF.needed(list, x.key) ? sideHTML(formCtx(x.key), P.chosen.get(chosenKey(x.key)) || "") : "",
      extra: x => RF.needed(list, x.key) ? `<div class="pl-free">${freeArea(formCtx(x.key))}</div>` : "",
    });
  }

  function paintSend() {
    const box = $("#plSend", P.pane), why = P.busy || P.loading ? "" : planBlock(), line = P.msg && !P.msg.bad ? "" : why;   /* beside "Sent.", no reason line */
    P.label = sendLabel();
    const sent = P.msg && P.msg.sent ? ` <button type="button" class="small" data-pl="open" data-id="${esc(P.msg.sent)}">Open it</button>` : "";
    box.innerHTML = `<div class="bar"><button type="button" class="primary" data-pl="send" ${P.busy || P.loading || why ? "disabled" : ""}>${esc(P.busy ? "Sending…" : P.label)}</button>${line ? `<span class="small muted">${esc(line)}</span>` : ""}${say(P.msg)}${sent}</div>
      ${P.msg && P.msg.files ? `<div class="bar">${say(P.msg.files)}</div>` : ""}
      ${P.teacher ? `<div class="note">${esc(P.teacher)} will see this in their Relief page and is asked to acknowledge and set work.</div>` : ""}`;
  }

  function changed() {
    P.dirty = true;
    if (P.msg && !P.busy) { P.msg = null; paintSend(); }
  }

  function lessonEdited() {   /* ReliefForm: typing, files, or "Ask for cover anyway" / "No relief needed", which change the counts */
    changed();
    if (!P.busy && sendLabel() !== P.label) paintSend();
  }

  async function reread() {
    const ds = dates(), key = P.teacher + "\n" + ds.join(","), seq = ++P.seq, some = P.away === "some", both = P.from !== null && P.to !== null;
    if (!P.teacher || !ds.length) {
      P.readFor = ""; P.lessons = []; P.lerr = null; P.loading = false;
      paintAway(); paintLessons(); paintSend(); return;
    }
    P.loading = true; P.lerr = null;
    if (P.readFor !== key) P.lessons = [];   /* another teacher or other dates: the old lessons are not shown while the new ones are read */
    paintAway(); paintLessons(); paintSend();
    const r = await R.api(`/api/relief/lessons?teacher=${enc(P.teacher)}&dates=${enc(ds.join(","))}${some && both ? `&from=${P.from}&to=${P.to}` : ""}`);
    if (seq !== P.seq) return;
    P.loading = false;
    if (!r.ok) { P.readFor = ""; P.lessons = []; P.lerr = { text: r.error, bad: true, status: r.status }; paintAway(); paintLessons(); paintSend(); return; }
    if (Array.isArray(r.data.periods)) P.periods = r.data.periods;
    P.readFor = key;
    P.duties = r.data.duties || {};
    P.lessons = some && !both ? [] : r.data.lessons || [];   /* "Some periods" lists nothing until from and to are chosen */
    paintAway(); paintLessons(); paintSend();
  }

  async function loadPeople() {
    P.perr = null; paintWho();
    const r = await R.people();
    if (!r.ok) { P.perr = { text: r.error, bad: true, status: r.status }; paintWho(); return; }
    P.people = r.data || [];
    paintWho();
  }

  function addDate() {
    const el = $("#plDate", P.pane), v = el && el.value;
    if (!v || !/^\d{4}-\d{2}-\d{2}$/.test(v)) { if (el) el.focus(); return; }
    if (!P.picked.includes(v) && P.picked.length < 10) P.picked.push(v);
    P.picked.sort(); changed(); paintDay(); reread();
    const again = $("#plDate", P.pane); if (again && !again.disabled) again.focus();
  }

  async function send() {
    if (P.busy || P.loading || planBlock()) return;
    const list = listEl(), teacher = P.teacher;
    P.busy = true; P.msg = null; paintSend();
    const lessons = RF.read(list).map(l => {
      const name = RF.needed(list, l.key) ? P.chosen.get(chosenKey(l.key)) : "";
      return name ? Object.assign(l, { relief: name }) : l;
    });
    const body = { teacher, dates: dates(), periods: P.away === "some" ? [P.from, P.to] : null, reason: P.reason,
                   reason_text: P.reason === "Other" ? P.text.trim() : "", remarks: P.remarks.trim(), reporting_officer: "", lessons };
    const res = await R.api("/api/relief/absences", R.json("POST", body));
    if (!res.ok) { P.busy = false; P.msg = { text: res.error, bad: true, status: res.status }; paintSend(); return; }
    const failed = await R.attach(res.data, list);
    Object.assign(P, { day: "today", picked: [], teacher: "", away: "whole", from: null, to: null, reason: "", text: "", remarks: "",
                       readFor: "", lessons: [], lerr: null, busy: false, dirty: false });
    P.chosen.clear();
    for (const k of [...F.st.keys()]) if (k.startsWith("new\n")) F.st.delete(k);
    if (F.open && F.open.startsWith("new\n")) F.open = null;
    P.msg = { text: `Sent. It is in Planned by me, below.`, bad: false, sent: res.data.id,
              files: failed.length ? { text: `Not added: ${failed.join(" ")} Add them when you open it.`, bad: true } : null };
    RF.reset(list);
    $("#plRemarks", P.pane).value = "";
    paintDay(); paintWho(); paintAway(); paintReason(); paintLessonsLabel(); paintLessons(); paintSend();
    view.put(res.data); paintPlanned();
    view.load();
  }

  /* ---------------------------------------------------------------- Planned by me */
  function plannedRow(r) {
    const cover = (r.lessons || []).filter(x => x.needed && !x.stopped), k = cover.filter(x => R.approvedOf(x).length || (x.covers || []).some(c => c.planned)).length;
    const changedNow = !r.cancelled && (r.lessons || []).some(x => x.changed && x.date >= RF.today());
    let chip;
    if (r.cancelled) chip = `<span class="chip st-off">${esc(`Cancelled${r.cancelled.by === "app" ? "" : ` by ${who(r.cancelled.by)}`}: ${r.cancelled.why}`)}</span>`;
    else if (r.acknowledged) chip = `<span class="chip st-ok">✓ acknowledged${cover.length && cover.every(hasWork) ? ", work set" : ""}</span>`;
    else chip = `<span class="chip st-amber">not acknowledged yet</span>`;
    return `<tr class="${r.cancelled ? "off" : ""}">
      <td><b>${esc(RF.dayRuns(r.dates))}</b><div class="small muted">${esc(R.span(r))}</div></td>
      <td>${esc(r.teacher)}<div class="small muted">${esc(R.reason(r))}</div></td>
      <td>${cover.length ? esc(`${k} chosen · ${cover.length - k} open`) : `<span class="muted">none to cover</span>`}${changedNow ? `<div class="small pl-changed">A lesson has changed since this was planned</div>` : ""}</td>
      <td>${chip}</td>
      <td class="act"><button type="button" class="small" data-pl="open" data-id="${esc(r.id)}" aria-label="Open the absence of ${esc(r.teacher)}">Open</button></td></tr>`;
  }

  function paintPlanned() {
    if (!P.pane) return;
    const list = view.list(), err = view.error(), box = $("#plPlannedList", P.pane), one = $("#plPlannedOne", P.pane), detail = $("#plDetail", P.pane);
    const opened = !!(Pl.open && list && list.some(r => r.id === Pl.open));
    box.hidden = opened; one.hidden = !opened; detail.hidden = !opened;
    $("#plOneMsg", P.pane).innerHTML = opened ? say(Pl.msg) : "";
    if (opened) return;
    if (!list) {
      box.innerHTML = err ? `<p>${say(err)} <button type="button" class="small" data-pl="replanned">Try again</button></p>` : `<p class="muted small">Loading…</p>`;
      return;
    }
    const top = (err ? `<p>${say(err)}</p>` : "") + (Pl.msg ? `<p>${say(Pl.msg)}</p>` : "");
    box.innerHTML = top + (list.length
      ? `<div class="tablewrap"><table class="rtable"><thead><tr><th>Date</th><th>For</th><th>Lessons</th><th>Absent teacher</th><th><span class="vh">Open</span></th></tr></thead><tbody>${list.map(plannedRow).join("")}</tbody></table></div>`
      : `<p class="muted small">Nothing planned by you yet. What you send above shows here.</p>`);
  }

  async function openOne(id) {
    if (!id) return;
    Pl.open = id; Pl.msg = null;
    if (F.open && !F.open.startsWith("new\n")) F.open = null;
    const r = await R.api(`/api/relief/absences/${enc(id)}`);   /* the absence as it is now */
    if (Pl.open !== id) return;
    if (r.ok) view.put(r.data);
    else if (view.find(id)) Pl.msg = { text: r.error, bad: true, status: r.status };   /* shown as last read */
    else { Pl.open = null; Pl.msg = { text: r.error, bad: true, status: r.status }; }
    view.paintAll();
    const card = $("#plPlanned", P.pane);
    if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
    const back = $("#plBack", P.pane); if (back && Pl.open) back.focus({ preventScroll: true });
  }

  function back() {
    const id = Pl.open;
    Pl.open = null; Pl.msg = null;
    if (F.open && !F.open.startsWith("new\n")) F.open = null;
    view.paintAll();
    const b = [...P.pane.querySelectorAll('#plPlannedList [data-pl="open"]')].find(x => x.dataset.id === id);
    if (b) b.focus();
  }

  function paintDl() {
    const m = Pl.dl, el = $("#plDlMsg", P.pane);
    if (el) el.innerHTML = !m ? "" : m.wait ? `<span class="small muted">${esc(m.text)}</span>` : say(m);
  }

  async function download() {
    const a = $("#plDlFrom", P.pane).value, b = $("#plDlTo", P.pane).value || a;
    if (!a || b < a) { Pl.dl = { text: "Choose the dates again.", bad: true }; paintDl(); return; }
    Pl.dl = { text: "Making the file…", wait: true }; paintDl();
    let r;
    try { r = await fetch(`/api/relief/planned.csv?start=${enc(a)}&end=${enc(b)}`, { cache: "no-store" }); }
    catch (e) { Pl.dl = { text: "Could not reach the server. Check the connection and try again.", bad: true }; paintDl(); return; }
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      Pl.dl = { text: (j && j.error) || "The file could not be made.", bad: true, status: r.status }; paintDl(); return;
    }
    const blob = await r.blob(), cd = r.headers.get("Content-Disposition") || "", m = /filename="?([^";]+)"?/.exec(cd);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob); link.download = m ? m[1] : `planned relief ${a}.csv`;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 10000);
    Pl.dl = null; paintDl();
  }

  /* ---------------------------------------------------------------- events */
  function onClick(e) {
    const b = e.target.closest("button[data-pl]");
    if (!b || b.disabled) return;
    const a = b.dataset.pl, v = b.dataset.v;
    switch (a) {
      case "day": if (v !== P.day) { P.day = v; changed(); paintDay(); reread(); if (v === "pick") { const d = $("#plDate", P.pane); if (d) d.focus(); } } return;
      case "adddate": addDate(); return;
      case "undate": P.picked = P.picked.filter(d => d !== v); changed(); paintDay(); reread(); return;
      case "away": if (v !== P.away) { P.away = v; changed(); paintAway(); reread(); } return;
      case "reason": P.reason = v; changed(); paintReason(); if (v === "Other") { const w = $("#plWhy", P.pane); if (w) w.focus(); } return;
      case "people": loadPeople(); return;
      case "reread": reread(); return;
      case "send": send(); return;
      case "free": { const c = ctxOf(b); if (c) openFree(c); return; }
      case "close": closeFree(); return;
      case "teaching": {
        const c = ctxOf(b), s = c && F.st.get(c);
        if (s) { s.teaching = !s.teaching; repaint(c, false); focusIn(c, '[data-pl="teaching"]'); }
        return;
      }
      case "duty": {
        const c = ctxOf(b), s = c && F.st.get(c);
        if (s) { s.duty = !s.duty; repaint(c, false); focusIn(c, '[data-pl="duty"]'); }
        return;
      }
      case "choose": { const c = ctxOf(b); if (c) choose(c, b.dataset.name || ""); return; }
      case "clear": { const c = ctxOf(b); if (c) choose(c, ""); return; }
      case "open": openOne(b.dataset.id); return;
      case "back": back(); return;
      case "replanned": view.load(); return;
      case "download": download(); return;
    }
  }

  function onInput(e) {
    const id = e.target.id;
    if (id === "plWhy") { P.text = e.target.value; changed(); }
    else if (id === "plRemarks") { P.remarks = e.target.value; changed(); }
  }

  function onChange(e) {
    const per = e.target.dataset.per;
    if ((per !== "from" && per !== "to") || !e.target.closest("#plAway")) return;
    const v = e.target.value === "" ? null : Number(e.target.value);
    if (per === "from") { P.from = v; if (P.from !== null && P.to !== null && P.to < P.from) P.to = null; }
    else P.to = v;
    changed(); paintAway(); reread();
  }

  function onKey(e) {
    if (e.target.id === "plDate" && e.key === "Enter") { e.preventDefault(); addDate(); }
    if (e.key === "Escape" && F.open && e.target.closest && e.target.closest(".pl-list")) { e.preventDefault(); closeFree(); }
  }

  R.tab("plan", {
    init(pane) {
      P.pane = pane;
      const t = RF.today();
      pane.innerHTML = `<div class="card"><h2>Plan relief for a colleague</h2>
        <div class="field"><div class="flabel">Which day?</div><div id="plDay"></div></div>
        <div class="field"><div class="flabel">Absent teacher</div><div id="plWho"></div></div>
        <div class="field"><div class="flabel">Away for</div><div id="plAway"></div></div>
        <div class="field"><div class="flabel">Reason</div><div id="plReason"></div></div>
        <div class="field"><label class="flabel" for="plRemarks">Remarks for the relief team</label><input id="plRemarks" class="reason-line" maxlength="300" placeholder="e.g. Worksheets are on the desk" autocomplete="off"></div>
        <div class="field"><div class="flabel" id="plLessonsLabel"></div><div id="plLessonsSay"></div><div id="plStopped"></div><div id="plLessonList"></div></div>
        <div id="plSend"></div></div>
        <div class="card" id="plPlanned"><div class="ab-top"><h2>Planned by me</h2></div>
          <div class="pl-dl"><span class="flabel">Download the relief sheet</span>
            <div class="line"><label for="plDlFrom">from</label><input type="date" id="plDlFrom" value="${esc(t)}"><label for="plDlTo">to</label><input type="date" id="plDlTo" value="${esc(t)}">
              <button type="button" class="small" data-pl="download">Download</button><span id="plDlMsg"></span></div>
            <div class="small muted under">Every absence with lessons on those dates, as a spreadsheet: the lessons, the relief teacher, the remarks and who set it. Never the reason.</div></div>
          <div id="plPlannedList"></div>
          <div id="plPlannedOne" class="bar" hidden><button type="button" class="small" id="plBack" data-pl="back">← All planned by me</button><span id="plOneMsg"></span></div></div>
        <div id="plDetail" hidden></div>`;
      pane.addEventListener("click", onClick);
      pane.addEventListener("input", onInput);
      pane.addEventListener("change", onChange);
      pane.addEventListener("keydown", onKey);
      view.mount($("#plDetail", pane));
      paintDay(); paintWho(); paintAway(); paintReason(); paintLessonsLabel(); paintLessons(); paintSend();
      loadPeople(); view.load();
    },
    shown() { view.load(); },
    dirty() { return P.dirty || P.busy || view.dirty(); },
  });
})();

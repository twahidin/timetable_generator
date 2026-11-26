"use strict";
/* Pick dates on Plan relief and on Ask for relief: two months side by side, Monday first. Loaded after relief-form.js and before
   relief.js (window.Relief is read only inside functions).

   ReliefDates.mount(box, {key, picked, max, onChange}) draws the calendar into box. The school days come from
   /api/relief/school-days, read once per page for every form (ReliefDates.load; a failed read is tried again on the next mount).
   Press on a school day and release: it is ticked, or taken off when it was ticked. Press and drag to another day: on release every
   school day between is ticked (from a ticked day: taken off), at most max, taken from the day the drag started. Enter or Space
   on a day ticks it or takes it off. onChange(list) is called once, with the sorted ISO dates, when a click or a drag changed them.
   The month shown is kept for each key, so a form that draws a new box keeps it; while a drag is in progress, a mount only records
   the dates, and the calendar is drawn on release. Grey days cannot be ticked and say why (ReliefDates.why).
   ReliefDates.focusFirst(box) focuses the first school day shown. between, dragResult, months and html are pure, for the tests. */
window.ReliefDates = (function () {
  const RF = window.ReliefForm, esc = RF.esc;
  const URL = "/api/relief/school-days", MAX = 20;
  const NO_DAYS = "There are no school days coming up in the calendar.";
  const NOT_HOLIDAY = ["Not in a term", "Not a school day"];
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const STEP = new Map([["ArrowLeft", -1], ["ArrowRight", 1], ["ArrowUp", -7], ["ArrowDown", 7]]);
  const NONE = { add: [], rem: [] }, ISO = /^\d{4}-\d{2}-\d{2}$/;
  const views = new Map(), keyOf = new WeakMap(), bound = new WeakSet();
  let once = null, info = null, active = null, docBound = false;

  /* ---------------------------------------------------------------- dates */
  const pad = n => String(n).padStart(2, "0");
  const sorted = list => [...new Set((Array.isArray(list) ? list : []).map(String).filter(d => ISO.test(d)))].sort();
  const weekday = iso => new Date(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10))).getUTCDay();
  function addMonth(ym, n) {   /* "2026-12" + 1 = "2027-01" */
    const d = new Date(Date.UTC(+ym.slice(0, 4), +ym.slice(5, 7) - 1 + n, 1));
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}`;
  }

  /* ---------------------------------------------------------------- the school days */
  function load(api) {   /* {ok, status, error, info}; info = {today, days: Set, list, off} */
    if (!once) once = Promise.resolve(api(URL)).then(r => {
      const d = r && r.ok ? r.data || {} : null, list = d ? sorted(d.days) : [];
      if (!list.length) {
        once = null;
        return { ok: false, status: r ? r.status : 0, error: (r && !r.ok && r.error) || NO_DAYS, info: null };
      }
      const today = ISO.test(String(d.today)) ? String(d.today) : list[0];
      info = { today, days: new Set(list), list, off: d.off && typeof d.off === "object" ? d.off : {} };
      return { ok: true, status: r.status, error: "", info };
    });
    return once;
  }

  function why(iso, inf) {   /* "" for a school day, else why it is grey */
    if (inf.days.has(iso)) return "";
    if (iso < inf.today) return "In the past";
    const w = weekday(iso);
    if (w === 0 || w === 6) return "Weekend";
    return (Object.prototype.hasOwnProperty.call(inf.off, iso) && String(inf.off[iso])) || "Not in a term";
  }

  function between(a, b, inf) {   /* the school days from a to b, either order, in date order */
    const lo = a < b ? a : b, hi = a < b ? b : a;
    return inf.list.filter(d => d >= lo && d <= hi);
  }

  /* a drag (a click: anchor = end) from anchor to end: from an unticked day it ticks the school days between, taken from the anchor
     towards the end while fewer than max are ticked (capped: some were left out); from a ticked day it takes every one off */
  function dragResult(picked, anchor, end, inf, max) {
    const have = sorted(picked), set = new Set(have), span = between(anchor, end, inf);
    if (set.has(anchor)) { const gone = new Set(span); return { picked: have.filter(d => !gone.has(d)), capped: false }; }
    let capped = false;
    for (const d of anchor <= end ? span : span.slice().reverse()) {
      if (set.has(d)) continue;
      if (set.size >= max) { capped = true; break; }
      set.add(d);
    }
    return { picked: [...set].sort(), capped };
  }

  function months(inf) { return { first: inf.list[0].slice(0, 7), last: inf.list[inf.list.length - 1].slice(0, 7) }; }

  function bounds(inf) {   /* the earliest and the latest left month: the right month holds the last school day at the latest */
    const m = months(inf), hi = addMonth(m.last, -1);
    return { lo: m.first, hi: hi > m.first ? hi : m.first };
  }

  /* ---------------------------------------------------------------- drawing */
  function html(view) {
    const inf = view.info, m = months(inf), first = view.first || m.first, right = addMonth(first, 1), max = Number(view.max) || MAX;
    const picked = sorted(view.picked), has = new Set(picked), pv = view.preview || NONE, add = new Set(pv.add || []), rem = new Set(pv.rem || []);
    let stop = false;   /* the first school day shown is the one Tab reaches; the arrow keys go on from there */
    const day = iso => {
      const off = why(iso, inf), c = ["rd-d"];
      if (off) c.push("off");
      if (off && off === inf.off[iso] && !NOT_HOLIDAY.includes(off)) c.push("hol");
      if (has.has(iso)) c.push("pick");
      if (add.has(iso)) c.push("add");
      if (rem.has(iso)) c.push("rem");
      if (iso === inf.today) c.push("today");
      const tab = !off && !stop ? (stop = true, "0") : "-1";
      const state = off ? ` aria-disabled="true" title="${esc(off)}"` : ` aria-pressed="${has.has(iso) ? "true" : "false"}"`;
      return `<button type="button" class="${c.join(" ")}" data-d="${iso}" tabindex="${tab}" aria-label="${esc(RF.day(iso))}"${state}>${Number(iso.slice(8))}</button>`;
    };
    const month = (ym, left) => {
      const y = +ym.slice(0, 4), mo = +ym.slice(5, 7), name = `${MONTHS[mo - 1]} ${y}`;
      const n = new Date(Date.UTC(y, mo, 0)).getUTCDate(), lead = (weekday(`${ym}-01`) + 6) % 7;
      const gap = `<span class="rd-gap"></span>`;
      const prev = left ? `<button type="button" class="rd-arrow" data-rd="prev" aria-label="Earlier month"${first <= m.first ? " disabled" : ""}>‹</button>` : gap;
      const next = left ? gap : `<button type="button" class="rd-arrow" data-rd="next" aria-label="Later month"${right >= m.last ? " disabled" : ""}>›</button>`;
      let cells = DOW.map(d => `<span class="rd-dow" aria-hidden="true">${d}</span>`).join("") + `<span class="rd-blank"></span>`.repeat(lead);
      for (let d = 1; d <= n; d++) cells += day(`${ym}-${pad(d)}`);
      return `<div class="rd-month" role="group" aria-label="${name}"><div class="rd-head">${prev}<span class="rd-name">${name}</span>${next}</div><div class="rd-grid">${cells}</div></div>`;
    };
    const k = picked.length, full = k >= max || !!view.capped;
    const line = k
      ? `<b>${k} school day${k === 1 ? "" : "s"}:</b> <span>${esc(RF.dayRuns(picked))}</span> <button type="button" class="small" data-rd="clear">Clear all</button>`
      : `<span class="muted">No dates yet. Up to ${max} school days.</span>`;
    return `<div class="rd-cal">${month(first, true)}${month(right, false)}</div>`
      + `<div class="rd-sum">${line}${full ? ` <span class="rd-full">That is ${max} school days, the most at one time.</span>` : ""}</div>`;
  }

  function draw(v) {
    const b = bounds(info);
    v.first = !v.first || v.first < b.lo ? b.lo : v.first > b.hi ? b.hi : v.first;
    v.box.innerHTML = html({ info, first: v.first, picked: v.picked, preview: NONE, max: v.max, capped: v.capped });
  }

  function show(v) {   /* draw at once when the school days are read; else read them first */
    if (info) { draw(v); return; }
    const box = v.box;
    box.innerHTML = `<p class="small muted rd-note">Reading the school calendar…</p>`;
    load(url => window.Relief.api(url)).then(r => {
      if (v.box !== box) return;   /* a newer mount drew it */
      if (r.ok) { draw(v); return; }
      box.innerHTML = `<p class="rd-note">${window.Relief.say({ text: r.error, bad: true, status: r.status })}`
        + `${r.status === 0 ? ` <button type="button" class="small" data-rd="retry">Try again</button>` : ""}</p>`;
    });
  }

  function paint(v) {   /* the drag's preview, by classes only: the grid under the pointer is never drawn again during a drag */
    const d = v.drag, had = new Set(v.picked), off = had.has(d.anchor);
    const add = new Set(off ? [] : dragResult(v.picked, d.anchor, d.end, info, v.max).picked.filter(x => !had.has(x)));
    const rem = new Set(off ? between(d.anchor, d.end, info).filter(x => had.has(x)) : []);
    v.box.querySelectorAll(".rd-d[data-d]").forEach(b => { b.classList.toggle("add", add.has(b.dataset.d)); b.classList.toggle("rem", rem.has(b.dataset.d)); });
  }

  const dayButton = (box, iso) => box.querySelector(`.rd-d[data-d="${iso}"]`);
  function focusDay(box, b) {   /* one day at a time is in the Tab order */
    box.querySelectorAll('.rd-d[tabindex="0"]').forEach(x => { x.tabIndex = -1; });
    b.tabIndex = 0;
    b.focus();
  }
  function focusFirst(box) {
    const b = box && box.querySelector(".rd-d:not(.off)");
    if (b) focusDay(box, b);
  }

  /* ---------------------------------------------------------------- what the person does */
  function apply(v, anchor, end, focus) {   /* a click or a drag ends */
    const res = dragResult(v.picked, anchor, end, info, v.max), changed = res.picked.join() !== v.picked.join();
    v.picked = res.picked;
    v.capped = res.capped;
    draw(v);
    if (focus) { const b = dayButton(v.box, end); if (b) focusDay(v.box, b); }
    if (changed && v.onChange) v.onChange(res.picked.slice());
  }

  function act(v, what) {
    if (what === "retry") { show(v); return; }
    if (!info) return;
    if (what === "clear") {
      const had = v.picked.length;
      v.picked = []; v.capped = false;
      draw(v); focusFirst(v.box);
      if (had && v.onChange) v.onChange([]);
      return;
    }
    if (what !== "prev" && what !== "next") return;
    v.first = addMonth(v.first, what === "prev" ? -1 : 1);
    draw(v);
    const again = v.box.querySelector(`[data-rd="${what}"]`);
    if (again && !again.disabled) again.focus(); else focusFirst(v.box);
  }

  function arrow(v, iso, n) {   /* focus moves by a day or a week; the months move on when it leaves them */
    const to = RF.addDays(iso, n), tm = to.slice(0, 7), right = addMonth(v.first, 1), b = bounds(info);
    const want = tm < v.first ? tm : tm > right ? addMonth(tm, -1) : v.first;
    if (want !== v.first) {
      if (want < b.lo || want > b.hi) return;
      v.first = want;
      draw(v);
    }
    const el = dayButton(v.box, to);
    if (el) focusDay(v.box, el);
  }

  function viewOf(box) { const v = views.get(keyOf.get(box)); return v && v.box === box ? v : null; }
  const dayOf = e => (e.target && e.target.closest ? e.target.closest(".rd-d[data-d]") : null);

  function bind(box) {
    box.addEventListener("pointerdown", e => {
      const v = viewOf(box), c = dayOf(e);
      if (!v || !info || active || e.button !== 0 || !c || why(c.dataset.d, info)) return;
      e.preventDefault();   /* no text selection, no focus ring under the pointer */
      v.drag = { anchor: c.dataset.d, end: c.dataset.d, pointerId: e.pointerId };
      active = v;
      paint(v);
    });
    box.addEventListener("click", e => {
      const v = viewOf(box);
      if (!v || v.drag) return;
      const b = e.target && e.target.closest ? e.target.closest("button[data-rd]") : null;
      if (b) { if (!b.disabled) act(v, b.dataset.rd); return; }
      const c = dayOf(e);
      /* a pointer's click was the press and release already; only Enter or Space (detail 0) ticks here */
      if (c && info && e.detail === 0 && !why(c.dataset.d, info)) apply(v, c.dataset.d, c.dataset.d, true);
    });
    box.addEventListener("keydown", e => {
      const v = viewOf(box), n = STEP.get(e.key), c = dayOf(e);
      if (!v || !info || !n || !c || e.altKey || e.ctrlKey || e.metaKey) return;
      e.preventDefault();
      if (!v.drag) arrow(v, c.dataset.d, n);
    });
  }

  function bindDocument() {
    if (docBound) return;
    docBound = true;
    document.addEventListener("pointermove", e => {
      const v = active;
      if (!v || e.pointerId !== v.drag.pointerId) return;
      const el = document.elementFromPoint(e.clientX, e.clientY), c = el && el.closest ? el.closest(".rd-d[data-d]") : null;
      if (!c || !v.box.contains(c) || why(c.dataset.d, info) || c.dataset.d === v.drag.end) return;   /* a grey day keeps the last school day */
      v.drag.end = c.dataset.d;
      paint(v);
    });
    const release = ok => e => {
      const v = active;
      if (!v || e.pointerId !== v.drag.pointerId) return;
      const d = v.drag;
      v.drag = null; active = null;
      if (ok) apply(v, d.anchor, d.end, false); else draw(v);
    };
    document.addEventListener("pointerup", release(true));
    document.addEventListener("pointercancel", release(false));
  }

  function mount(box, opts) {
    const o = opts || {}, key = String(o.key || "");
    let v = views.get(key);
    if (!v) { v = { first: null, picked: [], max: MAX, onChange: null, capped: false, box: null, drag: null }; views.set(key, v); }
    v.picked = sorted(o.picked);
    v.max = Number(o.max) || MAX;
    v.onChange = typeof o.onChange === "function" ? o.onChange : null;
    v.capped = false;
    keyOf.set(box, key);
    if (!bound.has(box)) { bound.add(box); bind(box); }
    bindDocument();
    if (v.drag) {   /* a form repaint during a drag: the calendar under the pointer moves into the new box as it is */
      if (v.box && v.box !== box) while (v.box.firstChild) box.appendChild(v.box.firstChild);
      v.box = box;
      return;
    }
    v.box = box;
    show(v);
  }

  return { load, why, between, dragResult, months, html, mount, focusFirst };
})();

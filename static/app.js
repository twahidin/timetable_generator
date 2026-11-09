"use strict";
/* Timetable Setup: a step-by-step editor for the timetable setup workbook. State lives in S.spec (same shape the
   server's ttgen package reads and writes); every list feeds the drop-downs of the later steps. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const KEY = "ttsetup.v1";
const S = { kind: null, spec: null, meta: null, step: 0, brush: "L", stu: { cls: "", q: "" }, tg: { lv: "", subj: "", t: "" }, tf: { dept: "", subj: "", q: "" }, pick: { lessons: new Set(), students: new Set(), teachers: new Set(), shown: {}, last: {}, t: "", g: "", c: "", s: "", v: "All", d: "", r: "", a: "", p: "" }, undo: [], redo: [], last: null };
const STEPS = [["start", "Start"], ["school", "School & day"], ["venues", "1 Venues"], ["classes", "2 Classes"], ["subjects", "3 Subjects"],
  ["teachers", "4 Teachers"], ["lessons", "5 Department map"], ["rules", "6 Configuration & constraints"], ["download", "7 Download"], ["publish", "8 Publish"], ["students", "Students"]];

/* ---------------- storage, server
   The setup lives on the server. SYNC.base is the copy the server last confirmed (at version SYNC.v); S.spec is the
   copy being edited. save() runs after every change: the change goes on the undo list (changes within a second count
   as one), what has not been sent yet is kept in this browser (as changes, not the whole setup) and syncNow() is
   asked to send it. syncNow() sends what changed since SYNC.base as small operations and takes in what other people
   changed meanwhile; with nothing to send it still asks every few seconds, which is how their changes arrive. */
const UNDO_MAX = 20;
const SYNC = { v: 0, base: null, client: "", state: "saved", others: 0, timer: null, busy: false, again: false,
  held: null,      // others' changes waiting for a redraw: {spec, from} (from: S.spec when they arrived)
  kept: false,     // this tab has written changes not yet sent to this browser's storage
  moved: false };  // an old-format copy in this browser has been moved aside
SYNC.client = Sync.newId();   // new on every load: a duplicated tab must not share it, or neither would see the other's changes
const REPLACED = "The committee replaced the school's setup.";
const DROPPED = "The committee replaced the school's setup, so the changes you had not sent were dropped.";
function save(o) {
  if (S.spec) Sync.ensureIds(S.spec);
  const js = S.spec ? JSON.stringify(S.spec) : null;
  if (js !== S.last) {
    if (S.snap && js && !(o && o.quiet)) {   // an entry holds the operations that take back (and bring again) this change
      const merge = Date.now() - (S.pushed || 0) <= 1000 && S.undo.length && S.from;
      const before = merge ? S.from : S.snap;
      const e = { undo: Sync.diff(S.spec, before), redo: Sync.diff(before, S.spec) };
      if (merge) S.undo[S.undo.length - 1] = e; else { S.undo.push(e); if (S.undo.length > UNDO_MAX) S.undo.shift(); S.from = before; }
      S.redo = []; S.pushed = Date.now();
    } else S.pushed = 0;   // other people's changes and quiet saves never join an entry
    S.last = js;
  }
  S.snap = S.spec ? Sync.clone(S.spec) : null;
  keepLocal();
  if (!(o && o.remote) && !S.practice) scheduleSync();
  saveState();
}
/* this browser's copy: {sync: 1, step, at, kind, v, pending}, pending = what this tab has not sent. A tab with nothing
   to send leaves another tab's unsent changes alone. A copy in the format before this one is moved aside, untouched. */
function keepLocal() {
  if (!S.spec || !SYNC.base || S.practice) return;   // a practice copy is never kept
  try {
    if (!SYNC.moved) {
      const old = localStorage.getItem(KEY); let x = null; try { x = JSON.parse(old || "null"); } catch (e) { }
      if (x && x.spec && !x.sync) localStorage.setItem(KEY + ".old", old);
      SYNC.moved = true;
    }
    const pending = Sync.diff(SYNC.base, working());
    if (!pending.length && !SYNC.kept) { const cur = saved(); if (cur && cur.pending && cur.pending.length) return; }
    localStorage.setItem(KEY, JSON.stringify({ sync: 1, step: S.step, at: (STEPS[S.step] || [])[0] || "", kind: S.kind, v: SYNC.v, pending }));
    SYNC.kept = pending.length > 0;
  } catch (e) { }
}
function saved() {   // this browser's copy in the current format; the step is kept by name ("at")
  try {
    const x = JSON.parse(localStorage.getItem(KEY) || "null"); if (!x || !x.sync) return null;
    const at = { generate: "publish", adjust: "publish" }[x.at] || x.at;   // steps that no longer exist: their work ends on Publish now
    x.step = at && stepAt(at) >= 0 ? stepAt(at) : 1; return x;
  } catch (e) { return null; }
}
function saveState() {
  const u = $("#undo"), r = $("#redo"), st = $("#saveState"), ot = $("#others");
  if (u) { u.disabled = !S.spec || !S.undo.length; r.disabled = !S.spec || !S.redo.length; }
  if (st) { st.className = "savestate" + (SYNC.state === "offline" && !S.practice ? " warn" : ""); st.textContent = !S.spec ? "" : S.practice ? "Practice copy" : { saved: "Saved", saving: "Saving…", offline: "Offline: your changes are kept in this browser and will be sent" }[SYNC.state]; }
  const here = SYNC.others === 1 ? "1 other here" : `${SYNC.others} others here`;
  if (ot) { ot.hidden = !S.spec || S.practice || !SYNC.others; ot.textContent = here; }
  const so = $("#startOthers"); if (so) so.textContent = SYNC.others ? here : "Nobody else is here now";
}
function undo(back) {   // takes back (or brings again) the last change made here; other people's changes stay
  const from = back ? S.undo : S.redo, to = back ? S.redo : S.undo;
  if (!S.spec || !from.length) return;
  const e = from.pop(); to.push(e);
  Sync.apply(S.spec, back ? e.undo : e.redo); S.pushed = 0; unpick();
  ensureDays(); save({ quiet: true }); render(); toast(back ? "Undone." : "Redone.");
}
/* the setup as edited: S.spec, or, while others' changes wait for a redraw, those changes with what S.spec gained since */
function working() {
  Sync.ensureIds(S.spec);
  if (!SYNC.held) return Sync.clone(S.spec);
  const w = Sync.clone(SYNC.held.spec); Sync.apply(w, Sync.diff(SYNC.held.from, S.spec)); return w;
}
/* a redraw would take something from under the person: an open pop-up, the day grid being painted, or a box in the step
   with typing not yet committed */
function canRedraw() {
  if (!$("#pop").hidden || painting) return false;
  const a = document.activeElement;
  const typing = a && $("#main").contains(a) && ((a.tagName === "INPUT" && ["text", "number", "time", "search"].includes(a.type)) || a.tagName === "TEXTAREA");
  return !(typing && a.value !== a.defaultValue);
}
const LIST_KEYS = ["venues", "classes", "subjects", "teachers", "blocks", "lessons", "rules", "students", "combinations"];
function takeSpec(spec) {   // a newer copy with others' changes in it: redraw now, or once the person is done with the box or pop-up
  if (!canRedraw()) { SYNC.held = { spec, from: Sync.clone(S.spec) }; return; }
  const rows = s => ["lessons", "students", "teachers"].map(k => (s[k] || []).map(r => r._id).join()).join("|");
  if (rows(spec) !== rows(S.spec)) unpick();   // ticks are by row number
  LIST_KEYS.forEach(k => spec[k] = spec[k] || []);
  S.spec = spec; SYNC.held = null; save({ quiet: true, remote: true }); render();
}
function tryHeld() { if (!SYNC.held || !S.spec || !canRedraw()) return false; takeSpec(working()); return true; }
function scheduleSync() {   // after a change: send it shortly (changes in quick succession go together)
  if (!S.spec || !SYNC.base) return;
  if (SYNC.state === "offline") return;   // the retry every 5 seconds sends it
  if (Sync.diff(SYNC.base, working()).length) SYNC.state = "saving";
  clearTimeout(SYNC.timer); SYNC.timer = setTimeout(syncNow, 600);
}
async function syncNow() {
  clearTimeout(SYNC.timer);
  if (!S.spec || !SYNC.base || S.practice) return;
  if (SYNC.busy) { SYNC.again = true; return; }
  SYNC.busy = true; SYNC.again = false;
  let wait = 4000;
  try {
    headsTeachers();
    const sent = working(), ops = Sync.diff(SYNC.base, sent);
    const r = ops.length
      ? await fetch("/api/setup/changes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ since: SYNC.v, client: SYNC.client, ops }) })
      : await fetch(`/api/setup/changes?since=${SYNC.v}&client=${encodeURIComponent(SYNC.client)}`);
    if (r.status === 401) { location.href = "/login"; return; }
    if (r.status >= 500) throw new Error(`server ${r.status}`);
    const j = await r.json().catch(() => ({}));
    if (r.status === 403) {   // fallback (the server now skips what a head may not make): nothing was applied, so start again from the server's copy
      toast(j.error || "That change is not allowed.");
      const srv = await fetchSetup(); if (!srv) return;
      if (srv.spec) { await openServer(srv); SYNC.base = Sync.clone(S.spec); keepLocal(); render(); }
    } else if (r.status === 409) {   // the server has no setup: a committee member's copy goes up whole
      if (!(G.st && G.st.role === "committee") || !await putSetup(sent, "Saved from a browser", S.step)) throw new Error("no setup");
      render();
    } else if (!r.ok) throw new Error(j.error || `status ${r.status}`);
    else if (j.reset) { await catchUp(j, sent, ops, r.ok && ops.length > 0); wait = 0; }
    else {
      const theirs = (j.patches || []).flatMap(p => p.ops || []);
      // operations the server would not make for this person (a head) are left out of what it applied: they drop out of
      // the working copy too, as they are in neither the new base nor the edits made since the send
      const no = new Set((j.refused || []).map(x => x.i)), ours = ops.filter((_, i) => !no.has(i));
      const nb = Sync.rebase(SYNC.base, sent, working(), theirs, ours);
      SYNC.base = nb.base; SYNC.v = j.v;
      if (theirs.length || no.size) takeSpec(nb.spec);
      if (theirs.length || ops.length) keepLocal();   // the base moved: what is kept as not sent must move with it
      if (no.size) {
        const why = [...new Set(j.refused.map(x => x.why))].join(" ");
        toast(`${no.size} change${no.size === 1 ? "" : "s"} could not be made: ${why}`);
      }
    }
    if ("others" in j) SYNC.others = j.others;
    SYNC.state = Sync.diff(SYNC.base, working()).length ? "saving" : "saved";
    if (SYNC.state === "saving") wait = Math.min(wait, 600);
  } catch (e) { SYNC.state = "offline"; wait = 5000; }
  SYNC.busy = false; saveState(); tryHeld();
  clearTimeout(SYNC.timer); SYNC.timer = setTimeout(syncNow, SYNC.again && SYNC.state !== "offline" ? 0 : wait);
}
/* the server's log no longer reaches back to SYNC.v: take its copy. Replaced by the committee: what was not sent is
   dropped; otherwise it goes on top of the new copy and is sent again. accepted: the reset came back from a send the
   server applied, so only the edits made since that send are still to go on top (applying the sent operations again
   could undo someone's newer change to the same field); after a fetch with nothing sent, everything since the old
   base is still to go. */
async function catchUp(j, sent, ops, accepted) {
  const old = SYNC.base;
  const srv = await fetchSetup(); if (!srv) return;
  if (!srv.spec) throw new Error("no setup");
  await useKind(srv.spec);
  if (j.replaced) {
    const dropped = ops.length > 0 || Sync.diff(sent, working()).length > 0;   // sent, or edited while the request was out
    SYNC.v = srv.v; SYNC.base = Sync.clone(srv.spec);
    S.undo = []; S.redo = []; SYNC.held = null;
    const spec = Sync.clone(srv.spec); defaultRoles(spec);
    takeSpec(spec);
    toast(dropped ? DROPPED : REPLACED);
  } else {
    const unsent = accepted ? Sync.diff(sent, working()) : Sync.diff(old, working());
    SYNC.v = srv.v; SYNC.base = Sync.clone(srv.spec);
    const spec = Sync.clone(srv.spec); Sync.apply(spec, unsent);
    takeSpec(spec);
  }
  keepLocal();
}
/* a teacher a head adds is provisional (the server makes it so): the same here before the change is taken, so this
   copy, the change sent and the base all agree with the server */
function headsTeachers() {
  if (!(G.st && G.st.role === "head")) return;
  Sync.ensureIds(S.spec);
  const had = new Set((SYNC.base.teachers || []).map(t => t && t._id));
  const fix = (S.spec.teachers || []).filter(t => t && !had.has(t._id) && t.provisional !== "Yes");
  if (!fix.length) return;
  // a change made outside save(): S.snap (and S.last, when it was up to date) take it too, so it is never an Undo entry
  const rest = S.last === JSON.stringify(S.spec);
  const also = [S.snap, S.from].filter(Boolean).flatMap(x => x.teachers || []).filter(t => t && fix.some(f => f._id === t._id));
  fix.concat(also).forEach(t => { t.provisional = "Yes"; });
  if (rest) S.last = JSON.stringify(S.spec);
}
async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(await r.text()); return r.json(); }
async function fetchSetup() {   // {spec, v, saved_at}; null when signed out (the page goes to sign in)
  const r = await fetch("/api/setup");
  if (r.status === 401) { location.href = "/login"; return null; }
  if (!r.ok) throw new Error(`status ${r.status}`);
  return r.json();
}
async function useKind(spec) {
  const k = (spec.school && spec.school.type) || S.kind || "secondary";
  if (k !== S.kind || !S.meta) { S.meta = await getJSON(`/api/meta/${k}`); S.kind = k; }
}
/* a setup with no roles gets the usual ones (S.meta.roles), written once when it is opened, never while drawing a step.
   Only where roles may be changed: the committee, or a practice copy (a head sees the usual ones listed, nothing written).
   The ids are fixed, so two committee members opening it at once add them once (an add with an id already there is
   skipped). True if any were added. */
function defaultRoles(spec) {
  if (!(committee() || S.practice) || !spec) return false;
  if (!Array.isArray(spec.roles)) spec.roles = [];
  if (spec.roles.length || !(S.meta && (S.meta.roles || []).length)) return false;
  spec.roles = S.meta.roles.map((r, i) => Object.assign(Sync.clone(r), { _id: "roledef" + String(i).padStart(3, "0") }));
  return true;
}
/* open the server's copy here: it is the base, the undo list starts empty */
async function openServer(srv, step) {
  await useKind(srv.spec);
  unpick(); SYNC.held = null; SYNC.v = srv.v; SYNC.base = Sync.clone(srv.spec);
  S.spec = Sync.clone(srv.spec); LIST_KEYS.forEach(k => S.spec[k] = S.spec[k] || []); defaultRoles(S.spec);
  if (step != null) S.step = step;
  ensureDays(); S.undo = []; S.redo = []; S.last = null; S.snap = null; save({ quiet: true });
}
/* a whole setup (a blank template, a workbook, a progress file, an earlier copy) goes on the server for the school, then
   the server's copy opens here */
async function putSetup(spec, why, step = 1) {
  const r = await fetch("/api/setup", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ spec, why }) });
  if (r.status === 401) { location.href = "/login"; return false; }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { toast(j.error || "Could not save the setup for the school."); return false; }
  const srv = await fetchSetup(); if (!srv || !srv.spec) return false;
  await openServer(srv, step); return true;
}
const committee = () => !!(G.st && G.st.role === "committee");
/* what a department head sees. The server decides what a head may change; the page mirrors it: Download, Publish and
   Students are not shown, every step but 4 and 5 is read-only, and on 4 only a provisional teacher's row and the
   Can teach cells can be changed. A practice copy is the head's own: nothing is read-only there (the hidden steps stay hidden). */
const isHead = () => !!(G.st && G.st.role === "head");
const HEAD_HIDDEN = ["download", "publish", "students"];
const stepShown = i => !(isHead() && STEPS[i] && HEAD_HIDDEN.includes(STEPS[i][0]));
const locked = id => isHead() && !S.practice && !["start", "_old", "teachers", "lessons"].includes(id);   // true: nothing on this step can be changed
const provisionalRow = t => !!t && t.provisional === "Yes";
function headLocks(main, id) {
  const off = (el, why) => { el.disabled = true; if (why && !el.title) el.title = why; };
  const all = () => [...main.querySelectorAll("input, select, textarea, button")];
  if (locked(id)) {
    all().forEach(el => off(el));
    main.querySelectorAll("[data-pop]").forEach(el => el.classList.add("ro"));
    main.insertAdjacentHTML("afterbegin", `<div class="notice readonly">Only the committee can change this step.</div>`);
    return;
  }
  if (!isHead() || S.practice || id !== "teachers") return;
  const why = "Only the committee can change this. A teacher the committee has not confirmed yet can be changed.";
  const bar = ["tc-dept", "tc-role", "tc-allow"];
  all().forEach(el => {
    const tr = el.closest("tr[id^='teachers-']");
    if (tr) {   // a row: the tick box always; the rest only while the teacher is provisional (and never the Provisional field)
      const own = provisionalRow(S.spec.teachers[Number(tr.id.slice(9))]) && !/\.provisional$/.test(el.dataset.k || "");
      if (!el.dataset.pick && !own) off(el, why);
      return;
    }
    if (el.closest(".bulk")) { if (bar.includes(el.dataset.bulk) || ["pickD", "pickR", "pickA"].includes(el.id)) off(el, why); return; }
    if (el.closest("#teacherList")) return;   // the teachers card: add, show, tick all
    off(el, why);   // the Roles card (the upload card is not drawn for a head)
  });
}
/* runs fn with this tab's sync stopped: a send already on its way finishes first, none starts meanwhile */
async function holdSync(fn) {
  while (SYNC.busy) await new Promise(r => setTimeout(r, 50));
  SYNC.busy = true; clearTimeout(SYNC.timer);
  try { return await fn(); } finally { SYNC.busy = false; }
}
/* the question before the school's whole setup is replaced (none when the school has no setup yet) */
function mayReplace() {
  if (!SYNC.base) return true;
  const n = SYNC.others;
  return confirm("This replaces the school's setup for everyone." + (n ? ` ${n} other${n === 1 ? " is" : "s are"} working in it now.` : "") + " An earlier copy is kept. Replace it?");
}
/* committee only: the setup becomes the school's, for everyone; a practice copy is left */
async function replaceSetup(spec, why) {
  if (!committee()) { toast("Only the committee can replace the school's setup."); return false; }
  if (!mayReplace()) return false;
  let ok = false;
  try {
    ok = await holdSync(async () => {
      const was = S.practice; let opened = false; S.practice = false;
      try { opened = await putSetup(spec, why); return opened; }
      finally { if (!opened) S.practice = was; }   // the server's copy did not open here: a practice copy stays one
    });
  } catch (e) { toast("Could not reach the server: " + e.message); }
  S.copies = null; render(); syncNow(); return ok;
}
async function restoreCopy(id) {
  if (!committee() || !mayReplace()) return;
  let ok = false;
  try { ok = await holdSync(async () => {
    const r = await fetch("/api/setup/restore", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id }) });
    if (r.status === 401) { location.href = "/login"; return false; }
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { toast(j.error || "Could not restore that copy."); return false; }
    const srv = await fetchSetup(); if (!srv || !srv.spec) return false;
    await openServer(srv, S.step); return true;
  }); } catch (e) { toast("Could not reach the server: " + e.message); }
  S.copies = null; render(); syncNow();
  if (ok) toast("The earlier copy is back as the school's setup.");
}
/* a practice copy: a sample school to try things on. Nothing in it reaches the server or this browser's storage; the
   school's setup (SYNC.base, and what was not sent, kept in this browser) waits for Back to the school's setup. */
async function practice(kind) {
  try {
    const spec = await getJSON(`/api/sample/${kind}`);
    await holdSync(async () => {
      await useKind(spec);   // may fail: nothing has changed yet, the school's setup stays open
      S.practice = true; SYNC.held = null; unpick();
      Sync.ensureIds(spec); LIST_KEYS.forEach(k => spec[k] = spec[k] || []); defaultRoles(spec); S.spec = spec;
      S.step = 1; ensureDays(); S.undo = []; S.redo = []; S.last = null; S.snap = null; save({ quiet: true });
    });
  } catch (e) {
    toast("Could not open the practice copy: " + e.message);
    if (!S.practice) syncNow();   // holdSync stopped the school's sync: start it again
    return;
  }
  render(); toast("Practice copy of the sample school opened: change anything, nothing is saved for the school.");
}
function leavePractice() {
  S.practice = false; S.spec = null; S.step = 0; S.undo = []; S.redo = []; S.last = null; S.snap = null; SYNC.base = null; unpick();
  openPage();
}
async function begin(kind, what) {
  if (what === "sample") { await practice(kind); return; }
  const spec = await getJSON(`/api/${what}/${kind}`);
  if (await replaceSetup(spec, "Started blank")) toast("Blank template started and saved for the school.");
}
async function adopt(spec, msg, why) {   // a workbook or a progress file opened: it becomes the school's setup
  if (!await replaceSetup(spec, why)) return false;
  if (msg) toast(msg); return true;
}
/* the rollout question: a copy of the setup this browser kept before the setup lived on the server, with changes that
   never reached it. One in the old place is moved aside first; one with nothing unsaved is removed without asking. */
const OLD = KEY + ".old";
function oldChanges() {
  try {
    const cur = localStorage.getItem(KEY); let x = null; try { x = JSON.parse(cur || "null"); } catch (e) { }
    if (x && x.spec && !x.sync) { localStorage.setItem(OLD, cur); localStorage.removeItem(KEY); }
    let o = null; try { o = JSON.parse(localStorage.getItem(OLD) || "null"); } catch (e) { }
    if (o && o.spec && o.spec.school && !o.sync && o.dirty) return o;
    localStorage.removeItem(OLD);
  } catch (e) { }
  return null;
}
async function oldChoice(k) {
  const o = S.asking; if (!o) return;
  if (k === "file") dl(new Blob([JSON.stringify(o.spec, null, 1)], { type: "application/json" }), `${o.spec.school.name || "timetable"}_setup.json`);
  if (k === "use" && !await replaceSetup(Sync.clone(o.spec), "Unsaved changes from a browser")) return;   // not replaced: the question stays
  try { localStorage.removeItem(OLD); } catch (e) { }
  S.asking = null; render();
  toast({ file: "Saved to a file. They are no longer kept in this browser.", use: "They are the school's setup now.", discard: "Discarded." }[k]);
}
function toast(m) { const t = $("#toast"); t.textContent = m; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => t.hidden = true, 3200); }

/* ---------------- lists */
const sc = () => S.spec.school;
const levels = () => sc().levels || [];
const bands = () => sc().bands || {};
const dayNames = () => {   // the workbook's own day names (e.g. "Odd Tues") when they fit the cycle
  const def = Number(sc().weeks) === 2 ? ["Odd", "Even"].flatMap(w => ["Mon", "Tue", "Wed", "Thu", "Fri"].map(d => `${w} ${d}`)) : ["Mon", "Tue", "Wed", "Thu", "Fri"];
  const wd = ["mon", "tue", "wed", "thu", "fri"], key = d => { const w = d.split(" "); return (w[0] === "Even" ? 10 : 0) + wd.indexOf(w[w.length - 1].slice(0, 3).toLowerCase()); };
  const have = Object.keys(Object.values(S.spec.day_structure || {})[0] || {}).sort((a, b) => key(a) - key(b));   // calendar order, as JSON may sort keys
  return have.length === def.length ? have : def;
};
const roles = () => S.spec.roles && S.spec.roles.length ? S.spec.roles : (S.meta.roles || []);
const groupCodes = () => lessonInfo().map(x => x.code).filter(c => c && c !== "Entire Class");
const tagLabel = () => sc().type === "primary" ? "Level tag" : "G-level";
const hhmm = p => { const [h, m] = String(sc().start_time || "07:30").split(":").map(Number); const t = h * 60 + m + p * Number(sc().period_minutes || 20); return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`; };
const mins = t => { const [h, m] = String(t || "0:0").split(":").map(Number); return h * 60 + (m || 0); };
function periodsBetween(a, b) {   // clock times -> the periods a block-out overlaps (as the reader does)
  const st = mins(sc().start_time), pl = Number(sc().period_minutes || 20), NP = Number(sc().periods_per_day);
  return [Math.max(0, Math.floor((mins(a) - st) / pl)), Math.min(NP - 1, Math.ceil((mins(b) - st) / pl) - 1)];
}
function ruleTimes(r) {   // a block-out's clock times: as typed while they still give its periods, else the times of its periods
  const a = Number(r.from) || 0, b = r.to == null || r.to === "" ? a : Number(r.to);
  if (r.times && r.times.length === 2) { const [x, y] = periodsBetween(r.times[0], r.times[1]); if (x === a && y === b) return r.times; }
  return [hhmm(a), hhmm(b + 1)];
}

/* ---------------- rule rows on Settings, Teacher availability, Fixed lessons, More rules (as ttgen.spec.split_rules) */
function loadChecks(load) {   // the 4 Teachers 'Load check' column: load against the allowance, the role's guide and the teacher average
  const tot = t => (load[t.name] || 0) + (Number(t.other_duties) || 0), role = r => roles().find(x => x.role === r) || {};
  const eo = S.spec.teachers.filter(t => t.role === "EO" && tot(t) > 0).map(tot), avg = eo.length ? eo.reduce((a, b) => a + b, 0) / eo.length : 0;
  const spread = Number(sc().role_spread ?? 15);
  return S.spec.teachers.map(t => {
    const m = [], T = tot(t), A = Number(t.allowance) || 0, g = Number(role(t.role).allowance) || 0;
    if (!t.role) m.push("No role.");
    if (g > 0 && A > 0 && A !== g) m.push(`Allowance differs from the ${t.role} guide (${g}).`);
    if (A > 0 && T > A) m.push("Over allowance.");
    if (role(t.role).group === "Management" && avg > 0 && T >= avg) m.push(`Management teaching as much as the average teacher (${Math.round(avg)}).`);
    if (t.role === "EO" && T > 0 && avg > 0 && avg - T >= spread) m.push(`Below the teacher average by ${Math.round(avg - T)} periods.`);
    if (t.role === "EO" && avg > 0 && T - avg >= spread) m.push(`Above the teacher average by ${Math.round(T - avg)} periods.`);
    if (t.role && A > 0 && T === 0) m.push("No lessons yet.");
    return m.join(" ");
  });
}
const SET = () => S.meta.setting_rules || [];
const ruleIs = (r, s) => s.rule && r.rule === s.rule.rule && r.scope === s.rule.scope && (r.scope !== "Department" || r.target === s.rule.target);
/* several names in one cell (Only these subjects, Only in venues), the subject without its tag, and the test for an HBL
   day's subjects (as ttgen.spec.names_list, untag, subject_test) */
const namesList = v => (Array.isArray(v) ? v : String(v ?? "").split(",")).map(x => String(x).trim()).filter(Boolean);
const untag = s => String(s || "").trim().replace(/\s+(G[123]|Std|Fdn|Standard|Foundation)$/, "");
const subjectTest = names => { const w = new Set(namesList(names).map(n => n.toLowerCase())); return (s, d) => [String(s || "").toLowerCase(), untag(s).toLowerCase(), String(d || "").toLowerCase()].some(x => x && w.has(x)); };
const EVERY = "Every class";   // Fixed lessons: that subject for every class of the level (Level All: of the whole school)
const isFixedLesson = r => ["Class", "Group", "Level", "School"].includes(r.scope);
const scopesOf = rt => String(rt.scopes || "").split(",").map(x => x.trim());
function placeRules() {
  const out = { settings: {}, availability: [], fixed: [], more: [] };
  S.spec.rules.forEach((r, i) => {
    const must = (r.strength || "Must") === "Must", s = SET().find(s => ruleIs(r, s)), has = r.from != null && r.from !== "";
    if (s && must && !(s.key in out.settings)) out.settings[s.key] = i;
    else if (r.rule === "Not available" && r.scope === "Teacher" && must && has) out.availability.push(i);
    else if (r.rule === "Fixed at" && isFixedLesson(r) && must && has) out.fixed.push(i);
    else out.more.push(i);
  });
  return out;
}
function settingValue(key) {
  if (key === "after_school") return sc().after_school === false ? "No" : "Yes";
  if (key === "pe_rain_home") return sc().pe_rain_home ? "Yes" : "No";
  const s = SET().find(x => x.key === key), i = placeRules().settings[key];
  return i == null ? (s.number ? "" : "No") : (s.number ? S.spec.rules[i].number : "Yes");
}
function setSetting(key, v) {
  if (key === "after_school") { sc().after_school = v !== "No"; return; }
  if (key === "pe_rain_home") { sc().pe_rain_home = v === "Yes"; return; }
  const s = SET().find(x => x.key === key), i = placeRules().settings[key], on = s.number ? v !== "" && v != null : v === "Yes";
  if (!on) { if (i != null) S.spec.rules.splice(i, 1); return; }
  if (i != null) { if (s.number) S.spec.rules[i].number = Number(v); return; }
  S.spec.rules.push({ ...s.rule, ...(s.number ? { number: Number(v) } : {}) });
}
const rooms = () => S.spec.venues.map(v => v.room).filter(Boolean);
const classNames = () => S.spec.classes.map(c => c.class).filter(Boolean);
const subjectNames = () => S.spec.subjects.map(s => s.subject).filter(Boolean);
const teacherNames = () => S.spec.teachers.map(t => t.name).filter(Boolean);
const blockNames = () => S.spec.blocks.map(b => b.block).filter(Boolean);
const scopes = () => ["All", ...levels(), ...[...new Set(Object.values(bands()))]];
const subj = n => S.spec.subjects.find(s => s.subject === n);
/* rooms: what a room is kept for (Venues 'For'), and the rooms a lesson row's group may use (as the server's Problem.allowed) */
const special = x => { const k = (subj(x.subject) || {}).room_kind; return !!k && k !== "classroom"; };   // a lab, studio, ... (not a classroom)
const forNames = () => [...new Set([...subjectNames(), ...(sc().departments || []), ...levels()])];
function groupSize(x, cls, code) {   // the Students sheet count for its code, else the row's Students, else (whole class) the class size
  const n = code && code !== "Entire Class" ? S.spec.students.filter(s => (s.groups || []).includes(code)).length : 0;
  if (n) return n;
  if (code === "Entire Class" || !x.block && !x.code_override) { const c = S.spec.classes.find(c => c.class === cls); return Number(c && c.size) || null; }
  return Number(x.students) || null;
}
function roomsFor(x, kind) {   // rooms of this kind the row may use: kept for its subject, department or level, or for anyone
  const s = subj(x.subject) || {};
  return S.spec.venues.filter(v => (v.kind || "classroom") === kind && (!(v.only_for || []).length || v.only_for.some(f => [x.subject, s.dept, x.level].includes(f))));
}
const clsLevel = c => (S.spec.classes.find(x => x.class === c) || {}).level;
function clock(p) {
  const [h, m] = String(sc().start_time || "07:30").split(":").map(Number); const t = h * 60 + m + p * Number(sc().period_minutes || 20);
  return `${((Math.floor(t / 60) + 11) % 12) + 1}.${String(t % 60).padStart(2, "0")}`;
}
function ensureDays() {
  const ds = S.spec.day_structure = S.spec.day_structure || {}; const NP = Number(sc().periods_per_day);
  for (const lv of levels()) {
    ds[lv] = ds[lv] || {}; const first = Object.values(ds[lv])[0] || Object.values(Object.values(ds)[0] || {})[0] || ".".repeat(NP);
    for (const d of dayNames()) ds[lv][d] = (ds[lv][d] || first).padEnd(NP, ".").slice(0, NP);
    for (const d of Object.keys(ds[lv])) if (!dayNames().includes(d)) delete ds[lv][d];
  }
  for (const lv of Object.keys(ds)) if (!levels().includes(lv)) delete ds[lv];
  ensureRecessRows();
}
// Settings rows for floating recess (the W periods): added the first time a recess window is painted
const RECESS_ROWS = [["Floating recess goes by", "Level", "Level: each level has its recess together. Class: each class has its own recess time. For the W (recess window) periods on Day structure."],
  ["Floating recess length (periods)", 2, "How long the recess is inside each recess window."],
  ["Most classes at recess at once", null, "Leave empty for no limit (canteen space). Counts fixed (R) and floating recess."]];
function hasWindows() { return Object.values(S.spec.day_structure || {}).some(days => Object.values(days).some(r => String(r).includes("W"))); }
const ampm = t => { const h = Math.floor(t / 60); return `${(h + 11) % 12 + 1}.${String(t % 60).padStart(2, "0")}${h % 24 < 12 ? "am" : "pm"}`; };
const listing = (a, n = 4) => a.slice(0, n).join(", ") + (a.length > n ? ` and ${a.length - n} more` : "");
function endRows() {   // 'Lessons end by (...)' rows -> [{label, days: Mon..Fri, cut: minutes}] (as ttgen.spec.end_rows)
  const full = ["monday", "tuesday", "wednesday", "thursday", "friday"], WD = ["Mon", "Tue", "Wed", "Thu", "Fri"];
  const idx = w => full.findIndex(d => d.slice(0, 3) === w.slice(0, 3).toLowerCase());
  return (sc().extra_settings || []).filter(x => String(x[0] || "").toLowerCase().startsWith("lessons end by") && /^\d{1,2}[:.]\d{2}$/.test(String(x[1] ?? "").trim())).map(x => {
    const m = String(x[0]).match(/\((.*?)\)/), txt = (m ? m[1] : "monday to friday").toLowerCase(), sp = txt.match(/^\s*(\w+)\s+to\s+(\w+)/);
    const a = sp ? idx(sp[1]) : -1, b = sp ? idx(sp[2]) : -1;
    const days = a >= 0 && b >= 0 ? WD.slice(a, b + 1) : (txt.match(/[a-z]+/g) || []).map(idx).filter(k => k >= 0).map(k => WD[k]);
    return { label: String(x[0]), days: new Set(days), cut: mins(String(x[1]).trim().replace(".", ":")) };
  });
}
function structureWarnings() {   // where the Day structure and the rules say different things (as ttgen.spec.structure_vs_rules): the rules win where stricter
  const s = sc(), ds = S.spec.day_structure || {}, NP = Number(s.periods_per_day), pl = Number(s.period_minutes || 20), st = mins(s.start_time);
  const lvls = levels().filter(lv => ds[lv] && Object.keys(ds[lv]).length), days = dayNames(), lesson = s.after_school !== false ? "LWA" : "LW";
  const row = (lv, d) => String((ds[lv] || {})[d] || "").padEnd(NP, ".").slice(0, NP);
  const last = r => { for (let p = r.length - 1; p >= 0; p--) if (lesson.includes(r[p])) return p; return -1; };
  const at = p => ampm(st + p * pl), every = l => l.length === lvls.length && l.length > 1 ? "every level" : l.join(", "), wd = d => d.split(" ").pop().slice(0, 3);
  const out = [], endAt = {}, keepBy = {};
  for (const e of endRows()) {
    const keep = Math.max(0, Math.min(NP, Math.floor((e.cut - st) / pl))), covered = days.filter(d => e.days.has(wd(d)));
    if (!covered.length) { out.push(`${e.label} matches no day of the Day structure, so it changes nothing.`); continue; }
    covered.forEach(d => { endAt[d] = `${e.label} (${ampm(e.cut)})`; keepBy[d] = Math.min(keepBy[d] ?? NP, keep); });
    const over = {}, ends = [];
    for (const d of covered) for (const lv of lvls) { const p = last(row(lv, d)); if (p < 0) continue; ends.push(p); if (p >= keep) (over[d] = over[d] || []).push([lv, p]); }
    const od = Object.keys(over);
    if (od.length) {
      const parts = od.map(d => `${d} (${every(over[d].map(x => x[0]))}, until ${at(Math.max(...over[d].map(x => x[1])) + 1)})`);
      out.push(`${e.label} is ${ampm(e.cut)}, but the Day structure has lessons after it on ${listing(parts)}. The time wins, so those periods stay empty: `
        + `end the Day structure at ${ampm(e.cut)} on those days, or set the time to ${at(Math.max(...od.flatMap(d => over[d].map(x => x[1]))) + 1)}.`);
    } else if (ends.length && Math.max(...ends) + 1 < keep) out.push(`${e.label} is ${ampm(e.cut)}, but the Day structure has no lesson after ${at(Math.max(...ends) + 1)} on those days, so the time changes nothing: the Day structure decides.`);
  }
  if (s.after_school === false) {
    const withA = days.filter(d => lvls.some(lv => row(lv, d).includes("A")));
    if (withA.length) out.push(`After-school slot allowed when a class cannot fit is No, but the Day structure has after-school slots (A) on ${listing(withA)}: they are never used.`);
  }
  if (S.spec.rules.some(r => r.rule === "At least one recess a day" && r.scope === "School")) {
    const bare = days.filter(d => lvls.some(lv => last(row(lv, d)) >= 0) && !lvls.some(lv => /[RW]/.test(row(lv, d))));
    if (bare.length) out.push(`Every teacher gets at least one recess a day, but on ${listing(bare)} no level has a recess (R or W) in the Day structure, so a teacher who teaches that day cannot have one.`);
  }
  const lvOf = Object.fromEntries(S.spec.classes.map(c => [c.class, c.level])), info = lessonInfo();
  S.spec.lessons.forEach((x, i) => { if (info[i].code && info[i].code !== "Entire Class") lvOf[info[i].code] = x.level; });
  for (const r of S.spec.rules) {   // a fixed lesson that starts outside lesson time can never be met
    if (r.rule !== "Fixed at" || r.from == null || r.from === "") continue;
    const p = Number(r.from), lv = r.level || lvOf[r.target], wk = String(r.week || "Both"), dy = String(r.day || "All");
    if (!ds[lv]) continue;
    for (const d of days) {
      if ((["Odd", "Even"].includes(wk) && !d.startsWith(wk)) || (dy !== "All" && wd(d) !== dy.slice(0, 3))) continue;
      const ch = p >= 0 && p < NP ? row(lv, d)[p] : ".";
      let why;
      if (!lesson.includes(ch)) why = `is ${String((S.meta.codes || {})[ch] || "not a lesson period").toLowerCase()} (${ch}) in the ${lv} Day structure`;
      else if (p >= (keepBy[d] ?? NP)) why = `is after ${endAt[d] || "the end time on Settings"}`;
      else continue;
      out.push(`Fixed lesson ${[r.target, r.subject].filter(Boolean).join(" ")} on ${d} at period ${p} (${at(p)}): that period ${why}, so it can never be met.`); break;
    }
  }
  return out;
}
function ensureRecessRows() {
  if (!hasWindows()) return false;
  const ex = sc().extra_settings = sc().extra_settings || []; let added = false;
  for (const r of RECESS_ROWS) if (!ex.some(x => String(x[0]).toLowerCase().startsWith(r[0].toLowerCase()))) { ex.push([...r]); added = true; }
  return added;
}
const isRecessRow = x => RECESS_ROWS.some(r => String(x[0]).toLowerCase().startsWith(r[0].toLowerCase()));
function settingRow(x, i) {   // one row of Settings below the rule rows, as a field
  const k = `spec.school.extra_settings.${i}.1`, lab = String(x[0]).toLowerCase();
  const field = lab.startsWith("lessons end by") ? `<span class="row" style="gap:6px;flex-wrap:nowrap">${inp(k, x[1], "time")}${x[1] ? `<button class="small" data-clear="${k}" title="Remove this end time: lessons may then use every L period of those days">✕</button>` : `<span class="muted small">no end time</span>`}</span>`   // trims the day: no lesson runs past this time on those days
    : lab.startsWith("students have no free periods") ? `<select data-k="${k}">${["Yes", "Prefer", "No"].map(v => opt(v, x[1])).join("")}</select>`
    : lab.startsWith("floating recess goes by") ? `<select data-k="${k}">${opt("Level", x[1], "Level: each level together")}${opt("Class", x[1], "Class: each class on its own")}</select>`
    : lab.startsWith("floating recess length") ? inp(k, x[1], "number", 'min="1" max="12"')
    : lab.startsWith("most classes at recess at once") ? inp(k, x[1], "number", 'min="1" placeholder="no limit"') : inp(k, x[1]);
  return `<label class="f" id="${isRecessRow(x) ? "school" : "config"}-${i}">${esc(x[0])} ${field}${x[2] ? `<span class="muted small">${esc(x[2])}</span>` : ""}</label>`;
}
function recessSetting(label) {   // [row index, value] of a floating recess row on Settings
  const ex = sc().extra_settings || [], i = ex.findIndex(x => String(x[0]).toLowerCase().startsWith(label.toLowerCase()));
  return [i, i >= 0 ? ex[i][1] : null];
}

/* ---------------- derived values (same logic as the workbook formulas) */
function split(p, L) { p = Number(p) || 0; L = Number(L) || 1; if (p <= 0) return [0, 0]; if (L <= 1) return [p, 0]; let s = ((-p % L) + L) % L; if (s * (L - 1) > p) s = 0; return [(p - s * (L - 1)) / L, s]; }
const patText = p => { const n = {}; p.forEach(v => n[v] = (n[v] || 0) + 1); return Object.keys(n).map(Number).sort((a, b) => b - a).map(v => `${n[v]}×${v}`).join(" + "); };
function parsePattern(t) {   // "5x3 + 2x2" or "3, 3, 2": the lesson lengths, longest first; null when it cannot be read (ttgen.reader.parse_pattern)
  const out = [];
  for (const part of String(t).trim().replace(/\s*[xX×*]\s*/g, "x").split(/[+,;\s]+/).filter(Boolean)) {
    const m = part.match(/^(?:(\d+)x)?(\d+)$/); if (!m || Number(m[2]) < 1 || (m[1] && Number(m[1]) < 1)) return null;
    for (let i = 0; i < Number(m[1] || 1); i++) out.push(Number(m[2]));
  }
  return out.length ? out.sort((a, b) => b - a) : null;
}
function lessonInfo() {
  const seq = {}; const letter = Object.fromEntries((sc().tags || []).map(([a, b]) => [a, b]));
  return S.spec.lessons.map(x => {
    const s = subj(x.subject) || {}; const p = Number(x.periods_override) || Number((s.periods || {})[x.level]) || 0;
    const L = Number(s.lesson_length) || Number(sc().lesson_length) || 1;
    const [full, short] = split(p, L), auto = p ? patText([...Array(full).fill(L), ...Array(short).fill(L - 1)]) : "", pat = (x.pattern || []).map(Number);   // pattern: lengths typed on this step or set on the Adjust page
    const lens = pat.length && pat.reduce((a, b) => a + b, 0) === p ? pat : [...Array(full).fill(L), ...Array(short).fill(L - 1)];
    let code = "";
    if (x.subject) {
      const k = `${x.level}|${x.subject}`; if (x.block) seq[k] = (seq[k] || 0) + 1;
      code = x.code_override ? String(x.code_override) : !x.block ? "Entire Class" : `${String(x.level).slice(-1)}${s.code || "??"}${letter[s.tag] || ""}${seq[k]}`;
    }
    const tp = p * (x.block ? 1 : Math.max(1, (x.classes || []).length));
    return { p, L, full, short, auto, lens, code, tp, kind: s.room_kind || (x.block || x.code_override ? "classroom" : "home room") };
  });
}
function teachingGroups(subject) {   // groups or classes taught this subject on step 5: a banded row is one group, a whole-class row one per class
  return S.spec.lessons.filter(x => x.subject === subject).reduce((n, x) => n + (x.block || x.code_override ? 1 : (x.classes || []).length), 0);
}
function canTeach(t, subject, level) { return DeptMap.canTeach(S.spec.teachers.find(x => x.name === t), subject, level, bands()); }
function issues() {
  const out = { school: {}, config: {}, lessons: {}, rules: {}, teachers: {}, blocks: {}, classes: {}, subjects: {}, venues: {}, students: {}, global: [] };
  // hard: no timetable can be made until it is fixed (critical). The rest are warnings: a timetable can still be made, but a person should look.
  const crit = new Set(), add = (k, i, m, hard) => { (out[k][i] = out[k][i] || []).push(m); if (hard) crit.add(`${k}|${i}|${m}`); };
  (sc().extra_settings || []).forEach((x, i) => {   // 'Lessons end by (...)' rows on Settings
    if (!String(x[0]).toLowerCase().startsWith("lessons end by") || x[1] == null || x[1] === "") return;   // blank: no end time on those days
    if (!/^\d{1,2}:\d{2}$/.test(String(x[1]))) { add("config", i, `${x[0]}: give a time such as 12:40, or clear it for no end time.`, true); return; }
    if (Math.floor((mins(x[1]) - mins(sc().start_time)) / Number(sc().period_minutes || 20)) <= 0) add("config", i, `${x[0]}: ${x[1]} is before the first period ends, so no lesson fits on those days.`, true);
  });
  if (hasWindows()) {   // floating recess: windows long enough, and the canteen limit not ruled out from the start
    const [li, len] = recessSetting("Floating recess length"), [ci, cap] = recessSetting("Most classes at recess at once"), [bi, by] = recessSetting("Floating recess goes by");
    const RL = Math.max(1, Number(len) || 2), at = {}, short = [];
    for (const [lv, days] of Object.entries(S.spec.day_structure)) {
      const n = S.spec.classes.filter(c => c.level === lv).length;
      Object.entries(days).forEach(([d, row]) => {
        for (const m of String(row).matchAll(/W+/g)) if (m[0].length < RL) short.push(`${lv} ${d}`);
        [...String(row)].forEach((ch, p) => { if (ch === "R") at[`${d}|${p}`] = (at[`${d}|${p}`] || 0) + n; });
      });
      if (Number(cap) && String(by || "Level").startsWith("L") && n > Number(cap) && Object.values(days).some(r => String(r).includes("W")))
        add("school", bi, `${lv} has ${n} classes and its recess goes by level, so ${n} are at recess at once: more than the ${cap} allowed. Pick Class, or raise Most classes at recess at once.`, true);
    }
    if (short.length) add("school", li, `The recess window on ${short[0]}${short.length > 1 ? ` and ${short.length - 1} more` : ""} is shorter than the ${RL}-period recess: widen the W periods, or shorten the recess.`, true);
    const worst = Object.entries(at).sort((a, b) => b[1] - a[1])[0];
    if (Number(cap) && worst && worst[1] > Number(cap)) add("school", ci, `${worst[1]} classes have their fixed recess (R) together on ${worst[0].split("|")[0]} period ${worst[0].split("|")[1]}, more than the ${cap} allowed at once.`, true);
  }
  structureWarnings().forEach((m, k) => m.startsWith("Fixed lesson")   // the Day structure and the rules saying different things: warnings,
    ? add("rules", `ds${k}`, m, true) : add("school", `ds${k}`, m));   // except a fixed lesson outside lesson time, which no timetable can meet
  const info = lessonInfo(); const codes = {};
  info.forEach((x, i) => { if (x.code && x.code !== "Entire Class") codes[x.code] = (codes[x.code] || 0) + 1; });
  S.spec.lessons.forEach((x, i) => {
    if (!x.subject) { add("lessons", i, "Pick a subject."); return; }
    if (!info[i].p) add("lessons", i, `No periods for ${x.level} on Subjects.`);
    if (!(x.classes || []).length) add("lessons", i, "No class.");
    if (!(x.teachers || []).filter(Boolean).length) add("lessons", i, "No teacher.");
    for (const t of (x.teachers || []).filter(Boolean)) {
      if (!canTeach(t, x.subject, x.level)) add("lessons", i, `${t} is not set to teach this at ${x.level}.`);
      if (x.block && S.spec.lessons.filter(y => y.block === x.block && (y.teachers || []).includes(t)).length > 1) add("lessons", i, `${t} twice in this band: a band's groups meet at the same time, so no timetable can be made.`, true);
    }
    if (x.block && !blockNames().includes(x.block)) add("lessons", i, "Band not on the Bands list (top of step 5).");
    if (x.pattern_text) add("lessons", i, `Could not read the lesson pattern "${x.pattern_text}". Write it like 5x3 + 2x2, or clear it.`);
    if ((x.pattern || []).length) {
      const t = x.pattern.reduce((a, v) => a + Number(v), 0), most = Math.max(...x.pattern.map(Number));
      if (t !== info[i].p) add("lessons", i, `${info[i].code}: lessons ${patText(x.pattern.map(Number))} add up to ${t} periods, but this row has ${info[i].p}. Until they match, the usual ${info[i].auto} is used.`);
      else if (most > Number(sc().periods_per_day)) add("lessons", i, `${info[i].code}: a ${most}-period lesson is longer than the ${sc().periods_per_day}-period day.`, true);
      else if (x.block) {   // a band's groups share its lessons, so a length the others do not have adds a slot for the whole band
        const tally = l => { const n = {}; l.forEach(v => n[v] = (n[v] || 0) + 1); return n; }, others = {};
        S.spec.lessons.forEach((y, j) => { if (j !== i && y.block === x.block) Object.entries(tally(info[j].lens)).forEach(([v, c]) => others[v] = Math.max(others[v] || 0, c)); });
        if (Object.keys(others).length && Object.entries(tally(info[i].lens)).some(([v, c]) => c > (others[v] || 0)))
          add("lessons", i, `${info[i].code}: ${patText(info[i].lens)} has lessons the other groups in ${x.block} do not, so the band takes extra slots and those groups' students have nothing on then. Give the band's groups the same pattern.`);
      }
    }
    if (!x.block && !x.code_override && Number(x.students) > 0) {   // fewer students than its classes, yet no band or code: it is taken as the whole class
      const size = (x.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
      if (size && Number(x.students) < size) add("lessons", i, `${x.subject}: ${x.students} of the ${size} students in ${(x.classes || []).join(", ")}, but with no band or code it is a lesson for the whole class. Pick its band, or enter Students again to give it a group code.`);
    }
    if (codes[info[i].code] > 1) add("lessons", i, "Code used twice.");
  });
  const load = {}; S.spec.lessons.forEach((x, i) => (x.teachers || []).filter(Boolean).forEach(t => load[t] = (load[t] || 0) + info[i].tp));
  S.spec.teachers.forEach((t, i) => {
    const tot = (load[t.name] || 0) + (Number(t.other_duties) || 0);
    if (t.allowance && tot > Number(t.allowance)) add("teachers", i, `${t.name}: load ${tot} (${load[t.name] || 0} lessons${t.other_duties ? ` + ${t.other_duties} other duties` : ""}), allowance ${t.allowance}.`);
    if (!t.name) add("teachers", i, "Name missing.");
  });
  S.spec.classes.forEach((c, i) => { if (c.home_room && !rooms().includes(c.home_room)) add("classes", i, `${c.class}: home room ${c.home_room} is not on Venues.`); });
  S.spec.blocks.forEach((b, i) => {
    const gs = S.spec.lessons.map((x, j) => [x, j]).filter(([x]) => x.block === b.block);
    if (!gs.length) add("blocks", i, `${b.block}: no groups yet (add them under Teaching groups).`);
    if (!(b.classes || []).length) add("blocks", i, `${b.block}: no classes. Pick the classes its groups take students from, or use Restore from an earlier copy on the Students step.`);
    const inG = gs.reduce((a, [x]) => a + (Number(x.students) || 0), 0), inC = (b.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
    if (gs.length && inG > inC) add("blocks", i, `${b.block}: ${inG} students in groups but ${inC} in its classes.`);
    else if (everyone(b) && gs.length && inC && inG < inC && gs.every(([x]) => Number(x.students) > 0) && !S.spec.students.some(s => (b.classes || []).includes(s.class)))   // with a student list, each student is checked instead
      add("blocks", i, `${b.block}: its groups are planned for ${inG} students but its classes have ${inC}, so ${inC - inG} ${inC - inG === 1 ? "is" : "are"} in none of them.`);
  });
  S.spec.subjects.forEach((s, i) => { if (!Object.values(s.periods || {}).some(Number)) add("subjects", i, `${s.subject || "Subject"}: no periods for any level.`); });
  ruleProblems(info).forEach(([i, m, hard]) => add("rules", i, m, hard));
  // rooms: 'For' names a subject, department or level; each group fits some room it may use; a home room seats its class
  const forOk = new Set(forNames());
  S.spec.venues.forEach((v, i) => { const bad = (v.only_for || []).filter(n => !forOk.has(n)); if (bad.length) add("venues", i, `${v.room}: For ${bad.join(", ")}: not a subject, department or level.`); });
  S.spec.lessons.forEach((x, i) => {
    if (!x.subject) return;
    const s = subj(x.subject) || {}, kind = s.room_kind || "classroom";
    if (x.room_weeks && !special(x)) add("lessons", i, "Special room weeks only applies to a subject with a special room kind, such as a lab (step 3).");
    const rooms = roomsFor(x, kind);
    if (!rooms.length) { if (s.room_kind && S.spec.venues.some(v => (v.kind || "classroom") === kind)) add("lessons", i, `Every ${kind} on Venues is kept for other subjects, departments or levels.`); return; }
    const most = Math.max(...rooms.map(v => Number(v.capacity) || 0)); if (!most) return;
    const sizes = !x.block && !x.code_override ? (x.classes || []).map(c => [c, groupSize(x, c, "Entire Class")]) : [[info[i].code, groupSize(x, null, info[i].code)]];
    const big = sizes.filter(([, n]) => n && n > most);
    if (big.length) add("lessons", i, `${big.map(([w, n]) => `${w}: ${n} students`).join(", ")}, but the largest ${kind} it may use seats ${most} (Venues). Correct the seats, or split the group.`);
  });
  S.spec.classes.forEach((c, i) => { const v = S.spec.venues.find(v => v.room === c.home_room); if (v && Number(v.capacity) && Number(c.size) > Number(v.capacity)) add("classes", i, `${c.class} has ${c.size} students but its home room ${v.room} seats ${v.capacity}.`); });
  // students: each one's groups must exist, be for their class, and take at most one group of a block (a block runs at one time)
  const gc = {}; S.spec.lessons.forEach((x, i) => { if (info[i].code && info[i].code !== "Entire Class") gc[info[i].code] = x; });
  const ids = {}, per = {}; S.spec.students.forEach((s, i) => { const k = stuKey(s); if (k) ids[k] = (ids[k] || 0) + 1; if (s.class) (per[s.class] = per[s.class] || []).push(i); });
  S.spec.students.forEach((s, i) => {
    const who = stuKey(s) || `Row ${i + 1}`;
    if (!stuKey(s)) add("students", i, `Row ${i + 1}: no student ID or name.`);
    else if (ids[who] > 1) add("students", i, `${who}: this ID is on the list twice (personal codes are made from the ID).`);
    if (!s.class) add("students", i, `${who}: no class.`); else if (!classNames().includes(s.class)) add("students", i, `${who}: class ${s.class} is not on step 2.`);
    const inBlock = {};
    for (const g of s.groups || []) {
      const x = gc[g]; if (!x) { add("students", i, `${who}: group ${g} is not on step 5.`); continue; }
      if (s.class && !(x.classes || []).includes(s.class)) add("students", i, `${who}: group ${g} is not for class ${s.class}.`);
      if (x.block) (inBlock[x.block] = inBlock[x.block] || []).push(g);
    }
    for (const [b, gs] of Object.entries(inBlock)) if (gs.length > 1) add("students", i, `${who}: ${gs.join(" and ")} are both in ${b}, so they clash.`);
  });
  // every listed student is in one group of each band over their class (the class splits into its groups, so a student in
  // none of them misses that subject), unless their Note says they are exempt from it ("Exempt: Mother Tongue", "exempt MTL")
  const bandCls = {}, bandFam = {};
  S.spec.lessons.forEach(x => {
    if (!x.block) return; const b = x.block;
    const bb = S.spec.blocks.find(y => y.block === b) || { block: b }; if (!everyone(bb)) return;
    if (!bandCls[b]) { bandCls[b] = new Set(bb.classes || []); bandFam[b] = new Set(); }
    (x.classes || []).forEach(c => bandCls[b].add(c)); bandFam[b].add(family(x.subject));
  });
  const missing = {}, none = {};
  S.spec.students.forEach((s, i) => {
    if (!s.class || !classNames().includes(s.class)) return;
    if (!(s.groups || []).length) { (none[s.class] = none[s.class] || []).push(i); return; }
    const has = new Set(s.groups.map(g => (gc[g] || {}).block).filter(Boolean)), fams = new Set(s.groups.map(g => family((gc[g] || {}).subject)));
    for (const [b, cs] of Object.entries(bandCls))   // in another band for the same subject (3I8's G1 English, say) counts
      if (cs.has(s.class) && !has.has(b) && ![...bandFam[b]].some(f => fams.has(f)) && !exemptFrom(s.note, b)) (missing[b] = missing[b] || []).push(i);
  });
  const names = l => l.slice(0, 6).map(i => `${stuKey(S.spec.students[i]) || `Row ${i + 1}`} (${S.spec.students[i].class})`).join(", ") + (l.length > 6 ? ` and ${l.length - 6} more` : "");
  for (const [b, l] of Object.entries(missing))
    add("students", l[0], `${b}: ${l.length} student${l.length === 1 ? " is" : "s are"} in none of its groups, so ${l.length === 1 ? "has" : "have"} none of its lessons: ${names(l)}. Pick their group, or "exempt" for a student not taking it (in their groups, on the Students step), or untick Everyone takes one for the band if it is an option.`);
  for (const [c, l] of Object.entries(none))
    add("students", l[0], `${c}: ${l.length} student${l.length === 1 ? " has" : "s have"} no groups yet, so only the class's whole-class lessons: ${names(l)}.`);
  S.spec.classes.forEach(c => {
    const l = per[c.class], size = Number(c.size) || 0; if (!l || !size) return;
    if (l.length < size) add("students", l[0], `${c.class}: ${l.length} of ${size} students listed. Once a class has a list, only the students on it are checked for clashes.`);
    if (l.length > size) add("students", l[0], `${c.class}: ${l.length} students listed but the class has ${size} on step 2.`);
  });
  return { out, load, info, crit };
}
const isCrit = (C, k, i, m) => C.has(`${k}|${i}|${m}`);
/* a row's colour in the step tables: red when one of its problems is critical, amber when it has only warnings */
const rowCls = (out, crit, k, i) => !out[k][i] ? "" : out[k][i].some(m => isCrit(crit, k, i, m)) ? "bad" : "caution";
const stuKey = s => String(s.id || s.name || "").trim();
function targetOptions(scope) {
  return { School: ["Whole school"], Level: levels(), Class: classNames(), Teacher: teacherNames(), Department: sc().departments || [], Subject: subjectNames(), Block: blockNames(),
    Group: groupCodes(), Room: rooms() }[scope] || [];
}
/* ---------------- rule rows the solver cannot use as written, and fixed lessons no timetable can meet (as
   ttgen.solver.rule_problems and fixed_clashes): [[rule index, message, critical]] */
const UNIT_RULES = new Set(["Fixed at", "Not in periods", "Only in periods", "Finish by", "Only these subjects", "Only in venues", "Not available", "Keep free together"]);
function ruleRows(r, info, anySubject) {   // the step 5 rows a rule covers (as ttgen.solver.units_for)
  const t = r.target, sj = anySubject ? null : r.subject;
  const bandCls = x => x.block ? ((S.spec.blocks.find(b => b.block === x.block) || {}).classes || []) : [];
  return S.spec.lessons.map((x, j) => [x, j]).filter(([x, j]) => {
    if (!x.subject) return false;
    if (r.scope === "Subject") return x.subject === t;
    if (r.scope === "Block") return x.block === t;
    if (r.scope === "Group") return info[j].code === t;
    if (sj && x.subject !== sj) return false;
    const cls = [...(x.classes || []), ...bandCls(x)];
    if (r.scope === "Class") return cls.includes(t);
    if (r.scope === "Level") return x.level === t || cls.some(c => clsLevel(c) === t);
    return r.scope === "School";
  });
}
function unitsOf(rows, info) {   // what the solver places as one: a band, a group with its own code, or one class's whole-class lesson
  const U = new Map();
  for (const [x, j] of rows) {
    const keys = x.block ? [[`B:${x.block}`, x.block]] : x.code_override ? [[`G:${info[j].code}`, info[j].code]] : (x.classes || []).map(c => [`C:${c}:${x.subject}`, `${c} ${x.subject}`]);
    const src = x.block ? S.spec.lessons.filter(y => y.block === x.block) : [x];
    for (const [k, name] of keys) {
      if (!U.has(k)) U.set(k, { name, teachers: new Set(), classes: new Set(), lessons: 0 });
      const u = U.get(k); u.lessons = Math.max(u.lessons, ...src.map(y => (info[S.spec.lessons.indexOf(y)] || {}).lens || []).map(l => l.length));   // a band's groups share its lessons
      src.forEach(y => (y.teachers || []).filter(Boolean).forEach(t => u.teachers.add(t)));
      if (x.block) [...((S.spec.blocks.find(b => b.block === x.block) || {}).classes || []), ...src.flatMap(y => y.classes || [])].forEach(c => u.classes.add(c));
      else if (k.startsWith("G:")) (x.classes || []).forEach(c => u.classes.add(c));
      else u.classes.add(k.split(":")[1]);
    }
  }
  return U;
}
function ruleProblems(info) {
  const out = [], RT = S.meta.rule_types || [], sd = S.spec.subjects.filter(s => s.subject).map(s => [s.subject, s.dept]);
  const roomKind = Object.fromEntries(S.spec.venues.filter(v => v.room).map(v => [v.room, v.kind || "classroom"])), kindOf = n => (subj(n) || {}).room_kind || "classroom";
  const NP = Number(sc().periods_per_day), days = dayNames(), fixedAt = new Map();   // start -> the units fixed to start there, and the rules that do it
  S.spec.rules.forEach((r, i) => {
    const say = m => out.push([i, m, false]), rt = RT.find(x => x.rule === r.rule);
    if (!rt) { say(r.rule ? `'${r.rule}' is not a rule the timetable knows, so this row is skipped. Pick one from the Rule list.` : "Pick a rule: without one this row is skipped."); return; }
    const can = scopesOf(rt), scope = String(r.scope || "").toLowerCase();
    if (!can.includes(r.scope)) { say(`${r.rule} cannot apply to ${r.scope ? `a ${scope}` : "nothing"}; it applies to ${can.join(", ")}. This row is skipped.`); return; }
    if (!r.target) { say(`Pick the ${scope}: without one this row matches nothing.`); return; }
    if (!targetOptions(r.scope).includes(r.target)) { say(`${r.target} is not a${/^[aeiou]/.test(scope) ? "n" : ""} ${scope} on the setup, so this row matches nothing.${r.scope === "Level" ? " For every level, apply it to School." : ""}`); return; }
    if (r.rule === "Only these subjects") {
      const names = namesList(r.subject), bad = names.filter(n => !sd.some(([s, d]) => subjectTest(n)(s, d)));
      if (!names.length) { say("List the subjects allowed in those periods under Subject. Without them this row does nothing."); return; }
      if (bad.length) say(`${bad.join(", ")}: not a subject or department on the setup, so ${bad.length === 1 ? "it matches" : "they match"} nothing.`);
    } else if (r.subject && !subjectNames().includes(r.subject)) {
      say(`Subject '${r.subject}' is not on step 3 (Subjects), so this row matches nothing.${/,|except/i.test(r.subject) ? " For a day when only some subjects are taught (an HBL day), use the rule Only these subjects and list them." : ""}`); return;
    }
    if (r.rule === "Fixed at" && ["Level", "School"].includes(r.scope) && !r.subject) { say("Pick the subject: a fixed lesson for every class needs one (without it this row is skipped)."); return; }
    if (["Same time across classes", "Not on the same day as"].includes(r.rule) && !r.subject) { say("Pick the Subject."); return; }
    const blank = v => v == null || v === "";
    if (rt.needs_time && !["Only these subjects", "Only in venues"].includes(r.rule) && blank(r.from) && blank(r.to)) say("Give the period(s).");
    if (!blank(r.from) && !blank(r.to) && Number(r.to) < Number(r.from)) say(`${r.target}: the end is before the start.`);
    if (r.rule === "Finish by" && blank(r.to)) say("Finish by uses the To period (the last period lessons may use), and it is blank, so this row changes nothing.");
    if (rt.needs_number && !r.number) say("Give the Number.");
    if (!["Must", "Prefer"].includes(r.strength || "Must")) say(`Must / Prefer is '${r.strength}': read as Prefer. Pick Must or Prefer.`);
    if (r.rule === "Only in venues") {
      const vs = namesList(r.venues), unknown = vs.filter(v => !(v in roomKind));
      if (!vs.length) { say("Pick the rooms under Venues. Without them this row is skipped."); return; }
      if (unknown.length) say(`${unknown.join(", ")}: not on step 1 (Venues).`);
    }
    if (!UNIT_RULES.has(r.rule) || ["Teacher", "Room", "Department"].includes(r.scope)) return;
    let rows = ruleRows(r, info, r.rule === "Only these subjects");
    if (r.rule === "Only in venues") {
      const sj = r.scope === "Subject" ? r.target : r.subject; rows = rows.filter(([x]) => !sj || x.subject === sj);
      const V = namesList(r.venues).filter(v => v in roomKind), kinds = [...new Set(rows.map(([x]) => kindOf(x.subject)))];
      if (rows.length && V.length && !V.some(v => kinds.includes(roomKind[v])))
        say(`None of ${V.join(", ")} is a room these lessons may use (they need a ${kinds.join(" or ")} room on step 1), so ${(r.strength || "Must") === "Must" ? "they cannot run in those periods" : "this row changes nothing"}.`);
    }
    if (!rows.length) { say(`No lesson on step 5 matches ${r.subject && r.scope !== "Subject" && r.rule !== "Only these subjects" ? `${r.target} ${r.subject}` : r.target}, so this row does nothing.`); return; }
    if (r.rule === "Fixed at" && (r.day || "All") !== "All" && !blank(r.from)) {
      const wk = String(r.week || "Both"), dy = String(r.day).slice(0, 3);
      days.forEach((d, di) => {
        if ((["Odd", "Even"].includes(wk) && !d.startsWith(wk)) || d.split(" ").pop().slice(0, 3) !== dy) return;
        const q = di * NP + Number(r.from); if (!fixedAt.has(q)) fixedAt.set(q, { units: new Map(), rules: [] });
        const F = fixedAt.get(q); F.rules.push(i); unitsOf(rows, info).forEach((u, k) => F.units.set(k, u));
      });
    }
  });
  // one teacher, or one class, with two lessons fixed to start at the same time; a lesson fixed at more times than it has lessons
  const when = q => `${days[Math.floor(q / NP)]} ${ampm(mins(sc().start_time) + (q % NP) * Number(sc().period_minutes || 20))}`;
  const clash = new Map(), need = new Map(), put = (M, k, v, i) => { if (!M.has(k)) M.set(k, { v: [], i }); M.get(k).v.push(v); };
  for (const [q, F] of [...fixedAt].sort((a, b) => a[0] - b[0])) {
    F.units.forEach((u, k) => { if (!need.has(k)) need.set(k, { u, qs: new Set(), i: F.rules[0] }); need.get(k).qs.add(q); });
    if (F.units.size < 2) continue;
    const T = {}, C = {};
    [...F.units.values()].sort((a, b) => a.name.localeCompare(b.name)).forEach(u => { u.teachers.forEach(t => (T[t] = T[t] || []).push(u.name)); u.classes.forEach(c => (C[c] = C[c] || []).push(u.name)); });
    for (const [t, names] of Object.entries(T)) if (names.length > 1) put(clash, `T|${t}|${names.join("|")}`, when(q), F.rules[0]);
    for (const [c, names] of Object.entries(C)) if (names.length > 1) put(clash, `C|${c}|${names.join("|")}`, when(q), F.rules[0]);
  }
  for (const [k, { v, i }] of clash) {
    const [kind, who, ...names] = k.split("|");
    out.push([i, kind === "T" ? `${who} teaches ${listing(names)}, but fixed lessons start ${names.length === 2 ? "both" : "them all"} at ${listing(v)}: no timetable can do that. Give those classes different teachers for it (step 5), or fix them at different times (step 6).`
      : `${who} has ${listing(names)} fixed to start at the same time (${listing(v)}): no timetable can do that. Fix them at different times (step 6).`, true]);
  }
  const few = new Map();
  need.forEach(({ u, qs, i }) => { const n = u.lessons; if (qs.size > n) put(few, `${n}|${[...qs].sort((a, b) => a - b).join(",")}`, u.name, i); });
  for (const [k, { v, i }] of few) {
    const [n, qs] = k.split("|"), one = v.length === 1, ws = qs.split(",").map(Number);
    out.push([i, `${listing(v.sort())} ${one ? "has" : "each have"} ${n} lesson${n === "1" ? "" : "s"} a cycle, but fixed lessons start ${one ? "it" : "each"} at ${ws.length} times (${listing(ws.map(when))}): no timetable can do that. Fix ${one ? "it" : "them"} on fewer days (Week Odd or Even rather than Both), or give more lessons.`, true]);
  }
  return out;
}

/* ---------------- small builders */
const opt = (v, cur, label) => `<option value="${esc(v)}"${String(v) === String(cur ?? "") ? " selected" : ""}>${esc(label ?? v)}</option>`;
const sel = (path, cur, list, blank = true, extra = "") => `<select data-k="${path}" ${extra}>${blank ? opt("", cur, "") : ""}${list.map(v => opt(v, cur)).join("")}${cur && !list.includes(cur) ? opt(cur, cur, cur + " (not on list)") : ""}</select>`;
const inp = (path, cur, type = "text", extra = "") => `<input data-k="${path}" type="${type}" value="${esc(cur)}" ${extra}>`;
const chips = (path, arr, what, extra = "") => `<div class="chips" data-pop="${what}" data-path="${path}" ${extra}>${(arr || []).length ? arr.map(a => `<span class="chip">${esc(a)}</span>`).join("") : '<span class="muted">pick…</span>'}</div>`;
const delBtn = (k, i) => `<button class="small danger" data-del="${k}.${i}" title="Remove row">✕</button>`;
function getPath(p) { return p.split(".").reduce((o, k) => (o == null ? o : o[k]), S); }
function setPath(p, v) { const ks = p.split("."); const last = ks.pop(); const o = ks.reduce((o, k) => o[k], S); o[last] = v; }

/* ---------------- render */
function render() {
  const nav = $("#steps");
  if (!stepShown(S.step)) S.step = Math.min(1, STEPS.length - 1);   // a head never lands on a hidden step
  nav.innerHTML = STEPS.map(([id, label], i) => !stepShown(i) ? "" : `<button data-step="${i}" class="${i === S.step ? "on" : ""}" ${!S.spec && i > 0 ? "disabled" : ""}><span>${label}</span><span class="n">${count(id)}</span></button>`).join("");
  $("#kindBadge").textContent = S.spec ? `${sc().type === "primary" ? "Primary" : "Secondary"} · ${sc().name}` : "No school yet";
  const id = S.asking ? "_old" : STEPS[S.step][0]; const main = $("#main"); const y = window.scrollY;
  // on a redraw of the same step, keep where each table was scrolled to (they scroll inside their own box) and the field in use
  const same = G.shown === id, boxes = same ? [...main.querySelectorAll(".tablewrap, .keep")].map(t => [t.scrollTop, t.scrollLeft]) : [];
  const f = same && main.contains(document.activeElement) ? document.activeElement : null, fk = f && (f.id ? `#${CSS.escape(f.id)}` : f.dataset.k ? `[data-k="${CSS.escape(f.dataset.k)}"]` : "");
  G.shown = id;
  main.innerHTML = (S.practice && !S.asking ? `<div class="practice"><span>Practice copy: nothing here is saved for the school.</span><button id="practiceBack">Back to the school's setup</button></div>` : "") + (VIEWS[id] || (() => ""))();
  headLocks(main, id);
  main.querySelectorAll(".tablewrap, .keep").forEach((t, i) => { if (boxes[i]) [t.scrollTop, t.scrollLeft] = boxes[i]; });
  if (fk) { const el = main.querySelector(fk); if (el) el.focus({ preventScroll: true }); }
  renderIssues(); saveState(); window.scrollTo(0, y);
  paintPublished();
  if (id === "download") fitCheck();
}
const stepAt = id => STEPS.findIndex(s => s[0] === ({ blocks: "lessons", config: "rules" }[id] || id));   // bands are a card on the teaching-groups step; the settings open step 6
function count(id) { if (!S.spec) return ""; const m = { venues: "venues", classes: "classes", subjects: "subjects", teachers: "teachers", blocks: "blocks", lessons: "lessons", rules: "rules", students: "students" }[id]; return m ? S.spec[m].length : ""; }
function renderIssues() {
  const el = $("#issues"); if (!S.spec) { el.innerHTML = ""; return; }
  const { out, crit } = issues();
  // students are added after the timetable is made, class by class, so their checks wait on the Students step
  const all = []; for (const [k, rows] of Object.entries(out)) if (k !== "global" && k !== "students") for (const [i, ms] of Object.entries(rows)) for (const m of ms) all.push([k, i, m]);
  const hard = all.filter(([k, i, m]) => isCrit(crit, k, i, m)), soft = all.filter(([k, i, m]) => !isCrit(crit, k, i, m));
  const list = (items, cls) => items.slice(0, 60).map(([k, i, m]) => `<div class="issue ${cls}" data-go="${stepAt(k)}" data-row="${k}-${i}">${esc(m)}</div>`).join("") + (items.length > 60 ? `<div class="muted">…and ${items.length - 60} more</div>` : "");
  const nStu = Object.values(out.students).reduce((a, ms) => a + ms.length, 0);
  el.innerHTML = `<div class="card"><h2>Things to fix</h2>${!all.length ? '<div class="okmsg">Nothing to fix. The template is consistent.</div>' : ""}
    ${hard.length ? `<h3 class="sev crit">Critical · ${hard.length}</h3><p class="muted small">No timetable can be made until these are fixed.</p>${list(hard, "crit")}` : all.length ? '<div class="okmsg">Nothing critical: a timetable can be made.</div>' : ""}
    ${soft.length ? `<h3 class="sev">Warnings · ${soft.length}</h3><p class="muted small">A timetable can still be made; a person should check these (rooms, loads, rows left out).</p>${list(soft, "soft")}` : ""}
    ${nStu ? `<p class="muted small" style="margin-top:8px">${nStu} note${nStu === 1 ? "" : "s"} on the student list wait on the Students step: students are added after the timetable is made.</p>` : ""}</div>`;
}


function exportCard() {
  return `<div class="card" id="printouts"><h2>Publish the finished timetable</h2><p class="muted">Upload the timetable the chatbot made, with its setup workbook. The timetable can be a workbook with a Lessons sheet or a timetable database (.sqlite); a database made by this app or the skill holds its setup, so it can come on its own.</p>
    <p class="muted"><b>Make printouts</b> gives you every timetable as PDFs (one page per class, teacher, room and student), one Excel file with them all, a searchable HTML page and the database, to keep or share. <b>Check, then publish</b> checks it against its setup and shows what it found; if you are happy, publish it and teachers and students see it straight away.</p>
    <div class="row" style="margin-top:10px"><label class="filebtn">Setup workbook (.xlsx)<input type="file" id="exSetup" accept=".xlsx" hidden></label><span class="muted" id="exSetupName">none chosen</span></div>
    <div class="row" style="margin-top:8px"><label class="filebtn">Timetable (.xlsx or .sqlite)<input type="file" id="exTT" accept=".xlsx,.sqlite,.sqlite3,.db" hidden></label><span class="muted" id="exTTName">none chosen</span></div>
    <div class="row" style="margin-top:10px"><label><input type="checkbox" id="exSingle" checked> Also a separate PDF for every class, teacher, room and student</label></div>
    <div class="row" style="margin-top:12px"><button class="primary" id="exGo">Make printouts (.zip)</button><button id="imCheck">Check, then publish</button><span class="muted" id="exMsg"></span></div>
    <div id="imResult"></div></div>`;
}
const VIEWS = {
  start() {
    const how = `<div class="card"><h2>How it works</h2><ol class="howto"><li>Fill the steps on the left. The panel on the right lists anything that does not add up (a teacher not set up for a subject, a teacher twice in a band, a lesson with no periods).</li><li>On <b>Download</b>, get the setup workbook and the timetable skill, and give both to an AI agent: it makes the timetable.</li><li>On <b>Publish</b>, upload the timetable it hands back, check it and publish. Teachers and students then sign in with their codes.</li></ol></div>`;
    const samples = `<button data-begin="secondary|sample"><b>Secondary school · sample</b><span class="muted">A fictional 16-class secondary school with G1/G2/G3 banding, option bands and rules. Opens as a practice copy: nothing is saved for the school.</span></button>
        <button data-begin="primary|sample"><b>Primary school · sample</b><span class="muted">A fictional 18-class primary school, weekly timetable, Standard/Foundation banding at P5–P6. Opens as a practice copy: nothing is saved for the school.</span></button>`;
    const blanks = `<button data-begin="secondary|blank"><b>Secondary school · blank</b><span class="muted">Typical subjects and a day shape filled in; you add rooms, classes, teachers and lessons.</span></button>
        <button data-begin="primary|blank"><b>Primary school · blank</b><span class="muted">Typical subjects and day shape for P1–P6; you add the rest.</span></button>`;
    const workbook = `<div class="row" style="margin-top:14px"><label class="filebtn">Open a setup workbook (.xlsx)<input type="file" id="importX" accept=".xlsx" hidden></label></div>`;
    if (S.practice) return `<div class="card"><h1>Practice copy</h1><p class="lead">A sample school to try the steps on. Change anything: nothing here is saved for the school, and nobody else sees it. The school's setup is as you left it.</p>
      <div class="choice">${samples}</div></div>${how}`;
    if (!S.spec) return committee()
      ? `<div class="card"><h1>Build your school's timetable setup</h1><p class="lead">This tool fills the timetable setup workbook step by step: rooms, classes, subjects, teachers, bands of groups, lessons, rules and students. Every list you make becomes the drop-down for the next step, so nothing is typed twice. At the end you download the workbook and the timetable skill, and an AI agent generates the timetable from them.</p>
      <p class="muted">The school has no setup yet. Start one blank or open a workbook: it is saved for the school, and everyone on the committee and the department heads work in it together.</p>
      <div class="choice">${blanks}${samples}</div>${workbook}</div>${how}`
      : `<div class="card"><h1>The school's timetable setup</h1><p class="lead">The committee has not started the setup yet.</p>
      <h2>Try things out</h2><p class="muted">A sample school as a practice copy: nothing in it is saved for the school.</p><div class="choice">${samples}</div></div>${how}`;
    const s = sc();
    return `<div class="card"><h1>The school's timetable setup</h1><p class="lead">Everyone works in this one setup together: each change is saved for the school as it is made.</p>
      <div><span class="stat">School <b>${esc(s.name || "no name yet")}</b></span><span class="stat">Timetable <b>${esc(s.timetable || "no name yet")}</b></span><span class="stat" id="startOthers">${SYNC.others ? (SYNC.others === 1 ? "1 other here" : `${SYNC.others} others here`) : "Nobody else is here now"}</span></div>
      <div class="row" style="margin-top:12px"><button class="primary" data-step="1">Open School & day</button></div></div>
      ${committee() ? `<div class="card"><h2>Replace the whole setup</h2><p class="muted">Each of these replaces the school's setup for everyone; an earlier copy is kept, and <b>7 Download</b> can restore it. Loading a progress file is on 7 Download too.</p>
      <div class="choice">${blanks}</div>${workbook}</div>` : ""}
      <div class="card"><h2>Try things out</h2><p class="muted">A sample school as a practice copy: nothing in it is saved for the school.</p><div class="choice">${samples}</div></div>${how}`;
  },
  _old() {   // the rollout question, before anything else
    return `<div class="card"><h1>Changes from before</h1><p class="lead">This browser has changes from before that were never saved for the school.</p>
      <p class="muted">They are from ${esc((S.asking.spec.school || {}).name || "a setup")}. Save them to a file to keep them${committee() ? ", use them as the school's setup (the school's setup now is kept as an earlier copy)" : ""}, or discard them.</p>
      <div class="row" style="margin-top:12px"><button class="primary" data-old="file">Save them to a file</button>${committee() ? `<button data-old="use">Use them</button>` : ""}<button data-old="discard">Discard them</button></div></div>`;
  },
  school() {
    const s = sc(); const NP = Number(s.periods_per_day); const days = dayNames();
    const head = `<tr><th></th>${Array.from({ length: NP }, (_, p) => `<th class="t">${p} · ${clock(p)}</th>`).join("")}</tr>`;
    const lvRows = levels().map(lv => `<tr><th colspan="${NP + 1}" style="text-align:left;background:#fff">${esc(lv)} <button class="small" data-copyday="${esc(lv)}">Copy first day to all days</button> <button class="small" data-copylevel="${esc(lv)}">Copy to all levels</button></th></tr>` +
      days.map(d => `<tr><th style="text-align:left">${esc(d)}</th>${Array.from({ length: NP }, (_, p) => { const c = (S.spec.day_structure[lv][d] || "")[p]; const v = c === "." ? "" : c; return `<td class="c c-${v}" data-cell="${esc(lv)}|${esc(d)}|${p}">${v}</td>`; }).join("")}</tr>`).join("")).join("");
    return `<div class="card"><h1>School and school day</h1><p class="lead">Basic settings, then what each period is for each level and day. Lessons can only go in <b>L</b> periods; <b>A</b> periods are an after-school slot used only when a class cannot fit. <b>W</b> is a recess window: the solver puts the recess somewhere in it (for each level together, or for each class, as set below) and the rest of the window is lesson time.</p>
      <div class="grid2">
        <label class="f">School name ${inp("spec.school.name", s.name)}</label>
        <label class="f">Timetable ${inp("spec.school.timetable", s.timetable)}</label>
        <label class="f">Cycle <select data-k="spec.school.weeks">${opt(1, s.weeks, "1 week")}${opt(2, s.weeks, "2 weeks (Odd, Even)")}</select></label>
        <label class="f">Period length (minutes) ${inp("spec.school.period_minutes", s.period_minutes, "number", 'min="5" max="90"')}</label>
        <label class="f">Period 0 starts at ${inp("spec.school.start_time", s.start_time, "time")}</label>
        <label class="f">Periods in a day ${inp("spec.school.periods_per_day", s.periods_per_day, "number", 'min="4" max="40"')}</label>
        <label class="f">Lesson length (periods) ${inp("spec.school.lesson_length", s.lesson_length, "number", 'min="1" max="6"')}</label>
        <label class="f">Levels (comma separated) <input data-list="levels" value="${esc(levels().join(", "))}"></label>
        <label class="f">Departments <input data-list="departments" value="${esc((s.departments || []).join(", "))}"></label>
        <label class="f">Room kinds <input data-list="room_kinds" value="${esc((s.room_kinds || []).join(", "))}"></label>
      </div></div>
      <div class="card"><h2>Day structure</h2>${(w => w.length ? `<div class="notice"><b>The Day structure and the settings on step 6 disagree.</b> The rules win where they are stricter, so make them say the same:<ul>${w.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : "")(structureWarnings())}<div class="legend">Brush: ${["L", "R", "W", "U", "F", "A", ""].map(c => `<button class="small ${S.brush === c ? "primary" : ""}" data-brush="${c}"><i class="c-${c}" style="width:12px;height:12px;display:inline-block;border-radius:3px;vertical-align:-2px"></i> ${{ L: "Lesson", R: "Recess", W: "Recess window", U: "Lunch", F: "Flag / assembly", A: "After-school slot", "": "No school" }[c]}</button>`).join("")}</div>
      <p class="muted" style="margin:4px 0 10px">Click or drag across cells to paint them with the brush.</p>
      <div class="tablewrap"><table class="dsgrid">${head}${lvRows}</table></div>
      ${hasWindows() ? `<h3 style="margin:14px 0 4px">Floating recess</h3><p class="muted" style="margin:0 0 8px">For the W periods: the solver puts a recess of this length in each recess window. Make a window the recess plus whole lessons (for example 2 + 3 + 3 periods with 3-period lessons), so the lessons still fit wherever the recess goes.</p>
        <div class="grid2">${(s.extra_settings || []).map((x, i) => isRecessRow(x) ? settingRow(x, i) : "").join("")}</div>` : ""}</div>`;
  },
  venues() {
    const { out, crit } = issues();
    return `<div class="card"><h1>Step 1 · Venues</h1><p class="lead">Every room. Its kind decides which subjects may use it (you set a subject's room kind on step 3). <b>Capacity</b> is seats: a group only goes in a room that seats it. <b>For</b> keeps a room for some subjects, departments or levels (for example "Chemistry G3, Sec 3"); blank = anyone. A room that holds two classes at once (a field, a hall) gets an "At most N at once" rule on step 6.</p>
      <div class="helper row"><b>Add rooms</b> prefix ${`<input id="hvPre" value="B1-" style="width:70px">`} from <input id="hvFrom" type="number" value="1" style="width:60px"> to <input id="hvTo" type="number" value="8" style="width:60px"> kind ${sel("_hv", "classroom", sc().room_kinds || [], false, 'id="hvKind" data-k=""')} <button data-helper="venues">Add</button></div>
      <div class="tablewrap"><table><tr><th>Room</th><th>Kind</th><th>Capacity</th><th>Block</th><th>Floor / level</th><th>Home room of</th><th>For</th><th>Note</th><th></th></tr>
      ${S.spec.venues.map((v, i) => `<tr id="venues-${i}" class="${rowCls(out, crit, "venues", i)}"><td>${inp(`spec.venues.${i}.room`, v.room)}</td><td>${sel(`spec.venues.${i}.kind`, v.kind, sc().room_kinds || [])}</td><td class="num">${inp(`spec.venues.${i}.capacity`, v.capacity, "number")}</td><td>${inp(`spec.venues.${i}.building`, v.building)}</td><td class="num">${inp(`spec.venues.${i}.floor`, v.floor)}</td><td class="calc">${esc(S.spec.classes.filter(c => c.home_room === v.room).map(c => c.class).join(", "))}</td><td style="min-width:170px"><input data-names="spec.venues.${i}.only_for" list="forNames" value="${esc((v.only_for || []).join(", "))}" placeholder="anyone"></td><td>${inp(`spec.venues.${i}.note`, v.note)}</td><td>${delBtn("venues", i)}</td></tr>`).join("")}
      </table></div><datalist id="forNames">${forNames().map(n => `<option value="${esc(n)}">`).join("")}</datalist><div class="row" style="margin-top:10px"><button data-add="venues">+ Add room</button></div></div>`;
  },
  classes() {
    const { out, crit } = issues();
    return `<div class="card"><h1>Step 2 · Classes</h1><p class="lead">Form classes with their level, size and home room (picked from step 1).</p>
      <div class="helper row"><b>Add classes</b> level ${sel("_hc", levels()[0], levels(), false, 'id="hcLevel" data-k=""')} names <input id="hcNames" value="A, B, C, D" style="width:120px"> students <input id="hcSize" type="number" value="38" style="width:70px"> <button data-helper="classes">Add (home rooms filled from free classrooms)</button></div>
      <div class="tablewrap"><table><tr><th>Class</th><th>Level</th><th>Students</th><th>Home room</th><th>Lesson rows</th><th>Note</th><th></th></tr>
      ${S.spec.classes.map((c, i) => `<tr id="classes-${i}" class="${rowCls(out, crit, "classes", i)}"><td>${inp(`spec.classes.${i}.class`, c.class)}</td><td>${sel(`spec.classes.${i}.level`, c.level, levels())}</td><td class="num">${inp(`spec.classes.${i}.size`, c.size, "number")}</td><td>${sel(`spec.classes.${i}.home_room`, c.home_room, rooms())}</td><td class="calc">${S.spec.lessons.filter(x => (x.classes || []).includes(c.class)).length}</td><td>${inp(`spec.classes.${i}.note`, c.note)}</td><td>${delBtn("classes", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="classes">+ Add class</button></div></div>`;
  },
  subjects() {
    const { out, crit } = issues(); const tags = (sc().tags || []).map(t => t[0]);
    return `<div class="card"><h1>Step 3 · Subjects</h1><p class="lead">Periods per ${Number(sc().weeks) === 2 ? "fortnight" : "week"} for each level that takes the subject (blank = not offered). Lessons are ${sc().lesson_length} periods long unless the subject says otherwise; leftovers become one or two shorter lessons. The code names the groups (1ELP1…). ${tagLabel()} is the level of study used for banding. <b>Teaching groups</b> fills in by itself: how many groups or classes are taught the subject on step 5 (each group in a band counts once, a whole-class subject once per class). 0 means no lessons yet, so it is not timetabled.</p>
      <div class="tablewrap"><table><tr><th>Subject</th><th>Code</th><th>${tagLabel()}</th><th>Department</th><th>Room kind</th><th>Lesson length</th>${levels().map(l => `<th>${esc(l)}</th>`).join("")}<th title="How many groups or classes have this subject on step 5 (Teaching groups & deployment): a banded group counts once, a whole-class subject once per class. 0: none yet, so it is not timetabled.">Teaching groups</th><th></th></tr>
      ${S.spec.subjects.map((s, i) => `<tr id="subjects-${i}" class="${rowCls(out, crit, "subjects", i)}"><td style="min-width:220px">${inp(`spec.subjects.${i}.subject`, s.subject)}</td><td class="num">${inp(`spec.subjects.${i}.code`, s.code, "text", 'style="width:54px"')}</td><td>${sel(`spec.subjects.${i}.tag`, s.tag, tags, false)}</td><td>${sel(`spec.subjects.${i}.dept`, s.dept, sc().departments || [])}</td><td>${sel(`spec.subjects.${i}.room_kind`, s.room_kind, sc().room_kinds || [])}</td><td class="num">${inp(`spec.subjects.${i}.lesson_length`, s.lesson_length, "number", 'style="width:56px"')}</td>${levels().map(l => `<td class="num">${inp(`spec.subjects.${i}.periods.${l}`, (s.periods || {})[l], "number", 'style="width:56px"')}</td>`).join("")}<td class="calc">${teachingGroups(s.subject)}</td><td>${delBtn("subjects", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="subjects">+ Add subject</button></div></div>`;
  },
  teachers() {
    const { out, crit, load } = issues(), f = S.tf, P = S.pick, q = f.q.trim().toLowerCase();
    const rows = S.spec.teachers.map((t, i) => [t, i]).filter(([t]) => (!f.dept || t.dept === f.dept) && (!f.subj || (t.can_teach || []).some(c => c.subject === f.subj))
      && (!q || `${t.name || ""} ${t.short || ""}`.toLowerCase().includes(q)));
    P.shown.teachers = rows.map(([, i]) => i); const all = rows.length && rows.every(([, i]) => P.teachers.has(i));
    return `<div class="card"><h1>Step 4 · Teachers</h1><p class="lead">Each teacher with the subjects and levels they can teach (click the subjects cell). Lessons on step 5 are checked against this, and the teacher drop-down there lists the teachers who can teach the subject first. Tick teachers (shift-click for a run) to give them a subject, department, role or allowance together.</p></div>
      ${VIEWS.roles(load)}${mayUpload() ? uploadCard() : ""}
      <div class="card" id="teacherList"><div class="helper" style="margin-top:0"><b>Add teachers</b> (one name per line) <div class="row" style="margin-top:6px"><textarea id="htNames" rows="3" style="width:280px;border:1px solid var(--line);border-radius:6px;padding:6px"></textarea> department ${sel("_ht", (sc().departments || [])[0], sc().departments || [], false, 'id="htDept" data-k=""')} allowance <input id="htAllow" type="number" value="${sc().type === "primary" ? 36 : 64}" style="width:70px"> <button data-helper="teachers">Add</button></div></div>
      <div class="row" style="margin:12px 0 8px"><b>Show</b> <select id="tfDept">${opt("", f.dept, "All departments")}${(sc().departments || []).map(d => opt(d, f.dept)).join("")}</select>
        <select id="tfSubj">${opt("", f.subj, "Any subject")}${subjectNames().map(n => opt(n, f.subj, `Can teach ${n}`)).join("")}</select>
        <input id="tfQ" type="search" placeholder="Search name" title="Type, then press Enter" value="${esc(f.q)}" style="width:160px">
        <span class="muted small">${rows.length === S.spec.teachers.length ? `${rows.length} teachers` : `${rows.length} of ${S.spec.teachers.length} teachers`}</span></div>
      ${teacherBar()}
      <div class="tablewrap"><table><tr><th><input type="checkbox" data-pickall="teachers" title="Tick every teacher shown (${rows.length})" ${all ? "checked" : ""}></th><th></th><th>Teacher</th><th>Short</th><th>Department</th><th>Allowance</th><th>Can teach</th><th>Given</th><th>Spare</th><th>Role</th><th>Other duties</th><th>Total load</th><th>Load check</th><th>Provisional</th><th></th></tr>
      ${(() => { const lc = loadChecks(load); return rows.map(([t, i]) => { const g = load[t.name] || 0; const sp = t.allowance ? Number(t.allowance) - g : ""; const tot = g + (Number(t.other_duties) || 0);
        return `<tr id="teachers-${i}" class="${rowCls(out, crit, "teachers", i)}${P.teachers.has(i) ? " picked" : ""}"><td><input type="checkbox" data-pick="teachers.${i}" ${P.teachers.has(i) ? "checked" : ""}></td><td class="avcell"><button class="avatar" data-avatar="${i}" title="New look" aria-label="New look for ${esc(t.name || "this teacher")}">${avatarOf(t, 32)}</button></td><td style="min-width:180px">${inp(`spec.teachers.${i}.name`, t.name)}</td><td>${inp(`spec.teachers.${i}.short`, t.short, "text", 'style="width:90px"')}</td><td>${sel(`spec.teachers.${i}.dept`, t.dept, sc().departments || [])}</td><td class="num">${inp(`spec.teachers.${i}.allowance`, t.allowance, "number")}</td><td style="min-width:260px">${chips(`spec.teachers.${i}.can_teach`, (t.can_teach || []).map(c => `${c.subject} · ${c.levels || "All"}`), "canteach")}</td><td class="calc">${g}</td><td class="calc" style="${sp !== "" && sp < 0 ? "color:var(--warn);font-weight:600" : ""}">${sp}</td><td style="min-width:96px">${sel(`spec.teachers.${i}.role`, t.role, roles().map(r => r.role))}</td><td class="num">${inp(`spec.teachers.${i}.other_duties`, t.other_duties, "number", 'style="width:60px"')}</td><td class="calc" style="${t.allowance && tot > Number(t.allowance) ? "color:var(--warn);font-weight:600" : ""}">${tot}</td><td class="calc" style="white-space:normal;min-width:200px;${lc[i] ? "color:var(--warn)" : ""}">${esc(lc[i])}</td><td>${sel(`spec.teachers.${i}.provisional`, t.provisional, ["Yes", "No"])}${committee() && t.provisional === "Yes" ? ` <span class="headmark" title="A department head added this teacher. Set Provisional to No to confirm them.">added by a head</span>` : ""}</td><td>${delBtn("teachers", i)}</td></tr>`; }).join(""); })()}
      </table></div><div class="row" style="margin-top:10px"><button data-add="teachers">+ Add teacher</button></div></div>`;
  },
  roles(load) {   // the Roles sheet: guide allowance per role and the load of the teachers in it
    // drawing never writes to the setup: the usual roles are written when the setup is opened (defaultRoles), and a
    // head, who may not change roles, sees them listed (read-only) when the setup has none
    const RL = S.spec.roles && S.spec.roles.length ? S.spec.roles : isHead() && !S.practice ? S.meta.roles || [] : [];
    const tot = t => (load[t.name] || 0) + (Number(t.other_duties) || 0), avg = a => a.length ? Math.round(a.reduce((x, y) => x + y, 0) / a.length) : "";
    const eo = avg(S.spec.teachers.filter(t => t.role === "EO" && tot(t) > 0).map(tot)), mgmt = avg(S.spec.teachers.filter(t => ["HOD", "SH"].includes(t.role) && tot(t) > 0).map(tot));
    return `<div class="card"><h2>1 · Roles</h2><p>Fill this first: the teacher list is checked against these roles.</p><p class="muted">Management (HOD, SH) should teach fewer periods than teachers; teachers (EO) should be spread evenly. Teachers (EO) average load <b>${eo || "–"}</b> · management (HOD, SH) <b>${mgmt || "–"}</b>.
      Flag a teacher <input data-k="spec.school.role_spread" type="number" value="${esc(sc().role_spread ?? 15)}" style="width:56px"> periods or more from the teacher average.</p>
      <div class="tablewrap"><table><tr><th>Role</th><th>What it is</th><th>Guide allowance</th><th>Group</th><th>Teachers</th><th>Average load</th><th></th></tr>
      ${RL.map((r, i) => { const ts = S.spec.teachers.filter(t => t.role === r.role);
        return `<tr><td>${inp(`spec.roles.${i}.role`, r.role, "text", 'style="width:80px"')}</td><td style="min-width:240px">${inp(`spec.roles.${i}.what`, r.what)}</td><td class="num">${inp(`spec.roles.${i}.allowance`, r.allowance, "number", 'style="width:64px"')}</td><td>${inp(`spec.roles.${i}.group`, r.group)}</td><td class="calc">${ts.length}</td><td class="calc">${avg(ts.map(tot))}</td><td>${delBtn("roles", i)}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="roles">+ Add role</button></div></div>`;
  },
  lessons() {   // step 5: the department map, or the table view of the same rows
    const sw = v => `<button class="${M.view === v ? "on" : ""}" data-mview="${v}">${v === "map" ? "Map" : "Table"}</button>`;
    return `<div class="card"><div class="row" style="justify-content:space-between"><div><h1 style="margin:0">Step 5 · Department map</h1><p class="lead" style="margin:6px 0 0">Tick teachers on the left, then click a subject basket to say what they can teach, or a class, group or band card to deploy them. Dragging works too. Click an avatar for the teacher's profile. The table view shows the same rows for bulk edits, bands and new groups.</p></div><div class="row switch">${sw("map")}${sw("table")}</div></div></div>`
      + (M.view === "map" ? VIEWS.map() : VIEWS.table());
  },
  table() {
    const { out, crit, info, load } = issues(); const T = teacherNames(), f = S.tg, P = S.pick;
    const tsel = (i, k, x) => { const path = `spec.lessons.${i}.teachers.${k}`; const cur = (x.teachers || [])[k] || ""; const yes = T.filter(t => canTeach(t, x.subject, x.level)), no = T.filter(t => !yes.includes(t));
      return `<select data-k="${path}">${opt("", cur, "")}<optgroup label="Can teach this">${yes.map(t => opt(t, cur)).join("")}</optgroup><optgroup label="Others">${no.map(t => opt(t, cur)).join("")}</optgroup></select>`; };
    const rows = S.spec.lessons.map((x, i) => [x, i]).filter(([x]) => (!f.lv || x.level === f.lv) && (!f.subj || x.subject === f.subj)
      && (!f.t || (f.t === "-" ? !(x.teachers || []).some(Boolean) : (x.teachers || []).includes(f.t))));
    P.shown.lessons = rows.map(([, i]) => i);
    const all = rows.length && rows.every(([, i]) => P.lessons.has(i));
    return `<div class="card"><h2>Table view</h2><p class="lead">Every teaching group (TG) and the teachers deployed to it. A whole-class subject is one group per class; a band splits its classes into groups that all have lessons at the same time. Set up the bands first, then add the groups and deploy teachers below.</p>
      ${VIEWS._bands(out, info, crit)}</div>
      <div class="card"><h2>Teaching groups</h2><p class="muted">One row per group, or per class for a whole-class subject. Pick level, subject and band (empty = whole class); choosing a band fills its classes. Group code and periods fill in by themselves. Lessons shows how the periods split, in grey; type your own, such as 5x3 + 2x2 (five 3-period lessons and two 2-period ones), or clear it to go back. Tick rows (shift-click for a run) to deploy a teacher or set Lessons on all of them at once.</p>
      <div class="helper row"><b>Add groups to a band</b> ${sel("_hb", "", blockNames(), true, 'id="hbBlock" data-k=""')} subject ${sel("_hbs", "", subjectNames(), true, 'id="hbSubj" data-k=""')} groups <input id="hbN" type="number" value="1" style="width:56px"> students each <input id="hbSt" type="number" style="width:64px"> <button data-helper="groups">Add</button></div>
      <div class="helper row"><b>Add a whole-class subject</b> level ${sel("_hw", levels()[0], levels(), false, 'id="hwLevel" data-k=""')} subject ${sel("_hws", "", subjectNames(), true, 'id="hwSubj" data-k=""')} <button data-helper="whole">Add one row per class</button></div>
      <div class="row" style="margin:12px 0 8px"><b>Show</b> <select id="tgLv">${opt("", f.lv, "All levels")}${levels().map(l => opt(l, f.lv)).join("")}</select>
        <select id="tgSubj">${opt("", f.subj, "All subjects")}${subjectNames().map(n => opt(n, f.subj)).join("")}</select>
        <select id="tgT">${opt("", f.t, "Any teacher")}${opt("-", f.t, "No teacher yet")}${T.map(t => opt(t, f.t)).join("")}</select>
        <span class="muted small">${rows.length === S.spec.lessons.length ? `${rows.length} rows` : `${rows.length} of ${S.spec.lessons.length} rows`}</span></div>
      ${tgBar(load, info)}
      <div class="tablewrap"><table><tr><th><input type="checkbox" data-pickall="lessons" title="Tick every row shown (${rows.length})" ${all ? "checked" : ""}></th><th>Level</th><th>Subject</th><th>Band</th><th>Classes</th><th>Teacher 1</th><th>Teacher 2</th><th title="A third teacher in the room (co-teaching)">Teacher 3</th><th>Students</th><th>Periods override</th><th>Keep code</th>${Number(sc().weeks) === 2 ? '<th title="Odd or Even: the group uses its special room (lab, studio...) on that week only, and a classroom on the other">Special room weeks</th>' : ""}<th>Code</th><th>Periods</th><th title="Type your own split, such as 5x3 + 2x2. Empty = the usual split shown in grey.">Lessons</th><th></th></tr>
      ${rows.map(([x, i]) => `<tr id="lessons-${i}" class="${rowCls(out, crit, "lessons", i)}${P.lessons.has(i) ? " picked" : ""}" title="${esc((out.lessons[i] || []).join(" "))}"><td><input type="checkbox" data-pick="lessons.${i}" ${P.lessons.has(i) ? "checked" : ""}></td><td class="lv">${sel(`spec.lessons.${i}.level`, x.level, levels())}</td><td style="min-width:200px">${sel(`spec.lessons.${i}.subject`, x.subject, subjectNames().filter(n => (subj(n).periods || {})[x.level] || n === x.subject))}</td><td style="min-width:160px">${sel(`spec.lessons.${i}.block`, x.block, S.spec.blocks.filter(b => !x.level || b.level === x.level).map(b => b.block))}</td><td style="min-width:120px">${chips(`spec.lessons.${i}.classes`, x.classes, "classes", `data-level="${esc(x.level || "")}"`)}</td><td style="min-width:150px">${tsel(i, 0, x)}</td><td style="min-width:120px">${tsel(i, 1, x)}</td><td style="min-width:120px">${tsel(i, 2, x)}</td><td class="num">${inp(`spec.lessons.${i}.students`, x.students, "number", 'style="width:60px"')}</td><td class="num">${inp(`spec.lessons.${i}.periods_override`, x.periods_override, "number", 'style="width:60px"')}</td><td class="num">${inp(`spec.lessons.${i}.code_override`, x.code_override, "text", 'style="width:70px"')}</td>${Number(sc().weeks) === 2 ? `<td><select data-k="spec.lessons.${i}.room_weeks" ${special(x) ? "" : "disabled title=\"Only for a subject with a special room kind, such as a lab (step 3)\""}>${opt("", x.room_weeks || "", "every week")}${opt("Odd", x.room_weeks, "Odd only")}${opt("Even", x.room_weeks, "Even only")}</select></td>` : ""}<td class="calc">${esc(info[i].code)}</td><td class="calc">${info[i].p || ""}</td><td><input id="pat-${i}" data-pat="${i}" value="${esc((x.pattern || []).length ? patText(x.pattern.map(Number)) : x.pattern_text || "")}" placeholder="${esc(info[i].auto)}" title="How the periods split into lessons: 5x3 + 2x2 is five 3-period lessons and two 2-period ones. Empty = the usual split shown in grey." style="width:112px"></td><td>${delBtn("lessons", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="lessons">+ Add teaching group</button></div></div>`;
  },
  map() {   // step 5's department map: roster (left), baskets (middle), cards (right)
    Sync.ensureIds(S.spec);
    const dept = mapDept(), D = sc().departments || [], T = S.spec.teachers, ro = DeptMap.roster(S.spec, dept, M.extra);
    tickedIdx();
    const nTick = ro.filter(i => M.ticked.has(T[i]._id)).length, some = nTick > 0 && nTick < ro.length;
    return `<div class="map"><section class="roster card">
      <div class="row"><select id="mDept" title="Department">${D.map(d => opt(d, dept)).join("")}</select><span class="muted small">${ro.length} teacher${ro.length === 1 ? "" : "s"}${nTick ? ` · ${nTick} ticked` : ""}</span></div>
      <div class="row" style="margin:8px 0"><button class="small" data-mall title="Tick every teacher on the roster">${some ? "Select all –" : "Select all"}</button><button class="small" data-mnone>Deselect all</button><button class="small" data-munplaced title="Tick the teachers with no subject yet">Not placed yet</button></div>
      <input id="mQ" type="search" placeholder="Find, or add a teacher from another department" value="${esc(M.q)}" style="width:100%">
      <div id="rbody">${rosterList(dept)}</div>
      <div class="row" style="margin-top:10px">${M.adding ? "" : `<button data-mnew>+ New teacher</button>`}</div>${M.adding ? newTeacherForm(dept) : ""}
    </section>${basketsView(dept)}${cardsView(dept)}</div>`;
  },
  _bands(out, info, crit) {
    const open = S.bandsOpen ?? (!S.spec.blocks.length || Object.keys(out.blocks).length > 0);   // until the committee opens or closes it
    return `<details class="bands" ${open ? "open" : ""}><summary><h2>Bands <span class="muted" style="font-weight:400;font-size:14px">${S.spec.blocks.length} band${S.spec.blocks.length === 1 ? "" : "s"}${Object.keys(out.blocks).length ? ` · ${Object.keys(out.blocks).length} to fix` : ""}</span></h2></summary><p class="muted">A band takes the students of its classes and splits them into groups that all have lessons at the same time (for example, Sec 1 English for 1A–1D split by G3, G2 and G1). Name the band and pick its classes; then add its groups under Teaching groups.</p>
      <div class="tablewrap"><table><tr><th>Band</th><th>Level</th><th>Classes</th><th>Groups (from Teaching groups)</th><th>Students in groups / classes</th><th title="Every student in its classes takes one of its groups (English, Mother Tongue...). Untick for an option or elective band some students are not in.">Everyone takes one</th><th>Note</th><th></th></tr>
      ${S.spec.blocks.map((b, i) => { const gs = S.spec.lessons.map((x, j) => [x, j]).filter(([x]) => x.block === b.block); const inG = gs.reduce((a, [x]) => a + (Number(x.students) || 0), 0), inC = (b.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
        return `<tr id="blocks-${i}" class="${rowCls(out, crit, "blocks", i)}"><td style="min-width:200px">${inp(`spec.blocks.${i}.block`, b.block)}</td><td>${sel(`spec.blocks.${i}.level`, b.level, levels())}</td><td style="min-width:180px">${chips(`spec.blocks.${i}.classes`, b.classes, "classes", `data-level="${esc(b.level || "")}"`)}</td><td class="calc" style="white-space:normal">${esc(gs.map(([x, j]) => info[j].code).join(", "))}</td><td class="calc">${inG} / ${inC}</td><td style="text-align:center"><input type="checkbox" data-k="spec.blocks.${i}.everyone" ${everyone(b) ? "checked" : ""}></td><td>${inp(`spec.blocks.${i}.note`, b.note)}</td><td>${delBtn("blocks", i)}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="blocks">+ Add band</button></div></details>`;
  },
  rules() {
    const { out, crit } = issues(); const RT = S.meta.rule_types || []; const NP = Number(sc().periods_per_day); const P = Array.from({ length: NP }, (_, p) => p);
    const psel = (path, cur) => `<select data-k="${path}">${opt("", cur ?? "", "")}${P.map(p => opt(p, cur, `${p} (${clock(p)})`)).join("")}</select>`;
    const weeks = Number(sc().weeks) === 2 ? ["Both", "Odd", "Even"] : ["Both"], days = ["All", "Mon", "Tue", "Wed", "Thu", "Fri"];
    const where = placeRules(), bad = i => rowCls(out, crit, "rules", i), tip = i => esc((out.rules[i] || []).join(" "));
    const msg = (i, n) => out.rules[i] ? `<tr class="rowmsg ${bad(i)}"><td colspan="${n}">${out.rules[i].map(esc).join("<br>")}</td></tr>` : "";   // what is wrong with the row, under it
    const avail = where.availability.map(i => { const r = S.spec.rules[i], [a, b] = ruleTimes(r);
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td style="min-width:180px">${sel(`spec.rules.${i}.target`, r.target, teacherNames())}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td>
        <td><input data-time="${i}|0" type="time" value="${esc(a)}"></td><td><input data-time="${i}|1" type="time" value="${esc(b)}"></td><td class="calc">${r.from === r.to || r.to == null ? `period ${r.from}` : `periods ${r.from}–${r.to}`}</td><td class="note">${inp(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>${msg(i, 8)}`; }).join("");
    const codes = groupCodes();
    const fixed = where.fixed.map(i => { const r = S.spec.rules[i], every = ["Level", "School"].includes(r.scope), lv = every ? (r.scope === "Level" ? r.target : "All") : r.level || clsLevel(r.target);
      const who = [EVERY, ...classNames().filter(c => !lv || lv === "All" || clsLevel(c) === lv), ...codes.filter(c => !lv || lv === "All" || String(lv).slice(-1) === c[0])];
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td><select data-fixlv="${i}">${["All", ...levels()].map(v => opt(v, lv || "All")).join("")}</select></td><td style="min-width:110px"><select data-fixwho="${i}">${opt("", every ? EVERY : r.target, "")}${who.map(v => opt(v, every ? EVERY : r.target)).join("")}${!every && r.target && !who.includes(r.target) ? opt(r.target, r.target, `${r.target} (not on list)`) : ""}</select></td><td style="min-width:180px">${sel(`spec.rules.${i}.subject`, r.subject, subjectNames())}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td><td>${psel(`spec.rules.${i}.from`, r.from)}</td><td class="note">${inp(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>${msg(i, 8)}`; }).join("");
    const more = where.more.map(i => { const r = S.spec.rules[i];
      const subjCell = r.rule === "Only these subjects" ? chips(`spec.rules.${i}.subject`, namesList(r.subject), "subjects") : sel(`spec.rules.${i}.subject`, r.subject, subjectNames());
      const venueCell = r.rule === "Only in venues" ? chips(`spec.rules.${i}.venues`, namesList(r.venues), "rooms") : '<span class="muted small">–</span>';
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td><select data-k="spec.rules.${i}.scope">${opt("", r.scope, "")}${S.meta.scopes.map(v => opt(v, r.scope, v === "Block" ? "Band" : v)).join("")}</select></td><td style="min-width:150px">${sel(`spec.rules.${i}.target`, r.target, targetOptions(r.scope))}</td><td style="min-width:180px">${subjCell}</td><td style="min-width:180px">${sel(`spec.rules.${i}.rule`, r.rule, RT.filter(t => !r.scope || scopesOf(t).includes(r.scope)).map(t => t.rule))}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td><td>${psel(`spec.rules.${i}.from`, r.from)}</td><td>${psel(`spec.rules.${i}.to`, r.to)}</td><td class="num">${inp(`spec.rules.${i}.number`, r.number, "number", 'style="width:56px"')}</td><td style="min-width:120px">${venueCell}</td><td>${sel(`spec.rules.${i}.strength`, r.strength || "Must", ["Must", "Prefer"], false)}</td><td class="note">${inp(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>${msg(i, 13)}`; }).join("");
    const s = sc();
    return `<div class="card"><h1>Step 6 · Configuration and constraints</h1><p class="lead">The school-wide settings first, then the constraints: times a teacher cannot teach, lessons fixed at a set time, and any other rule.</p>
      <h2>Configuration</h2><p class="muted">School-wide settings. They apply to every class and teacher.</p>
      <div class="grid2">${SET().map(x => `<label class="f">${esc(x.label)} ${x.number
        ? `<input data-set="${x.key}" type="number" min="1" value="${esc(settingValue(x.key))}" placeholder="no limit">`
        : `<select data-set="${x.key}">${["Yes", "No"].map(v => opt(v, settingValue(x.key))).join("")}</select>`}</label>`).join("")}
      ${(s.extra_settings || []).map((x, i) => isRecessRow(x) ? "" : settingRow(x, i)).join("")}</div></div>
      <div class="card"><h2>Teacher availability</h2><p class="muted">Times a teacher cannot teach (part-time days, a centre or programme after school). Times are clock times; every period they overlap is blocked.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Teacher</th><th>Week</th><th>Day</th><th>From</th><th>To</th><th>Blocks</th><th>Reason</th><th></th></tr>${avail}</table></div>
      <div class="row" style="margin-top:10px"><button data-add="avail">+ Add block-out</button></div></div>
      <div class="card"><h2>Fixed lessons</h2><p class="muted">Lessons that must start at a set time (optional): a class with a subject, a group code from step 5, or <b>${EVERY}</b>: that subject for every class of the level at once (Level <b>All</b>: the whole school), such as CCE. Leave empty to let the timetable place everything.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Level</th><th>Class or group</th><th>Subject</th><th>Week</th><th>Day</th><th>Start period</th><th>Note</th><th></th></tr>${fixed}</table></div>
      <div class="row" style="margin-top:10px"><button data-add="fixed">+ Add fixed lesson</button><button data-add="fixedall" title="A subject at one time for every class, such as whole-school CCE. One row per slot: a subject with two lessons a cycle needs two rows.">+ Every class at one time (CCE)</button></div></div>
      <div class="card"><h2>More rules</h2><p class="muted">Any other constraint: rooms, levels, subjects, Prefer rules and so on. First pick what the rule applies to; the next drop-down lists only those. <b>Must</b> is never broken; <b>Prefer</b> is kept where possible.</p>
      <p class="muted">Common ones in a click: an <b>HBL day</b> (Only these subjects: only the subjects you tick are taught that day) and <b>lessons late in the day only in some rooms</b> (Only in venues: PE after 11.00 only in the hall, say).</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Applies to</th><th>Which</th><th>Subject (optional)</th><th>Rule</th><th>Week</th><th>Day</th><th>From</th><th>To</th><th>Number</th><th title="For Only in venues: the rooms those lessons must use then">Venues</th><th>Must / Prefer</th><th>Note</th><th></th></tr>${more}</table></div>
      <div class="row" style="margin-top:10px"><button data-add="rules">+ Add rule</button><button data-add="hbl" title="Only the subjects you tick are taught on that day; every other lesson goes on another day.">+ HBL day</button><button data-add="venuerule" title="Lessons of a subject that run into the times you pick go only in the rooms you pick (PE after 11.00 in the hall or ISH).">+ Lessons late in the day only in some rooms</button></div></div>
      <div class="card"><h2>Rule types</h2><div class="tablewrap" style="max-height:none"><table><tr><th>Rule</th><th>Applies to</th><th>What it means</th><th>Example</th></tr>${RT.map(t => `<tr><td><b>${esc(t.rule)}</b></td><td>${esc(t.scopes)}</td><td>${esc(t.meaning)}</td><td class="muted">${esc(t.example)}</td></tr>`).join("")}</table></div></div>`;
  },
  students() {
    const { out, crit } = issues(); const L = S.spec.students, f = S.stu, q = f.q.trim().toLowerCase(), MAX = 200;
    const combos = (S.spec.combinations || []).map(c => c.code).filter(Boolean);
    const per = {}; L.forEach(s => per[s.class] = (per[s.class] || 0) + 1);
    const rows = L.map((s, i) => [s, i]).filter(([s]) => (!f.cls || s.class === f.cls) && (!q || `${s.id || ""} ${s.name || ""}`.toLowerCase().includes(q)));
    const P = S.pick; P.shown.students = rows.map(([, i]) => i); const all = rows.length && rows.every(([, i]) => P.students.has(i));
    const clsOpts = [opt("", f.cls, `All classes (${L.length})`), ...S.spec.classes.map(c => opt(c.class, f.cls, `${c.class} · ${per[c.class] || 0} of ${c.size || "?"}`)),
      ...[...new Set(L.map(s => s.class || ""))].filter(c => !classNames().includes(c)).map(c => opt(c, f.cls, c ? `${c} (not on step 2) · ${per[c]}` : `No class · ${L.filter(s => !s.class).length}`))].join("");
    return `<div class="card"><h1>Students <span class="muted" style="font-weight:400;font-size:15px">(after the timetable is made)</span></h1><p class="muted small">Add students class by class once the timetable is out; they are not needed to make it. Have it made again with the list only if you want each student's combination checked for clashes.</p><p class="lead">List each student with their class and the codes of the groups they are in (from step 5). The solver then makes sure no student has two lessons at once, and every student gets their own timetable and a personal sign-in code. Without a list, the students of a class are assumed to be in the same level tag (all G3, all Foundation) in every band, so students on mixed combinations are not checked. To fill groups here, tick students (shift-click for a run, or the box at the top for everyone shown) and add them to a group or move them to a class together.</p>
      ${restoreHelper()}
      <div class="helper"><b>Paste or upload the student list</b>
        <p class="muted small" style="margin:4px 0 8px">Copy the rows from Excel or a CSV file, with a header row: <b>Student ID</b>, <b>Name</b>, <b>Class</b> and <b>Groups</b> (codes in one cell separated by commas, or one code per column). Without a header, the columns are read as ID, name, class, then groups. Whole-class subjects need no codes: a student has those with their class. Use an ID that stays the same (an admission number, say): personal codes are made from it.</p>
        <textarea id="stuPaste" rows="5" spellcheck="false" placeholder="Student ID&#9;Name&#9;Class&#9;Groups&#10;S001&#9;Tan Wei Ming&#9;1A&#9;1ELP1, 1MAP1, 1SCP1"></textarea>
        <div class="row" style="margin-top:8px"><label class="filebtn">Choose a file (.xlsx or .csv)<input type="file" id="stuFile" accept=".xlsx,.csv,.tsv,.txt" hidden></label><button class="primary" data-stu="replace">Replace the list</button><button data-stu="add">Add to the list</button><span class="muted small" id="stuMsg"></span></div></div></div>
      <div class="card"><div class="row" style="justify-content:space-between"><h2 style="margin:0">The list</h2>
        <div class="row"><select id="stuCls">${clsOpts}</select><input id="stuQ" type="search" placeholder="Search ID or name" title="Type, then press Enter" value="${esc(f.q)}" style="width:190px"><span class="muted small">${rows.length === L.length ? `${L.length} students` : `${rows.length} of ${L.length}`}</span>${L.length ? `<button class="small danger" data-stu="clear">Remove all</button>` : ""}</div></div>
      ${stuBar()}${L.length ? `<div class="tablewrap" style="margin-top:10px"><table><tr><th><input type="checkbox" data-pickall="students" title="Tick every student shown (${rows.length})" ${all ? "checked" : ""}></th><th>Student ID</th><th>Name</th><th>Class</th><th>Level</th>${combos.length ? "<th>Combination</th>" : ""}<th>Groups (click to pick)</th><th>Note</th><th></th></tr>
      ${rows.slice(0, MAX).map(([s, i]) => `<tr id="students-${i}" class="${rowCls(out, crit, "students", i)}${P.students.has(i) ? " picked" : ""}" title="${esc((out.students[i] || []).join(" "))}"><td><input type="checkbox" data-pick="students.${i}" ${P.students.has(i) ? "checked" : ""}></td><td>${inp(`spec.students.${i}.id`, s.id, "text", 'style="width:110px"')}</td><td style="min-width:190px">${inp(`spec.students.${i}.name`, s.name)}</td><td style="min-width:88px">${sel(`spec.students.${i}.class`, s.class, classNames())}</td><td class="calc">${esc(clsLevel(s.class) || s.level || "")}</td>${combos.length ? `<td>${sel(`spec.students.${i}.combination`, s.combination, combos)}</td>` : ""}<td style="min-width:260px">${chips(`spec.students.${i}.groups`, s.groups, "groups", `data-cls="${esc(s.class || "")}"`)}</td><td>${inp(`spec.students.${i}.note`, s.note)}</td><td>${delBtn("students", i)}</td></tr>`).join("")}
      </table></div>${rows.length > MAX ? `<p class="muted small">Showing the first ${MAX}. Pick a class or search to see the rest.</p>` : ""}`
        : `<p class="muted" style="margin-top:10px">No students yet. Paste or upload a list above, or add students one by one.</p>`}
      <div class="row" style="margin-top:10px"><button data-add="students">+ Add student</button></div></div>`;
  },
  download() {
    const { out, crit } = issues(); let n = 0, nc = 0;
    for (const [k, rows] of Object.entries(out)) if (k !== "global" && k !== "students") for (const [i, ms] of Object.entries(rows)) { n++; if (ms.some(m => isCrit(crit, k, i, m))) nc++; }
    return `<div class="card"><h1>Step 7 · Download</h1><p class="lead">Everything an AI agent needs to make the timetable: your setup as a workbook, and the timetable skill. The workbook keeps the drop-downs and formulas, so it can still be edited in Excel.</p>
      <div><span class="stat"><b>${S.spec.classes.length}</b> classes</span><span class="stat"><b>${S.spec.teachers.length}</b> teachers</span><span class="stat"><b>${S.spec.blocks.length}</b> bands</span><span class="stat"><b>${S.spec.lessons.length}</b> lesson rows</span><span class="stat"><b>${S.spec.rules.length}</b> rules</span><span class="stat"><b>${S.spec.students.length}</b> students</span></div>
      ${nc ? `<p class="issue crit" style="margin-top:12px">${nc} row${nc === 1 ? " has" : "s have"} a critical problem: no timetable can be made until ${nc === 1 ? "it is" : "they are"} fixed (see the right-hand panel).${n > nc ? ` ${n - nc} more ${n - nc === 1 ? "has" : "have"} only warnings.` : ""}</p>`
        : n ? `<p class="issue soft" style="margin-top:12px">Nothing critical. ${n} row${n === 1 ? " has" : "s have"} warnings for a person to check (see the right-hand panel); a timetable can still be made.</p>` : '<p class="okmsg" style="margin-top:12px">Everything checks out.</p>'}</div>
      <div class="card" id="fitCard" style="margin-top:16px"></div>
      <div class="dl">
        <div class="card"><h2>1 · Configuration workbook</h2><p class="muted">Everything you entered, as the .xlsx template.</p><button class="primary" id="build">Download workbook (.xlsx)</button></div>
        <div class="card"><h2>2 · The timetable skill</h2><p class="muted">Use the zip when the chatbot can run code: its scripts make a timetable file this app can publish as it is. SKILL.md alone is for a chatbot that cannot run code.</p><div class="row"><a href="/download/skill.zip"><button class="primary">Skill (.zip)</button></a><a href="/download/SKILL.md"><button>SKILL.md only</button></a></div></div>
        <div class="card"><h2>Keep a copy</h2><p class="muted">The setup as a progress file, to keep or to open on another computer.</p><div class="row"><button id="saveJson" title="Download the setup as a progress file">Save to file</button>${committee() && !S.practice ? `<label class="filebtn" title="Open a progress file: it replaces the school's setup for everyone">Load from file<input type="file" id="loadJson" accept=".json" hidden></label>` : ""}</div>${committee() && !S.practice ? copiesList() : ""}</div>
      </div>
      <div class="card" style="margin-top:16px"><h2>How to make the timetable</h2><ol class="howto">
        <li>In Claude (or another agent that can run Python), add the skill: upload the .zip as a skill, or attach SKILL.md to the conversation.</li>
        <li>Upload your setup workbook and ask: <i>"Generate our timetable from this setup. Report anything that does not fit."</i></li>
        <li>The agent checks the inputs, solves (a few minutes for a typical school), and hands back the timetable file. Bring that file to step 8, Publish.</li>
        <li>Change the setup here or in Excel and ask again: the agent re-solves from the new file.</li></ol></div>
      <div class="card" style="margin-top:16px"><h2>Templates to share</h2><p class="muted">Ready-made workbooks for others to fill in Excel.</p><div class="row"><a href="/download/template/secondary"><button>Sample secondary</button></a><a href="/download/template/primary"><button>Sample primary</button></a><a href="/download/blank/secondary"><button>Blank secondary</button></a><a href="/download/blank/primary"><button>Blank primary</button></a></div></div>`;
  },
  publish() {
    if (S.practice) return `<div class="card"><h1>Step 8 · Publish</h1><p class="lead">Publishing is off in a practice copy.</p></div>`;
    return `<div class="card"><h1>Step 8 · Publish</h1><p class="lead">Bring back the timetable the AI agent made, check it, then publish it. Nothing is visible to teachers or students until you publish.</p></div>
      ${exportCard()}<div class="card" id="pubNow" style="margin-top:16px"></div>`;
  },
};

function copiesList() {   // the earlier copies of the school's setup the server keeps (a replacement keeps one)
  if (!S.copies) return `<div class="row" style="margin-top:10px"><button id="copiesLoad">Restore an earlier copy</button></div>`;
  if (!S.copies.length) return `<p class="muted small" style="margin-top:10px">The server has no earlier copies yet.</p>`;
  return `<h3 style="margin-top:12px">Restore an earlier copy</h3><p class="muted small">It replaces the school's setup for everyone; the setup as it is now is kept as a copy too.</p>
    <div class="tablewrap" style="max-height:260px"><table><tr><th>When</th><th>What</th><th></th></tr>${S.copies.map(c => `<tr><td>${esc(c.when)}</td><td>${esc(c.what)}</td><td><button class="small" data-restore="${esc(c.id)}">Restore</button></td></tr>`).join("")}</table></div>`;
}

/* ---------------- events */
document.addEventListener("click", async e => {
  const pop = $("#pop");
  if (!pop.hidden && !pop.contains(e.target)) commitPop();
  if (e.target.dataset && (e.target.dataset.pick || e.target.dataset.pickall)) { pick(e.target, e.shiftKey); return; }
  if (e.target.dataset && e.target.dataset.mtick) { mtick(e.target, e.shiftKey); return; }
  const b = e.target.closest("button, [data-pop], .issue, td.c, [data-mcard], [data-mbasket], [data-mstaff]"); if (!b) return;
  if (b.dataset.step) { if (!stepShown(Number(b.dataset.step))) return; S.step = Number(b.dataset.step); save(); render(); window.scrollTo(0, 0); return; }
  if (b.id === "undo" || b.id === "redo") { undo(b.id === "undo"); return; }
  if (b.dataset.clear) { setPath(b.dataset.clear, ""); save(); render(); return; }
  if (b.id === "practiceBack") { leavePractice(); return; }
  if (b.dataset.old) { oldChoice(b.dataset.old); return; }
  if (b.id === "copiesLoad") { try { S.copies = await getJSON("/api/setup/copies"); } catch (err) { toast("Could not load the earlier copies."); return; } render(); return; }
  if (b.dataset.restore) { restoreCopy(b.dataset.restore); return; }
  if (b.dataset.begin) { const [k, w] = b.dataset.begin.split("|"); try { await begin(k, w); } catch (err) { toast("Could not load: " + err.message); } return; }
  if (b.dataset.add) { addRow(b.dataset.add); return; }
  if (b.dataset.del) { const [k, i] = b.dataset.del.split("."); S.spec[k].splice(Number(i), 1); unpick(); save(); render(); return; }
  if (b.dataset.helper) { helper(b.dataset.helper); return; }
  if (b.dataset.avatar) { const t = S.spec.teachers[Number(b.dataset.avatar)]; if (t) { t.avatar = (Number(t.avatar) || 0) + 1; save(); render(); } return; }
  if (b.dataset.brush !== undefined) { S.brush = b.dataset.brush; render(); return; }
  if (b.dataset.copyday) { const lv = b.dataset.copyday; const ds = S.spec.day_structure[lv]; const f = ds[dayNames()[0]]; dayNames().forEach(d => ds[d] = f); save(); render(); return; }
  if (b.dataset.copylevel) { const src = S.spec.day_structure[b.dataset.copylevel]; levels().forEach(l => S.spec.day_structure[l] = { ...src }); save(); render(); return; }
  for (const k of ["mview", "mall", "mnone", "munplaced", "madd", "mnew", "mnewcancel", "mnewgo"]) if (b.dataset[k] !== undefined) { mapAction(k, b.dataset[k]); return; }
  if (b.dataset.mtab) { M.tab = b.dataset.mtab; render(); return; }
  if (b.dataset.mx) { const [li, cls, ...nm] = b.dataset.mx.split("|"); cardRemove(`${li}|${cls}`, nm.join("|")); return; }
  if (b.dataset.mbx) { const [id, ...sub] = b.dataset.mbx.split("|"); basketRemove([[S.spec.teachers.findIndex(t => t && t._id === id), sub.join("|")]]); return; }
  if (b.dataset.mbasket !== undefined) { basketAdd(b.dataset.mbasket, tickedIdx()); return; }
  if (b.dataset.mstaff !== undefined) { toast("Drag teachers here to take them out of the baskets, or use the ✕ on a basket."); return; }
  if (b.dataset.mcard !== undefined) { placeOn(cardAt(b.dataset.mcard), tickedIdx()); return; }
  if (b.dataset.pop) { if (!b.classList.contains("ro")) openPop(b); return; }
  if (b.dataset.stu) { stuApply(b.dataset.stu); return; }
  if (b.dataset.tl) { tlAction(b.dataset.tl); return; }
  if (b.dataset.past) { pastAction(b.dataset.past); return; }
  if (b.dataset.bulk) { bulk(b.dataset.bulk); return; }
  if (b.classList.contains("issue") && b.dataset.go) {
    const s = /^students-/.test(b.dataset.row) && S.spec.students[Number(b.dataset.row.slice(9))];
    if (s) S.stu = classNames().includes(s.class) ? { cls: s.class, q: "" } : { cls: "", q: stuKey(s) };
    if (/^lessons-/.test(b.dataset.row)) S.tg = { lv: "", subj: "", t: "" };
    if (/^teachers-/.test(b.dataset.row)) S.tf = { dept: "", subj: "", q: "" };
    if (!stepShown(Number(b.dataset.go))) return;
    S.step = Number(b.dataset.go); render(); const r = document.getElementById(b.dataset.row); if (r) r.scrollIntoView({ block: "center" }); return; }
  if (b.id === "build") { buildXlsx(); return; }
  if (b.id === "fitAgain") { fitCheck(true); return; }
  if (b.id === "exGo") { makePrintouts(); return; }
  if (b.id === "imCheck") { importTimetable(false); return; }
  if (b.id === "imPublish") { if (!confirm("Publish this timetable? Teachers and students will see it straight away, in place of what they see now.")) return; importTimetable(true); return; }
  if (b.id === "saveJson") { if (!S.spec) { toast("Open or start a setup first."); return; } const blob = new Blob([JSON.stringify(S.spec, null, 1)], { type: "application/json" }); dl(blob, `${sc().name || "timetable"}_setup.json`); return; }
});
document.addEventListener("toggle", e => { if (e.target.classList && e.target.classList.contains("bands")) S.bandsOpen = e.target.open; }, true);
document.addEventListener("keydown", e => {   // ⌘Z / Ctrl+Z undo, ⇧⌘Z / Ctrl+Y redo; inside a text box the browser's own undo applies
  if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
  const k = e.key.toLowerCase(); if (k !== "z" && k !== "y") return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable]")) return;
  e.preventDefault(); undo(k === "z" && !e.shiftKey);
});
let painting = false;
document.addEventListener("mousedown", e => { const c = e.target.closest("td.c"); if (!c || locked(G.shown)) return; painting = true; paint(c); e.preventDefault(); });
document.addEventListener("mouseover", e => { if (!painting) return; const c = e.target.closest("td.c"); if (c) paint(c); });
document.addEventListener("mouseup", () => { if (painting) { painting = false; const added = ensureRecessRows(); save(); if (added) render(); else renderIssues(); } });
function paint(c) {
  const [lv, d, p] = c.dataset.cell.split("|"); const row = S.spec.day_structure[lv][d].split(""); row[Number(p)] = S.brush || "."; S.spec.day_structure[lv][d] = row.join("");
  c.className = `c c-${S.brush}`; c.textContent = S.brush;
}
document.addEventListener("change", async e => {
  const el = e.target;
  if (el.id === "importX") { const f = el.files[0]; if (!f) return; el.value = ""; const fd = new FormData(); fd.append("file", f);
    try { const r = await fetch("/api/import", { method: "POST", body: fd }); const j = await r.json().catch(() => ({})); if (!r.ok) { toast(j.error || "Could not read that file."); return; } if (!await adopt(j, "Workbook opened and saved for the school.", "Opened a workbook")) return; }
    catch (err) { toast("Could not reach the server: " + err.message); return; }
    const nr = new Set(ruleProblems(lessonInfo()).map(x => x[0])).size;   // rules written in a way the timetable cannot use: say so now, not after generating
    if (nr) toast(`Workbook opened. ${nr} rule${nr === 1 ? "" : "s"} on step 6 cannot be used as written (skipped or matching nothing): see Things to fix. It is saved for the school.`);
    return; }
  if (el.id === "loadJson") { const f = el.files[0]; if (!f) return; el.value = ""; let spec = null; try { spec = JSON.parse(await f.text()); } catch (err) { }
    if (!spec || !spec.school) { toast("That file is not a progress file."); return; }
    try { await adopt(spec, "Progress loaded from the file and saved for the school.", "Loaded from a file"); } catch (err) { toast("Could not reach the server: " + err.message); } return; }
  if (el.dataset.names) { setPath(el.dataset.names, el.value.split(",").map(t => t.trim()).filter(Boolean)); save(); render(); return; }
  if (el.dataset.list) { sc()[el.dataset.list] = el.value.split(",").map(s => s.trim()).filter(Boolean); if (el.dataset.list === "levels") ensureDays(); save(); render(); return; }
  if (el.id === "stuFile") { stuFile(el); return; }
  if (el.id === "tlFile") { tlFile(el); return; }
  if (el.id === "pastPick") { S.pastPick = el.value; return; }
  if (el.id === "stuCls" || el.id === "stuQ") { S.stu[el.id === "stuCls" ? "cls" : "q"] = el.value; render(); return; }
  if (["tgLv", "tgSubj", "tgT"].includes(el.id)) { S.tg[{ tgLv: "lv", tgSubj: "subj", tgT: "t" }[el.id]] = el.value; render(); return; }
  if (["pickA", "pickP"].includes(el.id)) { S.pick[el.id.slice(4).toLowerCase()] = el.value; return; }   // typed boxes: no redraw, or it would swallow the click on the button next to them
  if (["pickT", "pickG", "pickC", "pickS", "pickV", "pickD", "pickR"].includes(el.id)) { S.pick[el.id.slice(4).toLowerCase()] = el.value; render(); return; }
  if (el.id === "mLevel") { M.level = el.value; render(); return; }
  if (el.id === "mDept") { M.dept = el.value; M.extra = []; M.ticked.clear(); M.q = ""; M.adding = false; M.nf = null; render(); return; }
  if (["mnDept", "mnRole"].includes(el.id) && M.nf) { M.nf[el.id === "mnDept" ? "dept" : "role"] = el.value; render(); return; }
  if (["tfDept", "tfSubj", "tfQ"].includes(el.id)) { S.tf[{ tfDept: "dept", tfSubj: "subj", tfQ: "q" }[el.id]] = el.value; render(); return; }
  if (el.dataset.pick || el.dataset.pickall) return;
  if (el.dataset.pat !== undefined) { if (setPattern(S.spec.lessons[Number(el.dataset.pat)], el.value)) { save(); render(); } else { const x = S.spec.lessons[Number(el.dataset.pat)]; el.value = (x.pattern || []).length ? patText(x.pattern.map(Number)) : ""; el.focus(); } return; }
  if (el.dataset.set) { setSetting(el.dataset.set, el.value); save(); render(); return; }
  if (el.dataset.time) {   // a block-out's clock time: keep the times and block every period they overlap
    const [i, k] = el.dataset.time.split("|").map(Number), r = S.spec.rules[i];
    r.times = [...ruleTimes(r)]; r.times[k] = el.value; [r.from, r.to] = periodsBetween(r.times[0], r.times[1]); save(); render(); return; }
  if (el.dataset.fixlv !== undefined || el.dataset.fixwho !== undefined) {   // Fixed lessons: level and class (or Every class) decide what the rule applies to
    const tr = el.closest("tr"), r = S.spec.rules[Number(el.dataset.fixlv ?? el.dataset.fixwho)];
    setFixedWho(r, tr.querySelector("[data-fixlv]").value, tr.querySelector("[data-fixwho]").value); save(); render(); return;
  }
  const path = el.dataset.k; if (!path) return;
  if (el.type === "checkbox") { setPath(path, el.checked); save(); render(); return; }
  let v = el.value; if (el.type === "number") v = v === "" ? null : Number(v); if (v === "") v = null;
  if (/\.(from|to)$/.test(path) && v !== null) v = Number(v);
  if (/^spec\.school\.(weeks|periods_per_day|period_minutes|lesson_length)$/.test(path)) v = Number(v);
  setPath(path, v);
  const m = path.match(/^spec\.lessons\.(\d+)\.block$/);
  if (m && v) { const b = S.spec.blocks.find(x => x.block === v); if (b) { S.spec.lessons[m[1]].classes = [...(b.classes || [])]; S.spec.lessons[m[1]].level = b.level || S.spec.lessons[m[1]].level; } }
  const t = path.match(/^spec\.lessons\.(\d+)\.teachers\.(\d+)$/); if (t) S.spec.lessons[t[1]].teachers = (S.spec.lessons[t[1]].teachers || []).map(x => x || null);
  const gm = path.match(/^spec\.lessons\.(\d+)\.(students|block|subject|level)$/); if (gm) groupCode(Number(gm[1]));
  const sm = path.match(/^spec\.students\.(\d+)\.class$/); if (sm) S.spec.students[sm[1]].level = clsLevel(v) || null;
  const fx = path.match(/^spec\.rules\.(\d+)\.target$/);   // a fixed lesson names a class or a group code
  if (fx) { const r = S.spec.rules[fx[1]]; if (r.rule === "Fixed at" && ["Class", "Group"].includes(r.scope)) r.scope = classNames().includes(v) ? "Class" : "Group"; }
  if (/^spec\.school\.(weeks|periods_per_day)$/.test(path)) ensureDays();
  if (/\.(room|class|subject|name|block)$/.test(path)) renameRefs(e.target, path, v);
  save(); render(); poll();
});
function renameRefs() { /* references are by name; renaming leaves old names flagged as "(not on list)" for the user to fix */ }

/* ---------------- rows and helpers */
const periodAt = t => Math.min(Number(sc().periods_per_day) - 1, Math.max(0, Math.ceil((mins(t) - mins(sc().start_time)) / Number(sc().period_minutes || 20))));   // the first period that starts at or after t
function firstLesson() {   // the first lesson period of the first level's first day (a new fixed lesson starts there)
  const row = String(Object.values((S.spec.day_structure || {})[levels()[0]] || {})[0] || ""), p = row.search(/[LW]/);
  return p >= 0 ? p : 0;
}
function setFixedWho(r, lv, who) {   // Fixed lessons: Every class is the level (or, with Level All, the whole school); else a class or a group code
  if (who === EVERY) { if (lv && lv !== "All") Object.assign(r, { scope: "Level", target: lv, level: lv }); else { Object.assign(r, { scope: "School", target: "Whole school" }); delete r.level; } return; }
  r.level = lv && lv !== "All" ? lv : null; r.target = who || null; r.scope = classNames().includes(who) ? "Class" : "Group";
}
function addRow(k) {
  const lv = levels()[0];
  const blank = { venues: { room: "", kind: "classroom", capacity: 40 }, classes: { class: "", level: lv, size: 38, home_room: null },
    subjects: { subject: "", code: "", tag: "-", dept: (sc().departments || [])[0], periods: {} }, teachers: { name: "", short: "", dept: (sc().departments || [])[0], allowance: sc().type === "primary" ? 36 : 64, provisional: isHead() && !S.practice ? "Yes" : "No", can_teach: [] },
    blocks: { block: "", level: lv, classes: [] }, lessons: { level: lv, subject: null, block: null, classes: [], teachers: [], students: null },
    rules: { scope: "Level", target: null, rule: "Not in periods", week: "Both", day: "All", strength: "Must" },
    avail: { scope: "Teacher", target: null, rule: "Not available", week: "Both", day: "All", from: 0, to: 0, strength: "Must", times: [hhmm(0), hhmm(1)] },
    fixed: { scope: "Class", target: null, subject: null, rule: "Fixed at", level: lv, week: "Both", day: "Mon", from: 0, strength: "Must" },
    // the common rules, filled in as far as the setup allows: whole-school CCE, an HBL day, PE late in the day only in some rooms
    fixedall: { scope: "School", target: "Whole school", subject: subjectNames().find(n => /character|\bcce\b/i.test(n) || (subj(n) || {}).dept === "CCE") || null, rule: "Fixed at", week: Number(sc().weeks) === 2 ? "Odd" : "Both", day: "Mon", from: firstLesson(), strength: "Must" },
    hbl: { scope: "School", target: "Whole school", rule: "Only these subjects", week: Number(sc().weeks) === 2 ? "Even" : "Both", day: "Fri", from: null, to: null, strength: "Must", note: "HBL day: only these subjects",
      subject: ["English Language", "Mathematics", "Additional Mathematics", "MT", "SC"].filter(n => S.spec.subjects.some(s => subjectTest(n)(s.subject, s.dept))).join(", ") || null },
    venuerule: { scope: "Subject", target: subjectNames().find(n => /physical education|^pe$/i.test(n)) || null, rule: "Only in venues", week: "Both", day: "All", from: periodAt("11:00"), to: Number(sc().periods_per_day) - 1,
      venues: [], strength: "Must", note: "Late in the day only in these rooms" },
    roles: { role: "", what: "", allowance: null, group: "" },
    students: { id: "", name: "", level: clsLevel(S.stu.cls) || null, class: S.stu.cls || null, groups: [] } }[k];
  if (k === "students") S.stu.q = "";
  const into = { avail: "rules", fixed: "rules", fixedall: "rules", hbl: "rules", venuerule: "rules" }[k] || k; S.spec[into] = S.spec[into] || [];
  S.spec[into].push(JSON.parse(JSON.stringify(blank))); save();
  const show = () => { const last = document.getElementById(`${into}-${S.spec[into].length - 1}`); if (last) { last.scrollIntoView({ block: "center" }); const f = last.querySelector("input,select"); if (f) f.focus({ preventScroll: true }); } };
  render(); show(); poll();
}
/* a teaching group with no band and fewer students than its classes (a pull-out group, say 9 of 1A2) is a group of its
   own, not the whole class: it gets a code in Keep code, made like a band group's (level digit, subject code, level
   letter, then the first unused number), so the solver, the workbook and the student list all see it as a group */
function groupCode(i) {
  const x = S.spec.lessons[i]; if (!x || x.block || x.code_override || !x.subject) return;
  const n = Number(x.students), size = (x.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
  if (!(n > 0) || !size || n >= size) return;
  const s = subj(x.subject) || {}, letter = Object.fromEntries((sc().tags || []).map(([a, b]) => [a, b]));
  const pre = `${String(x.level).slice(-1)}${s.code || "??"}${letter[s.tag] || ""}`, used = new Set(lessonInfo().map(f => f.code));
  let k = 1; while (used.has(`${pre}${k}`)) k++;
  x.code_override = `${pre}${k}`;
  toast(`${x.subject} for ${n} of the ${size} students in ${(x.classes || []).join(", ")} is a group of its own, so it gets code ${x.code_override} (Keep code). If the rest of the class has this subject at the same time, put it in their band instead.`);
}
/* a band whose classes all split into its groups (English, Mother Tongue, Maths by level): every student takes one of
   them. Option and elective bands are for some of the students only. The committee can tick or untick it (Bands). */
const everyone = b => b.everyone ?? !/option|elective/i.test(b.block || "");
const family = n => String(n || "").replace(/\s+(G[1-3]|NA|NT|Express|Foundation)$/i, "").replace(/\s*\([^)]*\)/g, "").trim().toLowerCase();   // Science (Bio) G2 and Science G1: both Science
/* a student's Note excuses them from a band: "Exempt: Sec 1 Mother Tongue 1A1-1A9" (what the exempt choice in the groups
   picker writes), or free text naming the subject, such as "Exempt from MTL" or "exempt: Mother Tongue" */
const EXEMPT = "!exempt:", ALIAS = { mt: ["mother", "tongue"], mtl: ["mother", "tongue"], el: ["english"], hum: ["humanities"], sci: ["science"], math: ["mathematics"], maths: ["mathematics"] };
const noteWords = t => String(t || "").toLowerCase().match(/[a-z]{2,}/g) || [];
function exemptFrom(note, b) {
  if (!/exempt/i.test(note || "")) return false;
  const bands = blockNames(); let bw = null;
  return String(note).split(";").some(p => {
    if (!/exempt/i.test(p)) return false;
    const m = p.match(/^\s*exempt:\s*(.+?)\s*$/i); if (m && bands.includes(m[1])) return m[1] === b;
    bw = bw || new Set([...noteWords(b), ...S.spec.lessons.filter(x => x.block === b).flatMap(x => noteWords(x.subject))].filter(w => w.length > 2 && !["sec", "language", "and"].includes(w)));
    return noteWords(p).some(w => bw.has(w) || (ALIAS[w] || []).some(a => bw.has(a)));
  });
}
function setExempt(st, shown, picked) {   // the groups picker: "Exempt: band" in the Note for each band picked as exempt
  const keep = String(st.note || "").split(";").map(p => p.trim()).filter(Boolean).filter(p => { const m = p.match(/^exempt:\s*(.+)$/i); return !(m && shown.includes(m[1].trim())); });
  const add = picked.filter(b => !exemptFrom(keep.join("; "), b)).map(b => `Exempt: ${b}`);   // free text already covering it stays as it is
  st.note = [...keep, ...add].join("; ") || null;
}
function setPattern(x, typed) {   // false (with a message) when it cannot be read; empty goes back to the usual split
  if (!String(typed).trim()) { delete x.pattern; delete x.pattern_text; return true; }
  const p = parsePattern(typed); if (!p) { toast(`Could not read "${typed}". Write lessons like 5x3 + 2x2: how many, x, how many periods each.`); return false; }
  x.pattern = p; delete x.pattern_text; return true;
}
function helper(k) {
  if (k === "venues") { const pre = $("#hvPre").value, a = Number($("#hvFrom").value), b = Number($("#hvTo").value), kind = $("#hvKind").value; for (let i = a; i <= b; i++) S.spec.venues.push({ room: `${pre}${String(i).padStart(2, "0")}`, kind, capacity: 40 }); }
  if (k === "classes") {
    const lv = $("#hcLevel").value, size = Number($("#hcSize").value) || 38; const used = new Set(S.spec.classes.map(c => c.home_room)); const free = S.spec.venues.filter(v => (v.kind || "classroom") === "classroom" && !used.has(v.room)).map(v => v.room);
    $("#hcNames").value.split(",").map(s => s.trim()).filter(Boolean).forEach(n => S.spec.classes.push({ class: `${String(lv).slice(-1)}${n}`, level: lv, size, home_room: free.shift() || null }));
  }
  if (k === "teachers") { const dept = $("#htDept").value, allow = Number($("#htAllow").value) || null; $("#htNames").value.split("\n").map(s => s.trim()).filter(Boolean).forEach(n => S.spec.teachers.push({ name: n, short: n.split(" ")[0], dept, allowance: allow, provisional: isHead() && !S.practice ? "Yes" : "No", can_teach: [] })); }
  if (k === "groups") { const b = S.spec.blocks.find(x => x.block === $("#hbBlock").value), s = $("#hbSubj").value, n = Number($("#hbN").value) || 1, st = Number($("#hbSt").value) || null; if (!b || !s) { toast("Pick a band and a subject."); return; } for (let i = 0; i < n; i++) S.spec.lessons.push({ level: b.level, subject: s, block: b.block, classes: [...(b.classes || [])], teachers: [], students: st }); }
  if (k === "whole") { const lv = $("#hwLevel").value, s = $("#hwSubj").value; if (!s) { toast("Pick a subject."); return; } S.spec.classes.filter(c => c.level === lv).forEach(c => S.spec.lessons.push({ level: lv, subject: s, block: null, classes: [c.class], teachers: [], students: c.size })); }
  save(); render(); toast("Added.");
}

/* ---------------- ticked rows: deploy a teacher to many teaching groups, or put many students in a group or class */
function unpick() { S.pick.lessons.clear(); S.pick.students.clear(); S.pick.teachers.clear(); S.pick.last = {}; }
function pick(el, shift) {   // a tick box on a teaching-group or student row; shift-click ticks the run from the last one ticked
  const P = S.pick;
  if (el.dataset.pickall) { const k = el.dataset.pickall; (P.shown[k] || []).forEach(i => el.checked ? P[k].add(i) : P[k].delete(i)); render(); return; }
  const [k, n] = el.dataset.pick.split("."), i = Number(n), shown = P.shown[k] || [];
  const a = shown.indexOf(P.last[k]), b = shown.indexOf(i);
  (shift && a >= 0 && b >= 0 ? shown.slice(Math.min(a, b), Math.max(a, b) + 1) : [i]).forEach(j => el.checked ? P[k].add(j) : P[k].delete(j));
  P.last[k] = i; render();
}
function tgBar(load, info) {
  const P = S.pick, ix = [...P.lessons].filter(i => S.spec.lessons[i]); if (!ix.length) return "";
  const rows = ix.map(i => S.spec.lessons[i]), T = teacherNames();
  const yes = T.filter(t => rows.every(x => canTeach(t, x.subject, x.level))), no = T.filter(t => !yes.includes(t));
  const t = S.spec.teachers.find(x => x.name === P.t); let line = "", over = false;
  if (t) {
    const now = (load[t.name] || 0) + (Number(t.other_duties) || 0), more = ix.filter(i => !(S.spec.lessons[i].teachers || []).includes(t.name)).reduce((a, i) => a + info[i].tp, 0);
    over = t.allowance && now + more > Number(t.allowance);
    line = `${t.name}: ${now}${t.allowance ? ` of ${t.allowance}` : ""} periods now${more ? `, ${now + more} with these` : ""}`;
  }
  const off = t ? "" : "disabled";
  return `<div class="bulk row"><b>${ix.length} ticked</b> teacher <select id="pickT">${opt("", P.t, "pick…")}<optgroup label="Can teach all of them">${yes.map(n => opt(n, P.t)).join("")}</optgroup><optgroup label="Others">${no.map(n => opt(n, P.t)).join("")}</optgroup></select>
    <button data-bulk="t1" ${off} title="Replaces Teacher 1 on every ticked row">Make Teacher 1</button><button data-bulk="t2" ${off} title="Adds them as Teacher 2 or 3 (co-teaching), or Teacher 1 on a row with none">Add as co-teacher</button><button data-bulk="tx" ${off}>Take off</button>
    ${line ? `<span class="small ${over ? "over" : "muted"}">${esc(line)}</span>` : ""}
    <span class="muted">·</span> lessons <input id="pickP" value="${esc(P.p)}" placeholder="5x3 + 2x2" title="Leave empty to go back to the usual split" style="width:104px"><button data-bulk="pat">Set lessons</button><button class="small ghost" data-bulk="tnone">Clear ticks</button></div>`;
}
/* ---------------- step 5: the department map. Teachers are held by _id, so another browser's change cannot move a tick */
const MAPVIEW = "ttsetup.mapview";
const M = { view: "map", dept: "", tab: "classes", level: "", ticked: new Set(), lastTick: null, extra: [], q: "", profile: null, adding: false, nf: null };
try { if (localStorage.getItem(MAPVIEW) === "table") M.view = "table"; } catch (e) { }
function mapDept() { const D = sc().departments || []; if (!D.includes(M.dept)) M.dept = D[0] || ""; return M.dept; }
function tickedIdx() {   // indexes of the ticked teachers, in setup order, dropping any removed meanwhile
  M.ticked = new Set(DeptMap.prune([...M.ticked], S.spec));
  return S.spec.teachers.map((t, i) => [t, i]).filter(([t]) => t && M.ticked.has(t._id)).map(([, i]) => i);
}
function rosterList(dept) {   // the roster's rows (filtered by the search box) and the teachers found in other departments
  const T = S.spec.teachers, L = DeptMap.loads(S.spec, lessonInfo()), ro = DeptMap.roster(S.spec, dept, M.extra), q = People.key(M.q);
  const shown = ro.filter(i => !q || People.key(T[i].name || "").includes(q) || People.key(T[i].short || "").includes(q));
  const found = DeptMap.search(S.spec, M.q, dept).filter(i => !ro.includes(i));
  const trow = i => { const t = T[i], ld = L[t.name] || {}, pct = ld.allowance ? Math.min(100, Math.round(100 * ld.total / ld.allowance)) : 0;
    return `<div class="trow${M.ticked.has(t._id) ? " on" : ""}"><input type="checkbox" data-mtick="${esc(t._id)}" ${M.ticked.has(t._id) ? "checked" : ""} aria-label="Tick ${esc(t.name || "")}">
      <button class="avatar" data-mprofile="${esc(t._id)}" draggable="true" data-mdrag="${esc(t._id)}" title="${esc(t.name || "")}: profile">${avatarOf(t, 32)}</button>
      <div class="tname"><div>${esc(t.name || "")}${t.dept !== dept ? ` <span class="tag">${esc(t.dept || "")}</span>` : ""}${provisionalRow(t) ? ` <span class="tag">provisional</span>` : ""}</div>
      <div class="row small" style="gap:6px;flex-wrap:nowrap"><span class="muted">${esc(t.role || "")}</span>${ld.allowance ? `<div class="load${ld.over ? " over" : ""}" title="${ld.lessons} periods deployed${ld.duties ? ` + ${ld.duties} other duties` : ""}, allowance ${ld.allowance}"><i style="width:${pct}%"></i></div><span class="${ld.over ? "overtxt" : "muted"}">${ld.total} / ${ld.allowance}</span>` : `<span class="muted" title="No allowance yet">${ld.total || 0} periods</span>`}</div></div></div>`; };
  return `<div class="rlist keep">${shown.map(trow).join("") || `<p class="muted small">No one on this roster matches.</p>`}</div>
    ${found.length ? `<div class="found"><div class="muted small" style="margin:6px 0 2px">From other departments</div>${found.map(i => `<div class="trow"><span>${avatarOf(T[i], 24)}</span><span class="tname">${esc(T[i].name || "")} <span class="tag">${esc(T[i].dept || "")}</span></span><button class="small" data-madd="${esc(T[i]._id)}">+ Add to roster</button></div>`).join("")}</div>` : ""}`;
}
function newTeacherForm(dept) {   // + New teacher: a hire, or a post still to be filled
  const f = M.nf || (M.nf = { name: "", short: "", dept, role: roles().some(r => r.role === "EO") ? "EO" : (roles()[0] || {}).role || "", allowance: "" });
  const guide = r => { const x = roles().find(y => y.role === r); return x && x.allowance != null && x.allowance !== "" ? x.allowance : ""; };
  return `<div class="helper newt"><b>New teacher</b><div class="grid2" style="margin-top:6px">
    <label class="f">Name <input id="mnName" value="${esc(f.name)}" placeholder="Name, or New Mathematics teacher 1"></label>
    <label class="f">Short name <input id="mnShort" value="${esc(f.short)}" placeholder="${esc(f.name.trim().split(/\s+/)[0] || "first word of the name")}"></label>
    <label class="f">Department <select id="mnDept">${(sc().departments || []).map(d => opt(d, f.dept)).join("")}</select></label>
    <label class="f">Role <select id="mnRole">${opt("", f.role, "")}${roles().map(r => opt(r.role, f.role)).join("")}</select></label>
    <label class="f">Allowance <input id="mnAllow" type="number" value="${esc(f.allowance)}" placeholder="${esc(guide(f.role))}" title="Empty: the role's guide allowance"></label></div>
    <div class="row" style="margin-top:8px"><button class="primary" data-mnewgo>Add</button><button class="ghost" data-mnewcancel>Cancel</button>${isHead() && !S.practice ? `<span class="muted small">The committee confirms new teachers on step 4.</span>` : ""}</div></div>`;
}
/* an avatar that opens the profile and can be dragged, with a ✕ when `x` names the action */
function avx(t, size, x) {
  return `<span class="avx"><button class="avatar" data-mprofile="${esc(t._id)}" draggable="true" data-mdrag="${esc(t._id)}" title="${esc(t.name || "")}: profile">${avatarOf(t, size)}</button>${x ? `<button class="x" ${x} title="Take ${esc(t.name || "")} off">✕</button>` : ""}</span>`;
}
function basketsView(dept) {   // the middle column: one basket per subject of the department, and the staff room
  const T = S.spec.teachers, ro = DeptMap.roster(S.spec, dept, M.extra), B = DeptMap.baskets(S.spec, dept), staff = DeptMap.staffRoom(S.spec, ro);
  const bk = b => `<div class="basket" data-mbasket="${esc(b.subject)}" title="Click to add the ticked teachers, or drop teachers here"><div class="row small" style="justify-content:space-between"><b>${esc(b.subject)}</b><span class="muted">${b.teachers.length}</span></div>
    <div class="avs">${b.teachers.map(i => avx(T[i], 28, `data-mbx="${esc(T[i]._id)}|${esc(b.subject)}"`)).join("") || `<span class="muted small">No one yet</span>`}</div></div>`;
  return `<section class="baskets card"><h3 style="margin:0 0 4px">Can teach</h3><p class="muted small" style="margin:0 0 8px">Tick teachers and click a subject, or drag them in. Teachers of other departments show here too.</p>
    <div class="blist keep">${B.map(bk).join("") || `<p class="muted small">No subjects for ${esc(dept)} on step 3.</p>`}
    <div class="basket staff" data-mstaff title="Drop teachers here to take them out of this department's baskets"><div class="row small" style="justify-content:space-between"><b>Staff room</b><span class="muted">no subject yet · ${staff.length}</span></div>
    <div class="avs">${staff.map(i => avx(T[i], 28, "")).join("") || `<span class="muted small">Everyone on the roster has a subject.</span>`}</div></div></div></section>`;
}
function cardsView(dept) {   // the right-hand column: where the department's subjects are taught
  const info = lessonInfo(), cards = DeptMap.cards(S.spec, info, dept, M.tab, M.level);
  const tabs = [["classes", "Classes"], ["groups", "Teaching groups"], ["bands", "Bands"]].map(([k, l]) => `<button class="small ${M.tab === k ? "on" : ""}" data-mtab="${k}">${l}</button>`).join("");
  const tcard = (nm, key) => { const t = S.spec.teachers.find(x => x.name === nm); return t ? avx(t, 28, `data-mx="${esc(key)}|${esc(nm)}"`) : `<span class="chip">${esc(nm)} (not on list) <button class="x" data-mx="${esc(key)}|${esc(nm)}" title="Take ${esc(nm)} off">✕</button></span>`; };
  const card = c => { const key = c.kind === "class" ? `${c.li}|${c.cls}` : `${c.li}|`, room = DeptMap.MAX - c.teachers.length;
    return `<div class="gcard" data-mcard="${esc(key)}" title="Click to deploy the ticked teachers, or drop teachers here"><div class="row small" style="justify-content:space-between"><b>${esc(c.title)}</b><span class="muted">${esc(c.level)} · ${c.periods || "?"} periods</span></div><div class="small muted">${esc(c.subject)}</div>
      <div class="avs">${c.teachers.map(nm => tcard(nm, key)).join("")}${room > 0 ? `<span class="plus" title="Room for ${room} more">+</span>` : ""}</div></div>`; };
  const band = b => `<div class="lane"><div class="row small" style="justify-content:space-between"><b>${esc(b.title)}</b><span class="muted">${esc(b.level)} · ${b.groups.length} group${b.groups.length === 1 ? "" : "s"}</span></div>
    ${b.twice.map(nm => `<div class="small overtxt">${esc(nm)} is on two groups of this band: a band's groups meet at the same time.</div>`).join("")}${b.groups.map(card).join("")}</div>`;
  const what = { classes: "whole-class lessons", groups: "teaching groups", bands: "bands" }[M.tab];
  const body = cards.length ? cards.map(c => c.kind === "band" ? band(c) : card(c)).join("") : `<p class="muted small">No ${what} for ${esc(dept)}${M.level ? ` at ${esc(M.level)}` : ""} yet. Add them in the table view.</p>`;
  return `<section class="cards card"><div class="row" style="justify-content:space-between"><div class="row" style="gap:4px">${tabs}</div><select id="mLevel">${opt("", M.level, "All levels")}${levels().map(l => opt(l, M.level)).join("")}</select></div>
    <div class="clist keep" style="margin-top:8px">${body}</div></section>`;
}
function cardAt(key) {   // "li|cls" (a class card) or "li|" (a group card)
  const [li, cls] = String(key).split("|"), i = Number(li), x = S.spec.lessons[i]; if (!x) return null;
  return cls ? { kind: "class", li: i, cls, title: cls } : { kind: "group", li: i, title: (lessonInfo()[i] || {}).code };
}
function placeOn(card, idxs) {   // deploy teachers (ticked, or dropped) onto a card
  if (!card) return;
  if (!idxs.length) { toast("Tick teachers first, then click a card."); return; }
  const x = S.spec.lessons[card.li];
  let r = DeptMap.deploy(S.spec, card, idxs, {}), placed = r.placed.slice(), already = r.already.slice();
  const nb = r.refused.filter(f => f.why.endsWith("basket."));
  if (nb.length && confirm(`${listing(nb.map(f => f.name))} ${nb.length === 1 ? "is" : "are"} not in the ${x.subject} basket. Add ${nb.length === 1 ? "them" : "them all"} to the basket and place them?`)) {
    const r2 = DeptMap.deploy(S.spec, card, idxs, { addToBasket: true }); placed = placed.concat(r2.placed); r = r2;
  }
  const over = r.refused.filter(f => !f.why.endsWith("basket."));
  if (placed.length) { save(); render(); }
  const where = `${card.title} ${x.subject}`;
  if (placed.length) toast(`Placed ${listing(placed)} on ${where}.${already.length ? ` ${listing(already)} ${already.length === 1 ? "was" : "were"} already on it.` : ""}${r.split ? " That class is now a row of its own in the table." : ""}`);
  else if (over.length) toast(over[0].why);
  else if (already.length) toast(`${listing(already)} ${already.length === 1 ? "is" : "are"} already on ${where}.`);
}
function basketAdd(subject, idxs) {
  if (!idxs.length) { toast("Tick teachers first, then click a subject."); return; }
  const n = DeptMap.addToBasket(S.spec, idxs, subject);
  if (!n) { toast(`${idxs.length === 1 ? "They are" : "They are all"} in ${subject} already.`); return; }
  save(); render(); toast(`${n} added to ${subject}.`);
}
const stillTeaches = (name, subject) => S.spec.lessons.filter(x => x.subject === subject && (x.teachers || []).includes(name)).length;
function basketRemove(pairs) {   // [[teacher index, subject]]: take the subject off the teacher, after one question
  pairs = pairs.filter(([i]) => S.spec.teachers[i]);
  if (!pairs.length) return;
  const who = [...new Set(pairs.map(([i]) => S.spec.teachers[i].name))], subs = [...new Set(pairs.map(([, s]) => s))];
  const n = pairs.reduce((a, [i, s]) => a + stillTeaches(S.spec.teachers[i].name, s), 0);
  const q = `Take ${listing(subs)} off ${listing(who)}?${n ? ` ${who.length === 1 ? "They still teach" : "They still teach"} it on ${n} lesson row${n === 1 ? "" : "s"}, which Things to fix will flag.` : ""}`;
  if (!confirm(q)) return;
  pairs.forEach(([i, s]) => DeptMap.removeFromBasket(S.spec, i, s));
  save(); render(); toast("Taken off.");
}
function staffDrop(idxs) {   // dropped on the staff room: out of every basket of this department
  const subs = DeptMap.deptSubjects(S.spec, mapDept()), pairs = [];
  idxs.forEach(i => (S.spec.teachers[i].can_teach || []).forEach(c => { if (c && subs.includes(c.subject) && !pairs.some(([j, s]) => j === i && s === c.subject)) pairs.push([i, c.subject]); }));
  if (!pairs.length) { toast("They are in none of these baskets."); return; }
  basketRemove(pairs);
}
function cardRemove(key, name) {
  const card = cardAt(key); if (!card || !DeptMap.undeploy(S.spec, card, name)) return;
  save(); render(); toast(`Took ${name} off ${card.title} ${S.spec.lessons[card.li].subject}.`);
}
function dropIds(e) {   // the teacher indexes a drop carries (ids, as JSON in text/plain)
  let ids = []; try { ids = JSON.parse(e.dataTransfer.getData("text/plain") || "[]"); } catch (err) { }
  if (!Array.isArray(ids) || !S.spec) return [];
  return S.spec.teachers.map((t, i) => [t, i]).filter(([t]) => t && ids.includes(t._id)).map(([, i]) => i);
}
const dropZone = e => e.target.closest ? e.target.closest("[data-mbasket], [data-mstaff], [data-mcard]") : null;
document.addEventListener("dragstart", e => {
  const el = e.target.closest && e.target.closest("[data-mdrag]"); if (!el) return;
  const id = el.dataset.mdrag, ids = M.ticked.has(id) ? [...M.ticked] : [id];   // a ticked teacher drags every ticked teacher
  e.dataTransfer.setData("text/plain", JSON.stringify(ids)); e.dataTransfer.effectAllowed = "copyMove";
  const m = $(".map"); if (m) m.classList.add("dragging");
});
document.addEventListener("dragend", () => { document.querySelectorAll(".map.dragging, .over").forEach(x => x.classList.remove("dragging", "over")); });
document.addEventListener("dragover", e => { const z = dropZone(e); if (!z) return; e.preventDefault(); z.classList.add("over"); });
document.addEventListener("dragleave", e => { const z = dropZone(e); if (z && !(e.relatedTarget && z.contains(e.relatedTarget))) z.classList.remove("over"); });
document.addEventListener("drop", e => {
  const z = dropZone(e); if (!z) return; e.preventDefault(); z.classList.remove("over");
  const idxs = dropIds(e); if (!idxs.length) return;
  if (z.dataset.mbasket !== undefined) basketAdd(z.dataset.mbasket, idxs);
  else if (z.dataset.mstaff !== undefined) staffDrop(idxs);
  else placeOn(cardAt(z.dataset.mcard), idxs);
});
function mtick(el, shift) {   // a roster tick box; shift-click ticks the run from the last one ticked, in roster order
  const order = DeptMap.roster(S.spec, mapDept(), M.extra).map(i => S.spec.teachers[i]._id);
  const id = el.dataset.mtick, a = order.indexOf(M.lastTick), b = order.indexOf(id);
  (shift && a >= 0 && b >= 0 ? order.slice(Math.min(a, b), Math.max(a, b) + 1) : [id]).forEach(x => el.checked ? M.ticked.add(x) : M.ticked.delete(x));
  M.lastTick = id; render();
}
function mapAction(k, v) {   // the roster's buttons
  const T = S.spec.teachers, ro = DeptMap.roster(S.spec, mapDept(), M.extra);
  if (k === "mview") { M.view = v === "table" ? "table" : "map"; try { localStorage.setItem(MAPVIEW, M.view); } catch (e) { } render(); return; }
  if (k === "mall") { ro.forEach(i => M.ticked.add(T[i]._id)); render(); return; }
  if (k === "mnone") { M.ticked.clear(); render(); return; }
  if (k === "munplaced") { M.ticked = new Set(DeptMap.unplaced(S.spec, ro).map(i => T[i]._id)); render(); return; }
  if (k === "madd") { if (!M.extra.includes(v)) M.extra.push(v); M.q = ""; render(); return; }
  if (k === "mnew") { M.adding = true; M.nf = null; render(); const el = $("#mnName"); if (el) el.focus(); return; }
  if (k === "mnewcancel") { M.adding = false; M.nf = null; render(); return; }
  if (k === "mnewgo") {
    const f = { name: $("#mnName").value, short: $("#mnShort").value, dept: $("#mnDept").value, role: $("#mnRole").value, allowance: $("#mnAllow").value };
    const r = DeptMap.newTeacher(S.spec, f, roles(), isHead() && !S.practice);
    if (r.error) { toast(r.error); return; }
    save(); M.ticked.add(S.spec.teachers[r.i]._id); M.adding = false; M.nf = null; render();
    toast(isHead() && !S.practice ? "Added. The committee confirms new teachers on step 4." : "Added."); return;
  }
}
/* the one place the page asks for a teacher's avatar (drawn from the name; the seed is the "new look" count) */
const avatarOf = (t, size) => People.avatar(t.name, t.avatar, size);
function teacherBar() {
  const P = S.pick, ix = [...P.teachers].filter(i => S.spec.teachers[i]); if (!ix.length) return "";
  const s = P.s, has = ix.filter(i => (S.spec.teachers[i].can_teach || []).some(c => c.subject === s)).length;
  return `<div class="bulk"><div class="row avstrip">${ix.slice(0, 8).map(i => `<span title="${esc(S.spec.teachers[i].name || "")}">${avatarOf(S.spec.teachers[i], 24)}</span>`).join("")}${ix.length > 8 ? `<span class="muted small">+${ix.length - 8}</span>` : ""}</div><div class="row"><b>${ix.length} ticked</b> can teach <select id="pickS">${opt("", s, "pick a subject…")}${subjectNames().map(n => opt(n, s)).join("")}</select> at <select id="pickV">${scopes().map(v => opt(v, P.v)).join("")}</select>
    <button data-bulk="tc-add" ${s ? "" : "disabled"}>Add</button><button data-bulk="tc-rm" ${s && has ? "" : "disabled"} title="Takes the subject off them at every level">Remove subject</button>${s ? `<span class="muted small">${has} of ${ix.length} can teach it now</span>` : ""}</div>
    <div class="row" style="margin-top:6px">department <select id="pickD">${opt("", P.d, "")}${(sc().departments || []).map(d => opt(d, P.d)).join("")}</select><button data-bulk="tc-dept" ${P.d ? "" : "disabled"}>Set</button>
    <span class="muted">·</span> role <select id="pickR">${opt("", P.r, "")}${roles().map(r => opt(r.role, P.r)).join("")}</select><button data-bulk="tc-role" ${P.r ? "" : "disabled"}>Set</button>
    <span class="muted">·</span> allowance <input id="pickA" type="number" value="${esc(P.a)}" style="width:64px"><button data-bulk="tc-allow">Set</button>
    <button class="small ghost" data-bulk="tc-none">Clear ticks</button></div></div>`;
}
function bulkTeachers(k) {   // step 4: one change for every ticked teacher
  const P = S.pick, T = S.spec.teachers, ix = [...P.teachers].filter(i => T[i]), n = ix.length, s1 = n === 1 ? "" : "s";
  if (k === "tc-none") { P.teachers.clear(); render(); return; }
  if (!n) return;
  if (isHead() && !S.practice && ["tc-dept", "tc-role", "tc-allow"].includes(k)) return;   // a head sets only who can teach what
  let msg = "";
  if (k === "tc-add") {
    if (!P.s) return; let added = 0;
    for (const i of ix) {
      const ct = T[i].can_teach = T[i].can_teach || [];
      if (ct.some(c => c.subject === P.s && [P.v, "All"].includes(c.levels || "All"))) continue;
      if (P.v === "All") T[i].can_teach = ct.filter(c => c.subject !== P.s);   // all levels takes the place of narrower ones
      T[i].can_teach.push({ subject: P.s, levels: P.v }); added++;
    }
    msg = `${P.s} at ${P.v === "All" ? "every level" : P.v} added to ${added} teacher${added === 1 ? "" : "s"}` + (added < n ? ` (${n - added} could already teach it)` : "");
  }
  if (k === "tc-rm") {
    if (!P.s) return; const who = ix.map(i => T[i].name);
    ix.forEach(i => T[i].can_teach = (T[i].can_teach || []).filter(c => c.subject !== P.s));
    const stuck = S.spec.lessons.filter(x => x.subject === P.s && (x.teachers || []).some(t => who.includes(t))).length;
    msg = `${P.s} taken off ${n} teacher${s1}` + (stuck ? `; ${stuck} teaching group${stuck === 1 ? " still names" : "s still name"} one of them for it, flagged in Things to fix` : "");
  }
  if (k === "tc-dept") { if (!P.d) return; ix.forEach(i => T[i].dept = P.d); msg = `${n} teacher${s1} now in ${P.d}`; }
  if (k === "tc-role") { if (!P.r) return; ix.forEach(i => T[i].role = P.r); msg = `${n} teacher${s1} now ${P.r}`; }
  if (k === "tc-allow") { const a = Number(P.a); if (P.a === "" || !(a >= 0)) { toast("Type the allowance first."); return; } ix.forEach(i => T[i].allowance = a); msg = `Allowance ${a} for ${n} teacher${s1}`; }
  save(); render(); toast(`${msg}. Undo takes it back.`);
}
function stuBar() {
  const P = S.pick, L = S.spec.students, ix = [...P.students].filter(i => L[i]); if (!ix.length) return "";
  const info = lessonInfo(), lvs = new Set(ix.map(i => clsLevel(L[i].class) || L[i].level));
  const n = {}; L.forEach(s => (s.groups || []).forEach(g => n[g] = (n[g] || 0) + 1));
  const gs = S.spec.lessons.map((x, i) => [x, info[i].code]).filter(([x, c]) => c && c !== "Entire Class" && (lvs.size !== 1 || lvs.has(x.level))).sort((a, b) => a[1].localeCompare(b[1]));
  const g = gs.find(([, c]) => c === P.g);
  return `<div class="bulk row"><b>${ix.length} ticked</b> group <select id="pickG">${opt("", P.g, "pick…")}${gs.map(([x, c]) => opt(c, P.g, `${c} · ${x.subject}${x.block ? ` · ${x.block}` : ""} · ${n[c] || 0}/${x.students || "?"}`)).join("")}</select>
    <button data-bulk="sadd" ${g ? "" : "disabled"} title="A group in a band takes the place of the student's other group in that band">Add to group</button><button data-bulk="srm" ${g ? "" : "disabled"}>Remove from group</button>
    ${g ? `<span class="small ${g[0].students && (n[P.g] || 0) > Number(g[0].students) ? "over" : "muted"}">${esc(P.g)}: ${n[P.g] || 0} of ${g[0].students || "?"} students</span>` : ""}
    <span class="muted">·</span> class <select id="pickC">${opt("", P.c, "pick…")}${classNames().map(c => opt(c, P.c)).join("")}</select><button data-bulk="scls" ${P.c ? "" : "disabled"}>Move to class</button>
    <button class="small ghost" data-bulk="snone">Clear ticks</button></div>`;
}
function bulk(k) {   // one change for every ticked row, so one Undo takes it all back
  const P = S.pick, s1 = n => n === 1 ? "" : "s";
  if (k.startsWith("tc-")) { bulkTeachers(k); return; }
  if (k === "pat") {
    const ix = [...P.lessons].filter(i => S.spec.lessons[i]); if (!ix.length) return;
    const typed = ($("#pickP") || {}).value ?? P.p; P.p = typed;
    if (!ix.every(i => setPattern(S.spec.lessons[i], typed))) return;
    save(); render(); const info = lessonInfo(), off = ix.filter(i => typed.trim() && parsePattern(typed).reduce((a, v) => a + v, 0) !== info[i].p).length;
    toast((typed.trim() ? `Set ${patText(parsePattern(typed))} on ${ix.length} group${s1(ix.length)}` : `${ix.length} group${s1(ix.length)} back to the usual split`) + (off ? `; ${off} ${off === 1 ? "has" : "have"} a different number of periods and ${off === 1 ? "is" : "are"} flagged in Things to fix` : "") + ". Undo takes it back."); return;
  }
  if (k === "tnone" || k === "snone") { P[k === "tnone" ? "lessons" : "students"].clear(); render(); return; }
  if (k[0] === "t") {
    const t = P.t, ix = [...P.lessons].filter(i => S.spec.lessons[i]); if (!t || !ix.length) return;
    let n = 0, full = 0;
    for (const i of ix) {
      const x = S.spec.lessons[i], ts = (x.teachers || []).filter(Boolean), was = ts.includes(t);
      if (k === "t1") { if (ts[0] === t) continue; x.teachers = [t, ...ts.slice(1).filter(y => y !== t)]; }
      if (k === "t2") { if (was) continue; if (ts.length >= 3) { full++; continue; } x.teachers = [...ts, t]; }
      if (k === "tx") { if (!was) continue; x.teachers = ts.filter(y => y !== t); }
      n++;
    }
    save(); render();
    const { out } = issues(), has = m => k === "tx" ? 0 : ix.filter(i => (out.lessons[i] || []).some(x => x.startsWith(`${t} ${m}`))).length;
    const cant = has("is not set to teach"), twice = has("twice in this band");
    toast(`${{ t1: `${t} is now Teacher 1 of`, t2: `${t} now co-teaches`, tx: `${t} was taken off` }[k]} ${n} group${s1(n)}` + (full ? `; ${full} already had three teachers` : "")
      + (cant ? `; ${cant} ${cant === 1 ? "is a subject or level" : "are subjects or levels"} they are not set to teach (step 4)` : "")
      + (twice ? `; ${twice} ${twice === 1 ? "is" : "are"} in a band where they already teach a group, and a band's groups meet at the same time` : "") + ". Undo takes it back.");
    return;
  }
  const L = S.spec.students, ix = [...P.students].filter(i => L[i]); if (!ix.length) return;
  if (k === "scls") {
    const c = P.c; if (!c) return; ix.forEach(i => { L[i].class = c; L[i].level = clsLevel(c) || null; }); save(); render();
    const { out } = issues(), bad = ix.filter(i => (out.students[i] || []).some(m => m.includes(`not for class ${c}`))).length;
    toast(`Moved ${ix.length} student${s1(ix.length)} to ${c}` + (bad ? `; ${bad} have groups not for ${c} (see Things to fix)` : "") + ". Undo takes it back."); return;
  }
  const info = lessonInfo(), row = {}; S.spec.lessons.forEach((x, i) => { if (info[i].code && info[i].code !== "Entire Class") row[info[i].code] = x; });
  const g = P.g, x = row[g]; if (!x) return; let n = 0, swapped = 0, notFor = 0;
  for (const i of ix) {
    const s = L[i], gs = s.groups || [];
    if (k === "srm") { if (gs.includes(g)) { s.groups = gs.filter(h => h !== g); n++; } continue; }
    if (s.class && !(x.classes || []).includes(s.class)) notFor++;
    if (gs.includes(g)) continue;
    const keep = gs.filter(h => !x.block || (row[h] || {}).block !== x.block); swapped += gs.length - keep.length; s.groups = [...keep, g]; n++;
  }
  save(); render();
  toast(k === "srm" ? `Took ${n} student${s1(n)} out of ${g}. Undo takes it back.` : `Added ${n} student${s1(n)} to ${g}` + (swapped ? `; ${swapped} left their other group in ${x.block}` : "")
    + (notFor ? `; ${notFor} are in a class ${g} is not for (see Things to fix)` : "") + ". Undo takes it back.");
}

/* ---------------- restore: students with no groups and bands with no classes, from an earlier copy of the setup (each
   restore point the server keeps). Only what is empty now is filled. */
function lostCounts() {
  const banded = new Set(S.spec.blocks.flatMap(b => b.classes || [])); S.spec.lessons.forEach(x => { if (x.block) (x.classes || []).forEach(c => banded.add(c)); });
  return { stu: S.spec.students.filter(s => !(s.groups || []).length && banded.has(s.class)).length, bands: S.spec.blocks.filter(b => b.block && !(b.classes || []).length).length };
}
function restoreHelper() {
  const n = lostCounts(); if (!n.stu && !n.bands) return "";
  const what = [n.stu ? `${n.stu} student${n.stu === 1 ? " has" : "s have"} no groups` : "", n.bands ? `${n.bands} band${n.bands === 1 ? " has" : "s have"} no classes` : ""].filter(Boolean).join(" and ");
  return `<div class="helper"><b>Restore from an earlier copy</b> <span class="muted">${what}.</span>
    ${S.past ? `<select id="pastPick">${S.past.map((p, k) => opt(k, S.pastPick, `${p.what} · ${p.when} · ${Object.keys(p.groups).length} students with groups`)).join("")}</select> <button data-past="restore">Restore</button>`
      : `<button data-past="load">Find earlier copies</button>`}
    <p class="muted small" style="margin:6px 0 0">Fills only students with no groups now (matched by Student ID) and bands with no classes now, from a copy the server kept. Nothing else changes; Undo takes it back.</p></div>`;
}
async function pastAction(k) {
  if (k === "load") {
    let j; try { j = await getJSON("/api/past-setups"); } catch (e) { toast("Could not load the earlier copies."); return; }
    if (!j.copies.length) { toast("The server has no earlier copies yet."); return; }
    S.past = j.copies; S.pastPick = "0"; render(); return;
  }
  const p = (S.past || [])[Number(S.pastPick || 0)]; if (!p) return;
  const stu = S.spec.students.filter(s => !(s.groups || []).length && (p.groups[stuKey(s)] || []).length);
  const bands = S.spec.blocks.filter(b => b.block && !(b.classes || []).length && (p.classes[b.block] || []).length);
  if (!stu.length && !bands.length) { toast(`The copy of ${p.when} has nothing for them either. Try an older one.`); return; }
  const what = [stu.length ? `groups for ${stu.length} student${stu.length === 1 ? "" : "s"}` : "", bands.length ? `classes for ${bands.length} band${bands.length === 1 ? "" : "s"}` : ""].filter(Boolean).join(" and ");
  if (!confirm(`Restore ${what} from the ${p.what.toLowerCase()} copy of ${p.when}? Nothing else changes.`)) return;
  stu.forEach(s => s.groups = [...p.groups[stuKey(s)]]); bands.forEach(b => b.classes = [...p.classes[b.block]]);
  save(); render(); toast(`Restored ${what}. Undo takes it back.`);
}

/* ---------------- student list: paste, upload, replace or add */
function splitRow(line, d) {
  const out = []; let cur = "", q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (q) { if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; }
    else if (ch === '"' && !cur.trim()) { q = true; cur = ""; } else if (ch === d) { out.push(cur.trim()); cur = ""; } else cur += ch;
  }
  out.push(cur.trim()); return out;
}
function readStudents(text) {
  const lines = text.replace(/\r\n?/g, "\n").split("\n").filter(l => l.trim());
  const d = lines.some(l => l.includes("\t")) ? "\t" : lines.some(l => l.includes(";")) && !lines.some(l => l.includes(",")) ? ";" : ",";
  const rows = lines.map(l => splitRow(l, d));
  const cls = Object.fromEntries(classNames().map(c => [c.toLowerCase(), c])), canon = v => cls[String(v || "").trim().toLowerCase()] || String(v || "").trim();
  const codes = Object.fromEntries(lessonInfo().map(x => x.code).filter(c => c && c !== "Entire Class").map(c => [c.toLowerCase(), c]));
  // a header row (within the first 20) names the columns; otherwise the class column is the one whose cells are class names
  let h = rows.slice(0, 20).findIndex(r => r.some(c => /^(form\s*)?class$/i.test(c)) && r.some(c => /\bid\b|name|group/i.test(c)));
  const col = { id: -1, name: -1, cls: -1, level: -1, combo: -1, note: -1, groups: [] };
  if (h >= 0) {
    rows[h].forEach((c, j) => {
      if (/^(form\s*)?class$/i.test(c)) col.cls = j; else if (/\bid\b|admission|index|register/i.test(c) && col.id < 0) col.id = j;
      else if (/name/i.test(c) && col.name < 0) col.name = j; else if (/^level$/i.test(c)) col.level = j; else if (/combination/i.test(c)) col.combo = j;
      else if (/^notes?$/i.test(c)) col.note = j; else if (/group|code|subject/i.test(c)) col.groups.push(j);
    });
    if (col.groups.length && col.groups[col.groups.length - 1] === rows[h].length - 1) for (let j = rows[h].length; j < Math.max(...rows.map(r => r.length)); j++) col.groups.push(j);
  } else {
    const width = Math.max(...rows.map(r => r.length));
    for (let j = 0; j < width && col.cls < 0; j++) if (rows.filter(r => cls[String(r[j] || "").toLowerCase()]).length >= rows.length / 2) col.cls = j;
    if (col.cls < 0) return { error: "Could not find the Class column. Add a header row (Student ID, Name, Class, Groups) or check the class names match step 2." };
    if (col.cls >= 2) { col.id = col.cls - 2; col.name = col.cls - 1; } else if (col.cls === 1) col.name = 0;
    for (let j = col.cls + 1; j < width; j++) col.groups.push(j);
  }
  const get = (r, j) => (j >= 0 ? String(r[j] ?? "").trim() : "");
  const students = rows.slice(h + 1).map(r => {
    const c = canon(get(r, col.cls)), id = get(r, col.id), name = get(r, col.name);
    if (!c && !id && !name) return null;
    const groups = [...new Set(col.groups.flatMap(j => get(r, j).split(/[,;\s]+/)).filter(Boolean).map(g => codes[g.toLowerCase()] || g))];
    const s = { id: id || null, name: name || null, level: clsLevel(c) || get(r, col.level) || null, class: c || null, groups };
    if (get(r, col.combo)) s.combination = get(r, col.combo); if (get(r, col.note)) s.note = get(r, col.note);
    return s;
  }).filter(Boolean);
  return students.length ? { students } : { error: "No students found in what you pasted." };
}
function fillIds() {
  // a student without an ID gets one from their class (1A-01, 1A-02, ...), skipping IDs already used
  const used = new Set(S.spec.students.map(s => String(s.id || "")).filter(Boolean)), n = {};
  for (const s of S.spec.students) {
    if (s.id) continue; const c = s.class || "S"; let id;
    do { n[c] = (n[c] || 0) + 1; id = `${c}-${String(n[c]).padStart(2, "0")}`; } while (used.has(id));
    s.id = id; used.add(id);
  }
}
function stuApply(mode) {
  const L = S.spec.students;
  if (mode === "clear") { if (!confirm(`Remove all ${L.length} students from the list?`)) return; S.spec.students = []; S.stu = { cls: "", q: "" }; unpick(); save(); render(); toast("Student list cleared."); return; }
  const text = $("#stuPaste").value; if (!text.trim()) { toast("Paste the rows, or choose a file, first."); return; }
  const r = readStudents(text); if (r.error) { toast(r.error); return; }
  let updated = 0;
  if (mode === "replace") { if (L.length && !confirm(`Replace the ${L.length} students on the list with these ${r.students.length}?`)) return; S.spec.students = r.students; }
  else {
    const at = new Map(L.map((s, i) => [stuKey(s), i]));
    for (const s of r.students) { const k = stuKey(s); if (k && at.has(k)) { L[at.get(k)] = s; updated++; } else L.push(s); }
  }
  fillIds(); S.stu = { cls: "", q: "" }; unpick(); save(); render();
  const nc = new Set(r.students.map(s => s.class)).size;
  toast(`Read ${r.students.length} students in ${nc} class${nc === 1 ? "" : "es"}${updated ? ` (${updated} already on the list were updated)` : ""}.`);
}
async function stuFile(el) {
  const f = el.files[0]; el.value = ""; if (!f) return;
  let text;
  if (/\.xlsx$/i.test(f.name)) {
    const fd = new FormData(); fd.append("file", f);
    const r = await fetch("/api/read-table", { method: "POST", body: fd }); const j = await r.json().catch(() => ({}));
    if (!r.ok) { toast(j.error || "Could not read that file."); return; }
    text = j.rows.map(row => row.join("\t")).join("\n");
  } else text = await f.text();
  $("#stuPaste").value = text; $("#stuMsg").textContent = `${f.name} is in the box above. Check it, then press Replace or Add.`;
}

/* ---------------- step 4: uploading the teacher list. Read the list changes nothing: it shows what Apply would do. The
   preview lives here (TL), never in the setup, and is dropped when the paste box changes or the teachers change some
   other way (another person, Undo, an edit in the table). Committee only, or anyone in a practice copy. */
const TL = { text: "", read: null, sig: "", err: "", msg: "" };
const teachersSig = () => JSON.stringify(S.spec.teachers);
const mayUpload = () => committee() || S.practice;
function tlClear() { TL.read = null; TL.err = ""; TL.msg = ""; }
const tlPlan = () => People.planTeachers(S.spec.teachers, TL.read.teachers, roles(), sc().departments || []);
const TL_STALE = "The teachers changed since the list was read. Press Read the list again.";
const TL_NO_EXCEL = "Reading an Excel file needs the committee's code. Paste the list or choose a .csv file.";
const TL_LABEL = { short: "short name", dept: "department", role: "role", allowance: "allowance", other_duties: "other duties", note: "note" };
function uploadCard() {
  if (TL.read && TL.sig !== teachersSig()) tlClear();
  const xl = committee();   // an Excel file is read by the server, which reads it for the committee only
  return `<div class="card" id="teacherUpload"><h2>2 · Upload the teacher list</h2>
    <p class="muted">Columns: Name, Short name, Department, Role, Allowance, Other duties, Note. Only Name is needed; a column you leave out is not changed.${xl ? "" : " Paste the list or choose a .csv file."}</p>
    <textarea id="tlPaste" rows="5" spellcheck="false" placeholder="Name&#9;Short name&#9;Department&#9;Role">${esc(TL.text)}</textarea>
    <div class="row" style="margin-top:8px"><label class="filebtn">Choose a file (${xl ? ".xlsx or .csv" : ".csv"})<input type="file" id="tlFile" accept="${xl ? ".xlsx,.csv" : ".csv"}" hidden></label><button class="primary" data-tl="read">Read the list</button></div>
    <div id="tlPreview">${tlPreview()}</div></div>`;
}
function tlPreview() {
  if (TL.err) return `<div class="notice tlbox">${esc(TL.err)}</div>`;
  if (!TL.read) return "";
  const p = tlPlan(), n = p.add.length, m = p.update.length, same = TL.read.teachers.length - n - m;
  const gone = p.missing.map(i => S.spec.teachers[i].name || "(no name)"), g = gone.length;
  const changes = Object.entries(p.fields).sort((a, b) => b[1] - a[1]).map(([f, k]) => `${TL_LABEL[f] || f} ${k}`).join(" · ");
  const pairs = p.alike.slice(0, 12).map(x => `<div class="notice">${esc(`${x.add} in the list looks like ${x.missing} on the setup. If they are one person, make the two names match and read the list again. Otherwise Apply adds a second teacher.`)}</div>`).join("")
    + (p.alike.length > 12 ? `<p class="muted small">and ${p.alike.length - 12} more</p>` : "");
  return `<div class="tlbox">${TL.msg ? `<div class="okmsg">${esc(TL.msg)}</div>` : ""}
    <p class="tlsum"><b>${n} new · ${m} to update · ${same} unchanged</b></p>
    ${n ? `<p class="muted small">New: ${esc(listing(p.add.map(t => t.name), 12))}</p>` : ""}
    ${m ? `<p class="muted small">Changes: ${esc(changes)}</p>` : ""}
    ${pairs}
    ${TL.read.skipped.length ? `<ul class="tlnotes">${TL.read.skipped.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${p.unknownRoles.length ? `<div class="row">Not in the roles table: ${esc(p.unknownRoles.join(", "))} <button data-tl="roles">Add these roles</button></div>` : ""}
    ${p.unknownDepts.length ? `<div class="row">Not in the school's departments: ${esc(p.unknownDepts.join(", "))} <button data-tl="depts">Add these departments</button></div>` : ""}
    <div class="row" style="margin-top:8px"><button class="primary" data-tl="apply" ${n || m ? "" : "disabled"}>Apply</button></div>
    ${g ? `<div class="tlgone"><p>${g === 1 ? "1 teacher is" : `${g} teachers are`} not in this list.</p><p class="muted small">${esc(listing(gone, 12))}</p>
      <button class="danger" data-tl="remove">${g === 1 ? "Remove this teacher" : `Remove these ${g} teachers`}</button></div>` : ""}</div>`;
}
function tlRead() {
  tlClear();
  if (!TL.text.trim()) TL.err = "Paste the list, or choose a file, first.";
  else { const r = People.readTeachers(TL.text); if (r.error) TL.err = r.error; else { TL.read = r; TL.sig = teachersSig(); } }
  render();
}
function tlAction(k) {
  if (!mayUpload()) return;
  if (k === "read") { tlRead(); return; }
  if (!TL.read || TL.sig !== teachersSig()) { const stale = !!TL.read; tlClear(); if (stale) TL.err = TL_STALE; render(); return; }
  const p = tlPlan(), T = S.spec.teachers;
  TL.msg = "";
  if (k === "roles") {
    if (!Array.isArray(S.spec.roles)) S.spec.roles = [];
    p.unknownRoles.forEach(role => S.spec.roles.push({ role, what: "", allowance: null, group: "" }));
    save(); toast(`Added ${p.unknownRoles.join(", ")} to the roles. Undo takes it back.`);
  }
  if (k === "depts") { sc().departments = [...(sc().departments || []), ...p.unknownDepts]; save(); toast(`Added ${p.unknownDepts.join(", ")} to the departments. Undo takes it back.`); }
  if (k === "apply") {
    if (!p.add.length && !p.update.length) return;
    p.update.forEach(u => Object.assign(T[u.i], u.changes));   // the same row object: its _id and Can teach stay
    p.add.forEach(t => T.push(t));
    save(); TL.msg = `Added ${p.add.length}, updated ${p.update.length}. Undo takes it back.`; toast(TL.msg);
  }
  if (k === "remove") {
    const n = p.missing.length; if (!n) return;
    const gone = new Set(p.missing.map(i => T[i].name).filter(Boolean));
    const hit = S.spec.lessons.filter(x => (x.teachers || []).some(t => gone.has(t))).length;
    const like = new Set(p.alike.map(a => a.missing).filter(x => gone.has(x))).size;
    const warn = !like ? "" : n === 1 ? "This teacher looks like a name in the list. "
      : like === 1 ? "One of these teachers looks like a name in the list. " : `${like} of these teachers look like names in the list. `;
    const who = n === 1 ? "1 teacher who is" : `${n} teachers who are`;
    const lessons = !hit ? "No lesson on step 5 names them."
      : `${hit === 1 ? "1 lesson" : `${hit} lessons`} on step 5 name${hit === 1 ? "s" : ""} them, and lose${hit === 1 ? "s" : ""} them (a shared lesson keeps its other teacher).`;
    if (!confirm(`${warn}Remove ${who} not in this list? ${lessons} Undo takes it back.`)) return;
    [...p.missing].sort((a, b) => b - a).forEach(i => T.splice(i, 1));
    S.spec.lessons.forEach(x => { if ((x.teachers || []).some(t => gone.has(t))) x.teachers = x.teachers.filter(t => t && !gone.has(t)); });
    unpick(); save(); TL.msg = `Removed ${n} teacher${n === 1 ? "" : "s"}. Undo takes it back.`; toast(TL.msg);
  }
  TL.sig = teachersSig();   // what this card just did is not a change "by other means": the preview stays, worked out again
  render();
}
async function tlFile(el) {   // an .xlsx goes through the server (its teachers sheet), a .csv is read here; either way it is read at once
  const f = el.files[0]; el.value = ""; if (!f) return;
  let text;
  if (/\.xlsx$/i.test(f.name)) {
    if (!committee()) { tlClear(); TL.err = TL_NO_EXCEL; render(); return; }   // the server reads an Excel file for the committee only
    const fd = new FormData(); fd.append("file", f); fd.append("sheet", "teachers");
    const r = await fetch("/api/read-table", { method: "POST", body: fd }); const j = await r.json().catch(() => ({}));
    if (!r.ok) { toast(j.error || "Could not read that file."); return; }
    text = j.rows.map(row => row.join("\t")).join("\n");
  } else text = await f.text();
  TL.text = text; tlRead();
}
document.addEventListener("input", e => {
  if (e.target.id === "mQ") { M.q = e.target.value; const rb = $("#rbody"); if (rb) rb.innerHTML = rosterList(mapDept()); return; }   // the roster only: a full redraw would take the caret
  if (["mnName", "mnShort", "mnAllow"].includes(e.target.id) && M.nf) { M.nf[{ mnName: "name", mnShort: "short", mnAllow: "allowance" }[e.target.id]] = e.target.value; return; }
  if (e.target.id !== "tlPaste") return;
  TL.text = e.target.value;
  if (TL.read || TL.err || TL.msg) { tlClear(); const pv = $("#tlPreview"); if (pv) pv.innerHTML = ""; }
});

/* ---------------- pop-ups: class picker, can-teach editor */
function openPop(anchor) {
  const pop = $("#pop"); const path = anchor.dataset.path; const r = anchor.getBoundingClientRect();
  pop.style.left = `${Math.min(window.scrollX + r.left, window.scrollX + window.innerWidth - 440)}px`; pop.style.top = `${window.scrollY + r.bottom + 6}px`; pop.dataset.path = path; pop.dataset.what = anchor.dataset.pop;
  if (anchor.dataset.pop === "classes") {
    const cur = getPath(path) || []; const lv = anchor.dataset.level; const all = S.spec.classes; const mine = all.filter(c => !lv || c.level === lv), other = all.filter(c => lv && c.level !== lv);
    pop.innerHTML = `<h3>Classes</h3><div class="opts">${mine.map(c => `<label><input type="checkbox" value="${esc(c.class)}" ${cur.includes(c.class) ? "checked" : ""}>${esc(c.class)}</label>`).join("") || '<span class="muted">No classes at this level yet (step 2).</span>'}</div>
      ${other.length ? `<details><summary class="muted">Other levels</summary><div class="opts">${other.map(c => `<label><input type="checkbox" value="${esc(c.class)}" ${cur.includes(c.class) ? "checked" : ""}>${esc(c.class)}</label>`).join("")}</div></details>` : ""}
      <div class="row"><button class="small" data-popall="1">All</button><button class="small" data-popnone="1">None</button><button class="small primary" data-popdone="1">Done</button></div>`;
  } else if (anchor.dataset.pop === "groups") {
    // one choice per block (its groups run at the same time), ticks for groups outside a block
    const cur = getPath(path) || [], c = anchor.dataset.cls, info = lessonInfo(), blocks = new Map(), other = [], note = (getPath(path.replace(/\.groups$/, "")) || {}).note;
    S.spec.lessons.forEach((x, i) => {
      const code = info[i].code; if (!code || code === "Entire Class" || !(x.classes || []).includes(c)) return;
      if (x.block) { if (!blocks.has(x.block)) blocks.set(x.block, []); blocks.get(x.block).push([code, x.subject]); } else other.push([code, x.subject]);
    });
    const known = new Set([...[...blocks.values()].flat(), ...other].map(([g]) => g)), lost = cur.filter(g => !known.has(g));
    const lab = (type, name, g, s, on) => `<label title="${esc(s || "")}"><input type="${type}" name="${name}" value="${esc(g)}" ${on ? "checked" : ""}><span>${esc(g)}${s ? ` <span class="muted">${esc(s)}</span>` : ""}</span></label>`;
    pop.innerHTML = `<h3>Groups${c ? ` for ${esc(c)}` : ""}</h3>` + (!c ? `<p class="muted">Pick the student's class first.</p>` : "")
      + [...blocks].map(([b, gs], k) => { const inIt = gs.some(([g]) => cur.includes(g)), ex = !inIt && exemptFrom(note, b);
        return `<div class="gblock" data-band="${esc(b)}"><div class="muted small">${esc(b)}</div><div class="opts wide">${lab("radio", `gb${k}`, "", "none", !inIt && !ex)}<label title="Not taking this subject: no lesson in this band. Written into the Note."><input type="radio" name="gb${k}" value="${esc(EXEMPT + b)}" ${ex ? "checked" : ""}><span>exempt</span></label>${gs.map(([g, s]) => lab("radio", `gb${k}`, g, s, cur.includes(g))).join("")}</div></div>`; }).join("")
      + (other.length ? `<div class="gblock"><div class="muted small">Groups outside a band</div><div class="opts wide">${other.map(([g, s]) => lab("checkbox", "", g, s, cur.includes(g))).join("")}</div></div>` : "")
      + (lost.length ? `<div class="gblock"><div class="muted small">Not on step 5 for ${esc(c || "this class")} (untick to remove)</div><div class="opts wide">${lost.map(g => lab("checkbox", "", g, "", true)).join("")}</div></div>` : "")
      + (c && !blocks.size && !other.length ? `<p class="muted">No groups on step 5 include ${esc(c)} yet.</p>` : "")
      + `<div class="row"><button class="small primary" data-popdone="1">Done</button></div>`;
  } else if (anchor.dataset.pop === "subjects") {   // Only these subjects (an HBL day): a department, or subjects without their G1/G2/G3 tag
    const cur = new Set(namesList(getPath(path)).map(n => n.toLowerCase())), by = new Map();
    S.spec.subjects.filter(s => s.subject).forEach(s => { const d = s.dept || "Other"; if (!by.has(d)) by.set(d, new Set()); by.get(d).add(untag(s.subject)); });
    const box = (v, label, cls = "") => `<label class="${cls}"><input type="checkbox" value="${esc(v)}" ${cur.has(String(v).toLowerCase()) ? "checked" : ""}>${label}</label>`;
    const known = new Set([...by.keys(), ...[...by.values()].flatMap(s => [...s])].map(x => String(x).toLowerCase())), lost = namesList(getPath(path)).filter(n => !known.has(n.toLowerCase()));
    pop.innerHTML = `<h3>Subjects taught then</h3><p class="muted small" style="margin:0 0 6px">Tick a department for all its subjects, or single subjects (every G1/G2/G3 group of it). Every other lesson is kept out of those periods.</p>`
      + [...by].map(([d, ss]) => `<div class="gblock"><div class="opts wide">${d !== "Other" ? box(d, `<b>All ${esc(d)}</b>`) : ""}${[...ss].map(s => box(s, esc(s))).join("")}</div></div>`).join("")
      + (lost.length ? `<div class="gblock"><div class="muted small">Not on step 3 (untick to remove)</div><div class="opts wide">${lost.map(n => box(n, esc(n))).join("")}</div></div>` : "")
      + `<div class="row"><button class="small" data-popnone="1">None</button><button class="small primary" data-popdone="1">Done</button></div>`;
  } else if (anchor.dataset.pop === "rooms") {   // Only in venues: the rooms, by kind
    const cur = namesList(getPath(path)), by = new Map();
    S.spec.venues.filter(v => v.room).forEach(v => { const k = v.kind || "classroom"; if (!by.has(k)) by.set(k, []); by.get(k).push(v.room); });
    const order = [...by.keys()].sort((a, b) => (a === "classroom") - (b === "classroom"));
    pop.innerHTML = `<h3>Rooms they may use then</h3>` + order.map(k => `<div class="gblock"><div class="muted small">${esc(k)}</div><div class="opts">${by.get(k).map(x => `<label><input type="checkbox" value="${esc(x)}" ${cur.includes(x) ? "checked" : ""}>${esc(x)}</label>`).join("")}</div></div>`).join("")
      + `<div class="row"><button class="small" data-popnone="1">None</button><button class="small primary" data-popdone="1">Done</button></div>`;
  } else {
    const cur = getPath(path) || [];
    pop.innerHTML = `<h3>Can teach</h3><div id="ctRows">${cur.map((c, i) => ctRow(c, i)).join("")}</div><div class="row" style="margin-top:8px"><button class="small" data-ctadd="1">+ Subject</button><button class="small primary" data-popdone="1">Done</button></div>`;
  }
  pop.hidden = false;
}
const ctRow = (c, i) => `<div class="row" style="margin-bottom:6px" data-ct="${i}"><select data-ctf="subject">${opt("", c.subject, "")}${subjectNames().map(s => opt(s, c.subject)).join("")}</select><select data-ctf="levels">${scopes().map(s => opt(s, c.levels || "All")).join("")}</select><button class="small danger" data-ctdel="${i}">✕</button></div>`;
$("#pop").addEventListener("click", e => {
  const pop = $("#pop"); const path = pop.dataset.path; e.stopPropagation();
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.popall || b.dataset.popnone) pop.querySelectorAll("input[type=checkbox]").forEach(x => { if (!x.closest("details") || b.dataset.popnone) x.checked = !!b.dataset.popall; });
  if (b.dataset.ctadd) { const cur = readCt(); cur.push({ subject: "", levels: "All" }); $("#ctRows").innerHTML = cur.map(ctRow).join(""); }
  if (b.dataset.ctdel) { const cur = readCt(); cur.splice(Number(b.dataset.ctdel), 1); $("#ctRows").innerHTML = cur.map(ctRow).join(""); }
  if (b.dataset.popdone) { commitPop(); }
});
function readCt() { return [...document.querySelectorAll("#ctRows [data-ct]")].map(r => ({ subject: r.querySelector('[data-ctf="subject"]').value, levels: r.querySelector('[data-ctf="levels"]').value })); }
function commitPop() {
  const pop = $("#pop"); if (pop.hidden) return; const path = pop.dataset.path;
  if (pop.dataset.what === "classes") setPath(path, [...pop.querySelectorAll("input[type=checkbox]:checked")].map(x => x.value));
  else if (pop.dataset.what === "subjects") setPath(path, [...new Set([...pop.querySelectorAll("input[type=checkbox]:checked")].map(x => x.value))].join(", ") || null);   // one cell, as on the workbook
  else if (pop.dataset.what === "rooms") setPath(path, [...pop.querySelectorAll("input[type=checkbox]:checked")].map(x => x.value));
  else if (pop.dataset.what === "groups") {
    const vals = [...pop.querySelectorAll("input:checked")].map(x => x.value).filter(Boolean), st = getPath(path.replace(/\.groups$/, ""));
    setPath(path, vals.filter(v => !v.startsWith(EXEMPT)));
    if (st) setExempt(st, [...pop.querySelectorAll("[data-band]")].map(x => x.dataset.band), vals.filter(v => v.startsWith(EXEMPT)).map(v => v.slice(EXEMPT.length)));
  }
  else setPath(path, readCt().filter(c => c.subject));
  const lc = pop.dataset.what === "classes" && path.match(/^spec\.lessons\.(\d+)\.classes$/); if (lc) groupCode(Number(lc[1]));
  pop.hidden = true; save(); if (!tryHeld()) render(); poll();
}

/* ---------------- the server: what is published, access codes, the volume */
const G = { st: null, timer: null, inflight: false };
async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { location.href = "/login"; return null; }
  if (!r.ok) { toast(j.error || "Something went wrong."); return null; }
  return j;
}
async function poll() {   // every few seconds: the published timetable and the deployment's state (G.st)
  clearTimeout(G.timer);
  if (G.inflight) { G.timer = setTimeout(poll, 500); return; }
  G.inflight = true;
  try {
    const r = await fetch("/api/status");
    if (r.status === 401) { location.href = "/login"; return; }
    G.st = await r.json();
    paintPublished();
  } catch (e) { }
  G.inflight = false;
  G.timer = setTimeout(poll, 5000);
}
/* Will it fit? The server's sums on the setup as it is now (checks.findings): each class's periods against its lesson
   time, lessons against the stretches between breaks, special rooms, teachers' time, floating recess and the rules.
   Run when the Download step opens and again whenever the setup has changed since. */
const FIT = { key: null, busy: false, res: null, err: "" };
async function fitCheck(force) {
  if (!S.spec) return;
  if (!force && FIT.key === S.last && (FIT.busy || FIT.res || FIT.err)) { paintFit(); return; }
  const key = S.last; Object.assign(FIT, { key, busy: true, res: null, err: "" }); paintFit();
  try {
    const r = await fetch("/api/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: key });
    if (r.status === 401) { location.href = "/login"; return; }
    const j = await r.json().catch(() => ({}));
    if (FIT.key !== key) return;   // the setup changed while this was running: a newer check is on its way
    if (r.ok) FIT.res = j; else FIT.err = j.error || "The check could not run.";
  } catch (e) { if (FIT.key === key) FIT.err = "Could not reach the server: " + e.message; }
  if (FIT.key === key) { FIT.busy = false; paintFit(); }
}
function paintFit() {
  const el = $("#fitCard"); if (!el) return;
  const head = `<h2>Will it fit?</h2><p class="muted">The sums on this setup before it goes to the AI agent: each class's periods against its lesson time, lessons against the stretches between breaks, special rooms, teachers' time and the rules.</p>`;
  if (FIT.busy) { el.innerHTML = head + `<p class="muted">Checking…</p>`; return; }
  if (FIT.err) { el.innerHTML = head + `<p class="issue">${esc(FIT.err)}</p><button id="fitAgain">Check again</button>`; return; }
  const j = FIT.res; if (!j) { el.innerHTML = head; return; }
  const item = f => { const at = stepAt(f.area); return `<li>${esc(f.text)}${at > 0 ? ` <button class="small" data-step="${at}">Open ${esc(STEPS[at][1].replace(/^\d+ /, ""))}</button>` : ""}</li>`; };
  const hard = j.findings.filter(f => f.level === "critical"), soft = j.findings.filter(f => f.level !== "critical");
  el.innerHTML = head + (hard.length
      ? `<p class="issue crit">${hard.length} thing${hard.length === 1 ? "" : "s"} will not fit: no timetable can be made until ${hard.length === 1 ? "it is" : "they are"} fixed.</p>
         <details open><summary class="sev crit">Critical · ${hard.length}</summary><ul class="fitlist">${hard.map(item).join("")}</ul></details>`
      : `<p class="okmsg">Nothing critical: by these sums a timetable can be made from this setup.</p>`)
    + (soft.length ? `<details ${hard.length ? "" : "open"}><summary class="sev">Warnings · ${soft.length}</summary><p class="muted small">A timetable can still be made; a person should look at these.</p><ul class="fitlist">${soft.map(item).join("")}</ul></details>` : "")
    + `<div class="row" style="margin-top:10px"><button id="fitAgain">Check again</button><span class="muted small">Checked against the setup as it is on this page now.</span></div>`;
}
function paintPublished() {   // the Publish step's lower card: what teachers and students see now, the downloads and the codes
  const el = $("#pubNow"), st = G.st; if (!el || !st) return;
  const p = st.published, f = p ? p.files || {} : {};
  el.innerHTML = `<h2>Published now</h2>` + (p ? `<p class="${p.ok ? "okmsg" : "issue"}">Published ${esc(p.at)}${p.source ? ` from ${esc(p.source)}` : ""} · ${p.classes} classes · ${p.students} students${p.after ? ` · ${p.after} after school` : ""}</p>
      <div class="row"><a href="/timetable" target="_blank"><button class="primary">Open the timetable</button></a></div>
      <h3>Downloads</h3><div class="links"><a href="/files/excel">Excel, every timetable</a><a href="/files/zip">PDFs, one per class, teacher, room and student (zip)</a>${f.db ? `<a href="/files/db" title="Every lesson, class, teacher and room as a SQLite database, for other systems to import. It also holds the setup, so Make printouts can rebuild everything from it.">Timetable database (.sqlite), for other systems</a>` : ""}
      ${Object.keys(f.books || {}).map(k => `<a href="/files/book/${k}">${k[0].toUpperCase() + k.slice(1)}: all in one PDF</a>`).join("")}</div>
      <h3>Personal student codes</h3>${p.students && !p.personal ? `<p class="issue">Personal codes are off until SECRET_KEY is set in Railway variables: without it, anyone who knows a Student ID could work out that student's code.</p>` : p.students ? `<div class="links"><a href="/api/code-slips.pdf">Code slips to print, by class (PDF)</a><a href="/api/codes.csv">Code list (CSV)</a></div>` : `<p class="muted small">Add students on the Students step to give each one a personal code.</p>`}`
    : `<p class="muted">Nothing published yet. Teachers and students see a "not published yet" page.</p>`) +
    `<h3>Access codes</h3><ul class="codes">${[["committee", "Committee"], ["teacher", "Teachers"], ["student", "Students"]].map(([k, t]) => `<li>${t}: ${st.codes && st.codes[k] ? "set" : "<b>not set</b>"}</li>`).join("")}<li>Department heads: ${st.codes && st.codes.head ? "set" : "not set (no heads' sign-in)"}</li></ul>
    ${(st.code_problems || []).map(x => `<p class="issue">${esc(x)}</p>`).join("")}${st.volume ? "" : `<p class="issue">No Railway volume: the published timetable will be lost on the next deploy. Add a volume (see README).</p>`}`;
}

/* ---------------- downloads */
document.addEventListener("change", e => {
  if (e.target.id === "exSetup" || e.target.id === "exTT") { const f = e.target.files[0]; $("#" + e.target.id + "Name").textContent = f ? f.name : "none chosen"; $("#imResult").innerHTML = ""; }
});
/* the chosen setup workbook and timetable as form data, or null (with a message) when something is missing */
function timetableForm() {
  const a = $("#exSetup").files[0], b = $("#exTT").files[0];
  const isDb = b && /\.(sqlite3?|db)$/i.test(b.name);
  if (!b || (!a && !isDb)) { toast(b ? "Choose the setup workbook too (a timetable database from this app can come alone)." : "Choose the timetable: a workbook or a timetable database."); return null; }
  const fd = new FormData(); if (a) fd.append("setup", a); fd.append("timetable", b); return fd;
}
async function makePrintouts() {
  const msg = $("#exMsg"), fd = timetableForm(); if (!fd) return;
  fd.append("single", $("#exSingle").checked ? "1" : "0");
  const go = $("#exGo"); go.disabled = true; msg.textContent = "Making printouts… a school with 600 students takes about a minute.";
  try {
    const r = await fetch("/api/export", { method: "POST", body: fd });
    if (!r.ok) { const j = await r.json().catch(() => ({})); msg.textContent = ""; toast(j.error || "Could not make the printouts."); return; }
    const name = (r.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)"?/);
    dl(await r.blob(), name ? name[1] : "Timetables.zip"); msg.textContent = r.headers.get("X-Checks") || "Done.";
  } catch (err) { msg.textContent = ""; toast("Could not make the printouts: " + err.message); }
  finally { go.disabled = false; }
}
/* a timetable made outside the app: check it against its setup, then (publish) make it the published timetable */
async function importTimetable(publish) {
  const fd = timetableForm(); if (!fd) return;
  fd.append("publish", publish ? "1" : "0");
  const box = $("#imResult"), btns = ["#imCheck", "#imPublish", "#exGo"].map(q => $(q)).filter(Boolean);
  btns.forEach(x => x.disabled = true);
  box.innerHTML = `<p class="muted" style="margin-top:10px">${publish ? "Publishing: making the PDFs, the Excel workbook and the timetable pages (about a minute for a school with 600 students)…" : "Checking the timetable against its setup…"}</p>`;
  try {
    const r = await fetch("/api/import-timetable", { method: "POST", body: fd }), j = await r.json().catch(() => ({}));
    if (!r.ok) { box.innerHTML = ""; toast(j.error || (publish ? "Could not publish the timetable." : "Could not check the timetable.")); return; }
    box.innerHTML = importHTML(j);
    if (j.published) { toast("Published. Teachers and students now see this timetable."); poll(); }
  } catch (err) { box.innerHTML = ""; toast("Could not reach the server: " + err.message); }
  finally { btns.forEach(x => x.disabled = false); }
}
function importHTML(j) {
  const list = (xs, more) => `<ul>${xs.map(x => `<li>${esc(x)}</li>`).join("")}${more ? `<li>…and ${more} more</li>` : ""}</ul>`;
  const head = `<h3 style="margin-top:14px">${esc(j.school)} · ${esc(j.timetable)}</h3><p class="muted small">${j.lessons} lessons · ${j.classes} classes · ${j.teachers} teachers · ${j.students} students</p>`;
  if (j.published) return head + `<div class="okmsg">Published. Teachers and students now see this timetable.</div>
    <div class="row" style="margin-top:8px"><a href="/timetable" target="_blank"><button class="primary">Open the timetable</button></a></div>
    <p class="muted small">Its downloads and the personal student codes are below.</p>`;
  const pub = G.st && G.st.published;
  return head + (j.other_school ? `<p class="issue">This timetable is for <b>${esc(j.school)}</b>, but the setup saved in the app is for <b>${esc(j.other_school)}</b>. Check it is the right file.</p>` : "")
    + (j.ok ? `<div class="okmsg">All checks passed: no teacher, class, room or student is double-booked, every lesson is in lesson time, and every subject has the periods the setup plans.</div>`
            : `<details open><summary class="sev crit">${j.problems.length + j.more} problem${j.problems.length + j.more === 1 ? "" : "s"} found</summary>${list(j.problems, j.more)}</details>`)
    + (j.after.length ? `<details><summary>${j.after.length} lesson${j.after.length === 1 ? " is" : "s are"} after school</summary>${list(j.after)}</details>` : "")
    + (j.notes.length ? `<details><summary>Notes</summary>${list(j.notes)}</details>` : "")
    + `<p class="muted small" style="margin-top:8px">${pub ? `Publishing replaces the timetable published ${esc(pub.at)}${pub.source ? ` (from ${esc(pub.source)})` : ""}.` : "Nothing is published yet."}${j.ok ? "" : " You can still publish it; the problems stay listed in its Read me sheet."}</p>
    <div class="row"><button class="primary" id="imPublish">Publish this timetable</button></div>`;
}
function dl(blob, name) { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); }
async function buildXlsx() {
  toast("Building your workbook…");
  const r = await fetch("/api/build", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.spec) });
  if (!r.ok) { const j = await r.json().catch(() => ({})); toast(j.error || "Could not build the workbook."); return; }
  dl(await r.blob(), `${(sc().name || "School").replace(/[^\w -]/g, "").trim().replace(/ /g, "_")}_Timetable_Setup.xlsx`);
}

/* others' changes kept aside while a box or pop-up was in use: shown once the person commits or leaves it */
document.addEventListener("change", () => setTimeout(tryHeld, 0));
document.addEventListener("focusout", () => setTimeout(tryHeld, 0));
/* on load: the server's copy, with what this browser had not sent yet on top (unless the committee has replaced the
   setup since); while the server cannot be reached, those changes stay kept here and the page tries again */
async function openPage() {
  let srv = null;
  await poll();   // the status first: it says whether this is the committee or a head
  try {
    srv = await fetchSetup(); if (!srv) return;
    if (srv.spec) {
      const local = saved(); let pending = local && Array.isArray(local.pending) && local.pending.length ? local.pending : null;
      if (pending && local.v !== srv.v) {
        const r = await fetch(`/api/setup/changes?since=${Number(local.v) || 0}&client=${encodeURIComponent(SYNC.client)}`);
        if (!r.ok) throw new Error(`status ${r.status}`);
        const j = await r.json();
        if (j.reset && j.replaced) { pending = null; SYNC.kept = true; toast(DROPPED); }
      }
      await openServer(srv, local ? local.step : 1);
      // pending was kept here and never accepted by the server (keepLocal drops what it accepts), so it goes on top
      if (pending) { Sync.apply(S.spec, pending); save({ quiet: true }); }
    }
  } catch (e) {
    if (!S.spec) {
      $("#main").innerHTML = `<div class="card"><h1>Cannot reach the server</h1><p class="lead">The changes this browser had not sent yet are kept here and will be sent when the server answers. The page tries again every 5 seconds.</p></div>`;
      setTimeout(openPage, 5000); return;
    }
  }
  if (!S.asking) S.asking = oldChanges();
  render(); if (S.spec) syncNow();
}
openPage();

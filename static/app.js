"use strict";
/* Timetable Setup: a step-by-step editor for the timetable setup workbook. State lives in S.spec (same shape the
   server's ttgen package reads and writes); every list feeds the drop-downs of the later steps. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const KEY = "ttsetup.v1";
const S = { kind: null, spec: null, meta: null, step: 0, brush: "L", stu: { cls: "", q: "" }, tg: { lv: "", subj: "", t: "" }, tf: { dept: "", q: "" }, pick: { lessons: new Set(), students: new Set(), teachers: new Set(), shown: {}, last: {}, t: "", g: "", c: "", d: "", r: "", a: "", p: "" }, undo: [], redo: [], last: null };
const STEPS = [["start", "Start"], ["school", "School & day"], ["venues", "1 Venues"], ["classes", "2 Classes"], ["subjects", "3 Subjects"],
  ["teachers", "4 Teachers"], ["lessons", "5 Department map"], ["rules", "6 Configuration & constraints"], ["download", "7 Download"], ["edit", "8 Upload and edit"], ["publish", "9 Publish"], ["students", "Students"]];

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
  // ids first, then the Class Parents rule (a lesson it makes takes its id from its class and subject); hand: only a person's own edit may mark "Changed by hand"
  // a head cannot change these lessons: running the rule on a head's page would make a missing lesson the server then refuses, reported to the head as a change they never made
  if (S.spec) { Sync.ensureIds(S.spec); if (!(isHead() && !S.practice)) Parents.settle(S.spec, S.snap, !(o && (o.quiet || o.remote))); }
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
    const at = { generate: "edit", adjust: "edit" }[x.at] || x.at;   // steps that no longer exist: their work ends on Upload and edit now
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
      const ps = j.patches || [], mineAt = typeof j.mine === "number" ? j.mine : null;   // patches after our own ops (the server's put-right) apply after them
      const theirs = ps.filter(p => mineAt === null || p.v < mineAt).flatMap(p => p.ops || []), after = ps.filter(p => mineAt !== null && p.v > mineAt).flatMap(p => p.ops || []);
      // operations the server would not make for this person (a head) are left out of what it applied: they drop out of
      // the working copy too, as they are in neither the new base nor the edits made since the send
      const no = new Set((j.refused || []).map(x => x.i)), ours = ops.filter((_, i) => !no.has(i));
      const nb = Sync.rebase(SYNC.base, sent, working(), theirs, ours, after);
      SYNC.base = nb.base; SYNC.v = j.v;
      if (theirs.length || after.length || no.size) takeSpec(nb.spec);
      if (theirs.length || after.length || ops.length) keepLocal();   // the base moved: what is kept as not sent must move with it
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
/* what a department head sees. The server decides what a head may change; the page mirrors it: Download, Upload and edit, Publish and
   Students are not shown, every step but 4 and 5 is read-only, and on 4 only a provisional teacher's row or card can be changed (never its
   Provisional or Second department: only the committee gives a second department). A head can add teachers, tick them, and switch between Cards and Table. A practice copy is the head's own: nothing is read-only there (the hidden steps stay hidden). */
const isHead = () => !!(G.st && G.st.role === "head");
const HEAD_HIDDEN = ["download", "edit", "publish", "students"];
const stepShown = i => !(isHead() && STEPS[i] && HEAD_HIDDEN.includes(STEPS[i][0]));
const locked = id => isHead() && !S.practice && !["start", "_old", "teachers", "lessons"].includes(id);   // true: nothing on this step can be changed
const provisionalRow = t => !!t && t.provisional === "Yes";
/* the options of a teacher box: with a department, its teachers (home or second) first under its name, then "Others"; without, one plain list in the teacher list's order */
function teacherOptions(dept, cur) {
  const names = S.spec.teachers.filter(t => t && t.name);
  const missing = cur && !names.some(t => t.name === cur) ? opt(cur, cur, cur + " (not on list)") : "";   // a teacher the lesson names who is not on the list
  if (!dept) return names.map(t => opt(t.name, cur)).join("") + missing;
  const mine = names.filter(t => People.inDept(t, dept)), rest = names.filter(t => !People.inDept(t, dept));
  return (mine.length ? `<optgroup label="${esc(dept)}">${mine.map(t => opt(t.name, cur)).join("")}</optgroup>` : "") + (rest.length ? `<optgroup label="Others">${rest.map(t => opt(t.name, cur)).join("")}</optgroup>` : "") + missing;
}
function headLocks(main, id) {
  const off = (el, why) => { el.disabled = true; if (why && !el.title) el.title = why; };
  const all = () => [...main.querySelectorAll("input, select, textarea, button")];
  if (locked(id)) {
    all().forEach(el => { if (el.dataset.rtab === undefined && el.dataset.cview === undefined && el.dataset.vview === undefined && el.dataset.sview === undefined && el.dataset.tview === undefined && el.dataset.cclose === undefined && el.dataset.vroom === undefined && el.dataset.vclose === undefined && el.dataset.cband === undefined && el.id !== "cvLevel") off(el); });   // the tabs of step 6 and the views of steps 2, 3 and 4 still switch, the level picker and the bars of Bands work, an open card still closes, and a room of step 1 opens (to read) and closes
    main.querySelectorAll("[data-pop]").forEach(el => el.classList.add("ro"));
    main.insertAdjacentHTML("afterbegin", `<div class="notice readonly">Only the committee can change this step.</div>`);
    return;
  }
  if (!isHead() || S.practice || id !== "teachers") return;
  const why = "Only the committee can change this. A teacher the committee has not confirmed yet can be changed.";
  const bar = ["tc-dept", "tc-role", "tc-allow"];
  all().forEach(el => {
    if (el.dataset.tview !== undefined || el.dataset.topen !== undefined || el.dataset.tclose !== undefined) return;   // the view switch, opening and closing a card
    const tr = el.closest("tr[id^='teachers-'], [data-tcard]");
    if (tr) {   // a row or a card: the tick box always; the rest only while the teacher is provisional (and never the Provisional or Second department fields)
      const k = el.dataset.k || "";
      if (/\.dept2$/.test(k)) { off(el, TK_SECOND_WHY); return; }
      const own = provisionalRow(S.spec.teachers[Number(tr.dataset.tcard !== undefined ? tr.dataset.tcard : tr.id.slice(9))]) && !/\.provisional$/.test(k);
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
const untag = s => Groups.untag(s);
const subjectTest = names => { const w = new Set(namesList(names).map(n => n.toLowerCase())); return (s, d) => [String(s || "").toLowerCase(), untag(s).toLowerCase(), String(d || "").toLowerCase()].some(x => x && w.has(x)); };
const EVERY = "Every class";   // Fixed lessons: that subject for every class of the level (Level All: of the whole school)
const isFixedLesson = r => ["Class", "Group", "Level", "School"].includes(r.scope);
const scopesOf = rt => String(rt.scopes || "").split(",").map(x => x.trim());
const TABS = [["school", "School", ["School"]], ["levels", "Levels and classes", ["Level", "Class", "Block", "Group"]], ["subjects", "Subjects", ["Subject", "Department"]], ["venues", "Venues", ["Room"]], ["teachers", "Teachers", ["Teacher"]]];
const R6 = { tab: "school" };   // step 6: the open tab
const CF = { open: false, kind: "setting", key: "", rule: "", level: "", second: "", fallback: "", from: "", to: "" };   // step 6: the + Add a second choice form
const FALLBACK_LABELS = [["Prefer", "Make it Prefer"], ["Instead", "Use this instead"], ["Drop", "Drop it"]];
const validChoices = () => (S.spec.choices || []).length - Object.keys(Choices.problems(S.spec, SET())).length;   // as the server counts them
const tabOf = r => (TABS.find(t => t[2].includes(r.scope)) || TABS[0])[0];
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
const DOUBLE = "Teachers may take two lessons at once on", DOUBLE_NOTE = "Days when a teacher may be in two lessons at once, such as a self-directed or home-based learning day: the day names as on Day structure, separated by commas (Even Fri), or a weekday for every week (Fri). Empty: never.";   // as ttgen.spec.DOUBLE
const isDouble = x => String(x[0] || "").trim().toLowerCase().startsWith(DOUBLE.toLowerCase());
function ensureDoubleRow() { const ex = sc().extra_settings = sc().extra_settings || []; if (!ex.some(isDouble)) ex.push([DOUBLE, null, DOUBLE_NOTE]); }   // the row is always offered on step 6; it is saved with the next change
const dayWords = s => String(s || "").toLowerCase().split(/\s+/).filter(Boolean).map(w => w.slice(0, 3));
const doubleDay = t => { const w = dayWords(t); return w.length > 0 && dayNames().some(d => { const dw = dayWords(d); return w.join(" ") === dw.join(" ") || (w.length === 1 && w[0] === dw[dw.length - 1]); }); };   // a name of Day structure, or a weekday alone
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
    : lab.startsWith("most classes at recess at once") ? inp(k, x[1], "number", 'min="1" placeholder="no limit"')
    : isDouble(x) ? inp(k, x[1], "text", `placeholder="never (for example ${esc(dayNames()[dayNames().length - 1] || "Fri")})"`) : inp(k, x[1]);
  return `<label class="f" id="${isRecessRow(x) ? "school" : "config"}-${i}">${esc(x[0])} ${field}${x[2] ? `<span class="muted small">${esc(x[2])}</span>` : ""}</label>`;
}
function recessSetting(label) {   // [row index, value] of a floating recess row on Settings
  const ex = sc().extra_settings || [], i = ex.findIndex(x => String(x[0]).toLowerCase().startsWith(label.toLowerCase()));
  return [i, i >= 0 ? ex[i][1] : null];
}

/* ---------------- derived values (same logic as the workbook formulas) */
function split(p, L) { p = Number(p) || 0; L = Number(L) || 1; if (p <= 0) return [0, 0]; if (L <= 1) return [p, 0]; let s = ((-p % L) + L) % L; if (s * (L - 1) > p) s = 0; return [Math.floor((p - s * (L - 1)) / L), s]; }   // whole numbers always, as ttgen.spec.lesson_split: periods that cannot be cut exactly lose the remainder (the Things to fix list says so)
const patText = p => { const n = {}; p.forEach(v => n[v] = (n[v] || 0) + 1); return Object.keys(n).map(Number).sort((a, b) => b - a).map(v => `${n[v]}×${v}`).join(" + "); };
function wholeAuto(lv, s) { const x = subj(s) || {}, p = Number((x.periods || {})[lv]) || 0, L = Number(x.lesson_length) || Number(sc().lesson_length) || 1, [full, short] = split(p, L); return { p, auto: p ? patText([...Array(full).fill(L), ...Array(short).fill(L - 1)]) : "" }; }   // a subject's periods at a level and its usual split, as lessonInfo works them out for a row with nothing of its own
function hwHint() { const el = document.getElementById("hwPat"); if (el) el.placeholder = wholeAuto(document.getElementById("hwLevel").value, document.getElementById("hwSubj").value).auto || "usual split"; }   // the Lessons box of "Add a whole-class subject" shows the usual split of the level and subject picked
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
const cpBlock = x => isHead() && !S.practice && Parents.staffed(S.spec, x);   // a head cannot change a staffed lesson's teachers
const cpWhy = () => `Only the committee can change these lessons: their teachers are the class's ${Parents.label(S.spec)}.`
const cpHand = (x, i, dis) => x.by_hand === true && Parents.staffed(S.spec, x) ? `<span class="small muted">Changed by hand</span> <button class="small ghost" data-cpback="${i}" ${dis ? `disabled title="${esc(cpWhy())}"` : ""}>Back to the ${esc(Parents.label(S.spec))}</button>` : "";
function issues() {
  const out = { school: {}, config: {}, choices: {}, lessons: {}, rules: {}, teachers: {}, blocks: {}, classes: {}, subjects: {}, venues: {}, students: {}, global: [] };
  // hard: no timetable can be made until it is fixed (critical). The rest are warnings: a timetable can still be made, but a person should look.
  const crit = new Set(), add = (k, i, m, hard) => { (out[k][i] = out[k][i] || []).push(m); if (hard) crit.add(`${k}|${i}|${m}`); };
  Object.entries(Choices.problems(S.spec, SET())).forEach(([i, ms]) => ms.forEach(m => add("choices", i, `${Choices.itemLabel(S.spec, S.spec.choices[i], SET())}: ${m}`)));   // the give-way list: warnings
  (sc().extra_settings || []).forEach((x, i) => {   // the days a teacher may take two lessons at once: every name is a day
    if (!isDouble(x)) return;
    String(x[1] ?? "").split(/[,;]/).map(t => t.trim()).filter(Boolean).filter(t => !doubleDay(t)).forEach(t => add("config", i, `${DOUBLE}: "${t}" is not a day. Write the days as on Day structure, such as ${dayNames()[dayNames().length - 1]}, separated by commas.`, true));
  });
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
  {   // periods that cannot be cut into lessons of the usual length or one shorter (1 period under a 3-period lesson): the remainder would not be timetabled
    const uncut = (p, L) => { const [f, sh] = split(p, L); return p - f * L - sh * (L - 1); }, used = new Set(S.spec.lessons.map(x => `${x.level}|${x.subject}`));
    const say = (what, p, L, lost) => `${what}: ${p} period${p === 1 ? "" : "s"} cannot be cut into lessons of ${L} or ${L - 1} periods, so ${lost === p ? (p === 1 ? "it" : "they") : lost} would not be timetabled.`;
    S.spec.subjects.forEach((s, i) => { const L = Number(s.lesson_length) || Number(sc().lesson_length) || 1;
      Object.entries(s.periods || {}).forEach(([lv, v]) => { const p = Number(v) || 0, lost = uncut(p, L); if (lost && used.has(`${lv}|${s.subject}`)) add("subjects", i, `${say(`${s.subject} at ${lv}`, p, L, lost)} Give the subject its own lesson length on this step.`); }); });
    S.spec.lessons.forEach((x, i) => { const p = Number(x.periods_override) || 0; if (!p) return; const sb = subj(x.subject) || {}, L = Number(sb.lesson_length) || Number(sc().lesson_length) || 1, lost = uncut(p, L);
      if (lost && !((x.pattern || []).length && x.pattern.map(Number).reduce((a, b) => a + b, 0) === p)) add("lessons", i, `${say("This row's own periods", p, L, lost)} Change them, or give the row a lesson pattern.`); });
  }
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
  Parents.issues(S.spec).forEach(x => add(x.kind, x.i, x.text));   // Class Parents: none of these is hard
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
    if (r.rule === "In words") { if (!String(r.text || "").trim()) say("Write the rule in words: without them this row says nothing."); return; }
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
const area = (path, cur, extra = "") => `<textarea data-k="${path}" class="wrapbox" rows="1" ${extra}>${esc(cur)}</textarea>`;   // a one-line box that wraps and grows, so a long note is read whole; Enter leaves it (no line breaks are kept)
const GROWS = typeof CSS !== "undefined" && CSS.supports && CSS.supports("field-sizing", "content");   // the browser sizes such a box itself; where it cannot, fitAreas does
function fitAreas(root) { if (GROWS) return; (root || document).querySelectorAll("textarea.wrapbox").forEach(t => { if (!t.offsetParent) return; t.style.height = "auto"; t.style.height = `${t.scrollHeight + 2}px`; }); }
const chips = (path, arr, what, extra = "") => `<div class="chips" data-pop="${what}" data-path="${path}" ${extra}>${(arr || []).length ? arr.map(a => `<span class="chip">${esc(a)}</span>`).join("") : '<span class="muted">pick…</span>'}</div>`;
const usesNumber = rule => !!((S.meta.rule_types || []).find(t => t.rule === rule) || {}).needs_number;   // only the "Max ..." and "At most N" rules read Number
const delBtn = (k, i, off) => `<button class="small danger" data-del="${k}.${i}" ${off ? `disabled title="${esc(off)}"` : 'title="Remove row"'}>✕</button>`;
const ROOTS = { _gf: () => gfState(), _bf: () => bfState() };   // step 5's form state, addressed like the setup
const rootOf = ks => ROOTS[ks[0]] ? ROOTS[ks.shift()]() : S;
function getPath(p) { const ks = p.split("."); const root = rootOf(ks); return ks.reduce((o, k) => (o == null ? o : o[k]), root); }
function setPath(p, v) { const ks = p.split("."); const root = rootOf(ks); const last = ks.pop(); const o = ks.reduce((o, k) => o[k], root); o[last] = v; }
const localPath = p => /^_[gb]f\./.test(p || "");

/* ---------------- render */
function render() {
  const nav = $("#steps");
  if (!stepShown(S.step)) S.step = Math.min(1, STEPS.length - 1);   // a head never lands on a hidden step
  nav.innerHTML = STEPS.map(([id, label], i) => !stepShown(i) ? "" : `<button data-step="${i}" class="${i === S.step ? "on" : ""}" ${!S.spec && i > 0 ? "disabled" : ""}><span>${label}</span><span class="n">${count(id)}</span></button>`).join("");
  $("#kindBadge").textContent = S.spec ? `${sc().type === "primary" ? "Primary" : "Secondary"} · ${sc().name}` : "No school yet";
  const id = S.asking ? "_old" : STEPS[S.step][0]; const main = $("#main"); const y = window.scrollY;
  // on a redraw of the same step, keep where each table was scrolled to (they scroll inside their own box) and the field in use
  const same = G.shown === id, boxes = same ? [...main.querySelectorAll(".tablewrap, .keep")].map(t => [t.scrollTop, t.scrollLeft]) : [];
  const bars = same ? [...main.querySelectorAll("[id]")].filter(e => /^h[vctbw][A-Z]/.test(e.id)).map(e => [e.id, e.value]) : [];   // the boxes of the "Add …" bars (hvPre, hcNames, htDept…): kept as they are
  const f = same && main.contains(document.activeElement) ? document.activeElement : null, fk = f && (f.id ? `#${CSS.escape(f.id)}` : f.dataset.k ? `[data-k="${CSS.escape(f.dataset.k)}"]` : "");
  document.querySelector(".layout").classList.toggle("wide", id === "edit" || id === "publish");   // the setup's "Things to fix" column is not shown on steps 8 and 9: the timetable takes its width
  G.shown = id; bdEnsure(id, true); const bw = same ? main.querySelector(".bdwrap") : null, bpos = bw ? [bw.scrollLeft, bw.scrollTop] : null;
  main.innerHTML = (S.practice && !S.asking ? `<div class="practice"><span>Practice copy: nothing here is saved for the school.</span><button id="practiceBack">Back to the school's setup</button></div>` : "") + (VIEWS[id] || (() => ""))();
  headLocks(main, id); if (S.board) bdPaint();   // the board's colours and outlines for the card selected
  main.querySelectorAll(".tablewrap, .keep").forEach((t, i) => { if (boxes[i]) [t.scrollTop, t.scrollLeft] = boxes[i]; });
  bars.forEach(([bid, v]) => { const e = document.getElementById(bid); if (e && e.value !== v && (e.tagName !== "SELECT" || [...e.options].some(o => o.value === v))) e.value = v; });
  hwHint(); fitAreas(main);
  const bw2 = bpos && main.querySelector(".bdwrap"); if (bw2) { bw2.scrollLeft = bpos[0]; bw2.scrollTop = bpos[1]; }
  if (fk) { const el = main.querySelector(fk); if (el) el.focus({ preventScroll: true }); }
  renderIssues(); saveState(); window.scrollTo(0, y);
  paintPublished();
  if (id === "edit" || id === "publish") { const again = G.refetch; G.refetch = false; loadDraft(again); }   // again: the person opened the step
  if (id === "download") fitCheck();
}
const stepAt = id => STEPS.findIndex(s => s[0] === ({ blocks: "lessons", config: "rules", choices: "rules" }[id] || id));   // bands are a card on the teaching-groups step; the settings and the give-way list open step 6
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
  return `<div class="card" id="printouts"><h2>Upload the timetable</h2><p class="muted">Upload the timetable the chatbot made, with its setup workbook. The timetable can be a workbook with a Lessons sheet or a timetable database (.sqlite); a database made by this app or the skill holds its setup, so it can come on its own.</p>
    <p class="muted"><b>Check</b> keeps the file as a draft, checks it against the setup and lists what it found. Fix it here, then go to step 9 to publish.</p>
    <div class="row" style="margin-top:10px"><label class="filebtn">Setup workbook (.xlsx)<input type="file" id="exSetup" accept=".xlsx" hidden></label><span class="muted" id="exSetupName">none chosen</span></div>
    <div class="row" style="margin-top:8px"><label class="filebtn">Timetable (.xlsx or .sqlite)<input type="file" id="exTT" accept=".xlsx,.sqlite,.sqlite3,.db" hidden></label><span class="muted" id="exTTName">none chosen</span></div>
    <div class="row" style="margin-top:12px"><button class="primary" id="imCheck">Check</button></div>
    <div id="imResult">${S.draft ? draftHTML(S.draft).head : loadingDraft() ? LOADING : ""}</div></div>`;
}
/* step 6's third card: the second choices in their give-way order, each editable in place, and the form that adds one */
function giveWay(out, crit, psel, weeks, days) {
  const ord = Choices.ordered(S.spec), drag = !locked("rules"), bad = i => rowCls(out, crit, "choices", i);
  const second = (i, c) => { const p = `spec.choices.${i}`, st = SET().find(x => x.key === c.key);
    if (c.kind === "setting") return !st ? '<span class="muted small">–</span>' : st.number ? inp(`${p}.second`, c.second === "no limit" ? "" : c.second, "number", 'min="1" placeholder="no limit" style="width:80px"') : sel(`${p}.second`, c.second, ["Yes", "No"], false);
    if (c.kind === "rule") return `<select data-k="${p}.fallback">${opt("", c.fallback, "")}${FALLBACK_LABELS.map(([v, l]) => opt(v, c.fallback, l)).join("")}</select>`;
    if (c.kind === "recess") { const w = c.window || []; return `<input data-k="${p}.window.0" type="time" value="${esc(w[0])}"> to <input data-k="${p}.window.1" type="time" value="${esc(w[1])}">`; }
    return "";
  };
  const instead = (i, c) => { if (c.kind !== "rule" || c.fallback !== "Instead" || !c.instead) return ""; const r = c.instead, p = `spec.choices.${i}.instead`, f = (l, x) => `<label class="f">${l} ${x}</label>`;
    const fields = r.rule === "In words" ? f("In words", inp(`${p}.text`, r.text, "text", 'style="min-width:320px"'))
      : [f("Subject", r.rule === "Only these subjects" ? chips(`${p}.subject`, namesList(r.subject), "subjects") : sel(`${p}.subject`, r.subject, subjectNames())), f("Week", sel(`${p}.week`, r.week || "Both", weeks, false)), f("Day", sel(`${p}.day`, r.day || "All", days, false)),
        f("From", psel(`${p}.from`, r.from)), f("To", psel(`${p}.to`, r.to)), usesNumber(r.rule) ? f("Number", inp(`${p}.number`, r.number, "number", 'style="width:56px"')) : "", r.rule === "Only in venues" ? f("Venues", chips(`${p}.venues`, namesList(r.venues), "rooms")) : ""].join("");
    return `<tr class="instead"><td></td><td colspan="4"><span class="muted small">Instead: ${esc(Choices.ruleLabel(r))}</span><div class="row" style="margin-top:4px">${fields}</div></td></tr>`; };
  const row = ({ i, c }, n) => `<tr id="choices-${i}" class="${bad(i)}"${drag ? ` draggable="true" data-cdrag="${i}"` : ""}><td class="calc">${n + 1} <button class="small" data-cmove="${i}|-1" title="Move up"${n ? "" : " disabled"}>▲</button><button class="small" data-cmove="${i}|1" title="Move down"${n < ord.length - 1 ? "" : " disabled"}>▼</button></td>
    <td class="item">${esc(Choices.itemLabel(S.spec, c, SET()))}</td><td>${esc(Choices.firstText(S.spec, c, SET()))}</td><td class="second">${second(i, c)}</td><td>${delBtn("choices", i)}</td></tr>${instead(i, c)}${out.choices[i] ? `<tr class="rowmsg ${bad(i)}"><td colspan="5">${out.choices[i].map(esc).join("<br>")}</td></tr>` : ""}`;
  return `<div class="card"><h2>If it does not fit, give way in this order</h2><p class="muted">The agent tries the first choices. If no timetable fits, it gives way on one item at a time, from the top of this list, and stops as soon as a timetable fits. Nothing that is not on the list is changed. Drag the rows, or use the arrows, to set the order.</p>
    <div class="tablewrap"><table class="giveway"><tr><th>#</th><th>Item</th><th>First choice</th><th>Second choice</th><th></th></tr>${ord.map(row).join("") || `<tr><td colspan="5" class="muted small">None yet. Without a list, the agent uses only the first choices.</td></tr>`}</table></div>
    <div class="cend" data-cend="1">${CF.open ? choiceForm() : `<div class="row" style="margin:10px 0 4px"><button data-cfopen="1">+ Add a second choice</button></div>`}</div></div>`;
}
function choiceForm() {   // + Add a second choice: what kind, which item (only those without one), then its second choice
  const cand = Choices.candidates(S.spec, SET()), k = CF.kind, key = { setting: "key", rule: "rule", recess: "level" }[k];
  const items = k === "setting" ? cand.settings.map(x => [x, SET().find(s => s.key === x).label])
    : k === "rule" ? cand.rules.map(j => S.spec.rules[j]._id).filter(Boolean).map(id => [id, Choices.itemLabel(S.spec, { kind: "rule", rule_id: id }, SET())])
    : cand.levels.map(l => [l, `Recess for ${l}`]);
  const csel = (f, list, blank = true) => `<select data-cf="${f}">${blank ? opt("", CF[f], "") : ""}${list.map(([v, l]) => opt(v, CF[f], l)).join("")}</select>`, st = SET().find(s => s.key === CF.key);
  const second = k === "setting" ? (!st ? "" : st.number ? `<input data-cf="second" type="number" min="1" value="${esc(CF.second)}" placeholder="no limit" style="width:80px">` : csel("second", [["Yes", "Yes"], ["No", "No"]], false))
    : k === "rule" ? csel("fallback", FALLBACK_LABELS) : `<input data-cf="from" type="time" value="${esc(CF.from)}"> to <input data-cf="to" type="time" value="${esc(CF.to)}">`;
  const picked = CF[key] ? Choices.firstText(S.spec, { kind: k, key: CF.key, rule_id: CF.rule, level: CF.level }, SET()) : "";
  return `<div class="row cf"><label class="f">Kind ${csel("kind", [["setting", "A setting"], ["rule", "A rule"], ["recess", "A level's recess"]], false)}</label><label class="f">Item ${csel(key, items)}</label>
    <label class="f">Second choice <span>${second}</span></label><button class="primary" data-cfadd="1">Add</button><button data-cfcancel="1">Cancel</button></div>
    ${picked ? `<p class="muted small">First choice: ${esc(picked)}</p>` : ""}${items.length ? "" : `<p class="muted small">${{ setting: "Every setting", rule: "Every rule", recess: "Every level with a fixed recess" }[k]} already has a second choice.</p>`}`;
}
function cfAdd() {   // the form's values as they are now (a box typed in may not have sent its change yet), then one new row
  document.querySelectorAll("[data-cf]").forEach(x => { CF[x.dataset.cf] = x.value; });
  const st = SET().find(x => x.key === CF.key);
  const r = CF.kind === "setting" ? Choices.newSetting(S.spec, SET(), CF.key, st && st.number && CF.second === "" ? "no limit" : CF.second)
    : CF.kind === "rule" ? Choices.newRule(S.spec, CF.rule, CF.fallback) : Choices.newRecess(S.spec, CF.level, CF.from, CF.to);
  if (r.error) { toast(r.error); return; }
  CF.open = false; save(); render();
  const el = document.getElementById(`choices-${r.i}`); if (el) el.scrollIntoView({ block: "center" });
}
/* ---------------- step 1: the Blocks and Table views of the rooms */
/* the open card or room is held by its row's own _id and found again on each draw, so another person's change cannot
   turn it into a different row; a row with no _id yet (not saved once) is held by its place until its first save */
function heldOpen(H, rows, i) { H.open = i; const r = i === null ? null : rows[i]; H.openId = r && r._id ? r._id : null; }
function heldResolve(H, rows) {
  if (H.openId) { const i = rows.findIndex(c => c && c._id === H.openId); H.open = i < 0 ? null : i; if (i < 0) H.openId = null; }
  else if (H.open !== null) { const r = rows[H.open]; if (r && r._id) H.openId = r._id; }
}
const VENUEVIEW = "ttsetup.view.venues";
const VV = { view: "blocks", open: null, openId: null, draft: null };   // open: the index of the open room, found again by openId (the row's own _id) on each draw
// draft: a small box being filled in ({ what: "kind" } the open room's new kind, { what: "block" } a new block), not saved
const VNEWKIND = "__new_kind__";   // the last choice of an open room's Kind box
const VNEW = "__new__";   // the last choice of a Block or Floor list: a new one, typed in a box
const vvOpen = vi => { heldOpen(VV, S.spec.venues, vi); VV.draft = null; VV.typing = null; };   // typing: "building" or "floor" while the open room's new block or floor is being typed
function vvTicks() {   // the rooms ticked to be moved together, by the rows' own ids; a room that is gone loses its tick
  if (!VV.ticked) VV.ticked = new Set(); const have = new Set(S.spec.venues.map(v => v && v._id));
  VV.ticked = new Set([...VV.ticked].filter(id => have.has(id))); return VV.ticked; }
const vvMv = () => VV.mv || (VV.mv = { block: "", floor: "", nb: false, nf: false, bt: "", ft: "" });   // where the ticked rooms go: a block and floor from the lists, or new ones being typed (nb, nf with bt, ft)
const vvFloorName = f => f === "" ? "No floor yet" : /^-?\d+(\.\d+)?$/.test(f) ? `Floor ${f}` : f;
function vvMove() {   // the ticked rooms go to the block and floor chosen on the bar: one save, one Undo
  if (locked("venues")) return;
  const mv = vvMv(), ticks = vvTicks(), block = String(mv.nb ? mv.bt : mv.block).trim(), floor = String(mv.nf ? mv.ft : mv.floor).trim();
  if (!ticks.size) { toast("Tick rooms first."); return; }
  if (mv.nb && !block) { toast("Give the new block a name."); const i = $("#vvMvBlock"); if (i) i.focus(); return; }
  const vis = S.spec.venues.map((v, i) => [v, i]).filter(([v]) => v && ticks.has(v._id)).map(([, i]) => i);
  const n = VenueView.move(S.spec, vis, block, floor);
  if (!n) { toast("Those rooms are there already."); return; }
  ticks.clear(); Object.assign(mv, { block, floor, nb: false, nf: false, bt: "", ft: "" }); save(); render();
  toast(`Moved ${n} room${n === 1 ? "" : "s"} to ${block || "No block yet"}, ${vvFloorName(floor)}. Undo, at the top, takes it back.`);
}
const vvResolve = () => heldResolve(VV, S.spec.venues);
try { const vv = localStorage.getItem(VENUEVIEW); if (["blocks", "table"].includes(vv)) VV.view = vv; } catch (e) { }
function venuesTable() {   // today's table, and two notes at its end
  const { out, crit } = issues();
  return `<div class="tablewrap"><table><tr><th>Room</th><th>Kind</th><th>Capacity</th><th>Block</th><th>Floor / level</th><th>Home room of</th><th>For</th><th>Note</th><th>Equipment</th><th>Configuration</th><th></th></tr>
      ${S.spec.venues.map((v, i) => `<tr id="venues-${i}" class="${rowCls(out, crit, "venues", i)}"><td>${inp(`spec.venues.${i}.room`, v.room)}</td><td>${sel(`spec.venues.${i}.kind`, v.kind, sc().room_kinds || [])}</td><td class="num">${inp(`spec.venues.${i}.capacity`, v.capacity, "number")}</td><td>${inp(`spec.venues.${i}.building`, v.building)}</td><td class="num">${inp(`spec.venues.${i}.floor`, v.floor)}</td><td class="calc">${esc(S.spec.classes.filter(c => c.home_room === v.room).map(c => c.class).join(", "))}</td><td style="min-width:170px"><input data-names="spec.venues.${i}.only_for" list="forNames" value="${esc((v.only_for || []).join(", "))}" placeholder="anyone"></td><td>${inp(`spec.venues.${i}.note`, v.note)}</td><td style="min-width:170px"><input data-names="spec.venues.${i}.equipment" value="${esc((Array.isArray(v.equipment) ? v.equipment : []).join(", "))}" placeholder="none"></td><td style="min-width:150px">${inp(`spec.venues.${i}.configuration`, v.configuration)}</td><td>${delBtn("venues", i)}</td></tr>`).join("")}
      </table></div><datalist id="forNames">${forNames().map(n => `<option value="${esc(n)}">`).join("")}</datalist><div class="row" style="margin-top:10px"><button data-add="venues">+ Add room</button></div>`;
}
/* the kinds the app ships with: a fixed colour and a short mark each; any other kind is neutral */
const VKINDS = { "classroom": ["CR", "#2563eb"], "lab": ["LB", "#7c3aed"], "science room": ["SC", "#0e7490"], "computer lab": ["CL", "#0369a1"], "art room": ["AR", "#c2410c"], "d&t studio": ["DT", "#a16207"], "food lab": ["FL", "#be185d"], "music room": ["MU", "#9333ea"], "pe venue": ["PE", "#15803d"], "hall": ["HL", "#b45309"], "special room": ["SP", "#475569"] };
const vkindOf = k => { const key = String(k || "").trim().toLowerCase(); return Object.prototype.hasOwnProperty.call(VKINDS, key) ? VKINDS[key] : ["··", "#7b8496"]; };
const vkindMark = k => { const [m, c] = vkindOf(k); return `<i class="vmark" style="background:${c}">${esc(m)}</i>`; };
function venuesBlocks() {   // the rooms by block and floor; a click on a tile opens the room to change it
  const { out, crit } = issues();
  Sync.ensureIds(S.spec); vvResolve(); if (VV.open !== null && !S.spec.venues[VV.open]) vvOpen(null);
  const bl = VenueView.blocks(S.spec), P = VenueView.places(S.spec), ticks = vvTicks(), mv = vvMv(), nT = ticks.size;
  if (!mv.nb && mv.block !== "" && !P.some(b => b.block === mv.block)) mv.block = "";   // a block that is gone is no longer chosen
  const mvFloors = mv.nb || mv.block === "" ? [] : (P.find(b => b.block === mv.block) || { floors: [] }).floors;
  if (!mv.nf && mv.floor !== "" && !mvFloors.includes(mv.floor)) mv.floor = "";
  const bar = nT ? `<div class="row bulk vmovebar"><b>${nT} room${nT === 1 ? "" : "s"} ticked.</b><span>Move to</span>
      <label>Block ${mv.nb ? `<input id="vvMvBlock" value="${esc(mv.bt)}" placeholder="the new block's name" autocomplete="off"><button class="small" data-vmvpick="block">Pick from the list</button>`
        : `<select id="vvMvBlockSel">${opt("", mv.block, "No block yet")}${P.map(b => opt(b.block, mv.block)).join("")}<option value="${VNEW}">New block…</option></select>`}</label>
      <label>Floor ${mv.nf ? `<input id="vvMvFloor" value="${esc(mv.ft)}" placeholder="1, 2, G…" autocomplete="off" style="width:110px">${mv.nb ? "" : `<button class="small" data-vmvpick="floor">Pick from the list</button>`}`
        : `<select id="vvMvFloorSel">${opt("", mv.floor, "No floor yet")}${mvFloors.map(f => opt(f, mv.floor, vvFloorName(f))).join("")}<option value="${VNEW}">New floor…</option></select>`}</label>
      <button class="primary" data-vmove="1">Move</button><button class="small" data-vuntick="1">Untick all</button></div>`
    : `<div class="row bulk vmovebar idle">${locked("venues") ? "" : `<span class="muted small">Tick rooms to move them to a block and a floor together.</span>`}</div>`;   // the same height as the bar, so the first tick does not push the rooms down
  const add = `<div class="row vblockbar">${VV.draft && VV.draft.what === "block"
    ? `<label>New block's name <input id="vvBlockName" value="${esc(VV.draft.text || "")}" autocomplete="off"></label> <button data-vblockadd="1">Add</button> <button data-vdraftx="1">Cancel</button><span class="muted small">It starts with one room, on floor 1.</span>`
    : `<button data-vblock="1">+ Block</button>`}</div>`;
  if (!bl.length) return `<p class="muted vempty">No rooms yet. Add them with the bar above, or add a block here.</p>${add}`;
  const used = VenueView.kinds(S.spec).filter(k => S.spec.venues.some(v => v && v.kind === k));
  const legend = used.length ? `<div class="vlegend">${used.map(k => `<span>${vkindMark(k)} ${esc(k)}</span>`).join("")}</div>` : "";
  const tile = r => {
    const line = r.home.length ? `Home of ${r.home.join(", ")}` : r.only_for.length ? `Kept for ${r.only_for.join(", ")}` : "";
    const notes = r.equipment.length || r.configuration.trim() ? `<span class="vflag" title="${esc([r.equipment.length ? "Equipment: " + r.equipment.join(", ") : "", r.configuration.trim() ? "Configuration: " + r.configuration.trim() : ""].filter(Boolean).join(". "))}">+ notes</span>` : "";
    const open = VV.open === r.vi;   // the open room's own box carries the row's id, so a message can scroll to it
    const id = (S.spec.venues[r.vi] || {})._id, tk = ticks.has(id);   // the tick box sits on the tile's corner; the tile itself still opens the room
    return `<span class="vtw${tk ? " ticked" : ""}"><input type="checkbox" class="vtick" id="vtick-${esc(id)}" data-vtick="${esc(id)}" ${tk ? "checked" : ""} aria-label="Tick ${esc(r.room || "this room")} to move it"><button class="vtile ${open ? "on " : ""}${rowCls(out, crit, "venues", r.vi)}" data-vroom="${r.vi}"${open ? ' aria-expanded="true"' : ' aria-expanded="false"'}${open ? "" : ` id="venues-${r.vi}"`}><span class="vname">${r.room ? esc(r.room) : "(no name yet)"}${notes}</span><span class="vkind">${vkindMark(r.kind)} ${esc(r.kind || "no kind")}${r.capacity != null ? ` · ${esc(r.capacity)} seats` : ""}</span>${line ? `<span class="vnote">${esc(line)}</span>` : ""}</button></span>`;
  };
  const openRoom = vi => {
    const v = S.spec.venues[vi], p = f => `spec.venues.${vi}.${f}`, msgs = out.venues[vi] || [];
    const kinds = sc().room_kinds || [], cur = v.kind || "";
    const curB = String(v.building == null ? "" : v.building).trim(), curF = String(v.floor == null ? "" : v.floor).trim(), fl = (P.find(b => b.block === curB) || { floors: [] }).floors;
    const typeBox = (field, cur, hint) => `<input id="vvType" data-vtype="${vi}|${field}" value="${esc(cur)}" placeholder="${hint}" autocomplete="off"><button class="small" data-vtypex="1">Pick from the list</button>`;   // a new block or floor, typed
    const blockBox = VV.typing === "building" ? typeBox("building", curB, "the new block's name")
      : `<select data-vplace="${vi}|building">${opt("", curB, "No block yet")}${P.map(b => opt(b.block, curB)).join("")}<option value="${VNEW}">New block…</option></select>`;
    const floorBox = VV.typing === "floor" ? typeBox("floor", curF, "1, 2, G…")
      : `<select data-vplace="${vi}|floor">${opt("", curF, "No floor yet")}${fl.map(f => opt(f, curF, vvFloorName(f))).join("")}${curF && !fl.includes(curF) ? opt(curF, curF, vvFloorName(curF)) : ""}<option value="${VNEW}">New floor…</option></select>`;
    const kindBox = `<select id="vvKind" data-vkind="${vi}">${opt("", cur, "")}${kinds.map(k => opt(k, cur)).join("")}${cur && !kinds.includes(cur) ? opt(cur, cur, cur + " (not on list)") : ""}<option value="${VNEWKIND}">New kind…</option></select>`;
    const draft = VV.draft && VV.draft.what === "kind"
      ? `<div class="row vdraft"><label>New kind's name <input id="vvKindName" value="${esc(VV.draft.text || "")}" autocomplete="off"></label> <button data-vkindadd="${vi}">Add</button> <button data-vdraftx="1">Cancel</button></div>` : "";
    return `<div class="vopen ${rowCls(out, crit, "venues", vi)}" id="venues-${vi}" data-vopen="${vi}">
      <div class="vfields"><label>Room ${inp(p("room"), v.room)}</label><label>Kind ${kindBox}</label><label>Capacity ${inp(p("capacity"), v.capacity, "number")}</label>
        <label>Block ${blockBox}</label><label>Floor / level ${floorBox}</label>
        <label>For <input data-names="${p("only_for")}" list="forNames" value="${esc((Array.isArray(v.only_for) ? v.only_for : []).join(", "))}" placeholder="anyone"></label>
        <label class="vwide">Equipment <input data-names="${p("equipment")}" value="${esc((Array.isArray(v.equipment) ? v.equipment : []).join(", "))}" placeholder="none"></label>
        <label class="vwide">Configuration ${inp(p("configuration"), v.configuration)}</label><label class="vwide">Note ${inp(p("note"), v.note)}</label></div>${draft}
      ${msgs.length ? `<div class="vmsgs">${msgs.map(m => `<div>${esc(m)}</div>`).join("")}</div>` : ""}
      <div class="row" style="margin-top:8px">${delBtn("venues", vi)} <button class="small" data-vclose="1">Close</button></div></div>`;
  };
  const floorName = vvFloorName;
  const tickAll = f => { const all = f.rooms.length && f.rooms.every(r => ticks.has((S.spec.venues[r.vi] || {})._id)); return f.rooms.length ? `<button class="small vtickall" data-vtickall="${f.rooms.map(r => r.vi).join(",")}">${all ? "Untick" : "Tick all"}</button>` : ""; };
  const at = (b, f) => `${encodeURIComponent(b)}|${encodeURIComponent(f)}`;   // "{block}|{floor}", each part encoded so a name with a bar in it still splits right
  return `${bar}${legend}<div class="vblocks">${bl.map(b => `<section class="vpanel"><h3>${b.block === "" ? "No block yet" : esc(b.block)} <span class="muted">${b.rooms} ${b.rooms === 1 ? "room" : "rooms"} · ${b.seats} seats</span> <button class="small vfloorbtn" data-vfloor="${esc(b.block)}">+ Floor</button></h3>
      ${b.floors.map(f => `<div class="vfloor"><div class="vflabel">${esc(floorName(f.floor))}${tickAll(f)}</div><div class="vtiles">${f.rooms.map(tile).join("")}<button class="small vaddbtn" data-vadd="${esc(at(b.block, f.floor))}">+ Room</button></div>${f.rooms.some(r => r.vi === VV.open) ? openRoom(VV.open) : ""}</div>`).join("")}</section>`).join("")}</div>${add}
    <datalist id="forNames">${forNames().map(n => `<option value="${esc(n)}">`).join("")}</datalist>`;
}
/* a room added from the Blocks view goes on the list the way the Add rooms bar adds one: pushed, then one save; it opens at once */
function vvAddRoom(block, floor) {
  const n = VenueView.nextRoom(S.spec, block, floor), row = { room: n.room, kind: n.kind, capacity: n.capacity };
  if (String(block).trim() !== "") row.building = String(block).trim();
  if (String(floor).trim() !== "") row.floor = String(floor).trim();
  S.spec.venues.push(row); save();
  const vi = S.spec.venues.length - 1; vvOpen(vi); render();
  const o = document.getElementById(`venues-${vi}`); if (o) o.scrollIntoView({ block: "center" });
  if (!n.room) { const f = o && o.querySelector(`[data-k="spec.venues.${vi}.room"]`); if (f) f.focus({ preventScroll: true }); }
}
function vvAddBlock() {
  const el = $("#vvBlockName"), name = el ? el.value.trim() : "";
  if (!name) { if (el) el.focus(); return; }
  vvAddRoom(name, "1");
}
function vvAddKind(vi) {   // the name goes at the end of the school's list (if no kind of that name is there, any case) and on the room: one save
  const el = $("#vvKindName"), name = el ? el.value.trim() : "", v = S.spec.venues[vi];
  if (!name || !v) { if (el) el.focus(); return; }
  const list = sc().room_kinds || [], have = list.find(k => String(k).toLowerCase() === name.toLowerCase());
  if (have === undefined) sc().room_kinds = [...list, name];
  v.kind = have === undefined ? name : have; VV.draft = null; save(); render();
}
/* ---------------- step 2: the Cards, Bands and Table views of the classes */
const CLASSVIEW = "ttsetup.view.classes";
const CV = { view: "cards", open: null, openId: null, level: "" };   // open: the index of the open card, found again by openId (the row's own _id) on each draw, so another person's change cannot move it to another class
const cvOpen = ci => heldOpen(CV, S.spec.classes, ci);
const cvResolve = () => heldResolve(CV, S.spec.classes);
try { const cv = localStorage.getItem(CLASSVIEW); if (["cards", "bands", "table"].includes(cv)) CV.view = cv; } catch (e) { }
function classesBars() {   // the two helper bars above the Cards and the Table
  const nm = Parents.label(S.spec);
  const hand = Parents.handRows(S.spec).length, fc = Parents.fillCount(S.spec);
  const bar = Parents.subjects(S.spec).length && (hand || fc) ? `<div class="helper row">${hand ? `<span>${hand} ${hand === 1 ? "lesson" : "lessons"} changed by hand</span><button data-pback="1">Put the ${esc(nm)} on all of them</button>` : ""}${fc ? `<button data-pfill="1">Take them from the lessons</button>` : ""}</div>` : "";
  return `${bar}
      <div class="helper row"><b>Add classes</b> level ${sel("_hc", levels()[0], levels(), false, 'id="hcLevel" data-k=""')} names <input id="hcNames" value="A, B, C, D" style="width:120px"> students <input id="hcSize" type="number" value="38" style="width:70px"> <button data-helper="classes">Add (home rooms filled from free classrooms)</button></div>`;
}
function classesTable() {   // today's table, as it was
  const { out, crit } = issues();
  const nm = Parents.label(S.spec), pm = Parents.maximum(sc().parents_max) || 2, T = teacherNames(), held = c => Parents.names(c).length;
  const NP = Math.max(pm, ...S.spec.classes.map(held));   // a class holding more than the school's most keeps its boxes
  const pcells = (c, i) => { const mine = Math.max(pm, held(c)); let h = "";
    for (let k = 0; k < NP; k++) { if (k >= mine) { h += "<td></td>"; continue; } const cur = Parents.names(c)[k] || "";
      h += `<td><select data-parent="${i}|${k}">${opt("", cur, "")}${T.map(t => opt(t, cur)).join("")}${cur && !T.includes(cur) ? opt(cur, cur, cur + " (not on list)") : ""}</select></td>`; }
    return h; };
  return `<div class="tablewrap"><table class="classtable"><tr><th>Class</th><th>Level</th><th>Students</th><th>Home room</th><th colspan="${NP}">${esc(nm)}</th><th>Lesson rows</th><th>Note</th><th></th></tr>
      ${S.spec.classes.map((c, i) => `<tr id="classes-${i}" data-parents="${i}" class="${rowCls(out, crit, "classes", i)}"><td>${inp(`spec.classes.${i}.class`, c.class)}</td><td>${sel(`spec.classes.${i}.level`, c.level, levels())}</td><td class="num">${inp(`spec.classes.${i}.size`, c.size, "number")}</td><td>${sel(`spec.classes.${i}.home_room`, c.home_room, rooms())}</td>${pcells(c, i)}<td class="calc">${S.spec.lessons.filter(x => (x.classes || []).includes(c.class)).length}</td><td>${inp(`spec.classes.${i}.note`, c.note)}</td><td>${delBtn("classes", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="classes">+ Add class</button></div>`;
}
function classesCards() {   // one grid of cards per level; a click opens a card to change the class
  const { out, crit } = issues(), nm = Parents.label(S.spec), pm = Parents.maximum(sc().parents_max) || 2, T = teacherNames();
  cvResolve(); if (CV.open !== null && !S.spec.classes[CV.open]) cvOpen(null);
  const people = n => { const t = S.spec.teachers.find(x => x && x.name === n);
    return t ? `<span class="avx named" title="${esc(n)}">${avatarOf(t, 28)}<span class="avn">${esc(t.short || n)}</span></span>` : `<span class="chip" title="${esc(n)} (not on the teacher list)">${esc(n)}</span>`; };
  const openCard = ci => { const c = S.spec.classes[ci], names = Parents.names(c), mine = Math.max(pm, names.length), msgs = out.classes[ci] || [];
    const boxes = Array.from({ length: mine }, (_, k) => { const cur = names[k] || "";
      return `<select data-parent="${ci}|${k}">${opt("", cur, "")}${T.map(t => opt(t, cur)).join("")}${cur && !T.includes(cur) ? opt(cur, cur, cur + " (not on list)") : ""}</select>`; }).join("");
    return `<div class="ccard open ${rowCls(out, crit, "classes", ci)}" id="classes-${ci}" data-ccard="${ci}" data-parents="${ci}">
      <div class="cfields"><label>Class ${inp(`spec.classes.${ci}.class`, c.class)}</label><label>Level ${sel(`spec.classes.${ci}.level`, c.level, levels())}</label>
        <label>Students ${inp(`spec.classes.${ci}.size`, c.size, "number")}</label><label>Home room ${sel(`spec.classes.${ci}.home_room`, c.home_room, rooms())}</label>
        <label class="cwide">${esc(nm)}<span class="cboxes">${boxes}</span></label><label class="cwide">Note ${inp(`spec.classes.${ci}.note`, c.note)}</label></div>
      ${msgs.length ? `<div class="cmsgs">${msgs.map(m => `<div>${esc(m)}</div>`).join("")}</div>` : ""}
      <div class="row" style="margin-top:8px">${delBtn("classes", ci)} <button class="small" data-cclose="1">Close</button></div></div>`; };
  const card = k => { if (CV.open === k.ci) return openCard(k.ci);
    const held = k.parents.length;
    const count = k.real !== null ? `${k.real} on the list · ${k.planned === null ? "?" : k.planned} planned` : `${k.planned === null ? "?" : k.planned} planned`;
    return `<div class="ccard ${rowCls(out, crit, "classes", k.ci)}" id="classes-${k.ci}" data-ccard="${k.ci}"><div class="chead"><b>${esc(k["class"] || "(no name yet)")}</b><span class="muted small">${count}</span></div>
      <div class="muted small">${k.home_room ? `Home room ${esc(k.home_room)}` : "No home room"}</div>
      <div class="avs">${k.parents.map(people).join("")}${held < pm ? `<span class="plus" title="Add one">+</span>` : ""}</div>
      ${k.subjects.length ? `<div class="csubs">${k.subjects.map(s => `<span class="chip ${s.whole ? "cwhole" : "cpart"}" title="${s.whole ? "The whole class together" : "Part of the class, in a teaching group"}">${esc(s.subject)}${!s.whole && s.count !== null ? ` · ${s.count}` : ""}</span>`).join("")}</div>` : ""}</div>`; };
  const view = ClassView.cards(S.spec), shown = new Set();
  const groups = view.map(g => { g.cards.forEach(k => shown.add(k.ci));
    const n = g.cards.length;
    return `<h3 class="clevel">${esc(g.level || "No level")} · ${n} ${n === 1 ? "class" : "classes"} · ${g.planned} students${g.real !== null ? ` · ${g.real} on the list` : ""}</h3><div class="cgrid">${g.cards.map(card).join("")}</div>`; });
  const fresh = S.spec.classes.map((c, ci) => [c, ci]).filter(([c, ci]) => c && !shown.has(ci))   // a class with no name yet has no level to sit under
    .map(([c, ci]) => ({ ci, "class": "", planned: c.size === "" || c.size == null || isNaN(Number(c.size)) ? null : Number(c.size), real: null, home_room: c.home_room || "", parents: Parents.names(c), subjects: [] }));
  if (fresh.length) groups.push(`<h3 class="clevel">New classes</h3><div class="cgrid">${fresh.map(card).join("")}</div>`);
  return (groups.length ? groups.join("") : `<p class="muted">No classes yet. Add them with the bar above.</p>`)
    + `<div class="row" style="margin-top:10px"><button data-cadd="1">+ Add class</button></div>`;
}
function cvLevel() { const L = ClassView.levels(S.spec); if (!L.includes(CV.level)) CV.level = L.length ? L[0] : ""; return CV.level; }   // the level shown on Bands: the chosen one, else the first
function classesBands() {   // a picture of one level: a column per class, a row per label; bands are bars across their classes
  const L = ClassView.levels(S.spec);
  if (!L.length) return `<p class="muted">No classes yet. Add them on Cards or the Table.</p>`;
  const lv = cvLevel(), name = lv || "No level", pic = ClassView.bands(S.spec, lv);
  const picker = `<div class="row" style="margin:12px 0 8px"><label>Level <select id="cvLevel">${L.map(l => opt(l, lv, l || "No level")).join("")}</select></label>
    <span class="cvlegend small muted"><span class="lgd whole"></span>Whole class <span class="lgd bar"></span>Band: its groups meet at the same time <span class="lgd part"></span>Part of the class</span></div>`;
  if (!pic.classes.length) return `${picker}<p class="muted">No classes at ${esc(name)} yet.</p>`;
  if (!pic.rows.length) return `${picker}<p class="muted">No lesson rows for ${esc(name)} yet. Add them on step 5.</p>`;
  const col = k => k + 2, head = pic.classes.map((c, k) => `<div class="chcol" style="grid-row:1;grid-column:${col(k)}">${esc(c)}</div>`).join("");
  const cells = pic.rows.map((r, i) => {
    const row = i + 2, same = i > 0 && pic.rows[i - 1].label === r.label, covered = new Set();
    r.bars.forEach(b => b.spans.forEach(([f, n]) => { for (let k = f; k < f + n; k++) covered.add(k); }));
    let h = `<div class="clab${same ? " again" : ""}" style="grid-row:${row};grid-column:1">${esc(r.label)}</div>`;
    pic.classes.forEach((_, k) => { const c = r.cells[k];
      if (c && c.kind === "whole") h += `<div class="cwcell" style="grid-row:${row};grid-column:${col(k)}" title="The whole class together"></div>`;
      else if (c) h += `<div class="cpcell" style="grid-row:${row};grid-column:${col(k)}" title="Part of the class, in a teaching group">${esc(c.code)}</div>`;
      else if (!covered.has(k)) h += `<div class="cecell" style="grid-row:${row};grid-column:${col(k)}"></div>`; });
    r.bars.forEach(b => b.spans.forEach(([f, n], pi) => {
      const chips = pi ? "" : `<span class="cchips">${b.groups.map(g => { const sub = g.subject || "", rest = sub && Groups.untag(sub) === r.label ? sub.trim().slice(r.label.length).trim() : "";
        return `<span class="chip">${esc(rest || sub || "No subject yet")}${g.students != null ? ` · ${esc(g.students)}` : ""}</span>`; }).join("")}</span>`;
      h += `<button class="cbar" data-cband="${esc(b.block)}" style="grid-row:${row};grid-column:${col(f)} / span ${n}" title="Open ${esc(b.block)} on step 5"><b>${esc(b.block)}</b>${chips}</button>`; }));
    return h; }).join("");
  return `${picker}<div class="bandwrap"><div class="bandgrid" style="grid-template-columns:minmax(120px,max-content) repeat(${pic.classes.length},minmax(84px,1fr))"><div class="chcol corner" style="grid-row:1;grid-column:1"></div>${head}${cells}</div></div>`;
}
function openBand(block) {   // from a bar: step 5 on Groups and bands, at the level shown, with the band in view
  const lv = cvLevel(); M.view = "groups"; try { localStorage.setItem(MAPVIEW, M.view); } catch (e) { }
  const gp = gpState(); if (levels().includes(lv) && gp.level !== lv) { gp.level = lv; gp.ticked.clear(); M.gpTo = ""; }
  gp.dept = ""; gp.subject = ""; gp.teacher = ""; gp.band = ""; M.gtab = "bands"; M.gask = null;   // no filter and no tab may hide the band being opened
  S.step = STEPS.findIndex(x => x[0] === "lessons"); save(); render(); window.scrollTo(0, 0);
  const lane = [...document.querySelectorAll("[data-glane]")].find(x => x.dataset.glane === block);
  if (lane) lane.scrollIntoView({ block: "center" });
}
function openBands(level) {   // from step 5: step 2 on Bands at that level
  CV.view = "bands"; if (ClassView.levels(S.spec).includes(level)) CV.level = level; cvOpen(null); try { localStorage.setItem(CLASSVIEW, CV.view); } catch (e) { }
  S.step = STEPS.findIndex(x => x[0] === "classes"); save(); render(); window.scrollTo(0, 0);
}
const SUBJECTVIEW = "ttsetup.view.subjects";
const SV = { view: "cards" };   // "cards" or "table"; kept for each person in their browser
try { const sv = localStorage.getItem(SUBJECTVIEW); if (["cards", "table"].includes(sv)) SV.view = sv; } catch (e) { }
function subjectsTable() {   // today's table and its Add button
  const { out, crit } = issues(); const tags = (sc().tags || []).map(t => t[0]);
  return `<div class="tablewrap"><table><tr><th>Subject</th><th>Code</th><th>${tagLabel()}</th><th>Department</th><th>Room kind</th><th>Lesson length</th>${levels().map(l => `<th>${esc(l)}</th>`).join("")}<th title="How many groups or classes have this subject on step 5 (Teaching groups & deployment): a banded group counts once, a whole-class subject once per class. 0: none yet, so it is not timetabled.">Teaching groups</th><th></th></tr>
      ${S.spec.subjects.map((s, i) => `<tr id="subjects-${i}" class="${rowCls(out, crit, "subjects", i)}"><td style="min-width:220px">${inp(`spec.subjects.${i}.subject`, s.subject)}</td><td class="num">${inp(`spec.subjects.${i}.code`, s.code, "text", 'style="width:54px"')}</td><td>${sel(`spec.subjects.${i}.tag`, s.tag, tags, false)}</td><td>${sel(`spec.subjects.${i}.dept`, s.dept, sc().departments || [])}</td><td>${sel(`spec.subjects.${i}.room_kind`, s.room_kind, sc().room_kinds || [])}</td><td class="num">${inp(`spec.subjects.${i}.lesson_length`, s.lesson_length, "number", 'style="width:56px"')}</td>${levels().map(l => `<td class="num">${inp(`spec.subjects.${i}.periods.${l}`, (s.periods || {})[l], "number", 'style="width:56px"')}</td>`).join("")}<td class="calc">${teachingGroups(s.subject)}</td><td>${delBtn("subjects", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="subjects">+ Add subject</button></div>`;
}
/* step 3, Cards view: a subject and its G-levels as one card, a column per department. Nothing is kept between draws: the cards come from SubjectView.columns each time. */
function subjectsCards() {
  const { out, crit } = issues(), cols = SubjectView.columns(S.spec), T = SubjectView.tags(S.spec), L = levels(), subs = S.spec.subjects;
  const tw = sjWord(), tl = sjWord(true);
  const kinds = sc().room_kinds || [], depts = sc().departments || [], allTags = (sc().tags || []).map(t => t[0]);
  const addBtn = d => `<button class="small" data-sadd="${encodeURIComponent(d)}">+ Add a subject</button>`;
  if (!cols.length) return `<p class="muted">No subjects yet. Add one here, or switch to Table.</p><div class="row" style="margin-top:10px">${addBtn("")}</div>`;
  const TG = `title="How many groups or classes have this subject on step 5 (Teaching groups & deployment): a banded group counts once, a whole-class subject once per class. 0: none yet, so it is not timetabled."`;
  const sjSel = (id, what, cur, list) => `<select id="${id}" data-sset="${what}">${opt("", cur, "")}${list.map(v => opt(v, cur)).join("")}${cur && !list.includes(cur) ? opt(cur, cur, cur + " (not on list)") : ""}</select>`;
  const mark = ris => ris.some(ri => (out.subjects[ri] || []).some(m => isCrit(crit, "subjects", ri, m))) ? "bad" : ris.some(ri => (out.subjects[ri] || []).length) ? "caution" : "";
  const periods = ri => L.map(l => `<td class="num">${inp(`spec.subjects.${ri}.periods.${l}`, ((subs[ri] || {}).periods || {})[l], "number", 'style="width:56px"')}</td>`).join("");
  const msgsOf = ris => { const m = ris.flatMap(ri => out.subjects[ri] || []); return m.length ? `<div class="sjmsgs">${m.map(x => `<div>${esc(x)}</div>`).join("")}</div>` : ""; };
  const odd = c => {   // a row shown as it is: the table's own boxes
    const ri = c.ri, s = subs[ri] || {}, why = c.odd === "tag" ? (c.rows[0].tag !== "" ? `Shown as it is: this row's name does not end with its ${tw}, ${c.rows[0].tag}.` : `Shown as it is: this row's name ends with a ${tw} that is not set on it.`) : `Another row has this name and ${tw}. Delete one of the two.`;
    return `<div class="sjcard sjodd ${mark([ri])}" data-scard="${ri}">
      <div class="sjfields"><label>Subject ${inp(`spec.subjects.${ri}.subject`, s.subject)}</label><label>Code ${inp(`spec.subjects.${ri}.code`, s.code, "text", 'style="width:70px"')}</label><label>${esc(tagLabel())} ${sel(`spec.subjects.${ri}.tag`, s.tag, allTags, false)}</label>
        <label>Department ${sel(`spec.subjects.${ri}.dept`, s.dept, depts)}</label><label>Room kind ${sel(`spec.subjects.${ri}.room_kind`, s.room_kind, kinds)}</label><label>Lesson length ${inp(`spec.subjects.${ri}.lesson_length`, s.lesson_length, "number", 'style="width:70px"')}</label></div>
      <p class="muted small sjwhy">${esc(why)}</p>
      <div class="sjgridwrap"><table class="sjgrid"><tr>${L.map(l => `<th>${esc(l)}</th>`).join("")}<th ${TG}>Teaching groups</th></tr>
        <tr id="subjects-${ri}" class="${rowCls(out, crit, "subjects", ri)}">${periods(ri)}<td class="calc">${teachingGroups(s.subject)}</td></tr></table></div>
      ${msgsOf([ri])}<div class="row" style="margin-top:8px"><button class="small danger" data-sremove title="Remove this row">Delete</button></div></div>`;
  };
  const card = c => {
    if (c.odd) return odd(c);
    const ri = c.ri, first = subs[c.rows[0].ri] || {}, named = c.name !== "", ris = c.rows.map(x => x.ri), tagged = c.ticked.length > 0;
    const ticks = (c.plain !== null && tagged ? [`<label class="sjtick"><input type="checkbox" id="sjtick-${ri}-plain" data-stick="" checked ${named ? "" : 'disabled title="Give the subject a name first."'}> no ${esc(tw)}</label>`] : [])
      .concat(T.map((t, n) => `<label class="sjtick"><input type="checkbox" id="sjtick-${ri}-${n}" data-stick="${esc(t)}" ${c.ticked.includes(t) ? "checked" : ""} ${named ? "" : 'disabled title="Give the subject a name first."'}> ${esc(t)}</label>`));
    const label = x => tagged ? (x.tag === "" ? `no ${esc(tw)}` : esc(x.tag)) : "";
    const showKind = !c.same_kind, showLen = !c.same_length;
    const grid = `<div class="sjgridwrap"><table class="sjgrid"><tr><th></th>${showKind ? "<th>Room kind</th>" : ""}${showLen ? "<th>Lesson length</th>" : ""}${L.map(l => `<th>${esc(l)}</th>`).join("")}<th ${TG}>Teaching groups</th></tr>
      ${c.rows.map(x => `<tr id="subjects-${x.ri}" class="${rowCls(out, crit, "subjects", x.ri)}"><th scope="row" class="sjrow">${label(x)}</th>${showKind ? `<td>${sel(`spec.subjects.${x.ri}.room_kind`, (subs[x.ri] || {}).room_kind, kinds)}</td>` : ""}${showLen ? `<td class="num">${inp(`spec.subjects.${x.ri}.lesson_length`, (subs[x.ri] || {}).lesson_length, "number", 'style="width:56px"')}</td>` : ""}${periods(x.ri)}<td class="calc">${teachingGroups((subs[x.ri] || {}).subject)}</td></tr>`).join("")}</table></div>`;
    return `<div class="sjcard ${mark(ris)}" data-scard="${ri}">
      <div class="sjtop"><input id="sjname-${ri}" data-sname placeholder="Subject name" value="${esc(c.name)}"><input id="sjcode-${ri}" data-sset="code" placeholder="Code" value="${esc(c.code)}" style="width:64px"><button class="small danger" data-sremove title="Remove this subject and all its ${esc(tl)}">Delete</button></div>
      ${ticks.length ? `<div class="sjticks">${ticks.join("")}</div>` : ""}
      ${grid}
      ${showKind || showLen ? `<p class="muted small sjwhy">The ${esc(tl)} differ in room kind or lesson length: each has its own in the grid.</p>` : ""}
      <div class="sjfields"><label>Department ${sjSel(`sjdept-${ri}`, "dept", first.dept, depts)}</label>${showKind ? "" : `<label>Room kind ${sjSel(`sjkind-${ri}`, "room_kind", first.room_kind, kinds)}</label>`}${showLen ? "" : `<label>Lesson length <input type="number" id="sjlen-${ri}" data-sset="lesson_length" value="${esc(first.lesson_length)}" style="width:70px"></label>`}</div>
      ${msgsOf(ris)}</div>`;
  };
  return `<div class="sjcols">${cols.map(col => `<section class="sjcol"><div class="sjhead"><b>${col.dept === "" ? "No department yet" : esc(col.dept)}</b><span class="muted small">${col.cards.length} subject${col.cards.length === 1 ? "" : "s"}</span></div>
    ${col.cards.map(card).join("")}<div class="row">${addBtn(col.dept)}</div></section>`).join("")}</div>`;
}
/* step 3, Cards view: what a card's boxes do. A card is found again from SubjectView.columns after every change (a row's index moves when rows come or go). */
function sjCardOf(ri) { for (const col of SubjectView.columns(S.spec)) for (const c of col.cards) if (c.rows.some(x => x.ri === ri)) return c; return null; }
function sjShow(ri, sel, scroll) {   // after a redraw: the card that holds this row, the box in it (if sel) with the keyboard, the card in view (if scroll)
  const row = document.getElementById(`subjects-${ri}`), c = row && row.closest("[data-scard]");
  if (!c) return null;
  const el = sel && c.querySelector(sel); if (el && !el.disabled) el.focus({ preventScroll: true });
  if (scroll) c.scrollIntoView({ block: "nearest" });
  return c;
}
const sjNum = (n, one, many) => `${n} ${n === 1 ? one : many}`;
function sjWord(plural) { return (tagLabel() === "G-level" ? "G-level" : "level tag") + (plural ? "s" : ""); }   // the school's own word for a G-level
function sjLost(names, ris) {   // lesson rows that name one of these subjects, when no row left on the list (outside ris) still has that name
  const keep = new Set(S.spec.subjects.filter((x, i) => x && typeof x === "object" && !ris.includes(i)).map(x => String(x.subject == null ? "" : x.subject).trim()));
  return [...new Set(names)].filter(x => x !== "" && !keep.has(x)).reduce((a, x) => a + SubjectView.uses(S.spec, x), 0);
}
function sjName(e) {   // the name box: every row of the card is renamed
  if (locked("subjects")) return;
  const el = e.target, c = sjCardOf(Number(el.closest("[data-scard]").dataset.scard));
  if (!c) { render(); return; }
  if (el.value.trim() !== c.name) {
    if (!SubjectView.rename(S.spec, c.ri, el.value)) { toast(`A subject with ${sjWord(true)} needs a name.`); render(); return; }
    save(); render(); poll(); return;
  }
  render();
}
function sjSet(e) {   // code, department, room kind, lesson length: the same value on every row, stored as the table stores it
  if (locked("subjects")) return;
  const el = e.target, c = sjCardOf(Number(el.closest("[data-scard]").dataset.scard)); if (!c) { render(); return; }
  let v = el.value; if (el.type === "number") v = v === "" ? null : Number(v); if (v === "") v = null;
  if (!SubjectView.set(S.spec, c.ri, el.dataset.sset, v)) { render(); return; }
  save(); render(); poll();
  if (el.dataset.sset === "dept") sjShow(c.rows[0].ri, "[data-sset=dept]", true);
}
function sjTick(e) {   // a G-level's tick box: ticked adds it, unticked takes it off (asking first when lessons use it)
  if (locked("subjects")) return;
  const el = e.target, tag = el.dataset.stick, c = sjCardOf(Number(el.closest("[data-scard]").dataset.scard));
  if (!c) { render(); return; }
  if (el.checked) {
    const r = tag === "" ? null : SubjectView.tick(S.spec, c.ri, tag);
    if (!r) {
      const other = tag === "" ? "" : SubjectView.clash(S.spec, c.ri, tag);
      if (other) toast(`${other} is already on the list as this subject's ${tag}, on a card of its own.`);
      render(); return;
    }
    save(); render(); poll(); sjShow(r.ri, `[data-stick="${CSS.escape(tag)}"]`); return;
  }
  const row = c.rows.find(x => x.tag === tag); if (!row) { render(); return; }
  const n = sjLost([row.subject], [row.ri]);
  if (n > 0 && !confirm(`${row.subject} is on ${sjNum(n, "lesson row", "lesson rows")} of step 5. Take it off step 3? Those lessons keep the name and show it as not on the list until they are given a subject. Undo takes it back.`)) { render(); return; }
  const left = c.rows.find(x => x.ri !== row.ri), r = SubjectView.untick(S.spec, c.ri, tag);
  if (!r) { render(); return; }
  save(); render(); poll();
  if (r.how === "emptied") sjShow(row.ri, `[data-stick="${CSS.escape(tag)}"]`);
  else if (left) sjShow(left.ri > row.ri ? left.ri - 1 : left.ri, tag === "" ? "[data-sname]" : `[data-stick="${CSS.escape(tag)}"]`);
}
function sjRemove(b) {   // Delete: always asks
  if (locked("subjects")) return;
  const c = sjCardOf(Number(b.closest("[data-scard]").dataset.scard)); if (!c) { render(); return; }
  const n = sjLost(c.rows.map(x => x.subject), c.rows.map(x => x.ri));
  const k = c.ticked.length, one = c.rows.length === 1, nm = one ? c.rows[0].subject : c.name;
  const what = nm === "" ? "this subject" : one ? nm : `${c.name} and its ${sjNum(k, sjWord(), sjWord(true))}`;
  if (!confirm(`Remove ${what}?${n ? ` ${sjNum(n, "lesson row", "lesson rows")} of step 5 ${n === 1 ? "uses" : "use"} ${c.rows.length === 1 ? "it" : "them"}.` : ""} Undo takes it back.`)) return;
  if (!SubjectView.remove(S.spec, c.ri)) return;
  unpick(); save(); render(); poll();
}
function sjAdd(dept) {
  if (locked("subjects")) return;
  const ri = SubjectView.add(S.spec, dept); save(); render(); poll();
  const c = sjShow(ri, "[data-sname]", false); if (c) c.scrollIntoView({ block: "center" });
}
/* ---------------- step 4: the Cards and Table views of the teachers */
const TEACHERVIEW = "ttsetup.view.teachers";
const TV = { view: "cards", open: null, openId: null, col: "" };   // open: the index of the open teacher, found again by openId (the row's own _id) on each draw; col: the department column the card was opened in
try { const tv = localStorage.getItem(TEACHERVIEW); if (["cards", "table"].includes(tv)) TV.view = tv; } catch (e) { }
const TK_SECOND_WHY = "Only the committee gives a teacher a second department.";
const tkHead = () => isHead() && !S.practice;   // a department head: never gives a second department
const tkOpen = (ti, col) => { heldOpen(TV, S.spec.teachers, ti); TV.col = col || ""; };
const tkText = v => v == null ? "" : String(v).trim();
const tkSecondOf = t => { const d2 = tkText(t.dept2); return d2 === tkText(t.dept) ? "" : d2; };   // the second department a row really has
const tkMark = t => t.provisional === "Yes" ? ` <span class="headmark"${committee() ? ' title="A department head added this teacher. Set Provisional to No to confirm them."' : ""}>added by a head, not yet confirmed</span>` : "";
function teachersTable(rows, iss) {   // today's table plus Department 2
  const { out, crit, load } = iss, P = S.pick, lc = loadChecks(load), all = rows.length && rows.every(([, i]) => P.teachers.has(i)), depts = sc().departments || [];
  return `<div class="tablewrap"><table><tr><th><input type="checkbox" data-pickall="teachers" title="Tick every teacher shown (${rows.length})" ${all ? "checked" : ""}></th><th></th><th>Teacher</th><th>Short</th><th>Department</th><th>Department 2</th><th>Allowance</th><th>Given</th><th>Spare</th><th>Role</th><th>Other duties</th><th>Total load</th><th>Load check</th><th>Provisional</th><th></th></tr>
    ${rows.map(([t, i]) => { const g = load[t.name] || 0; const sp = t.allowance ? Number(t.allowance) - g : ""; const tot = g + (Number(t.other_duties) || 0);
      return `<tr id="teachers-${i}" class="${rowCls(out, crit, "teachers", i)}${P.teachers.has(i) ? " picked" : ""}"><td><input type="checkbox" data-pick="teachers.${i}" ${P.teachers.has(i) ? "checked" : ""}></td><td class="avcell" title="New look is on the teacher's profile, step 5">${avatarOf(t, 32)}</td><td style="min-width:180px">${inp(`spec.teachers.${i}.name`, t.name)}</td><td>${inp(`spec.teachers.${i}.short`, t.short, "text", 'style="width:90px"')}</td><td>${sel(`spec.teachers.${i}.dept`, t.dept, depts)}</td><td>${sel(`spec.teachers.${i}.dept2`, tkSecondOf(t), depts.filter(d => d !== tkText(t.dept)))}</td><td class="num">${inp(`spec.teachers.${i}.allowance`, t.allowance, "number")}</td><td class="calc">${g}</td><td class="calc" style="${sp !== "" && sp < 0 ? "color:var(--warn);font-weight:600" : ""}">${sp}</td><td style="min-width:96px">${sel(`spec.teachers.${i}.role`, t.role, roles().map(r => r.role))}</td><td class="num">${inp(`spec.teachers.${i}.other_duties`, t.other_duties, "number", 'style="width:60px"')}</td><td class="calc" style="${t.allowance && tot > Number(t.allowance) ? "color:var(--warn);font-weight:600" : ""}">${tot}</td><td class="calc" style="white-space:normal;min-width:200px;${lc[i] ? "color:var(--warn)" : ""}">${esc(lc[i])}</td><td>${sel(`spec.teachers.${i}.provisional`, t.provisional, ["Yes", "No"])}${tkMark(t)}</td><td>${delBtn("teachers", i)}</td></tr>`; }).join("")}
    </table></div>`;
}
/* the Cards view: a column per department; a teacher with two departments has a card in each. Nothing is kept between draws but which card is open. */
function teachersCards(cols, iss) {
  const { out, crit, load } = iss, P = S.pick, T = S.spec.teachers, lc = loadChecks(load), depts = sc().departments || [], head = tkHead();
  if (!cols.length) return `<p class="muted">No teachers yet. Add them with the bar above, or with + Add teacher.</p>`;
  // the open card is in the column it was opened in; if that column no longer holds the teacher, in their home column
  let openCol = null;
  if (TV.open !== null) {
    const has = (col, home) => col.cards.some(c => c.ti === TV.open && (!home || c.home));
    const w = cols.find(c => c.dept === TV.col && has(c)) || cols.find(c => has(c, true));
    if (w) { openCol = w.dept; TV.col = w.dept; }
  }
  const chipBar = depts.filter(d => tkText(d) !== "").length ? `<div class="tkchips"><span class="muted small">${head ? "Departments: only the committee gives a teacher a second department." : "Departments: drag one onto a teacher to give them a second department, or open the teacher and pick it."}</span>
    ${depts.filter(d => tkText(d) !== "").map(d => `<span class="chip tkdept"${head ? "" : ' draggable="true"'} data-tchip="${esc(encodeURIComponent(d))}">${esc(d)}</span>`).join("")}</div>` : "";
  const openCard = (c, colDept) => {
    const ti = c.ti, t = T[ti], p = f => `spec.teachers.${ti}.${f}`, g = load[t.name] || 0, tot = g + (Number(t.other_duties) || 0), A = Number(t.allowance) || 0, sp = t.allowance ? Number(t.allowance) - g : "", msgs = out.teachers[ti] || [];
    return `<div class="tkcard open ${rowCls(out, crit, "teachers", ti)}" ${c.home ? `id="teachers-${ti}" ` : ""}data-tcard="${ti}" data-tcol="${esc(encodeURIComponent(colDept))}">
      <div class="tktop"><span class="tkav">${avatarOf(t, 32)}</span><b class="tkwho">${t.name ? esc(t.name) : "(no name yet)"}</b></div>
      <div class="tkfields"><label>Name ${inp(p("name"), t.name)}</label><label>Short ${inp(p("short"), t.short, "text", 'style="width:90px"')}</label>
        <label>Department ${sel(p("dept"), t.dept, depts)}</label><label>Second department ${sel(p("dept2"), tkSecondOf(t), depts.filter(d => d !== tkText(t.dept)))}</label>
        <label>Allowance ${inp(p("allowance"), t.allowance, "number", 'style="width:70px"')}</label><label>Role ${sel(p("role"), t.role, roles().map(r => r.role))}</label>
        <label>Other duties ${inp(p("other_duties"), t.other_duties, "number", 'style="width:70px"')}</label><label>Provisional ${sel(p("provisional"), t.provisional, ["Yes", "No"])}</label></div>
      <div class="tkfigs"><span>Given <b>${g}</b></span><span>Spare <b style="${sp !== "" && sp < 0 ? "color:var(--warn)" : ""}">${sp}</b></span><span>Total load <b style="${A && tot > A ? "color:var(--warn)" : ""}">${tot}</b></span></div>
      ${lc[ti] ? `<div class="tkcheck">${esc(lc[ti])}</div>` : ""}${msgs.length ? `<div class="tkmsgs">${msgs.map(m => `<div>${esc(m)}</div>`).join("")}</div>` : ""}${t.provisional === "Yes" ? `<div class="small">${tkMark(t)}</div>` : ""}
      <div class="row" style="margin-top:8px">${delBtn("teachers", ti)} <button class="small" data-tclose="1">Close</button></div></div>`;
  };
  const card = (c, colDept) => {
    if (openCol !== null && c.ti === TV.open && colDept === openCol) return openCard(c, colDept);
    const t = T[c.ti], ds = People.depts(t), g = load[t.name] || 0, other = Number(t.other_duties) || 0, tot = g + other, A = Number(t.allowance) || 0, over = A > 0 && tot > A;
    const nm = t.name ? esc(t.name) : "(no name yet)";
    const dchips = ds.map((d, i) => i === 1 && !head ? `<span class="chip tkdsec">${esc(d)} <button class="tkx" data-tsecond="${c.ti}" title="Take ${esc(d)} off ${esc(t.name || "this teacher")}" aria-label="Take ${esc(d)} off ${esc(t.name || "this teacher")}">✕</button></span>` : `<span class="chip">${esc(d)}</span>`).join("");
    return `<div class="tkcard ${rowCls(out, crit, "teachers", c.ti)}${P.teachers.has(c.ti) ? " picked" : ""}" ${c.home ? `id="teachers-${c.ti}" ` : ""}data-tcard="${c.ti}" data-tcol="${esc(encodeURIComponent(colDept))}">
      <div class="tktop"><input type="checkbox" data-pick="teachers.${c.ti}" aria-label="Tick ${esc(t.name || "this teacher")}" ${P.teachers.has(c.ti) ? "checked" : ""}><span class="tkav">${avatarOf(t, 32)}</span>
        <div class="tkwho"><button class="tkname" data-topen="${c.ti}">${nm}</button>${t.short ? ` <span class="muted small">${esc(t.short)}</span>` : ""}<div class="muted small">${esc(t.role || "")}</div></div></div>
      <div class="tkdepts">${dchips}</div>
      <div class="tkloadrow"><div class="tkload${over ? " over" : ""}" title="${g} periods given${other ? ` + ${other} other duties` : ""}${A ? `, allowance ${A}` : ""}"><i style="width:${A ? Math.min(100, Math.round(100 * tot / A)) : 0}%"></i></div><span class="${over ? "overtxt" : "muted"} small">${A ? `${tot} / ${A}` : `${tot} periods`}</span></div>
      ${lc[c.ti] ? `<div class="tkcheck">${esc(lc[c.ti])}</div>` : ""}${t.provisional === "Yes" ? `<div class="small">${tkMark(t)}</div>` : ""}</div>`;
  };
  return `${chipBar}<div class="tkcols${cols.length === 1 ? " one" : ""}">${cols.map(col => `<section class="tkcol"><div class="tkhead"><b>${col.dept === "" ? "No department yet" : esc(col.dept)}</b><span class="muted small">${col.cards.length} teacher${col.cards.length === 1 ? "" : "s"}</span></div>
    ${col.cards.length ? col.cards.map(c => card(c, col.dept)).join("") : `<p class="muted small">No teachers yet.</p>`}</section>`).join("")}</div>`;
}
function tkOpenCard(ti, cardEl) {   // opens the card that was clicked, in its column (from the keyboard, the name button opens it)
  let col = ""; try { col = decodeURIComponent(cardEl ? cardEl.dataset.tcol || "" : ""); } catch (e) { }
  tkOpen(ti, col); render();
  const o = document.querySelector(`.tkcard.open[data-tcard="${ti}"]`) || document.getElementById(`teachers-${ti}`);
  if (o) { o.scrollIntoView({ block: "nearest" }); const f = o.querySelector("input:not(:disabled), select:not(:disabled)") || o.querySelector("[data-tclose]"); if (f) f.focus({ preventScroll: true }); }
}
/* a second department given, changed or taken off (a chip dropped on a card, the Second department box, the ✕): one save, one Undo step, one toast */
function tkSecond(ti, dept) {
  if (tkHead()) return;
  const t = S.spec.teachers[ti]; if (!t) return;
  const r = TeacherView.setSecond(S.spec, ti, dept), nm = t.name || "This teacher", d = tkText(dept);
  if (!r) { render(); return; }
  const said = { home: `${d} is already ${nm}'s department.`, same: `${nm} is already in ${d} too.` }[r.how];
  if (said) { render(); toast(said); return; }   // nothing to save
  const msg = { set: `${nm} is now in ${d} too.`, changed: `${nm}'s second department is now ${d}, not ${r.was}.`, off: `${r.was} taken off ${nm}.` }[r.how];
  save(); render(); if (msg) toast(`${msg} Undo takes it back.`);
}
const VIEWS = {
  start() {
    const how = `<div class="card"><h2>How it works</h2><ol class="howto"><li>Fill the steps on the left. The panel on the right lists anything that does not add up (a teacher twice in a band, a lesson with no periods, a teacher over their allowance).</li><li>On <b>Download</b>, get the setup workbook and the timetable skill, and give both to an AI agent: it makes the timetable.</li><li>On <b>Upload and edit</b>, upload the timetable it hands back, check it and fix what it finds; on <b>Publish</b>, publish it. Teachers and students then sign in with their codes.</li></ol></div>`;
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
        <label class="f">What your school calls a class's form teachers ${inp("spec.school.parents_name", s.parents_name, "text", 'placeholder="Form teachers"')}</label>
        <label class="f">Most a class can have <input data-pmax type="number" min="1" max="6" value="${esc(Parents.maximum(s.parents_max) || 2)}"></label>
      </div></div>
      <div class="card"><h2>Day structure</h2>${(w => w.length ? `<div class="notice"><b>The Day structure and the settings on step 6 disagree.</b> The rules win where they are stricter, so make them say the same:<ul>${w.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : "")(structureWarnings())}<div class="legend">Brush: ${["L", "R", "W", "U", "F", "A", ""].map(c => `<button class="small ${S.brush === c ? "primary" : ""}" data-brush="${c}"><i class="c-${c}" style="width:12px;height:12px;display:inline-block;border-radius:3px;vertical-align:-2px"></i> ${{ L: "Lesson", R: "Recess", W: "Recess window", U: "Lunch", F: "Flag / assembly", A: "After-school slot", "": "No school" }[c]}</button>`).join("")}</div>
      <p class="muted" style="margin:4px 0 10px">Click or drag across cells to paint them with the brush.</p>
      <div class="tablewrap"><table class="dsgrid">${head}${lvRows}</table></div>
      ${hasWindows() ? `<h3 style="margin:14px 0 4px">Floating recess</h3><p class="muted" style="margin:0 0 8px">For the W periods: the solver puts a recess of this length in each recess window. Make a window the recess plus whole lessons (for example 2 + 3 + 3 periods with 3-period lessons), so the lessons still fit wherever the recess goes.</p>
        <div class="grid2">${(s.extra_settings || []).map((x, i) => isRecessRow(x) ? settingRow(x, i) : "").join("")}</div>` : ""}</div>`;
  },
  venues() {   // step 1: the same rooms as Blocks (by block and floor) or as the Table
    const sw = v => `<button class="${VV.view === v ? "on" : ""}" data-vview="${v}">${{ blocks: "Blocks", table: "Table" }[v]}</button>`;
    return `<div class="card"><div class="row" style="justify-content:space-between"><div><h1 style="margin:0">Step 1 · Venues</h1></div><div class="row switch">${sw("blocks")}${sw("table")}</div></div><p class="lead">Every room. Its kind decides which subjects may use it (you set a subject's room kind on step 3). <b>Capacity</b> is seats: a group only goes in a room that seats it. <b>For</b> keeps a room for some subjects, departments or levels (for example "Chemistry G3, Sec 3"); blank = anyone. A room that holds two classes at once (a field, a hall) gets an "At most N at once" rule on step 6. <b>Equipment</b> and <b>Configuration</b> are notes for people: nothing checks them.</p>
      <div class="helper row"><b>Add rooms</b> prefix ${`<input id="hvPre" value="B1-" style="width:70px">`} from <input id="hvFrom" type="number" value="1" style="width:60px"> to <input id="hvTo" type="number" value="8" style="width:60px"> kind ${sel("_hv", "classroom", sc().room_kinds || [], false, 'id="hvKind" data-k=""')} <button data-helper="venues">Add</button></div>
      ${VV.view === "table" ? venuesTable() : venuesBlocks()}</div>`;
  },
  classes() {   // step 2: the same classes as Cards, as Bands (a picture per level) or as the Table
    const sw = v => `<button class="${CV.view === v ? "on" : ""}" data-cview="${v}">${{ cards: "Cards", bands: "Bands", table: "Table" }[v]}</button>`;
    return `<div class="card"><div class="row" style="justify-content:space-between"><div><h1 style="margin:0">Step 2 · Classes</h1><p class="lead" style="margin:6px 0 0">Form classes with their level, size and home room (picked from step 1).</p></div><div class="row switch">${sw("cards")}${sw("bands")}${sw("table")}</div></div>
      ${CV.view === "bands" ? classesBands() : classesBars() + (CV.view === "table" ? classesTable() : classesCards())}</div>`;
  },
  subjects() {   // step 3: the same subjects as Cards (a subject and its G-levels in one card) or as the Table
    const sw = v => `<button class="${SV.view === v ? "on" : ""}" data-sview="${v}">${{ cards: "Cards", table: "Table" }[v]}</button>`;
    const tl = sjWord(true);
    return `<div class="card"><div class="row" style="justify-content:space-between;align-items:flex-start"><div><h1 style="margin:0">Step 3 · Subjects</h1></div><div class="row switch">${sw("cards")}${sw("table")}</div></div>
      <p class="lead">Periods per ${Number(sc().weeks) === 2 ? "fortnight" : "week"} for each level that takes the subject (blank = not offered). Lessons are ${sc().lesson_length} periods long unless the subject says otherwise; leftovers become one or two shorter lessons. The code names the groups (1ELP1…). ${tagLabel()} is the level of study used for banding. <b>Teaching groups</b> fills in by itself: how many groups or classes are taught the subject on step 5 (each group in a band counts once, a whole-class subject once per class). 0 means no lessons yet, so it is not timetabled. On Cards, a subject and its ${tl} are one card: type the name once and tick the ${tl}.</p>
      ${SV.view === "table" ? subjectsTable() : subjectsCards()}</div>`;
  },
  teachers() {   // step 4: the teachers as Cards (a column per department) or as the Table, then the Roles
    const iss = issues(), { load } = iss, f = S.tf, P = S.pick, q = f.q.trim().toLowerCase(), cards = TV.view === "cards";
    heldResolve(TV, S.spec.teachers); if (TV.open !== null && !S.spec.teachers[TV.open]) tkOpen(null);
    const rows = S.spec.teachers.map((t, i) => [t, i]).filter(([t]) => (!f.dept || People.inDept(t, f.dept)) && (!q || `${t.name || ""} ${t.short || ""}`.toLowerCase().includes(q)));
    const cols = cards ? TeacherView.columns(S.spec, { dept: f.dept, q: f.q.trim() }) : null;
    const ix = cards ? [...new Set(cols.flatMap(c => c.cards.map(x => x.ti)))] : rows.map(([, i]) => i);
    P.shown.teachers = ix;
    const sw = v => `<button class="${TV.view === v ? "on" : ""}" data-tview="${v}">${{ cards: "Cards", table: "Table" }[v]}</button>`;
    return `<div class="card"><div class="row" style="justify-content:space-between;align-items:flex-start"><div><h1 style="margin:0">Step 4 · Teachers</h1></div><div class="row switch">${sw("cards")}${sw("table")}</div></div>
      <p class="lead">Each teacher with their department, role and allowance. A teacher who teaches in two departments can have a second department: they are then on both departments' pages on step 5. Who teaches which class or group is set on step 5. Tick teachers (shift-click for a run) to give them a department, role or allowance together.</p></div>
      ${mayUpload() ? uploadCard() : ""}
      <div class="card" id="teacherList"><div class="helper" style="margin-top:0"><b>Add teachers</b> (one name per line) <div class="row" style="margin-top:6px"><textarea id="htNames" rows="3" style="width:280px;border:1px solid var(--line);border-radius:6px;padding:6px"></textarea> department ${sel("_ht", (sc().departments || [])[0], sc().departments || [], false, 'id="htDept" data-k=""')} allowance <input id="htAllow" type="number" value="${sc().type === "primary" ? 36 : 64}" style="width:70px"> <button data-helper="teachers">Add</button></div></div>
      <div class="row" style="margin:12px 0 8px"><b>Show</b> <select id="tfDept">${opt("", f.dept, "All departments")}${(sc().departments || []).map(d => opt(d, f.dept)).join("")}</select>
        <input id="tfQ" type="search" placeholder="Search name" title="Type, then press Enter" value="${esc(f.q)}" style="width:160px">
        <span class="muted small">${ix.length === S.spec.teachers.length ? `${ix.length} teachers` : `${ix.length} of ${S.spec.teachers.length} teachers`}</span></div>
      ${teacherBar()}
      ${cards ? teachersCards(cols, iss) : teachersTable(rows, iss)}
      <div class="row" style="margin-top:10px"><button data-add="teachers">+ Add teacher</button></div></div>
      ${VIEWS.roles(load)}`;
  },
  roles(load) {   // the Roles sheet: guide allowance per role and the load of the teachers in it
    // drawing never writes to the setup: the usual roles are written when the setup is opened (defaultRoles), and a
    // head, who may not change roles, sees them listed (read-only) when the setup has none
    const RL = S.spec.roles && S.spec.roles.length ? S.spec.roles : isHead() && !S.practice ? S.meta.roles || [] : [];
    const tot = t => (load[t.name] || 0) + (Number(t.other_duties) || 0), avg = a => a.length ? Math.round(a.reduce((x, y) => x + y, 0) / a.length) : "";
    const eo = avg(S.spec.teachers.filter(t => t.role === "EO" && tot(t) > 0).map(tot)), mgmt = avg(S.spec.teachers.filter(t => ["HOD", "SH"].includes(t.role) && tot(t) > 0).map(tot));
    return `<div class="card"><h2>Roles</h2><p>The teacher list above is checked against these roles.</p><p class="muted">Management (HOD, SH) should teach fewer periods than teachers; teachers (EO) should be spread evenly. Teachers (EO) average load <b>${eo || "–"}</b> · management (HOD, SH) <b>${mgmt || "–"}</b>.
      Flag a teacher <input data-k="spec.school.role_spread" type="number" value="${esc(sc().role_spread ?? 15)}" style="width:56px"> periods or more from the teacher average.</p>
      <div class="tablewrap"><table><tr><th>Role</th><th>What it is</th><th>Guide allowance</th><th>Group</th><th>Teachers</th><th>Average load</th><th></th></tr>
      ${RL.map((r, i) => { const ts = S.spec.teachers.filter(t => t.role === r.role);
        return `<tr><td>${inp(`spec.roles.${i}.role`, r.role, "text", 'style="width:80px"')}</td><td style="min-width:240px">${inp(`spec.roles.${i}.what`, r.what)}</td><td class="num">${inp(`spec.roles.${i}.allowance`, r.allowance, "number", 'style="width:64px"')}</td><td>${inp(`spec.roles.${i}.group`, r.group)}</td><td class="calc">${ts.length}</td><td class="calc">${avg(ts.map(tot))}</td><td>${delBtn("roles", i)}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="roles">+ Add role</button></div></div>`;
  },
  lessons() {   // step 5: the department map, or the table view of the same rows
    const sw = v => `<button class="${M.view === v ? "on" : ""}" data-mview="${v}">${{ map: "Map", groups: "Groups and bands", table: "Table" }[v]}</button>`;
    return `<div class="card"><div class="row" style="justify-content:space-between"><div><h1 style="margin:0">Step 5 · Department map</h1><p class="lead" style="margin:6px 0 0">Tick teachers at the top, then click a class or group card to place them there. Dragging works too. Click an avatar for the teacher's profile. The table view shows the same rows for bulk edits, bands and new groups.</p></div><div class="row switch">${sw("map")}${sw("groups")}${sw("table")}</div></div></div>`
      + (M.view === "map" ? VIEWS.map() : M.view === "groups" ? VIEWS.groups() : VIEWS.table());
  },
  table() {
    const { out, crit, info, load } = issues(); const T = teacherNames(), f = S.tg, P = S.pick;
    const tsel = (i, k, x) => { const path = `spec.lessons.${i}.teachers.${k}`; const cur = (x.teachers || [])[k] || ""; const dept = (subj(x.subject) || {}).dept || "", lock = cpBlock(x);
      return `<select data-k="${path}" ${lock ? `disabled title="${esc(cpWhy())}"` : ""}>${opt("", cur, "")}${teacherOptions(dept, cur)}</select>`; };
    const rows = S.spec.lessons.map((x, i) => [x, i]).filter(([x]) => (!f.lv || x.level === f.lv) && (!f.subj || x.subject === f.subj)
      && (!f.t || (f.t === "-" ? !(x.teachers || []).some(Boolean) : (x.teachers || []).includes(f.t))));
    P.shown.lessons = rows.map(([, i]) => i);
    const held = x => (x.teachers || []).reduce((m, n, k) => String(n == null ? "" : n).trim() ? k + 1 : m, 0);   // a lesson never hides a teacher it holds (blanks at the end do not count)
    const NT = Math.max(3, Parents.subjects(S.spec).length ? Parents.cap(S.spec) : 0, ...rows.map(([x]) => held(x)));   // a staffed row following a shared lesson, or one kept from before the rule went off, may hold more
    const tcell = (i, k, x) => k >= (Parents.staffed(S.spec, x) ? Math.max(Parents.cap(S.spec), held(x)) : Math.max(3, held(x))) ? "<td></td>" : `<td style="min-width:${k ? 120 : 150}px">${tsel(i, k, x)}</td>`;
    const all = rows.length && rows.every(([, i]) => P.lessons.has(i));
    return `<div class="card"><h2>Table view</h2><p class="lead">Every teaching group (TG) and the teachers deployed to it. A whole-class subject is one group per class; a band splits its classes into groups that all have lessons at the same time. Set up the bands first, then add the groups and deploy teachers below.</p>
      ${VIEWS._bands(out, info, crit)}</div>
      <div class="card"><h2>Teaching groups</h2><p class="muted">One row per group, or per class for a whole-class subject. Pick level, subject and band (empty = whole class); choosing a band fills its classes. Group code and periods fill in by themselves. Lessons shows how the periods split, in grey; type your own, such as 5x3 + 2x2 (five 3-period lessons and two 2-period ones), or clear it to go back. Tick rows (shift-click for a run) to deploy a teacher or set Lessons on all of them at once.</p>
      <div class="helper row"><b>Add groups to a band</b> ${sel("_hb", "", blockNames(), true, 'id="hbBlock" data-k=""')} subject ${sel("_hbs", "", subjectNames(), true, 'id="hbSubj" data-k=""')} groups <input id="hbN" type="number" value="1" style="width:56px"> students each <input id="hbSt" type="number" style="width:64px"> <button data-helper="groups">Add</button></div>
      <div class="helper row"><b>Add a whole-class subject</b> level ${sel("_hw", levels()[0], levels(), false, 'id="hwLevel" data-k=""')} subject ${sel("_hws", "", subjectNames(), true, 'id="hwSubj" data-k=""')} <label style="white-space:nowrap">lessons <input id="hwPat" placeholder="usual split" title="How the periods split into lessons, for every row added: 5x3 + 2x2 is five 3-period lessons and two 2-period ones. Empty = the usual split shown in grey. Each row's own Lessons box can still be changed afterwards." style="width:128px"></label> <button data-helper="whole">Add one row per class</button></div>
      <div class="row" style="margin:12px 0 8px"><b>Show</b> <select id="tgLv">${opt("", f.lv, "All levels")}${levels().map(l => opt(l, f.lv)).join("")}</select>
        <select id="tgSubj">${opt("", f.subj, "All subjects")}${subjectNames().map(n => opt(n, f.subj)).join("")}</select>
        <select id="tgT">${opt("", f.t, "Any teacher")}${opt("-", f.t, "No teacher yet")}${T.map(t => opt(t, f.t)).join("")}</select>
        <span class="muted small">${rows.length === S.spec.lessons.length ? `${rows.length} rows` : `${rows.length} of ${S.spec.lessons.length} rows`}</span></div>
      ${tgBar(load, info)}
      <div class="tablewrap"><table><tr><th><input type="checkbox" data-pickall="lessons" title="Tick every row shown (${rows.length})" ${all ? "checked" : ""}></th><th>Level</th><th>Subject</th><th>Band</th><th>Classes</th><th>Teacher 1</th><th>Teacher 2</th><th title="A third teacher in the room (co-teaching)">Teacher 3</th>${Array.from({ length: NT - 3 }, (_, k) => `<th>Teacher ${k + 4}</th>`).join("")}<th>Students</th><th>Periods override</th><th>Keep code</th>${Number(sc().weeks) === 2 ? '<th title="Odd or Even: the group uses its special room (lab, studio...) on that week only, and a classroom on the other">Special room weeks</th>' : ""}<th>Code</th><th>Periods</th><th title="Type your own split, such as 5x3 + 2x2. Empty = the usual split shown in grey.">Lessons</th><th></th></tr>
      ${rows.map(([x, i]) => { const lk = cpBlock(x), ro = h => lk ? h.replace('class="chips"', 'class="chips ro"') : h, D = lk ? `disabled title="${esc(cpWhy())}"` : "";   // the server refuses a head's change to a staffed row's subject, level, band, classes, code and deletion
      return `<tr id="lessons-${i}" class="${rowCls(out, crit, "lessons", i)}${P.lessons.has(i) ? " picked" : ""}" title="${esc((out.lessons[i] || []).join(" "))}"><td><input type="checkbox" data-pick="lessons.${i}" ${P.lessons.has(i) ? "checked" : ""}></td><td class="lv">${sel(`spec.lessons.${i}.level`, x.level, levels(), true, D)}</td><td style="min-width:200px">${sel(`spec.lessons.${i}.subject`, x.subject, subjectNames().filter(n => (subj(n).periods || {})[x.level] || n === x.subject), true, D)}</td><td style="min-width:160px">${sel(`spec.lessons.${i}.block`, x.block, S.spec.blocks.filter(b => !x.level || b.level === x.level).map(b => b.block), true, D)}</td><td style="min-width:120px">${ro(chips(`spec.lessons.${i}.classes`, x.classes, "classes", `data-level="${esc(x.level || "")}"${lk ? ` title="${esc(cpWhy())}"` : ""}`))}</td>${Array.from({ length: NT }, (_, k) => tcell(i, k, x)).join("")}<td class="num">${inp(`spec.lessons.${i}.students`, x.students, "number", 'style="width:60px"')}</td><td class="num">${inp(`spec.lessons.${i}.periods_override`, x.periods_override, "number", 'style="width:60px"')}</td><td class="num">${inp(`spec.lessons.${i}.code_override`, x.code_override, "text", `style="width:70px" ${D}`)}</td>${Number(sc().weeks) === 2 ? `<td><select data-k="spec.lessons.${i}.room_weeks" ${special(x) ? "" : "disabled title=\"Only for a subject with a special room kind, such as a lab (step 3)\""}>${opt("", x.room_weeks || "", "every week")}${opt("Odd", x.room_weeks, "Odd only")}${opt("Even", x.room_weeks, "Even only")}</select></td>` : ""}<td class="calc">${esc(info[i].code)}</td><td class="calc">${info[i].p || ""}</td><td><input id="pat-${i}" data-pat="${i}" value="${esc((x.pattern || []).length ? patText(x.pattern.map(Number)) : x.pattern_text || "")}" placeholder="${esc(info[i].auto)}" title="How the periods split into lessons: 5x3 + 2x2 is five 3-period lessons and two 2-period ones. Empty = the usual split shown in grey." style="width:112px"></td><td>${cpHand(x, i, lk)} ${delBtn("lessons", i, lk && cpWhy())}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="lessons">+ Add teaching group</button></div></div>`;
  },
  map() {   // step 5's department page: the department's teachers as a strip, then its classes and groups by level and subject
    Sync.ensureIds(S.spec);
    const dept = mapDept(), D = sc().departments || [], T = S.spec.teachers, ro = DeptMap.roster(S.spec, dept, M.extra);
    tickedIdx();
    if (M.profile && !DeptMap.prune([M.profile], S.spec).length) M.profile = null;
    const prof = M.profile ? T.findIndex(t => t && t._id === M.profile) : -1;
    const nTick = ro.filter(i => M.ticked.has(T[i]._id)).length, some = nTick > 0 && nTick < ro.length;
    return `<div class="map"><section class="dpstrip card">
      <div class="row"><select id="mDept" title="Department">${D.map(d => opt(d, dept)).join("")}</select><span class="muted small">${ro.length} teacher${ro.length === 1 ? "" : "s"} · ${nTick} ticked</span>
        <button class="small" data-mall title="Tick every teacher here">${some ? "Select all –" : "Select all"}</button><button class="small" data-mnone>Deselect all</button><button class="small" data-munplaced title="Tick the teachers with no lessons yet">No lessons yet</button></div>
      <div class="row" style="margin:8px 0"><input id="mQ" type="search" placeholder="Find a teacher here, or one from another department" value="${esc(M.q)}" class="dpfind">${M.adding ? "" : `<button data-mnew>+ New teacher</button>`}</div>${M.adding ? newTeacherForm(dept) : ""}
      <div id="rbody">${rosterList(dept)}</div>
    </section>${prof >= 0 ? profileView(T[prof], prof) : cardsView(dept)}</div>`;
  },
  groups() {   // step 5's "Groups and bands": a new group and a new band across the top; the filter; then, as two tabs, the single teaching groups and the banded ones
    Sync.ensureIds(S.spec);
    const gf = gfState(), bf = bfState(), tags = (sc().tags || []).map(t => t[0]).filter(t => t && t !== "-");
    const subjAt = lv => subjectNames().filter(n => ((subj(n) || {}).periods || {})[lv]);
    const gSubjects = subjAt(gf.level).filter(n => !gf.tag || (subj(n) || {}).tag === gf.tag), gBands = S.spec.blocks.filter(b => b.level === gf.level).map(b => b.block);
    const bandPicked = gBands.includes(gf.block), code = Groups.codeFor(S.spec, gf.level, gf.subject, bandPicked ? gf.block : "", gf.students, gf.classes);
    const codeLine = !gf.subject ? `<span class="muted small">Pick a subject to see the code.</span>` : code === "Entire Class" ? `<span class="muted small">Whole class: no group code.</span>` : `<span class="small">Code</span> <span class="codeline">${esc(code)}</span>`;
    const bSubjects = subjAt(bf.level).filter(n => !bf.subjects.includes(n)), suggested = Groups.bandName(bf.level, bf.subjects, blockNames());
    const name = bf.touched ? bf.name : suggested, everyone = bf.evTouched ? bf.everyone : !/option|elective/i.test(name);
    const v = gpView();
    return `<div class="gb"><section class="gform card">
      <h3 style="margin:0 0 6px">New teaching group</h3><p class="muted small" style="margin:0 0 8px">A group of a band, or a whole-class lesson with no band. The code forms as you pick.</p>
      <div class="gfields"><label class="f">Level <select id="gfLevel">${levels().map(l => opt(l, gf.level)).join("")}</select></label>
      <label class="f">${tagLabel()} <select id="gfTag">${opt("", gf.tag, "any")}${tags.map(t => opt(t, gf.tag)).join("")}</select></label>
      <label class="f">Subject <select id="gfSubject">${opt("", gf.subject, "")}${gSubjects.map(n => opt(n, gf.subject)).join("")}</select></label>
      <label class="f">Band <select id="gfBlock">${opt("", bandPicked ? gf.block : "", "none: whole class")}${gBands.map(b => opt(b, gf.block)).join("")}</select></label>
      <label class="f wide">Classes ${chips("_gf.classes", gf.classes, "classes", `data-level="${esc(gf.level)}"`)}${bandPicked && !gf.classes.length ? `<span class="muted small">Empty: the band's classes.</span>` : ""}</label>
      <label class="f narrow">Students <input id="gfStudents" type="number" value="${esc(gf.students)}" placeholder="all"></label></div>
      <div class="row" style="margin-top:10px"><button class="primary" data-gfadd>Add</button>${bandPicked ? "" : `<button data-gfeach title="One whole-class row for each class picked, or for every class of the level">Add one per class</button>`}<span>${codeLine}</span></div>
    </section><section class="gform card">
      <h3 style="margin:0 0 6px">New band</h3><p class="muted small" style="margin:0 0 8px">Its groups have lessons at the same time. The name forms from the level and subjects; change it if you like.</p>
      <div class="gfields"><label class="f">Level <select id="bfLevel">${levels().map(l => opt(l, bf.level)).join("")}</select></label>
      <label class="f wide">Subjects <div class="chips" style="cursor:default">${bf.subjects.map(x => `<span class="chip">${esc(x)} <button class="x" data-bfsubject="${esc(x)}" title="Remove ${esc(x)}">✕</button></span>`).join("") || `<span class="muted">none yet</span>`}</div>
        <select id="bfAddSubject"><option value="">add a subject…</option>${bSubjects.map(n => opt(n, "")).join("")}</select></label>
      <label class="f wide">Classes ${chips("_bf.classes", bf.classes, "classes", `data-level="${esc(bf.level)}"`)}</label>
      <label class="f wide">Name <input id="bfName" value="${esc(name)}"></label></div>
      <div class="row" style="margin-top:10px"><button class="primary" data-bfadd>Add band</button><label><input type="checkbox" id="bfEveryone" ${everyone ? "checked" : ""}> Everyone takes one <span class="muted small">(untick for an option or elective band)</span></label></div>
    </section>${barView(v)}${tabsView(v)}${gTab() === "pool" ? poolView(v) : lanesView(v)}</div>`;
  },
  _bands(out, info, crit) {
    const open = S.bandsOpen ?? (!S.spec.blocks.length || Object.keys(out.blocks).length > 0);   // until the committee opens or closes it
    const bt = btState(), nfix = Object.keys(out.blocks).length; if (!nfix) bt.fix = false;
    const ok = (b, i) => (!bt.level || b.level === bt.level) && (!bt.fix || !!out.blocks[i]), shown = S.spec.blocks.filter((b, i) => btShown(b.block, ok(b, i), bt.q)).length;   // a band with no name yet is always shown
    const bar = !S.spec.blocks.length ? "" : `<div class="row btbar"><b>Show</b><label>Level <select id="btLevel">${opt("", bt.level, "All levels")}${levels().map(l => opt(l, bt.level)).join("")}</select></label><label>Name has <input id="btQ" value="${esc(bt.q)}" placeholder="a word of the name"></label>${nfix ? `<label><input type="checkbox" id="btFix" ${bt.fix ? "checked" : ""}> Only the ${nfix} to fix</label>` : ""}<span class="muted small" id="btN">${shown} of ${S.spec.blocks.length} shown</span>${bt.level || bt.q || bt.fix ? `<button class="small" data-btclear>Show all</button>` : ""}</div>`;
    return `<details class="bands" ${open ? "open" : ""}><summary><h2>Bands <span class="muted" style="font-weight:400;font-size:14px">${S.spec.blocks.length} band${S.spec.blocks.length === 1 ? "" : "s"}${Object.keys(out.blocks).length ? ` · ${Object.keys(out.blocks).length} to fix` : ""}</span></h2></summary><p class="muted">A band takes the students of its classes and splits them into groups that all have lessons at the same time (for example, Sec 1 English for 1A–1D split by G3, G2 and G1). Name the band and pick its classes; then add its groups under Teaching groups.</p>${bar}
      <div class="tablewrap"><table><tr><th>Band</th><th>Level</th><th>Classes</th><th>Groups (from Teaching groups)</th><th>Students in groups / classes</th><th title="Every student in its classes takes one of its groups (English, Mother Tongue...). Untick for an option or elective band some students are not in.">Everyone takes one</th><th>Note</th><th></th></tr>
      ${S.spec.blocks.map((b, i) => { const gs = S.spec.lessons.map((x, j) => [x, j]).filter(([x]) => x.block === b.block); const inG = gs.reduce((a, [x]) => a + (Number(x.students) || 0), 0), inC = (b.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
        return `<tr id="blocks-${i}" class="${rowCls(out, crit, "blocks", i)}" data-btname="${esc(String(b.block || "").trim().toLowerCase())}" data-btok="${ok(b, i) ? 1 : 0}" ${btShown(b.block, ok(b, i), bt.q) ? "" : "hidden"}><td style="min-width:200px">${inp(`spec.blocks.${i}.block`, b.block)}</td><td>${sel(`spec.blocks.${i}.level`, b.level, levels())}</td><td style="min-width:180px">${chips(`spec.blocks.${i}.classes`, b.classes, "classes", `data-level="${esc(b.level || "")}"`)}</td><td class="calc" style="white-space:normal">${esc(gs.map(([x, j]) => info[j].code).join(", "))}</td><td class="calc">${inG} / ${inC}</td><td style="text-align:center"><input type="checkbox" data-k="spec.blocks.${i}.everyone" ${everyone(b) ? "checked" : ""}></td><td class="bnote">${area(`spec.blocks.${i}.note`, b.note)}</td><td>${delBtn("blocks", i)}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="blocks">+ Add band</button></div></details>`;
  },
  rules() {
    const { out, crit } = issues(); const RT = S.meta.rule_types || []; const NP = Number(sc().periods_per_day); const P = Array.from({ length: NP }, (_, p) => p);
    const psel = (path, cur) => `<select data-k="${path}">${opt("", cur ?? "", "")}${P.map(p => opt(p, cur, `${p} (${clock(p)})`)).join("")}</select>`;
    const weeks = Number(sc().weeks) === 2 ? ["Both", "Odd", "Even"] : ["Both"], days = ["All", "Mon", "Tue", "Wed", "Thu", "Fri"];
    const where = placeRules(), bad = i => rowCls(out, crit, "rules", i), tip = i => esc((out.rules[i] || []).join(" "));
    const msg = (i, n) => out.rules[i] ? `<tr class="rowmsg ${bad(i)}"><td colspan="${n}">${out.rules[i].map(esc).join("<br>")}</td></tr>` : "";   // what is wrong with the row, under it
    const codes = groupCodes();
    const availRow = (i) => { const r = S.spec.rules[i], [a, b] = ruleTimes(r);
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td style="min-width:180px">${sel(`spec.rules.${i}.target`, r.target, teacherNames())}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td>
        <td><input data-time="${i}|0" type="time" value="${esc(a)}"></td><td><input data-time="${i}|1" type="time" value="${esc(b)}"></td><td class="calc">${r.from === r.to || r.to == null ? `period ${r.from}` : `periods ${r.from}–${r.to}`}</td><td class="note">${area(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>${msg(i, 8)}`; };
    const fixedRow = (i) => { const r = S.spec.rules[i], every = ["Level", "School"].includes(r.scope), lv = every ? (r.scope === "Level" ? r.target : "All") : r.level || clsLevel(r.target);
      const who = [EVERY, ...classNames().filter(c => !lv || lv === "All" || clsLevel(c) === lv), ...codes.filter(c => !lv || lv === "All" || String(lv).slice(-1) === c[0])];
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td><select data-fixlv="${i}">${["All", ...levels()].map(v => opt(v, lv || "All")).join("")}</select></td><td style="min-width:110px"><select data-fixwho="${i}">${opt("", every ? EVERY : r.target, "")}${who.map(v => opt(v, every ? EVERY : r.target)).join("")}${!every && r.target && !who.includes(r.target) ? opt(r.target, r.target, `${r.target} (not on list)`) : ""}</select></td><td style="min-width:180px">${sel(`spec.rules.${i}.subject`, r.subject, subjectNames())}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td><td>${psel(`spec.rules.${i}.from`, r.from)}</td><td class="note">${area(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>${msg(i, 8)}`; };
    const moreRow = (i, tabScopes) => { const r = S.spec.rules[i];
      const subjCell = r.rule === "Only these subjects" ? chips(`spec.rules.${i}.subject`, namesList(r.subject), "subjects") : sel(`spec.rules.${i}.subject`, r.subject, subjectNames());
      const venueCell = r.rule === "Only in venues" ? chips(`spec.rules.${i}.venues`, namesList(r.venues), "rooms") : '<span class="muted small">–</span>';
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td><select data-k="spec.rules.${i}.scope">${opt("", r.scope, "")}${S.meta.scopes.filter(v => tabScopes.includes(v) || v === r.scope).map(v => opt(v, r.scope, v === "Block" ? "Band" : v)).join("")}</select></td><td style="min-width:150px">${sel(`spec.rules.${i}.target`, r.target, targetOptions(r.scope))}</td><td style="min-width:180px">${subjCell}</td><td style="min-width:180px">${sel(`spec.rules.${i}.rule`, r.rule, RT.filter(t => !r.scope || scopesOf(t).includes(r.scope)).map(t => t.rule))}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td><td>${psel(`spec.rules.${i}.from`, r.from)}</td><td>${psel(`spec.rules.${i}.to`, r.to)}</td><td class="num">${usesNumber(r.rule) ? inp(`spec.rules.${i}.number`, r.number, "number", 'style="width:56px"') : '<span class="muted small" title="This rule does not use a number">–</span>'}</td><td style="min-width:120px">${venueCell}</td><td>${sel(`spec.rules.${i}.strength`, r.strength || "Must", ["Must", "Prefer"], false)}</td><td class="note">${area(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>${msg(i, 13)}`; };
    const typedNo = {}; let tn = 0; S.spec.rules.forEach((r, i) => { if (r.rule === "In words") typedNo[i] = ++tn; });
    const typedScopes = scopesOf(RT.find(t => t.rule === "In words") || { scopes: "School, Level, Class, Subject, Room, Teacher" });
    const typedRow = (i, tabScopes) => { const r = S.spec.rules[i];
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td class="calc">T${typedNo[i]}</td><td>${sel(`spec.rules.${i}.strength`, r.strength || "Must", ["Must", "Prefer"], false)}</td><td><select data-k="spec.rules.${i}.scope">${opt("", r.scope, "")}${S.meta.scopes.filter(v => (tabScopes.includes(v) && typedScopes.includes(v)) || v === r.scope).map(v => opt(v, r.scope, v === "Block" ? "Band" : v)).join("")}</select></td><td style="min-width:150px">${sel(`spec.rules.${i}.target`, r.target, targetOptions(r.scope))}</td><td class="words">${area(`spec.rules.${i}.text`, r.text, 'placeholder="What must, or should, happen"')}</td><td>${delBtn("rules", i)}</td></tr>${msg(i, 6)}`; };
    const tab = TABS.find(t => t[0] === R6.tab) || TABS[0], [tid, tlabel, tscopes] = tab;
    const standard = where.more.filter(i => S.spec.rules[i].rule !== "In words"), typed = where.more.filter(i => S.spec.rules[i].rule === "In words");
    const onTab = (ix, id) => ix.filter(i => tabOf(S.spec.rules[i]) === id);
    const count = id => onTab(where.availability, id).length + onTab(where.fixed, id).length + onTab(standard, id).length + onTab(typed, id).length;
    const strip = `<div class="row tabs">${TABS.map(([id, label]) => `<button data-rtab="${id}" class="${id === tid ? "on" : ""}">${label}<span class="n">${count(id) || ""}</span></button>`).join("")}</div>`;
    const first = tscopes[0], add = (k, label, title) => `<button data-add="${k}" data-scope="${esc(first)}"${title ? ` title="${esc(title)}"` : ""}>${label}</button>`;
    const parts = [];
    const av = onTab(where.availability, tid);
    if (tid === "teachers") parts.push(`<h2>Teacher availability</h2><p class="muted">Times a teacher cannot teach (part-time days, a centre or programme after school). Times are clock times; every period they overlap is blocked.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Teacher</th><th>Week</th><th>Day</th><th>From</th><th>To</th><th>Blocks</th><th>Reason</th><th></th></tr>${av.map(availRow).join("")}</table></div>
      <div class="row" style="margin:10px 0 16px"><button data-add="avail">+ Add block-out</button></div>`);
    const fx = onTab(where.fixed, tid);
    if (tid === "school" || tid === "levels") parts.push(`<h2>Fixed lessons</h2><p class="muted">Lessons that must start at a set time (optional): ${tid === "school" ? `<b>${EVERY}</b> with Level <b>All</b>: that subject for the whole school at once, such as CCE` : `a class with a subject, a group code from step 5, or <b>${EVERY}</b>: that subject for every class of the level at once`}. Leave empty to let the timetable place everything.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Level</th><th>Class or group</th><th>Subject</th><th>Week</th><th>Day</th><th>Start period</th><th>Note</th><th></th></tr>${fx.map(fixedRow).join("")}</table></div>
      <div class="row" style="margin:10px 0 16px">${tid === "levels" ? `<button data-add="fixed">+ Add fixed lesson</button>` : `<button data-add="fixedall" title="A subject at one time for every class, such as whole-school CCE. One row per slot: a subject with two lessons a cycle needs two rows.">+ Every class at one time (CCE)</button>`}</div>`);
    const st = onTab(standard, tid);
    parts.push(`<h2>Standard rules</h2><p class="muted">From the list of rule types below. First pick what the rule applies to; the next drop-down lists only those. <b>Must</b> is never broken; <b>Prefer</b> is kept where possible.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Applies to</th><th>Which</th><th>Subject (optional)</th><th>Rule</th><th>Week</th><th>Day</th><th>From</th><th>To</th><th title="A limit, for the rules that have one: Max periods a day, Max periods in a row, At most N at once">Number</th><th title="For Only in venues: the rooms those lessons must use then">Venues</th><th>Must / Prefer</th><th>Note</th><th></th></tr>${st.map(i => moreRow(i, tscopes)).join("")}</table></div>
      <div class="row" style="margin:10px 0 16px">${add("rules", "+ Add rule")}${tid === "school" ? `<button data-add="hbl" title="Only the subjects you tick are taught on that day; every other lesson goes on another day.">+ HBL day</button>` : ""}${tid === "subjects" ? `<button data-add="venuerule" title="Lessons of a subject that run into the times you pick go only in the rooms you pick (PE after 11.00 in the hall or ISH).">+ Lessons late in the day only in some rooms</button>` : ""}</div>`);
    const ty = onTab(typed, tid);
    parts.push(`<h2>Typed rules</h2><p class="muted">Anything the list cannot say, in a sentence. The timetable scripts do not enforce it: the agent honours a <b>Must</b>, tries a <b>Prefer</b>, and reports how each was met.</p>
      <div class="tablewrap"><table class="ruletable typed"><tr><th></th><th>Must / Prefer</th><th>Applies to</th><th>Which</th><th>In words</th><th></th></tr>${ty.map(i => typedRow(i, tscopes)).join("") || `<tr><td colspan="6" class="muted small">None yet.</td></tr>`}</table></div>
      <div class="row" style="margin:10px 0 4px">${add("typed", "+ Typed rule")}</div>
      <details style="margin-top:12px"><summary class="muted">Rule types for this tab</summary><div class="tablewrap" style="max-height:none"><table><tr><th>Rule</th><th>Applies to</th><th>What it means</th><th>Example</th></tr>${RT.filter(t => scopesOf(t).some(x => tscopes.includes(x))).map(t => `<tr><td><b>${esc(t.rule)}</b></td><td>${esc(t.scopes)}</td><td>${esc(t.meaning)}</td><td class="muted">${esc(t.example)}</td></tr>`).join("")}</table></div></details>`);
    const s = sc(); ensureDoubleRow();
    return `<div class="card"><h1>Step 6 · Configuration and constraints</h1><p class="lead">The school-wide settings first, then the constraints under five tabs: what applies to the whole school, to levels and classes, to subjects, to venues, and to teachers.</p>
      <h2>Configuration</h2><p class="muted">School-wide settings. They apply to every class and teacher.</p>
      <div class="grid2">${SET().map(x => `<label class="f">${esc(x.label)} ${x.number
        ? `<input data-set="${x.key}" type="number" min="1" value="${esc(settingValue(x.key))}" placeholder="no limit">`
        : `<select data-set="${x.key}">${["Yes", "No"].map(v => opt(v, settingValue(x.key))).join("")}</select>`}</label>`).join("")}
      ${(s.extra_settings || []).map((x, i) => isRecessRow(x) ? "" : settingRow(x, i)).join("")}</div>
      <div class="row" style="margin-top:12px"><b>${esc(Parents.label(S.spec))} take these lessons</b>${chips("spec.school.parents_subjects", namesList(s.parents_subjects), "subjects")}</div>
      <p class="muted small" style="margin:4px 0 0">They are put on these lessons for every class, all together. You can still change one lesson by hand on step 5.</p></div>
      <div class="card"><h2>Constraints</h2>${strip}${parts.join("")}</div>${giveWay(out, crit, psel, weeks, days)}`;
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
    const { out, crit } = issues(); let n = 0, nc = 0; const nch = (S.spec.choices || []).length, mode = sc().choices_mode === "compare" ? "compare" : "fallback";
    for (const [k, rows] of Object.entries(out)) if (k !== "global" && k !== "students") for (const [i, ms] of Object.entries(rows)) { n++; if (ms.some(m => isCrit(crit, k, i, m))) nc++; }
    return `<div class="card"><h1>Step 7 · Download</h1><p class="lead">Everything an AI agent needs to make the timetable: your setup as a workbook, and the timetable skill. The workbook keeps the drop-downs and formulas, so it can still be edited in Excel.</p>
      <div><span class="stat"><b>${S.spec.classes.length}</b> classes</span><span class="stat"><b>${S.spec.teachers.length}</b> teachers</span><span class="stat"><b>${S.spec.blocks.length}</b> bands</span><span class="stat"><b>${S.spec.lessons.length}</b> lesson rows</span><span class="stat"><b>${S.spec.rules.length}</b> rules</span>${(n => n ? `<span class="stat"><b>${n}</b> typed rule${n === 1 ? "" : "s"} for the agent to honour</span>` : "")(S.spec.rules.filter(r => r.rule === "In words").length)}${nch ? `<span class="stat"><b>${nch}</b> second choice${nch === 1 ? "" : "s"}</span>` : ""}<span class="stat"><b>${S.spec.students.length}</b> students</span></div>
      ${nc ? `<p class="issue crit" style="margin-top:12px">${nc} row${nc === 1 ? " has" : "s have"} a critical problem: no timetable can be made until ${nc === 1 ? "it is" : "they are"} fixed (see the right-hand panel).${n > nc ? ` ${n - nc} more ${n - nc === 1 ? "has" : "have"} only warnings.` : ""}</p>`
        : n ? `<p class="issue soft" style="margin-top:12px">Nothing critical. ${n} row${n === 1 ? " has" : "s have"} warnings for a person to check (see the right-hand panel); a timetable can still be made.</p>` : '<p class="okmsg" style="margin-top:12px">Everything checks out.</p>'}</div>
      <div class="card" id="fitCard" style="margin-top:16px"></div>
      <div class="dl">
        <div class="card"><h2>1 · Configuration workbook</h2><p class="muted">Everything you entered, as the .xlsx template.</p>${nch ? `<div class="cmode"><p style="margin:0 0 4px">If the first choices do not fit:</p>${[["fallback", "Fall back only when needed", "one timetable with as many first choices as possible; the agent gives way down the list and stops at the first that fits."],
          ["compare", "Make one timetable for each", "the first choices, then one more after each step of the list, for the committee to compare (more solving time)."]].map(([v, l, m]) => `<label class="radio"><input type="radio" name="choicesMode" data-k="spec.school.choices_mode" value="${v}"${v === mode ? " checked" : ""}> <b>${l}</b>: <span class="muted">${m}</span></label>`).join("")}</div>` : ""}<button class="primary" id="build">Download workbook (.xlsx)</button></div>
        <div class="card"><h2>2 · The timetable skill</h2><p class="muted">Use the zip when the chatbot can run code: its scripts make a timetable file this app can publish as it is. SKILL.md alone is for a chatbot that cannot run code.</p><div class="row"><a href="/download/skill.zip"><button class="primary">Skill (.zip)</button></a><a href="/download/SKILL.md"><button>SKILL.md only</button></a></div></div>
        <div class="card"><h2>3 · Starter prompt</h2><p class="muted">Paste this into the chatbot with the two files.</p><textarea id="prompt" readonly rows="7">${esc(starterPrompt())}</textarea><div class="row"><button id="copyPrompt">Copy</button></div></div>
        <div class="card"><h2>Keep a copy</h2><p class="muted">The setup as a progress file, to keep or to open on another computer.</p><div class="row"><button id="saveJson" title="Download the setup as a progress file">Save to file</button>${committee() && !S.practice ? `<label class="filebtn" title="Open a progress file: it replaces the school's setup for everyone">Load from file<input type="file" id="loadJson" accept=".json" hidden></label>` : ""}</div>${committee() && !S.practice ? copiesList() : ""}</div>
      </div>
      <div class="card" style="margin-top:16px"><h2>How to make the timetable</h2><ol class="howto">
        <li>In Claude (or another agent that can run Python), add the skill: upload the .zip as a skill, or attach SKILL.md to the conversation.</li>
        <li>Upload your setup workbook and ask: <i>"Generate our timetable from this setup. Report anything that does not fit."</i></li>
        <li>The agent checks the inputs, solves (a few minutes for a typical school), and hands back the timetable file. Bring that file to step 8, Upload and edit.</li>
        <li>Change the setup here or in Excel and ask again: the agent re-solves from the new file.</li></ol></div>
      <div class="card" style="margin-top:16px"><h2>Templates to share</h2><p class="muted">Ready-made workbooks for others to fill in Excel.</p><div class="row"><a href="/download/template/secondary"><button>Sample secondary</button></a><a href="/download/template/primary"><button>Sample primary</button></a><a href="/download/blank/secondary"><button>Blank secondary</button></a><a href="/download/blank/primary"><button>Blank primary</button></a></div></div>`;
  },
  edit() {
    if (S.practice) return `<div class="card"><h1>Step 8 · Upload and edit</h1><p class="lead">Uploading a timetable is off in a practice copy.</p></div>`;
    return `<div class="card"><h1>Step 8 · Upload and edit</h1><p class="lead">Bring back the timetable the AI agent made and check it. Change it here until it is right, then publish it on step 9. Nothing is visible to teachers or students until you publish.</p></div>
      ${exportCard()}${S.board ? `<div class="card" id="bdBox">${bdHTML()}</div>` : ""}`;
  },
  publish() {
    if (S.practice) return `<div class="card"><h1>Step 9 · Publish</h1><p class="lead">Publishing is off in a practice copy.</p></div>`;
    return `<div class="card"><h1>Step 9 · Publish</h1><p class="lead">Publish the timetable for teachers and students. Every warning is shown here. A critical mistake has to be settled on step 8 first.</p></div>
      <div class="card" id="pbTimetable" style="margin-top:16px">${publishHTML(S.draft)}</div>${S.draft ? printoutsCard() : ""}<div class="card" id="pubNow" style="margin-top:16px"></div>`;
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
  if (e.target.dataset && e.target.dataset.gtick) { const gp = gpState(); e.target.checked ? gp.ticked.add(e.target.dataset.gtick) : gp.ticked.delete(e.target.dataset.gtick); render(); return; }
  const cc = e.target.closest("[data-ccard]");   // a class card: a click on its face opens it (not on a field or button inside the open one)
  if (cc && !e.target.closest("button, input, select, textarea, label") && Number(cc.dataset.ccard) !== CV.open) { cvOpen(Number(cc.dataset.ccard)); render(); const o = document.getElementById(`classes-${CV.open}`); if (o) o.scrollIntoView({ block: "nearest" }); return; }
  const tc = e.target.closest("[data-tcard]");   // a teacher card: a click on its face opens it (not on a box or button in it)
  if (tc && !e.target.closest("button, input, select, textarea, label") && !tc.classList.contains("open")) { tkOpenCard(Number(tc.dataset.tcard), tc); return; }
  if (bdCellClick(e)) return;
  if (e.target.closest("#pbDownload")) { e.preventDefault(); downloadDraft(); return; }   // fetched, so a refusal is said in words, not shown as a page
  const b = e.target.closest("button, [data-pop], .issue, td.c, [data-mcard]"); if (!b) return;
  if (b.dataset.step) { if (!stepShown(Number(b.dataset.step))) return; S.step = Number(b.dataset.step); G.refetch = onDraftStep(); save(); render(); window.scrollTo(0, 0); return; }
  if (b.id === "undo" || b.id === "redo") { undo(b.id === "undo"); return; }
  if (b.dataset.clear) { setPath(b.dataset.clear, ""); save(); render(); return; }
  if (b.dataset.cpback !== undefined) { const i = Number(b.dataset.cpback), x = S.spec.lessons[i]; if (!x || cpBlock(x)) return; Parents.back(S.spec, i); save(); render(); poll(); return; }
  if (b.dataset.pback) { const n = Parents.handRows(S.spec).length, nm = Parents.label(S.spec); if (!n || !confirm(`Put the ${nm} back on ${n} ${n === 1 ? "lesson" : "lessons"}? The teachers typed on them are replaced.`)) return; Parents.backAll(S.spec); save(); render(); poll(); return; }
  if (b.dataset.pfill) { const n = Parents.fillCount(S.spec), nm = Parents.label(S.spec); if (!n || !confirm(`Give ${n} ${n === 1 ? "class" : "classes"} their ${nm} from the teachers now on their lessons?`)) return; Parents.fill(S.spec); save(); render(); poll(); return; }
  if (b.id === "practiceBack") { leavePractice(); return; }
  if (b.dataset.old) { oldChoice(b.dataset.old); return; }
  if (b.id === "copiesLoad") { try { S.copies = await getJSON("/api/setup/copies"); } catch (err) { toast("Could not load the earlier copies."); return; } render(); return; }
  if (b.dataset.restore) { restoreCopy(b.dataset.restore); return; }
  if (b.dataset.begin) { const [k, w] = b.dataset.begin.split("|"); try { await begin(k, w); } catch (err) { toast("Could not load: " + err.message); } return; }
  if (b.dataset.rtab) { R6.tab = b.dataset.rtab; render(); return; }
  if (b.dataset.sview) { SV.view = b.dataset.sview === "table" ? "table" : "cards"; try { localStorage.setItem(SUBJECTVIEW, SV.view); } catch (e) { } render(); return; }
  if (b.dataset.tview) { TV.view = b.dataset.tview === "table" ? "table" : "cards"; tkOpen(null); try { localStorage.setItem(TEACHERVIEW, TV.view); } catch (e) { } render(); return; }
  if (b.dataset.topen !== undefined) { const ti = Number(b.dataset.topen), c = b.closest("[data-tcard]"); if (!S.spec.teachers[ti]) return; tkOpenCard(ti, c); return; }
  if (b.dataset.tclose !== undefined) { const ti = TV.open, col = TV.col; tkOpen(null); render(); const c = ti !== null && [...document.querySelectorAll(`[data-tcard="${ti}"]`)].find(x => { try { return decodeURIComponent(x.dataset.tcol) === col; } catch (e) { return false; } }), t = c && c.querySelector("[data-topen]"); if (t) t.focus({ preventScroll: true }); return; }
  if (b.dataset.tsecond !== undefined) { if (tkHead()) return; tkSecond(Number(b.dataset.tsecond), ""); return; }
  if (b.dataset.vview) { VV.view = b.dataset.vview === "table" ? "table" : "blocks"; VV.open = null; VV.openId = null; try { localStorage.setItem(VENUEVIEW, VV.view); } catch (e) { } render(); return; }
  if (b.dataset.vroom !== undefined) { const vi = Number(b.dataset.vroom); if (!S.spec.venues[vi]) return; const was = VV.open === vi; vvOpen(was ? null : vi); render();
    if (was) { const t = document.querySelector(`[data-vroom="${vi}"]`); if (t) t.focus({ preventScroll: true }); }
    else { const o = document.getElementById(`venues-${vi}`); if (o) { o.scrollIntoView({ block: "nearest" }); const f = o.querySelector("input:not(:disabled), select:not(:disabled)") || o.querySelector("[data-vclose]"); if (f) f.focus({ preventScroll: true }); } }
    return; }
  if (b.dataset.vclose !== undefined) { const vi = VV.open; vvOpen(null); render(); const t = vi !== null && document.querySelector(`[data-vroom="${vi}"]`); if (t) t.focus({ preventScroll: true }); return; }
  if (b.dataset.vdraftx !== undefined) { VV.draft = null; render(); return; }
  if (b.dataset.vmove !== undefined) { vvMove(); return; }
  if (b.dataset.vuntick !== undefined) { vvTicks().clear(); render(); return; }
  if (b.dataset.vtickall !== undefined) { const t = vvTicks(), ids = b.dataset.vtickall.split(",").map(i => (S.spec.venues[Number(i)] || {})._id).filter(Boolean), all = ids.every(id => t.has(id)); ids.forEach(id => all ? t.delete(id) : t.add(id)); render(); return; }
  if (b.dataset.vmvpick !== undefined) { const mv = vvMv(); if (b.dataset.vmvpick === "block") { mv.nb = false; mv.nf = false; } else mv.nf = false; render(); return; }
  if (b.dataset.vtypex !== undefined) { VV.typing = null; render(); return; }
  if (b.dataset.vadd !== undefined) { if (locked("venues")) return; const [bk, fl] = b.dataset.vadd.split("|").map(decodeURIComponent); vvAddRoom(bk, fl); return; }
  if (b.dataset.vfloor !== undefined) { if (locked("venues")) return; vvAddRoom(b.dataset.vfloor, VenueView.nextFloor(S.spec, b.dataset.vfloor)); return; }
  if (b.dataset.vblock !== undefined) { if (locked("venues")) return; VV.draft = { what: "block", text: "" }; render(); const i = $("#vvBlockName"); if (i) i.focus(); return; }
  if (b.dataset.vblockadd !== undefined) { if (locked("venues")) return; vvAddBlock(); return; }
  if (b.dataset.vkindadd !== undefined) { if (locked("venues")) return; vvAddKind(Number(b.dataset.vkindadd)); return; }
  if (b.dataset.sadd !== undefined) { if (locked("subjects")) return; sjAdd(decodeURIComponent(b.dataset.sadd)); return; }
  if (b.dataset.sremove !== undefined) { if (locked("subjects")) return; sjRemove(b); return; }
  if (b.dataset.cview) { CV.view = ["cards", "bands", "table"].includes(b.dataset.cview) ? b.dataset.cview : "cards"; cvOpen(null); try { localStorage.setItem(CLASSVIEW, CV.view); } catch (e) { } render(); return; }
  if (b.dataset.cclose) { cvOpen(null); render(); return; }
  if (b.dataset.cband !== undefined) { openBand(b.dataset.cband); return; }
  if (b.dataset.cbands !== undefined) { openBands(b.dataset.cbands); return; }
  if (b.dataset.btclear !== undefined) { M.bt = null; render(); return; }
  if (b.dataset.cadd) { addRow("classes"); cvOpen(S.spec.classes.length - 1); render(); const o = document.getElementById(`classes-${CV.open}`); if (o) o.scrollIntoView({ block: "center" }); return; }
  if (b.dataset.add) { addRow(b.dataset.add, b.dataset.scope); return; }
  if (b.dataset.del) { const [k, i] = b.dataset.del.split("."); if (k === "teachers" && TV.open !== null) { if (TV.open === Number(i)) tkOpen(null); else if (TV.open > Number(i) && !TV.openId) TV.open--; } S.spec[k].splice(Number(i), 1); if (k === "classes") cvOpen(null); if (k === "venues") vvOpen(null); if (k === "rules") Choices.prune(S.spec); unpick(); save(); render(); return; }   // a choice on a deleted rule goes with it
  if (b.dataset.cmove) { const [i, d] = b.dataset.cmove.split("|").map(Number); if (!Choices.move(S.spec, i, d)) return; save(); render(); const nb = $(`[data-cmove="${i}|${d}"]`); if (nb && !nb.disabled) nb.focus({ preventScroll: true }); return; }
  if (b.dataset.cfopen) { Object.assign(CF, { open: true, kind: "setting", key: "", rule: "", level: "", second: "", fallback: "", from: "", to: "" }); render(); return; }
  if (b.dataset.cfcancel) { CF.open = false; render(); return; }
  if (b.dataset.cfadd) { cfAdd(); return; }
  if (b.dataset.helper) { helper(b.dataset.helper); return; }
  if (b.dataset.avatar) { const t = S.spec.teachers[Number(b.dataset.avatar)]; if (t) { t.avatar = (Number(t.avatar) || 0) + 1; save(); render(); } return; }
  if (b.dataset.brush !== undefined) { S.brush = b.dataset.brush; render(); return; }
  if (b.dataset.copyday) { const lv = b.dataset.copyday; const ds = S.spec.day_structure[lv]; const f = ds[dayNames()[0]]; dayNames().forEach(d => ds[d] = f); save(); render(); return; }
  if (b.dataset.copylevel) { const src = S.spec.day_structure[b.dataset.copylevel]; levels().forEach(l => S.spec.day_structure[l] = { ...src }); save(); render(); return; }
  for (const k of ["mview", "mall", "mnone", "munplaced", "madd", "mnew", "mnewcancel", "mnewgo"]) if (b.dataset[k] !== undefined) { mapAction(k, b.dataset[k]); return; }
  if ((b.dataset.gdel !== undefined || b.dataset.gtx !== undefined) && e.detail > 1) return;   // the second click of a double click would delete the row that moved up under the pointer
  for (const k of ["gfadd", "gfeach", "bfadd", "bfsubject", "gall", "gnone", "gclear", "gmove", "gout", "gdel", "gtab", "gbdel", "gbyes", "gbno", "gbname", "gbsave", "gbcancel", "gtx"]) if (b.dataset[k] !== undefined) { groupsAction(k, b.dataset[k]); return; }
  if (b.dataset.mprofile) { M.profile = b.dataset.mprofile; render(); return; }
  if (b.dataset.mclose !== undefined) { M.profile = null; render(); return; }
  if (b.dataset.mx) { const [li, cls, ...nm] = b.dataset.mx.split("|"); cardRemove(`${li}|${cls}`, nm.join("|")); return; }
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
    if (/^teachers-/.test(b.dataset.row)) S.tf = { dept: "", q: "" };
    if (!stepShown(Number(b.dataset.go))) return;
    S.step = Number(b.dataset.go);
    const ck = /^classes-(\d+)$/.exec(b.dataset.row);
    if (ck && S.spec.classes[Number(ck[1])]) {   // a class: its card opens, on Cards, so its messages show (Bands switches to Cards first)
      if (CV.view === "bands") { CV.view = "cards"; try { localStorage.setItem(CLASSVIEW, CV.view); } catch (e) { } }
      if (CV.view === "cards") cvOpen(Number(ck[1]));
    }
    const tk = /^teachers-(\d+)$/.exec(b.dataset.row);
    if (tk && TV.view === "cards" && S.spec.teachers[Number(tk[1])]) tkOpen(Number(tk[1]), People.depts(S.spec.teachers[Number(tk[1])])[0] || "");   // a teacher: their card opens in their home column, so its messages show
    const vk = /^venues-(\d+)$/.exec(b.dataset.row);
    if (vk && VV.view === "blocks" && S.spec.venues[Number(vk[1])]) vvOpen(Number(vk[1]));   // a room: its box opens, on Blocks, so its messages show (the Table stays as it is)
    render(); const r = document.getElementById(b.dataset.row); if (r) r.scrollIntoView({ block: "center" }); return; }
  if (b.id === "build") { buildXlsx(); return; }
  if (b.id === "fitAgain") { fitCheck(true); return; }
  if (b.id === "pbPrint") { makePrintouts(); return; }
  if (b.dataset.pbshow !== undefined || b.dataset.pbfind !== undefined) {   // step 8 with the warning in the side panel's Warnings, marked and in view, and its card selected when the board has it; a lesson not placed is selected in the Not placed tab instead
    const key = b.dataset.pbshow !== undefined ? b.dataset.pbshow : b.dataset.pbfind, w = ((S.draft && S.draft.warnings) || []).find(x => x.key === key);
    const id = w && w.crit === "notplaced" && w.where && w.where.id !== null && w.where.id !== undefined ? Number(w.where.id) : NaN;
    S.step = stepAt("edit"); G.refetch = true; if (w && !Draft.isOpen(w)) S.dfilter = "all"; else if (S.dfilter !== "all") S.dfilter = "open"; save(); render(); window.scrollTo(0, 0);
    if (!S.board) return;
    if (Number.isFinite(id)) bdShowTray(id); else bdShowWarning(key, true);
    return;
  }
  if (b.id === "imCheck") { uploadDraft(false); return; }
  if (b.id === "pbPublish") { if (!confirm("Publish this timetable? Teachers and students will see it straight away, in place of what they see now.")) return; publishDraft(); return; }
  if (bdClick(b)) return;
  if (fxClick(b)) return;
  if (b.dataset.decide) { const i = b.dataset.decide.indexOf("|"); decide(b.dataset.decide.slice(0, i), b.dataset.decide.slice(i + 1)); return; }
  if (b.id === "copyPrompt") { const ta = $("#prompt"); const done = () => toast("Copied."); if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(ta.value).then(done, () => { ta.select(); document.execCommand("copy"); done(); }); else { ta.select(); document.execCommand("copy"); done(); } return; }
  if (b.id === "saveJson") { if (!S.spec) { toast("Open or start a setup first."); return; } const blob = new Blob([JSON.stringify(S.spec, null, 1)], { type: "application/json" }); dl(blob, `${sc().name || "timetable"}_setup.json`); return; }
});
document.addEventListener("toggle", e => { if (e.target.classList && e.target.classList.contains("bands")) S.bandsOpen = e.target.open; }, true);
document.addEventListener("keydown", e => {   // ⌘Z / Ctrl+Z undo, ⇧⌘Z / Ctrl+Y redo; inside a text box the browser's own undo applies. On step 8, with the board there, the keys are the timetable's: Z undoes its last change, redo does nothing
  if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
  const k = (e.key || "").toLowerCase(); if (k !== "z" && k !== "y") return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable]")) return;
  e.preventDefault();
  if (S.board) { if (k === "z" && !e.shiftKey) bdUndo(); return; }
  undo(k === "z" && !e.shiftKey);
});
document.addEventListener("input", e => { if (VV.draft && (e.target.id === "vvKindName" || e.target.id === "vvBlockName")) VV.draft.text = e.target.value; });
document.addEventListener("keydown", e => {   // step 1, Blocks: Enter in a small name box adds; Escape drops the box, or closes the open room
  if (e.isComposing || S.asking || !S.spec || !STEPS[S.step] || STEPS[S.step][0] !== "venues" || VV.view !== "blocks") return;
  if (e.key === "Enter" && (e.target.id === "vvMvBlock" || e.target.id === "vvMvFloor")) { e.preventDefault(); vvMove(); return; }
  if (e.key === "Escape" && (e.target.id === "vvMvBlock" || e.target.id === "vvMvFloor")) { e.preventDefault(); const mv = vvMv(); if (e.target.id === "vvMvBlock") { mv.nb = false; mv.nf = false; } else if (!mv.nb) mv.nf = false; render(); return; }   // back to the lists; the open room stays open
  if (e.key === "Enter" && e.target.id === "vvType") { e.preventDefault(); e.target.blur(); return; }
  if (e.key === "Escape" && e.target.id === "vvType") { e.preventDefault(); VV.typing = null; render(); return; }
  if (e.key === "Enter" && (e.target.id === "vvKindName" || e.target.id === "vvBlockName")) { e.preventDefault(); const b = document.querySelector(e.target.id === "vvKindName" ? "[data-vkindadd]" : "[data-vblockadd]"); if (b) b.click(); return; }
  if (e.key !== "Escape" || (VV.open === null && !VV.draft)) return;
  e.preventDefault(); const a = document.activeElement; if (a && a.blur && $("#main").contains(a)) a.blur();   // a box being typed in keeps what was typed first
  if (VV.draft) { VV.draft = null; render(); return; }
  const vi = VV.open; vvOpen(null); render(); const t = document.querySelector(`[data-vroom="${vi}"]`); if (t) t.focus({ preventScroll: true });
});
document.addEventListener("keydown", e => { if (e.key === "Enter" && !e.isComposing && e.target.id === "fxAskIn") { e.preventDefault(); if (!e.shiftKey) fxAsk(); } });   // Enter in the typed-request box asks; nothing while a request is out (fxAsk)
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
  if (el.dataset.cf) {   // the + Add a second choice form (not saved): a new kind starts afresh; a Yes/No setting offers the other value
    const f = el.dataset.cf; CF[f] = el.value;
    if (f === "kind") Object.assign(CF, { key: "", rule: "", level: "", second: "", fallback: "", from: "", to: "" });
    if (f === "key") { const st = SET().find(x => x.key === el.value); CF.second = st && !st.number ? (Choices.settingValue(S.spec, SET(), st.key) === "Yes" ? "No" : "Yes") : ""; }
    if (el.tagName === "SELECT") render(); return; }
  if (["pickA", "pickP"].includes(el.id)) { S.pick[el.id.slice(4).toLowerCase()] = el.value; return; }   // typed boxes: no redraw, or it would swallow the click on the button next to them
  if (["pickT", "pickG", "pickC", "pickD", "pickR"].includes(el.id)) { S.pick[el.id.slice(4).toLowerCase()] = el.value; render(); return; }
  if (el.id === "cvLevel") { CV.level = el.value; render(); return; }
  if (el.id === "mLevel") { M.level = el.value; render(); return; }
  if (el.id === "gpLevel") { const gp = gpState(); gp.level = el.value; gp.ticked.clear(); M.gpTo = ""; render(); return; }   // the subject and the teacher stay while they are on offer at the new level
  if (el.id === "gpTeacher") { gpState().teacher = el.value; render(); return; }
  if (el.id === "gpDept") { gpState().dept = el.value; M.gask = null; render(); return; }   // a subject or a teacher outside the department is dropped by the view
  if (el.id === "btLevel") { btState().level = el.value; render(); return; }
  if (el.id === "btFix") { btState().fix = el.checked; render(); return; }
  if (el.id === "btQ") { btState().q = el.value; render(); return; }   // Enter or leaving the box: drawn again, so "Show all" appears
  if (el.id === "gpBand") { gpState().band = el.value; if (el.value) M.gtab = "bands"; M.gask = null; render(); return; }   // one band alone: shown at once
  if (el.id === "gpSubject") { gpState().subject = el.value; render(); return; }
  if (el.id === "gpTo") { M.gpTo = el.value; render(); return; }
  if (el.id === "gfLevel") { const gf = gfState(); gf.level = el.value; gf.subject = ""; gf.block = ""; gf.classes = []; render(); return; }
  if (el.id === "gfTag") { const gf = gfState(); gf.tag = el.value; if (gf.subject && el.value && (subj(gf.subject) || {}).tag !== el.value) gf.subject = ""; render(); return; }
  if (el.id === "gfSubject" || el.id === "gfBlock") { gfState()[el.id === "gfSubject" ? "subject" : "block"] = el.value; render(); return; }
  if (el.id === "bfLevel") { M.bf = null; bfState().level = el.value; M.bf.classes = classesAt(el.value); render(); return; }
  if (el.id === "bfAddSubject") { if (el.value) bfState().subjects.push(el.value); render(); return; }
  if (el.id === "bfEveryone") { const bf = bfState(); bf.everyone = el.checked; bf.evTouched = true; return; }
  if (el.id === "mDept") { M.dept = el.value; M.extra = []; M.ticked.clear(); M.q = ""; M.adding = false; M.nf = null; render(); return; }
  if (["mnDept", "mnRole"].includes(el.id) && M.nf) { M.nf[el.id === "mnDept" ? "dept" : "role"] = el.value; render(); return; }
  if (["tfDept", "tfQ"].includes(el.id)) { S.tf[{ tfDept: "dept", tfQ: "q" }[el.id]] = el.value; render(); return; }
  if (el.dataset.pick || el.dataset.pickall) return;
  if (el.dataset.pat !== undefined) { if (setPattern(S.spec.lessons[Number(el.dataset.pat)], el.value)) { save(); render(); } else { const x = S.spec.lessons[Number(el.dataset.pat)]; el.value = (x.pattern || []).length ? patText(x.pattern.map(Number)) : ""; el.focus(); } return; }
  if (el.dataset.set) { setSetting(el.dataset.set, el.value); save(); render(); return; }
  if (el.dataset.pmax !== undefined) { const msg = Parents.setMax(S.spec, el.value); if (msg) toast(msg); save(); render(); poll(); return; }   // a refusal leaves the old number, redrawn
  if (el.dataset.parent) {   // a Class Parents box: all of that class's boxes make its list (setPath would throw on a class with no list)
    const i = Number(el.dataset.parent.split("|")[0]);
    Parents.setParents(S.spec, i, [...el.closest("[data-parents]").querySelectorAll("[data-parent]")].map(x => x.value)); save(); render(); poll(); return; }
  if (el.dataset.time) {   // a block-out's clock time: keep the times and block every period they overlap
    const [i, k] = el.dataset.time.split("|").map(Number), r = S.spec.rules[i];
    r.times = [...ruleTimes(r)]; r.times[k] = el.value; [r.from, r.to] = periodsBetween(r.times[0], r.times[1]); save(); render(); return; }
  if (el.dataset.fixlv !== undefined || el.dataset.fixwho !== undefined) {   // Fixed lessons: level and class (or Every class) decide what the rule applies to
    const tr = el.closest("tr"), r = S.spec.rules[Number(el.dataset.fixlv ?? el.dataset.fixwho)];
    setFixedWho(r, tr.querySelector("[data-fixlv]").value, tr.querySelector("[data-fixwho]").value); save(); render(); return;
  }
  if (el.dataset.vtick !== undefined) { const t = vvTicks(); el.checked ? t.add(el.dataset.vtick) : t.delete(el.dataset.vtick); render(); return; }
  if (el.id === "vvMvBlockSel") { const mv = vvMv(); if (el.value === VNEW) { Object.assign(mv, { nb: true, nf: true, bt: "", ft: "" }); render(); const i = $("#vvMvBlock"); if (i) i.focus(); return; }   // a new block has no floors to pick: its floor is typed too
    mv.block = el.value; mv.floor = ""; render(); return; }
  if (el.id === "vvMvFloorSel") { const mv = vvMv(); if (el.value === VNEW) { mv.nf = true; mv.ft = ""; render(); const i = $("#vvMvFloor"); if (i) i.focus(); return; } mv.floor = el.value; render(); return; }
  if (el.id === "vvMvBlock" || el.id === "vvMvFloor") return;   // kept as typed (the input handler); Move reads them
  if (el.dataset.vplace !== undefined || el.dataset.vtype !== undefined) {   // the open room's Block or Floor: one from the list, "New …" (a box to type it), or the typed one
    const [vi, field] = (el.dataset.vplace || el.dataset.vtype).split("|"), v = S.spec.venues[Number(vi)]; if (!v || !["building", "floor"].includes(field) || locked("venues")) return;
    if (el.dataset.vplace !== undefined && el.value === VNEW) { VV.typing = field; render(); const i = $("#vvType"); if (i) { i.focus(); i.select(); } return; }
    const val = el.value.trim(); if (val === "") delete v[field]; else v[field] = val; VV.typing = null; save(); render(); return; }
  if (el.dataset.vkind !== undefined) {   // the open room's Kind box: a kind, or "New kind…" (a small box for its name)
    const v = S.spec.venues[Number(el.dataset.vkind)]; if (!v || locked("venues")) return;
    if (el.value === VNEWKIND) { VV.draft = { what: "kind", text: "" }; render(); const i = $("#vvKindName"); if (i) i.focus(); return; }
    v.kind = el.value === "" ? null : el.value; save(); render(); return; }
  if (el.dataset.sname !== undefined || el.dataset.sset !== undefined || el.dataset.stick !== undefined) {   // a box on a subject card (step 3)
    if (locked("subjects") || !el.closest("[data-scard]")) return;
    if (el.dataset.sname !== undefined) sjName(e); else if (el.dataset.sset !== undefined) sjSet(e); else sjTick(e);
    return; }
  const path = el.dataset.k; if (!path) return;
  if (path.startsWith("_h")) { hwHint(); return; }   // a list on an "Add …" bar (kind, level, department, band, subject): the bar's own, read when Add is pressed. It used to be saved as a stray value and the page drawn again, which put every box of the bar back to its default
  if (path === "spec.school.parents_name") { const t = el.value.trim(); if (t) sc().parents_name = t; else delete sc().parents_name; save(); render(); poll(); return; }   // an empty box takes the key away
  const tkp = /^spec\.teachers\.(\d+)\.(dept2?)$/.exec(path);
  if (tkp && tkp[2] === "dept2") { tkSecond(Number(tkp[1]), el.value); return; }   // the Second department box: as a dropped chip is
  if (el.type === "checkbox") { setPath(path, el.checked); save(); render(); return; }
  let v = el.value; if (el.type === "number") v = v === "" ? null : Number(v); if (v === "") v = null;
  if (/\.(from|to)$/.test(path) && v !== null) v = Number(v);
  if (/^spec\.school\.(weeks|periods_per_day|period_minutes|lesson_length)$/.test(path)) v = Number(v);
  if (/^spec\.choices\.\d+\.second$/.test(path) && v === null) v = "no limit";   // a number setting's second choice left blank
  setPath(path, v);
  if (tkp && !tkHead() && S.spec.teachers[Number(tkp[1])]) TeacherView.tidy(S.spec.teachers[Number(tkp[1])]);   // a home department now equal to the second takes the second off, in the same save
  const cfb = path.match(/^spec\.choices\.(\d+)\.fallback$/); if (cfb) Choices.setFallback(S.spec, Number(cfb[1]), v);
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
  if (/^spec\.venues\.\d+\.(building|floor)$/.test(path) && VV.view === "blocks" && VV.open !== null) { const o = document.getElementById(`venues-${VV.open}`); if (o) o.scrollIntoView({ block: "nearest" }); }   // the room moved to its new place and stays open
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
function addRow(k, scope) {   // scope: a preset for a rule added from a tab of step 6
  const lv = levels()[0];
  const blank = { venues: { room: "", kind: "classroom", capacity: 40 }, classes: { class: "", level: lv, size: 38, home_room: null },
    subjects: { subject: "", code: "", tag: "-", dept: (sc().departments || [])[0], periods: {} }, teachers: { name: "", short: "", dept: (sc().departments || [])[0], allowance: sc().type === "primary" ? 36 : 64, provisional: isHead() && !S.practice ? "Yes" : "No" },
    blocks: { block: "", level: lv, classes: [] }, lessons: { level: lv, subject: null, block: null, classes: [], teachers: [], students: null },
    rules: { scope: "Level", target: null, rule: "Not in periods", week: "Both", day: "All", strength: "Must" },
    typed: { scope: "School", target: null, rule: "In words", text: "", strength: "Must", week: "Both", day: "All" },
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
  const into = { avail: "rules", fixed: "rules", fixedall: "rules", hbl: "rules", venuerule: "rules", typed: "rules" }[k] || k; S.spec[into] = S.spec[into] || [];
  const row = JSON.parse(JSON.stringify(blank)); if (scope && (k === "rules" || k === "typed")) { row.scope = scope; row.target = scope === "School" ? "Whole school" : null;
    if (k === "rules") { const rt = (S.meta.rule_types || []).find(t => !["In words", "Fixed at"].includes(t.rule) && scopesOf(t).includes(scope)); if (rt) row.rule = rt.rule; } }   // a rule that applies to the tab's scope (a fixed lesson has its own button)
  S.spec[into].push(row); save();
  const show = () => { const last = document.getElementById(`${into}-${S.spec[into].length - 1}`); if (last) { last.scrollIntoView({ block: "center" }); const f = last.querySelector("input,select"); if (f) f.focus({ preventScroll: true }); } };
  if (k === "teachers" && TV.view === "cards") {   // on Cards the new teacher's card opens in its home column, with the cursor in Name (the Show bar's filter and search clear first, as a Things to fix click does)
    const ti = S.spec.teachers.length - 1; S.tf = { dept: "", q: "" }; tkOpen(ti, People.depts(row)[0] || ""); render();
    const o = document.getElementById(`teachers-${ti}`);
    if (o) { o.scrollIntoView({ block: "nearest" }); const f = o.querySelector(`[data-k="spec.teachers.${ti}.name"]`); if (f) f.focus({ preventScroll: true }); }
    poll(); return;
  }
  render(); show(); poll();
}
/* a teaching group with no band and fewer students than its classes (a pull-out group, say 9 of 1A2) is a group of its
   own, not the whole class: it gets a code in Keep code, made like a band group's (level digit, subject code, level
   letter, then the first unused number), so the solver, the workbook and the student list all see it as a group */
function groupCode(i) {   // a pull-out group gets a kept code (Groups.pullOutCode); said once here
  const code = Groups.pullOutCode(S.spec, i); if (!code) return;
  const x = S.spec.lessons[i], size = (x.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
  toast(`${x.subject} for ${x.students} of the ${size} students in ${(x.classes || []).join(", ")} is a group of its own, so it gets code ${code} (Keep code). If the rest of the class has this subject at the same time, put it in their band instead.`);
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
  if (k === "venues") {
    const r = VenueView.newRooms(S.spec, $("#hvPre").value, $("#hvFrom").value, $("#hvTo").value), kind = $("#hvKind").value || null;
    if (r.error) { toast(r.error); return; }
    if (!r.names.length) { toast(r.skipped === 1 ? "That room is there already." : "Those rooms are there already."); return; }
    const first = S.spec.venues.length, n = r.names.length, blocks = VV.view === "blocks";
    r.names.forEach(room => S.spec.venues.push({ room, kind, capacity: 40 })); Sync.ensureIds(S.spec);
    if (blocks) { const t = vvTicks(); S.spec.venues.slice(first).forEach(v => t.add(v._id)); }   // ticked, so the bar can put them in a block and floor at once
    save(); render(); const el = document.getElementById(`venues-${first}`); if (el) el.scrollIntoView({ block: "center" });
    toast(`${n} room${n === 1 ? "" : "s"} added${r.skipped ? ` (${r.skipped} there already ${r.skipped === 1 ? "was" : "were"} left)` : ""}.${blocks ? ` ${n === 1 ? "It is" : "They are"} under No block yet, ticked: pick a block and a floor on the bar to place ${n === 1 ? "it" : "them"}.` : ""}`); return;
  }
  if (k === "classes") {
    const lv = $("#hcLevel").value, size = Number($("#hcSize").value) || 38; const used = new Set(S.spec.classes.map(c => c.home_room)); const free = S.spec.venues.filter(v => (v.kind || "classroom") === "classroom" && !used.has(v.room)).map(v => v.room);
    $("#hcNames").value.split(",").map(s => s.trim()).filter(Boolean).forEach(n => S.spec.classes.push({ class: `${String(lv).slice(-1)}${n}`, level: lv, size, home_room: free.shift() || null }));
    $("#hcNames").value = "";   // added: the bar keeps its other boxes, not the names
  }
  if (k === "teachers") { const dept = $("#htDept").value, allow = Number($("#htAllow").value) || null; $("#htNames").value.split("\n").map(s => s.trim()).filter(Boolean).forEach(n => S.spec.teachers.push({ name: n, short: n.split(" ")[0], dept, allowance: allow, provisional: isHead() && !S.practice ? "Yes" : "No" })); $("#htNames").value = ""; }
  if (k === "groups") { const b = S.spec.blocks.find(x => x.block === $("#hbBlock").value), s = $("#hbSubj").value, n = Number($("#hbN").value) || 1, st = Number($("#hbSt").value) || null; if (!b || !s) { toast("Pick a band and a subject."); return; } for (let i = 0; i < n; i++) S.spec.lessons.push({ level: b.level, subject: s, block: b.block, classes: [...(b.classes || [])], teachers: [], students: st }); }
  if (k === "whole") {
    const lv = $("#hwLevel").value, s = $("#hwSubj").value, typed = $("#hwPat").value.trim(); if (!s) { toast("Pick a subject."); return; }
    let pat = null;   // the Lessons box: the same split for every row added; empty leaves each row on the usual split
    if (typed) {
      pat = parsePattern(typed); if (!pat) { toast(`Could not read "${typed}". Write lessons like 5x3 + 2x2: how many, x, how many periods each.`); return; }
      const { p } = wholeAuto(lv, s), t = pat.reduce((a, b) => a + b, 0); if (p && t !== p) { toast(`Lessons ${patText(pat)} add up to ${t} periods, but ${s} has ${p} at ${lv} (step 3). Nothing was added.`); return; }
    }
    S.spec.classes.filter(c => c.level === lv).forEach(c => S.spec.lessons.push({ level: lv, subject: s, block: null, classes: [c.class], teachers: [], students: c.size, ...(pat ? { pattern: [...pat] } : {}) }));
    $("#hwPat").value = "";   // added: the bar keeps its level and subject, not the lessons typed for them
  }
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
  const depts = [...new Set(ix.map(i => (subj(S.spec.lessons[i].subject) || {}).dept || ""))], dept = depts.length === 1 ? depts[0] : "";   // one department only when every ticked row's subject has the same one
  const t = S.spec.teachers.find(x => x.name === P.t); let line = "", over = false;
  if (t) {
    const now = (load[t.name] || 0) + (Number(t.other_duties) || 0), more = ix.filter(i => !(S.spec.lessons[i].teachers || []).includes(t.name)).reduce((a, i) => a + info[i].tp, 0);
    over = t.allowance && now + more > Number(t.allowance);
    line = `${t.name}: ${now}${t.allowance ? ` of ${t.allowance}` : ""} periods now${more ? `, ${now + more} with these` : ""}`;
  }
  const off = t ? "" : "disabled";
  return `<div class="bulk row"><b>${ix.length} ticked</b> teacher <select id="pickT">${opt("", P.t, "pick…")}${teacherOptions(dept, P.t)}</select>
    <button data-bulk="t1" ${off} title="Replaces Teacher 1 on every ticked row">Make Teacher 1</button><button data-bulk="t2" ${off} title="Adds them as a co-teacher, or as Teacher 1 on a row with none">Add as co-teacher</button><button data-bulk="tx" ${off}>Take off</button>
    ${line ? `<span class="small ${over ? "over" : "muted"}">${esc(line)}</span>` : ""}
    <span class="muted">·</span> lessons <input id="pickP" value="${esc(P.p)}" placeholder="5x3 + 2x2" title="Leave empty to go back to the usual split" style="width:104px"><button data-bulk="pat">Set lessons</button><button class="small ghost" data-bulk="tnone">Clear ticks</button></div>`;
}
/* ---------------- step 5: the department map. Teachers are held by _id, so another browser's change cannot move a tick */
const MAPVIEW = "ttsetup.mapview";
const M = { view: "map", dept: "", level: "", ticked: new Set(), lastTick: null, extra: [], q: "", profile: null, adding: false, nf: null };
try { const mv = localStorage.getItem(MAPVIEW); if (["table", "groups"].includes(mv)) M.view = mv; } catch (e) { }
function mapDept() { const D = sc().departments || []; if (!D.includes(M.dept)) M.dept = D[0] || ""; return M.dept; }
function tickedIdx() {   // indexes of the ticked teachers, in setup order, dropping any removed meanwhile
  M.ticked = new Set(DeptMap.prune([...M.ticked], S.spec));
  return S.spec.teachers.map((t, i) => [t, i]).filter(([t]) => t && M.ticked.has(t._id)).map(([, i]) => i);
}
function rosterList(dept) {   // the strip's chips (filtered by the search box) and the teachers found in other departments
  const T = S.spec.teachers, L = DeptMap.loads(S.spec, lessonInfo()), ro = DeptMap.roster(S.spec, dept, M.extra), q = People.key(M.q);
  const shown = ro.filter(i => !q || People.key(T[i].name || "").includes(q) || People.key(T[i].short || "").includes(q));
  const found = DeptMap.search(S.spec, M.q, dept).filter(i => !ro.includes(i));
  const home = t => t.dept && t.dept !== dept ? ` <span class="tag" title="Home department: ${esc(t.dept)}">${esc(t.dept)}</span>` : "";
  const chip = i => { const t = T[i], ld = L[t.name] || {}, pct = ld.allowance ? Math.min(100, Math.round(100 * ld.total / ld.allowance)) : 0;
    return `<div class="dpchip${M.ticked.has(t._id) ? " on" : ""}"><input type="checkbox" data-mtick="${esc(t._id)}" ${M.ticked.has(t._id) ? "checked" : ""} aria-label="Tick ${esc(t.name || "")}">
      <button class="avatar" data-mprofile="${esc(t._id)}" draggable="true" data-mdrag="${esc(t._id)}" title="${esc(t.name || "")}: profile">${avatarOf(t, 32)}</button>
      <div class="dpcn"><div class="dpname" title="${esc(t.name || "")}">${esc(t.name || "")}${home(t)}${provisionalRow(t) ? ` <span class="tag" title="Added by a head, not yet confirmed">provisional</span>` : ""}</div>
      <div class="row small" style="gap:6px;flex-wrap:nowrap">${ld.allowance ? `<div class="load${ld.over ? " over" : ""}" title="${ld.lessons} periods deployed${ld.duties ? ` + ${ld.duties} other duties` : ""}, allowance ${ld.allowance}"><i style="width:${pct}%"></i></div><span class="${ld.over ? "overtxt" : "muted"}">${ld.total} / ${ld.allowance}</span>` : `<span class="muted" title="No allowance yet">${ld.total || 0} periods</span>`}</div></div></div>`; };
  return `<div class="dpchips">${shown.map(chip).join("") || `<p class="muted small">No one here matches.</p>`}</div>
    ${found.length ? `<div class="dpothers"><span class="muted small">Others</span>${found.map(i => `<span class="dpother"><span>${avatarOf(T[i], 24)}</span><span>${esc(T[i].name || "")}${home(T[i])}</span><button class="small" data-madd="${esc(T[i]._id)}" title="Add them to this page to place them. Their departments do not change.">+ Add</button></span>`).join("")}</div>` : ""}`;
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
function cardsView(dept) {   // the department's classes and groups: each level, then each subject, a band as a lane
  const info = lessonInfo(), pg = DeptMap.page(S.spec, info, dept, M.level);
  const tline = (nm, key, lock) => { const t = S.spec.teachers.find(x => x.name === nm);
    return `<div class="dpt">${t ? `<button class="avatar" data-mprofile="${esc(t._id)}" draggable="true" data-mdrag="${esc(t._id)}" title="${esc(nm)}: profile">${avatarOf(t, 24)}</button>` : ""}<span class="dpn" title="${esc(nm)}">${esc(nm)}${t ? "" : " (not on list)"}</span>${lock ? "" : `<button class="dpx" data-mx="${esc(key)}|${esc(nm)}" title="Take ${esc(nm)} off">✕</button>`}</div>`; };
  const card = (c, named) => { const key = c.kind === "class" ? `${c.li}|${c.cls}` : `${c.li}|`, x = S.spec.lessons[c.li], stf = c.kind === "class" && Parents.staffed(S.spec, x), lock = stf && cpBlock(x);
    const room = (stf ? Parents.cap(S.spec) : DeptMap.MAX) - c.teachers.length;
    const pl = n => n === 1 ? "" : "s", fig = `${c.students === null || c.students === undefined ? "" : `${c.students} student${pl(c.students)} · `}${c.periods ? `${c.periods} period${pl(c.periods)}` : "? periods"}`;
    return `<div class="dpcard${lock ? " locked" : ""}" data-mcard="${esc(key)}" title="${esc(lock ? cpWhy() : "Click to place the ticked teachers, or drop teachers here")}"><div><b>${esc(c.title)}</b>${stf ? ` <span class="cpbadge">${esc(Parents.label(S.spec))}</span>` : ""}</div>${named ? `<div class="small">${esc(c.subject)}</div>` : ""}
      <div class="small muted">${fig}</div>${stf ? `<div class="small">${cpHand(x, c.li, lock)}</div>` : ""}
      <div class="dpts">${c.teachers.map(nm => tline(nm, key, lock)).join("")}${room > 0 && !lock ? `<span class="plus" title="Room for ${room} more">+</span>` : ""}</div></div>`; };
  const section = sec => sec.kind === "band"
    ? `<div class="lane dplane"><div class="row small" style="justify-content:space-between"><b>${esc(sec.title)}</b><span class="muted">${sec.groups.length} group${sec.groups.length === 1 ? "" : "s"}</span></div>
      ${sec.twice.map(nm => `<div class="small overtxt">${esc(nm)} is on two groups of this band: a band's groups meet at the same time.</div>`).join("")}<div class="dpgrid">${sec.groups.map(g => card(g, true)).join("")}</div></div>`
    : `<div class="dpsub"><h4>${esc(sec.subject)}</h4><div class="dpgrid">${sec.cards.map(c => card(c, false)).join("")}</div></div>`;
  const body = pg.length ? pg.map(l => `<div class="dplevel"><h3>${esc(l.level || "No level")}</h3>${l.sections.map(section).join("")}</div>`).join("")
    : `<p class="muted small">No lessons for ${esc(dept)}${M.level ? ` at ${esc(M.level)}` : ""} yet. Add them in Groups and bands or the table view.</p>`;
  return `<section class="dpcards card"><div class="row"><select id="mLevel" title="Level">${opt("", M.level, "All levels")}${levels().map(l => opt(l, M.level)).join("")}</select></div>${body}</section>`;
}
function profileView(t, i) {   // a teacher's profile, in place of the cards while open
  const info = lessonInfo(), ld = DeptMap.loads(S.spec, info)[t.name] || {}, key = c => c.kind === "class" ? `${c.li}|${c.cls}` : `${c.li}|`;
  const teaches = [], seen = new Set();
  [...new Set(S.spec.subjects.map(x => x.dept))].forEach(d => ["classes", "groups"].forEach(tab => DeptMap.cards(S.spec, info, d, tab, "").forEach(c => { if (c.teachers.includes(t.name) && !seen.has(key(c))) { seen.add(key(c)); teaches.push(c); } })));
  const mayLook = !isHead() || S.practice || provisionalRow(t);   // the server lets a head change only a provisional teacher's row
  const tRows = teaches.map(c => `<div class="row" style="gap:6px;margin-bottom:4px"><span style="flex:1">${esc(c.title)} · ${esc(c.subject)} · ${c.periods || "?"} periods</span>${c.kind === "class" && cpBlock(S.spec.lessons[c.li]) ? "" : `<button class="small danger" data-mx="${esc(key(c))}|${esc(t.name)}" title="Take ${esc(t.name)} off ${esc(c.title)}">✕</button>`}</div>`).join("") || `<p class="muted small">Not deployed yet.</p>`;
  const fc = Parents.of(S.spec, t.name);   // the classes this teacher is a form teacher of
  return `<section class="cards card profile"><div class="row" style="justify-content:space-between"><h3 style="margin:0">Profile</h3><button class="small ghost" data-mclose>✕ Close</button></div>
    <div class="row" style="align-items:flex-start;margin-top:8px;flex-wrap:nowrap"><div style="text-align:center">${avatarOf(t, 64)}${mayLook ? `<div><button class="small" data-avatar="${i}" title="Another face for this teacher">New look</button></div>` : ""}</div>
    <div style="min-width:0"><div style="font-weight:600">${esc(t.name || "")}</div><div class="muted small">${esc(t.short || "")}${t.role ? ` · ${esc(t.role)}` : ""}${People.depts(t).length ? ` · ${esc(People.depts(t).join(", "))}` : ""}${provisionalRow(t) ? ` <span class="tag">provisional</span>` : ""}</div>
    <div class="small ${ld.over ? "overtxt" : ""}" style="margin-top:4px">${ld.lessons || 0} periods deployed${ld.duties ? ` + ${ld.duties} other duties` : ""}${ld.allowance ? ` = ${ld.total} of ${ld.allowance}` : ""}</div>${fc.length ? `<div class="small" style="margin-top:4px">${esc(Parents.label(S.spec))} of ${esc(fc.join(", "))}</div>` : ""}</div></div>
    <h4>Teaches</h4><div class="keep" style="max-height:40vh;overflow:auto">${tRows}</div>
    <p class="muted small" style="margin:10px 0 0">${isHead() && !S.practice ? "Details are changed by the committee on step 4; a provisional teacher's by you there." : "Details are changed on step 4."}</p></section>`;
}
function cardAt(key) {   // "li|cls" (a class card) or "li|" (a group card)
  const [li, cls] = String(key).split("|"), i = Number(li), x = S.spec.lessons[i]; if (!x) return null;
  return cls ? { kind: "class", li: i, cls, title: cls } : { kind: "group", li: i, title: (lessonInfo()[i] || {}).code };
}
function placeOn(card, idxs) {   // place teachers (ticked, or dropped) on a card, in one save
  if (!card) return;
  if (!idxs.length) { toast("Tick teachers first, then click a card."); return; }
  const x = S.spec.lessons[card.li], stf = card.kind === "class" && Parents.staffed(S.spec, x);
  if (stf && cpBlock(x)) { toast(cpWhy()); return; }
  const r = DeptMap.deploy(S.spec, card, idxs, stf ? { max: Parents.cap(S.spec) } : {});   // a staffed lesson holds the school's most
  if (r.placed.length) { save(); render(); }
  const where = `${card.title} ${x.subject}`, parts = [];
  if (r.placed.length) parts.push(`Placed ${listing(r.placed)} on ${where}.${r.split ? " That class is now a row of its own in the table." : ""}`);
  if (r.already.length) parts.push(`${listing(r.already)} ${r.already.length === 1 ? "was" : "were"} already on ${r.placed.length ? "it" : where}.`);
  if (r.refused.length) parts.push(r.refused[0].why);
  if (parts.length) toast(parts.join(" "));
}
function cardRemove(key, name) {
  const card = cardAt(key); if (!card) return;
  if (card.kind === "class" && cpBlock(S.spec.lessons[card.li])) { toast(cpWhy()); return; }
  if (!DeptMap.undeploy(S.spec, card, name)) return;
  save(); render(); toast(`Took ${name} off ${card.title} ${S.spec.lessons[card.li].subject}.`);
}
function dropIds(e) {   // the teacher indexes a drop carries (ids, as JSON in text/plain)
  let ids = []; try { ids = JSON.parse(e.dataTransfer.getData("text/plain") || "[]"); } catch (err) { }
  if (!Array.isArray(ids) || !S.spec) return [];
  return S.spec.teachers.map((t, i) => [t, i]).filter(([t]) => t && ids.includes(t._id)).map(([, i]) => i);
}
const dropZone = e => { const z = e.target.closest ? e.target.closest("[data-mcard], tr[data-cdrag], [data-cend], [data-tcard]") : null; return z && z.dataset.tcard !== undefined && tkHead() ? null : z; };   // a card takes a department chip, for the committee only
document.addEventListener("dragstart", e => {
  const el = e.target.closest && e.target.closest("[data-mdrag], [data-cdrag], [data-tchip]"); if (!el) return;
  let payload;
  if (el.dataset.tchip !== undefined) { if (tkHead()) { e.preventDefault(); return; } let d = ""; try { d = decodeURIComponent(el.dataset.tchip); } catch (err) { } payload = { dept: d }; }   // a department chip (step 4)
  else if (el.dataset.cdrag !== undefined) payload = { choice: Number(el.dataset.cdrag) };   // a row of the give-way list
  else { const id = el.dataset.mdrag; payload = M.ticked.has(id) ? [...M.ticked] : [id]; }   // a ticked teacher drags every ticked teacher
  e.dataTransfer.setData("text/plain", JSON.stringify(payload)); e.dataTransfer.effectAllowed = "copyMove";
  const m = $(".map"); if (m) m.classList.add("dragging");
});
document.addEventListener("dragend", () => { document.querySelectorAll(".dragging, .over").forEach(x => x.classList.remove("dragging", "over")); });
document.addEventListener("dragover", e => { const z = dropZone(e); if (!z) return; e.preventDefault(); z.classList.add("over"); });
document.addEventListener("dragleave", e => { const z = dropZone(e); if (z && !(e.relatedTarget && z.contains(e.relatedTarget))) z.classList.remove("over"); });
document.addEventListener("drop", e => {
  const z = dropZone(e); if (!z) return; e.preventDefault(); z.classList.remove("over");
  if (z.dataset.cdrag !== undefined || z.dataset.cend !== undefined) {   // the give-way list: before the row dropped on, or last when dropped below the table
    let p = {}; try { p = JSON.parse(e.dataTransfer.getData("text/plain") || "{}"); } catch (err) { }
    if (locked(G.shown) || !p || typeof p.choice !== "number") return;
    if (Choices.moveTo(S.spec, p.choice, z.dataset.cend !== undefined ? null : Number(z.dataset.cdrag))) { save(); render(); } return; }
  if (z.dataset.tcard !== undefined) {   // a department chip on a teacher's card: their second department
    let p = {}; try { p = JSON.parse(e.dataTransfer.getData("text/plain") || "{}"); } catch (err) { }
    if (tkHead() || !p || typeof p.dept !== "string" || p.dept.trim() === "") return;
    tkSecond(Number(z.dataset.tcard), p.dept); return; }
  const idxs = dropIds(e); if (!idxs.length) return;
  placeOn(cardAt(z.dataset.mcard), idxs);
});
/* ---- the Table view's list of bands: its filter */
function btState() { if (!M.bt) M.bt = { level: "", q: "", fix: false }; if (M.bt.level && !levels().includes(M.bt.level)) M.bt.level = ""; return M.bt; }
const btShown = (name, ok, q) => { const nm = String(name || "").trim().toLowerCase(), w = String(q || "").trim().toLowerCase(); return !nm || (ok && (!w || nm.includes(w))); };   // a band with no name yet is always shown
function btApply() {   // after a keystroke in "Name has": show and hide the rows in place, so the box keeps the keyboard
  const bt = btState(), rows = [...document.querySelectorAll("tr[data-btname]")]; let n = 0;
  rows.forEach(r => { const on = btShown(r.dataset.btname, r.dataset.btok === "1", bt.q); r.hidden = !on; if (on) n++; });
  const el = $("#btN"); if (el) el.textContent = `${n} of ${rows.length} shown`;
}
document.addEventListener("focusout", e => {   // the open room's typed Block or Floor left as it was: back to the list
  if (!e.target || e.target.id !== "vvType" || !VV.typing || !e.target.isConnected) return;
  const [vi, field] = String(e.target.dataset.vtype || "").split("|"), v = S.spec && S.spec.venues[Number(vi)];
  if (v && e.target.value.trim() === String(v[field] == null ? "" : v[field]).trim()) setTimeout(() => { if (VV.typing === field && !$("#vvType:focus")) { VV.typing = null; render(); } }, 0);
});
document.addEventListener("keydown", e => {   // a wrapping box is one line of words: Enter leaves it, which saves it
  if (e.key === "Enter" && !e.isComposing && e.target.classList && e.target.classList.contains("wrapbox")) { e.preventDefault(); e.target.blur(); }
});
/* ---- the Groups and bands view: form state and actions */
document.addEventListener("keydown", e => {   // in the box for a band's name: Enter saves, Escape leaves the name as it was
  if (!e.target || e.target.id !== "gbName" || e.isComposing || !(e.key === "Enter" || e.key === "Escape")) return;
  e.preventDefault(); e.stopPropagation(); groupsAction(e.key === "Enter" ? "gbsave" : "gbcancel");
}, true);
const classesAt = lv => S.spec.classes.filter(c => c.level === lv).map(c => c.class);
function gfState() { const lv = levels()[0] || ""; if (!M.gf) M.gf = { level: lv, tag: "", subject: "", block: "", classes: [], students: "" }; if (!levels().includes(M.gf.level)) M.gf.level = lv; return M.gf; }
function bfState() { const lv = levels()[0] || ""; if (!M.bf) M.bf = { level: lv, subjects: [], classes: classesAt(lv), name: "", everyone: true, touched: false, evTouched: false }; if (!levels().includes(M.bf.level)) M.bf.level = lv; return M.bf; }
function gpState() { const lv = levels()[0] || ""; if (!M.gp) M.gp = { level: lv, dept: "", subject: "", teacher: "", band: "", ticked: new Set() }; if (M.gp.level && !levels().includes(M.gp.level)) M.gp.level = lv; return M.gp; }   // level "" is every level
const gTab = () => M.gtab === "bands" ? "bands" : "pool";   // which of the two lists is shown: the single teaching groups (the first tab), or the banded ones
const gpIdx = ids => S.spec.lessons.map((x, i) => [x, i]).filter(([x]) => x && ids.includes(x._id)).map(([, i]) => i);
function gpView() {   // what the filter shows; a choice that is no longer on offer is dropped, and so is the tick of a row that is no longer shown
  const gp = gpState(), v = Groups.view(S.spec, gp), shown = new Set(v.pool.map(p => S.spec.lessons[p.li]._id));
  gp.dept = v.f.dept; gp.subject = v.f.subject; gp.teacher = v.f.teacher; gp.band = v.f.band; gp.ticked = new Set([...gp.ticked].filter(id => shown.has(id)));
  if (M.gask && !v.lanes.some(l => l.block === M.gask)) M.gask = null;   // a question about a band that is not shown is withdrawn
  if (M.grename != null && (gTab() !== "bands" || !v.lanes.some(l => l.block === M.grename))) { M.grename = null; M.grenameText = null; }   // and so is a name being changed
  return v; }
function gpShow(level, row, block) {   // after an add: the filter and the tab must not hide what was just made (row: the new lesson row, or none for a band, which has no groups yet; block: its band, if any)
  const gp = gpState(); if (gp.level && level && gp.level !== level) { gp.level = level; M.gpTo = ""; }
  if (!row || (gp.subject && row.subject !== gp.subject)) gp.subject = "";
  if (!row || (gp.dept && String((subj(row.subject) || {}).dept || "").trim() !== gp.dept)) gp.dept = "";
  const who = row ? (row.teachers || []).filter(Boolean) : [];
  if (!row || (gp.teacher && !(gp.teacher === Groups.NONE ? !who.length : who.includes(gp.teacher)))) gp.teacher = "";
  if (gp.band && gp.band !== block) gp.band = "";
  M.gtab = block ? "bands" : "pool"; M.gask = null;
}
const gAv = (nm, li) => { const t = S.spec.teachers.find(x => x.name === nm);   // the face with the teacher's short name beside it: a face alone does not say who it is; with a row (li), a small ✕ takes the teacher off it
  const off = li === undefined || cpBlock(S.spec.lessons[li]) ? "" : `<button class="gavx" data-gtx="${li}|${esc(nm)}" title="Take ${esc(nm)} off this teaching group" aria-label="Take ${esc(nm)} off this teaching group">✕</button>`;
  return t ? `<span class="gav" title="${esc(nm)}">${avatarOf(t, 24)}<span class="gavn">${esc(t.short || t.name || "")}</span>${off}</span>` : `<span class="chip">${esc(nm)}${off}</span>`; };
const byLevel = (items, draw) => gpState().level ? items.map(draw).join("") : levels().concat([...new Set(items.map(x => x.level || ""))].filter(l => !levels().includes(l))).map(lv => { const mine = items.filter(x => (x.level || "") === lv);   // under a heading for each level when every level is shown
  return mine.length ? `<div class="glv">${esc(lv || "No level")}</div>${mine.map(draw).join("")}` : ""; }).join("");
function barView(v) {   // one filter for both lists: the level (or all), a subject, a teacher (or the rows with none); and one band alone
  const gp = gpState();
  return `<section class="gbar card"><div class="row"><b>Show</b>
    <label>Level <select id="gpLevel">${opt("", gp.level, "All levels")}${levels().map(l => opt(l, gp.level)).join("")}</select></label>
    <label title="The department of the subject">Department <select id="gpDept" title="The department of the subject">${opt("", gp.dept, "All departments")}${v.depts.map(n => opt(n, gp.dept)).join("")}</select></label>
    <label>Subject <select id="gpSubject">${opt("", gp.subject, "All subjects")}${v.subjects.map(n => opt(n, gp.subject)).join("")}</select></label>
    <label>Teacher <select id="gpTeacher">${opt("", gp.teacher, "All teachers")}${v.none ? opt(Groups.NONE, gp.teacher, "No teacher") : ""}${v.teachers.map(n => opt(n, gp.teacher)).join("")}</select></label>
    <label>Band <select id="gpBand">${opt("", gp.band, "All bands")}${v.bands.map(n => opt(n, gp.band)).join("")}</select></label>
    ${v.filtered || gp.band ? `<button class="small" data-gclear>Show all</button>` : ""}
    <span style="flex:1"></span>${gp.level ? `<button class="small" data-cbands="${esc(gp.level)}">See how ${esc(gp.level)} is banded</button>` : `<button class="small" data-cbands="">See how the levels are banded</button>`}</div></section>`;
}
function tabsView(v) {   // the two lists as tabs, each with how many it shows
  const banded = v.lanes.reduce((n, l) => n + l.groups.filter(g => g.match).length, 0), tab = (k, label, n) => `<button class="${gTab() === k ? "on" : ""}" data-gtab="${k}">${label}<span class="n">${n}</span></button>`;
  return `<div class="gtabs tabs row">${tab("pool", "Single teaching groups", v.pool.length)}${tab("bands", "Banded teaching groups", banded)}<span class="muted small">${banded} group${banded === 1 ? "" : "s"} in ${v.lanes.length} band${v.lanes.length === 1 ? "" : "s"}</span></div>`;
}
function poolView(v) {   // the rows with no band that the filter shows: tick them and move them into a band, or delete one
  const gp = gpState(), items = v.pool, lanes = Groups.lanes(S.spec, gp.level), where = gp.level || "any level";
  const row = p => { const id = S.spec.lessons[p.li]._id, on = gp.ticked.has(id);
    return `<div class="prow${on ? " on" : ""}"><input type="checkbox" data-gtick="${esc(id)}" ${on ? "checked" : ""} aria-label="Tick ${esc(p.title)}"><span style="flex:1;min-width:0">${esc(p.title)}</span>${p.kind === "group" ? `<span class="codeline small">${esc(p.code)}</span>` : ""}<span class="muted small" title="Students">${p.students != null ? p.students : ""}</span><span class="avs" style="margin:0;min-height:0">${p.teachers.map(nm => gAv(nm, p.li)).join("") || `<span class="small overtxt">No teacher</span>`}</span><button class="small danger" data-gdel="${p.li}" title="Delete this teaching group">Delete</button></div>`; };
  return `<section class="gpool card"><h3 style="margin:0 0 6px">Single teaching groups</h3><p class="muted small" style="margin:0 0 8px">Whole-class rows and groups with their own code, each with who teaches it: the teaching groups that are in no band. Tick rows and move them into a band.</p>
    <div class="row" style="margin:8px 0"><button class="small" data-gall>Select all shown</button><button class="small" data-gnone>Deselect all</button><span class="muted small">${items.length} row${items.length === 1 ? "" : "s"}${gp.ticked.size ? ` · ${gp.ticked.size} ticked` : ""}</span>
      <span style="flex:1"></span><span>Move into band</span><select id="gpTo">${opt("", M.gpTo || "", "")}${lanes.map(l => opt(l.block, M.gpTo || "")).join("")}</select><button data-gmove ${gp.ticked.size && lanes.length ? "" : "disabled"}>Move</button></div>
    <div class="plist keep">${byLevel(items, row) || `<p class="muted small">${v.filtered ? `No single teaching group matches at ${esc(where)}.` : `Every teaching group at ${esc(where)} is in a band.`}</p>`}</div></section>`;
}
function lanesView(v) {   // the bands the filter shows as lanes, each whole; a group that does not match is faded; a band or a group can be deleted
  const gp = gpState(), lanes = v.lanes, s = n => n === 1 ? "" : "s";
  const grow = (g, l) => { const own = g.classes.join(",") !== l.classes.join(",");   // a group of fewer classes than its band says which
    return `<div class="grow${g.match ? "" : " dim"}"><span class="codeline small">${esc(g.code)}</span><span style="flex:1;min-width:0">${esc(g.subject)}${own ? ` <span class="muted small">${esc(g.classes.join(", "))}</span>` : ""}</span>${g.students != null ? `<span class="muted small" title="Students">${g.students}</span>` : ""}<span class="avs" style="margin:0;min-height:0">${g.teachers.map(nm => gAv(nm, g.li)).join("") || `<span class="small overtxt">No teacher</span>`}</span><button class="small" data-gout="${g.li}" title="Out of the band: it becomes a single teaching group">Take out</button><button class="small danger" data-gdel="${g.li}" title="Delete this teaching group">Delete</button></div>`; };
  const ask = l => { const n = l.groups.length, r = Groups.bandRules(S.spec, l.block);   // the question "Delete band" asks, in the band itself
    return `<div class="gask"><div>Delete ${esc(l.block)}?${n ? ` It has ${n} group${s(n)}.` : ""}${r ? ` ${r} rule${s(r)} on step 6 name${r === 1 ? "s" : ""} this band and will need another.` : ""}</div>
      <div class="row">${n ? `<button class="small danger" data-gbyes="all">Delete the band and its ${n} group${s(n)}</button><button class="small" data-gbyes="keep">Delete the band, keep the group${s(n)}</button>` : `<button class="small danger" data-gbyes="all">Delete the band</button>`}<button class="small" data-gbno>Cancel</button></div></div>`; };
  const name = l => M.grename === l.block   // the band's name: a click on it opens a box to change it, there
    ? `<span class="gbedit"><input id="gbName" value="${esc(M.grenameText ?? l.block)}" aria-label="The band's name"><button class="small primary" data-gbsave>Save</button><button class="small" data-gbcancel>Cancel</button></span>`
    : `<button class="gbtitle" data-gbname="${esc(l.block)}" title="Change the band's name"><b>${esc(l.block) || "(no name yet)"}</b><span class="muted small">Rename</span></button>`;
  const lane = l => `<div class="lane" data-glane="${esc(l.block)}"><div class="row small" style="justify-content:space-between">${name(l)}<span class="muted">${esc(l.classes.join(", "))}${l.everyone ? " · everyone takes one" : ""}</span><button class="small danger" data-gbdel="${esc(l.block)}">Delete band</button></div><div class="muted small">Its groups have lessons at the same time.</div>
    ${M.gask === l.block ? ask(l) : ""}${l.twice.map(nm => `<div class="small overtxt">${esc(nm)} is on two groups of this band: a band's groups meet at the same time.</div>`).join("")}${l.groups.map(g => grow(g, l)).join("") || `<div class="muted small">No groups yet: tick rows under Single teaching groups and move them here, or add groups above.</div>`}</div>`;
  return `<section class="glanes card"><h3 style="margin:0 0 6px">Banded teaching groups${gp.level ? ` at ${esc(gp.level)}` : ""}</h3><div class="llist keep">${byLevel(lanes, lane) || `<p class="muted small">${v.filtered ? "No band has a group that matches." : `No bands at ${esc(gp.level || "any level")} yet. Add one above.`}</p>`}</div></section>`;
}
/* a row moving into a band gets a code of its own ("Entire Class" → 1AR1): that is not a renumbering, so it is not listed */
const renumbered = sh => sh.changes.filter(([, a]) => a !== "Entire Class");
const describeShift = sh => listing(renumbered(sh).map(([, a, b]) => b == null ? `${a} deleted` : `${a} → ${b}`), 4);
function askShift(sh) {   // before a move that renumbers codes a student list or a Group rule names
  const n = renumbered(sh).length; if (!n || !(sh.students || sh.rules)) return true;
  const who = [sh.students ? `${sh.students} student${sh.students === 1 ? "'s group list names" : "s' group lists name"} the old codes (update them on the Students step)` : "",
    sh.rules ? `${sh.rules} rule${sh.rules === 1 ? "" : "s"} on step 6 name${sh.rules === 1 ? "s" : ""} the old codes` : ""].filter(Boolean).join(", and ");
  return confirm(`This changes ${n} group code${n === 1 ? "" : "s"}: ${describeShift(sh)}. ${who}. Go on?`);
}
const shiftNote = sh => renumbered(sh).length && !(sh.students || sh.rules) ? ` Codes changed: ${describeShift(sh)}.` : "";
function moveRows(lis, block) {
  if (!lis.length) { toast("Tick rows first."); return; }
  if (!block) { toast("Pick a band."); return; }
  const sh = Groups.shift(S.spec, c => Groups.toBand(c, lis, block)); if (!askShift(sh)) return;
  const r = Groups.toBand(S.spec, lis, block);
  if (!r.moved) { toast(r.skipped ? `Those rows are of another level than ${block}.` : "Nothing moved."); return; }
  save(); gpState().ticked.clear(); render();
  toast(`Moved ${r.moved} into ${block}.${r.widened.length ? ` ${block} now also covers ${listing(r.widened)}.` : ""}${r.skipped ? ` ${r.skipped} row${r.skipped === 1 ? "" : "s"} of another level ${r.skipped === 1 ? "was" : "were"} left.` : ""}${shiftNote(sh)}`);
}
function teacherOff(li, name) {   // a teacher is taken off one teaching group, there in the list; the top bar's Undo puts them back
  const x = S.spec.lessons[li]; if (!x) return;
  if (cpBlock(x)) { toast(cpWhy()); return; }
  if (!DeptMap.undeploy(S.spec, { kind: "group", li }, name)) return;   // the row itself, whatever classes it has
  const code = (lessonInfo()[li] || {}).code, what = `${code && code !== "Entire Class" ? code + " " : ""}${x.subject || "the row"}${(x.classes || []).length ? ` for ${listing(x.classes)}` : ""}`;
  save(); render(); toast(`Took ${name} off ${what}. Undo, at the top, puts them back.`);
}
function rowDelete(li) {   // a teaching group is deleted, in a band or not; the top bar's Undo brings it back
  if (!S.spec.lessons[li]) return;
  const sh = Groups.shift(S.spec, c => Groups.dropRow(c, li)); if (!askShift(sh)) return;
  const was = Groups.dropRow(S.spec, li); if (!was) return; unpick(); save(); render();   // the Table view's ticks are row numbers: they no longer fit
  toast(`Deleted ${was.code && was.code !== "Entire Class" ? was.code + " " : ""}${was.subject || "the row"}${was.classes.length ? ` for ${listing(was.classes)}` : ""}.${shiftNote(sh)} Undo, at the top, brings it back.`);
}
function bandDelete(block, keep) {   // a band is deleted, with its groups or leaving them as single teaching groups
  const sh = Groups.shift(S.spec, c => Groups.dropBand(c, block, keep)); if (!askShift(sh)) return;
  const named = Groups.bandRules(S.spec, block), r = Groups.dropBand(S.spec, block, keep), gp = gpState(), gf = gfState(); M.gask = null; if (!r) { render(); return; }
  unpick();   // the Table view's ticks are row numbers: they no longer fit
  if (gp.band === block) gp.band = ""; if (M.gpTo === block) M.gpTo = ""; if (gf.block === block) gf.block = "";
  save(); render(); const g = `${r.groups} group${r.groups === 1 ? "" : "s"}`;
  toast(`Deleted the band ${block}${!r.groups ? "." : keep ? `. Its ${g} ${r.groups === 1 ? "is a single teaching group" : "are single teaching groups"} now.` : ` and its ${g}.`}${named ? ` ${named} rule${named === 1 ? "" : "s"} on step 6 still name${named === 1 ? "s" : ""} it.` : ""}${shiftNote(sh)} Undo, at the top, brings it back.`);
}
function bandRename(block, to) {   // a band's new name, typed on the band itself; its groups and the rules that name it follow
  const r = Groups.renameBand(S.spec, block, to);
  if (r.error) { toast(r.error); const box = $("#gbName"); if (box) box.focus(); return; }
  M.grename = null; M.grenameText = null; if (r.same) { render(); return; }
  const gp = gpState(), gf = gfState(); if (gp.band === block) gp.band = r.name; if (M.gpTo === block) M.gpTo = r.name; if (gf.block === block) gf.block = r.name;
  save(); render(); const s = n => n === 1 ? "" : "s";
  toast(`${block || "The band"} is now ${r.name}.${r.groups ? ` Its ${r.groups} group${s(r.groups)} ${r.groups === 1 ? "follows" : "follow"}.` : ""}${r.rules ? ` ${r.rules} rule${s(r.rules)} on step 6 ${r.rules === 1 ? "follows" : "follow"} too.` : ""} Undo, at the top, brings it back.`);
}
function rowOut(li) {
  const x = S.spec.lessons[li]; if (!x || !x.block) return; const block = x.block;
  const sh = Groups.shift(S.spec, c => { Groups.fromBand(c, li); Groups.pullOutCode(c, li); }); if (!askShift(sh)) return;
  Groups.fromBand(S.spec, li); const kept = Groups.pullOutCode(S.spec, li); save(); render();
  toast(`Out of ${block}: a single teaching group now.${kept ? ` It is a group of its own, with Keep code ${kept}.` : ""}${shiftNote(sh)}`);
}
function groupsAction(k, v) {
  const gf = gfState(), bf = bfState();
  if (k === "bfsubject") { bf.subjects = bf.subjects.filter(x => x !== v); render(); return; }
  if (k === "gall") { const gp = gpState(); gpView().pool.forEach(p => gp.ticked.add(S.spec.lessons[p.li]._id)); render(); return; }
  if (k === "gclear") { const gp = gpState(); gp.dept = ""; gp.subject = ""; gp.teacher = ""; gp.band = ""; M.gask = null; render(); return; }
  if (k === "gtab") { M.gtab = v === "pool" ? "pool" : "bands"; M.gask = null; render(); return; }
  if (k === "gdel") { rowDelete(Number(v)); return; }
  if (k === "gtx") { const [li, ...nm] = String(v).split("|"); teacherOff(Number(li), nm.join("|")); return; }
  if (k === "gbdel") { M.gask = M.gask === v ? null : v; render(); return; }   // the question opens in the band; a second press closes it
  if (k === "gbno") { M.gask = null; render(); return; }
  if (k === "gbname") { M.grename = v; M.grenameText = null; M.gask = null; render(); const box = $("#gbName"); if (box) { box.focus(); box.select(); } return; }
  if (k === "gbcancel") { M.grename = null; M.grenameText = null; render(); return; }
  if (k === "gbsave") { const box = $("#gbName"); if (M.grename != null && box) bandRename(M.grename, box.value); return; }
  if (k === "gbyes") { if (M.gask) bandDelete(M.gask, v === "keep"); return; }
  if (k === "gnone") { gpState().ticked.clear(); render(); return; }
  if (k === "gmove") { moveRows(gpIdx([...gpState().ticked]), M.gpTo || ""); return; }
  if (k === "gout") { rowOut(Number(v)); return; }
  if (k === "gfadd") {
    const r = Groups.newGroup(S.spec, gf); if (r.error) { toast(r.error); return; }
    const kept = Groups.pullOutCode(S.spec, r.i);   // a pull-out group (fewer students than its classes hold) keeps a code of its own
    save(); const x = S.spec.lessons[r.i], code = lessonInfo()[r.i].code;
    gf.classes = []; gf.students = ""; gpShow(x.level, x, x.block); render();
    toast(`Added ${code === "Entire Class" ? "" : code + " "}${x.subject} for ${listing(x.classes)}.${kept ? ` ${x.students} of the class: a group of its own, with Keep code ${kept}.` : ""}`); return;
  }
  if (k === "gfeach") {
    if (!gf.subject) { toast("Pick a subject."); return; }
    const n = Groups.addOnePerClass(S.spec, gf.level, gf.subject, gf.classes.length ? gf.classes : classesAt(gf.level));
    if (!n) { toast(`Every class has ${gf.subject} already.`); return; }
    save(); gf.classes = []; gpShow(gf.level, { subject: gf.subject, teachers: [] }, null); render(); toast(`${n} row${n === 1 ? "" : "s"} added.`); return;
  }
  if (k === "bfadd") {
    const name = bf.touched ? bf.name : Groups.bandName(bf.level, bf.subjects, blockNames());
    const r = Groups.newBand(S.spec, { block: name, level: bf.level, classes: bf.classes, everyone: bf.evTouched ? bf.everyone : undefined }); if (r.error) { toast(r.error); return; }
    save(); const b = S.spec.blocks[r.i]; gf.level = b.level; gf.block = b.block; gf.classes = []; M.bf = null; gpShow(b.level, null, b.block); render();
    toast(`Band ${b.block} added. Add its groups above, or move single teaching groups into it.`); return;
  }
}
function mtick(el, shift) {   // a roster tick box; shift-click ticks the run from the last one ticked, in roster order
  const order = DeptMap.roster(S.spec, mapDept(), M.extra).map(i => S.spec.teachers[i]._id);
  const id = el.dataset.mtick, a = order.indexOf(M.lastTick), b = order.indexOf(id);
  (shift && a >= 0 && b >= 0 ? order.slice(Math.min(a, b), Math.max(a, b) + 1) : [id]).forEach(x => el.checked ? M.ticked.add(x) : M.ticked.delete(x));
  M.lastTick = id; render();
}
function mapAction(k, v) {   // the roster's buttons
  const T = S.spec.teachers, ro = DeptMap.roster(S.spec, mapDept(), M.extra);
  if (k === "mview") { M.view = ["table", "groups"].includes(v) ? v : "map"; try { localStorage.setItem(MAPVIEW, M.view); } catch (e) { } render(); return; }
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
  return `<div class="bulk"><div class="row avstrip">${ix.slice(0, 8).map(i => `<span title="${esc(S.spec.teachers[i].name || "")}">${avatarOf(S.spec.teachers[i], 24)}</span>`).join("")}${ix.length > 8 ? `<span class="muted small">+${ix.length - 8}</span>` : ""}</div>
    <div class="row"><b>${ix.length} ticked</b> department <select id="pickD">${opt("", P.d, "")}${(sc().departments || []).map(d => opt(d, P.d)).join("")}</select><button data-bulk="tc-dept" ${P.d ? "" : "disabled"}>Set</button>
    <span class="muted">·</span> role <select id="pickR">${opt("", P.r, "")}${roles().map(r => opt(r.role, P.r)).join("")}</select><button data-bulk="tc-role" ${P.r ? "" : "disabled"}>Set</button>
    <span class="muted">·</span> allowance <input id="pickA" type="number" value="${esc(P.a)}" style="width:64px"><button data-bulk="tc-allow">Set</button>
    <button class="small ghost" data-bulk="tc-none">Clear ticks</button></div></div>`;
}
function bulkTeachers(k) {   // step 4: one change for every ticked teacher
  const P = S.pick, T = S.spec.teachers, ix = [...P.teachers].filter(i => T[i]), n = ix.length, s1 = n === 1 ? "" : "s";
  if (k === "tc-none") { P.teachers.clear(); render(); return; }
  if (!n) return;
  if (isHead() && !S.practice) return;   // a head ticks teachers but changes none of these
  let msg = "";
  if (k === "tc-dept") { if (!P.d) return; ix.forEach(i => { T[i].dept = P.d; TeacherView.tidy(T[i]); }); msg = `${n} teacher${s1} now in ${P.d}`; }
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
    let n = 0, full = 0, left = 0, kept = 0;
    for (const i of ix) {
      const x = S.spec.lessons[i], ts = (x.teachers || []).filter(Boolean), was = ts.includes(t);
      if (cpBlock(x)) { left++; continue; }   // a head leaves the form teachers' lessons alone
      if (k === "t1") { if (ts[0] === t) continue; if (Parents.follows(S.spec, x) && Parents.want(S.spec, x).includes(t)) { kept++; continue; } x.teachers = [t, ...ts.slice(1).filter(y => y !== t)]; }
      if (k === "t2") { if (was) continue; if (ts.length >= (Parents.staffed(S.spec, x) ? Parents.cap(S.spec) : 3)) { full++; continue; } x.teachers = [...ts, t]; }
      if (k === "tx") { if (!was) continue; x.teachers = ts.filter(y => y !== t); }
      n++;
    }
    save(); render();
    const { out } = issues(), has = m => k === "tx" ? 0 : ix.filter(i => (out.lessons[i] || []).some(x => x.startsWith(`${t} ${m}`))).length;
    const twice = has("twice in this band");
    toast(`${{ t1: `${t} is now Teacher 1 of`, t2: `${t} now co-teaches`, tx: `${t} was taken off` }[k]} ${n} group${s1(n)}` + (full ? `; ${full} already had as many teachers as they can hold` : "")
      + (kept ? `; ${kept} lesson${s1(kept)} keep the order of their ${Parents.label(S.spec)}` : "")
      + (left ? `; ${left} lesson${s1(left)} of the ${Parents.label(S.spec)} ${left === 1 ? "was" : "were"} left alone` : "")
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
  return `<div class="card" id="teacherUpload"><h2>Upload the teacher list</h2>
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
    p.update.forEach(u => { Object.assign(T[u.i], u.changes); TeacherView.tidy(T[u.i]); });   // the same row object: its _id stays; a Department that is now the second takes the second off
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
    const cl = S.spec.classes.filter(c => Parents.names(c).some(t => gone.has(t))).length;
    const forms = !cl ? "" : ` They also leave the ${Parents.label(S.spec)} of ${cl === 1 ? "1 class" : `${cl} classes`}.`;
    if (!confirm(`${warn}Remove ${who} not in this list? ${lessons}${forms} Undo takes it back.`)) return;
    [...p.missing].sort((a, b) => b - a).forEach(i => T.splice(i, 1));
    S.spec.lessons.forEach(x => { if ((x.teachers || []).some(t => gone.has(t))) x.teachers = x.teachers.filter(t => t && !gone.has(t)); });
    S.spec.classes.forEach((c, i) => { if (Parents.names(c).some(t => gone.has(t))) Parents.setParents(S.spec, i, Parents.names(c).filter(t => !gone.has(t))); });   // and off every class's Class Parents
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
  if (e.target.id === "fxAskIn") { fxHelp().words = e.target.value; return; }
  if (e.target.id === "gfStudents") { gfState().students = e.target.value; return; }
  if (e.target.classList && e.target.classList.contains("wrapbox")) { if (/[\r\n]/.test(e.target.value)) { const at = e.target.selectionStart; e.target.value = e.target.value.replace(/\s*[\r\n]+\s*/g, " "); e.target.selectionStart = e.target.selectionEnd = Math.min(at, e.target.value.length); } fitAreas(e.target.parentElement); return; }   // pasted line breaks become spaces
  if (e.target.id === "btQ") { btState().q = e.target.value; btApply(); return; }
  if (e.target.id === "vvMvBlock") { vvMv().bt = e.target.value; return; }   // kept, so a redraw does not lose what was typed
  if (e.target.id === "vvMvFloor") { vvMv().ft = e.target.value; return; }
  if (e.target.id === "gbName") { M.grenameText = e.target.value; return; }   // kept, so a redraw from elsewhere does not lose what was typed
  if (e.target.id === "bfName") { const bf = bfState(); bf.name = e.target.value; bf.touched = true; const ev = $("#bfEveryone"); if (ev && !bf.evTouched) ev.checked = !/option|elective/i.test(bf.name); return; }
  if (e.target.id === "mQ") { M.q = e.target.value; const rb = $("#rbody"); if (rb) rb.innerHTML = rosterList(mapDept()); return; }   // the roster only: a full redraw would take the caret
  if (["mnName", "mnShort", "mnAllow"].includes(e.target.id) && M.nf) { M.nf[{ mnName: "name", mnShort: "short", mnAllow: "allowance" }[e.target.id]] = e.target.value; return; }
  if (e.target.id !== "tlPaste") return;
  TL.text = e.target.value;
  if (TL.read || TL.err || TL.msg) { tlClear(); const pv = $("#tlPreview"); if (pv) pv.innerHTML = ""; }
});

/* ---------------- pop-ups: class, group, subject and room pickers */
const PCPATH = "spec.school.parents_subjects";
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
    const pc = path === PCPATH;   // the Class Parents subjects: the names as they are on step 3, one by one
    const cur = new Set(namesList(getPath(path)).map(n => n.toLowerCase())), by = new Map(), tg = n => pc ? n : untag(n);
    S.spec.subjects.filter(s => s.subject).forEach(s => { const d = s.dept || "Other"; if (!by.has(d)) by.set(d, new Set()); by.get(d).add(tg(s.subject)); });
    const box = (v, label, cls = "") => `<label class="${cls}"><input type="checkbox" value="${esc(v)}" ${cur.has(String(v).toLowerCase()) ? "checked" : ""}>${label}</label>`;
    const known = new Set([...(pc ? [] : by.keys()), ...[...by.values()].flatMap(s => [...s])].map(x => String(x).toLowerCase())), lost = namesList(getPath(path)).filter(n => !known.has(n.toLowerCase()));
    pop.innerHTML = (pc ? `<h3>${esc(Parents.label(S.spec))} take these lessons</h3><p class="muted small" style="margin:0 0 6px">Tick the subjects whose lessons they take.</p>`
      : `<h3>Subjects taught then</h3><p class="muted small" style="margin:0 0 6px">Tick a department for all its subjects, or single subjects (every G1/G2/G3 group of it). Every other lesson is kept out of those periods.</p>`)
      + [...by].map(([d, ss]) => `<div class="gblock"><div class="opts wide">${d !== "Other" && !pc ? box(d, `<b>All ${esc(d)}</b>`) : ""}${[...ss].map(s => box(s, esc(s))).join("")}</div></div>`).join("")
      + (lost.length ? `<div class="gblock"><div class="muted small">Not on step 3 (untick to remove)</div><div class="opts wide">${lost.map(n => box(n, esc(n))).join("")}</div></div>` : "")
      + `<div class="row"><button class="small" data-popnone="1">None</button><button class="small primary" data-popdone="1">Done</button></div>`;
  } else if (anchor.dataset.pop === "rooms") {   // Only in venues: the rooms, by kind
    const cur = namesList(getPath(path)), by = new Map();
    S.spec.venues.filter(v => v.room).forEach(v => { const k = v.kind || "classroom"; if (!by.has(k)) by.set(k, []); by.get(k).push(v.room); });
    const order = [...by.keys()].sort((a, b) => (a === "classroom") - (b === "classroom"));
    pop.innerHTML = `<h3>Rooms they may use then</h3>` + order.map(k => `<div class="gblock"><div class="muted small">${esc(k)}</div><div class="opts">${by.get(k).map(x => `<label><input type="checkbox" value="${esc(x)}" ${cur.includes(x) ? "checked" : ""}>${esc(x)}</label>`).join("")}</div></div>`).join("")
      + `<div class="row"><button class="small" data-popnone="1">None</button><button class="small primary" data-popdone="1">Done</button></div>`;
  }
  pop.hidden = false;
}
$("#pop").addEventListener("click", e => {
  const pop = $("#pop"); const path = pop.dataset.path; e.stopPropagation();
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.popall || b.dataset.popnone) pop.querySelectorAll("input[type=checkbox]").forEach(x => { if (!x.closest("details") || b.dataset.popnone) x.checked = !!b.dataset.popall; });
  if (b.dataset.popdone) { commitPop(); }
});
function commitPop() {
  const pop = $("#pop"); if (pop.hidden) return; const path = pop.dataset.path;
  if (pop.dataset.what === "classes") setPath(path, [...pop.querySelectorAll("input[type=checkbox]:checked")].map(x => x.value));
  else if (pop.dataset.what === "subjects" && path === PCPATH) Parents.setSubjects(S.spec, [...pop.querySelectorAll("input[type=checkbox]:checked")].map(x => x.value));
  else if (pop.dataset.what === "subjects") setPath(path, [...new Set([...pop.querySelectorAll("input[type=checkbox]:checked")].map(x => x.value))].join(", ") || null);   // one cell, as on the workbook
  else if (pop.dataset.what === "rooms") setPath(path, [...pop.querySelectorAll("input[type=checkbox]:checked")].map(x => x.value));
  else if (pop.dataset.what === "groups") {
    const vals = [...pop.querySelectorAll("input:checked")].map(x => x.value).filter(Boolean), st = getPath(path.replace(/\.groups$/, ""));
    setPath(path, vals.filter(v => !v.startsWith(EXEMPT)));
    if (st) setExempt(st, [...pop.querySelectorAll("[data-band]")].map(x => x.dataset.band), vals.filter(v => v.startsWith(EXEMPT)).map(v => v.slice(EXEMPT.length)));
  }
  const lc = pop.dataset.what === "classes" && path.match(/^spec\.lessons\.(\d+)\.classes$/); if (lc) groupCode(Number(lc[1]));
  pop.hidden = true; if (localPath(path)) { render(); return; } save(); if (!tryHeld()) render(); poll();
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
async function postTry(url, body) {   // as post, but a refusal is not said: {j} on success, {error: the server's sentence} on a refusal, {} when the page goes to sign in
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { location.href = "/login"; return {}; }
  if (!r.ok) return { error: j.error || "Something went wrong." };
  return { j };
}
async function poll() {   // every few seconds: the published timetable and the deployment's state (G.st)
  clearTimeout(G.timer);
  if (G.inflight) { G.timer = setTimeout(poll, 500); return; }
  G.inflight = true;
  try {
    const r = await fetch("/api/status");
    if (r.status === 401) { location.href = "/login"; return; }
    G.st = await r.json();
    paintPublished(); draftWatch();
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
  const fb = j.fallbacks, things = m => `${m} thing${m === 1 ? "" : "s"}`;   // the sums again down the give-way list, when the first choices fail
  const down = !fb || !(j.critical > 0) ? "" : fb.pass_at == null ? `<p class="issue crit">Even after every second choice (${fb.items.length}), ${things(fb.critical[fb.critical.length - 1])} will not fit.</p>`
    : fb.pass_at >= 1 ? `<p class="issue soft">With the first choices, ${things(j.critical)} will not fit. Giving way in your order, the sums pass after choice ${fb.pass_at}: ${esc(fb.items.slice(0, fb.pass_at).join("; "))}.</p>` : "";
  el.innerHTML = head + (hard.length
      ? `<p class="issue crit">${hard.length} thing${hard.length === 1 ? "" : "s"} will not fit: no timetable can be made until ${hard.length === 1 ? "it is" : "they are"} fixed.</p>${down}
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
      ${p.config_id ? `<p class="muted small">Made from configuration ${esc(p.config_id)}.</p>` : ""}${p.compared_v ? `<p class="muted small">Checked against the setup at ${esc(p.compared_v)}</p>` : ""}${p.compared_v ? ((p.left || []).length || p.open ? `<details><summary>${p.open || p.left.length} warning${(p.open || p.left.length) === 1 ? " was" : "s were"} open when it was published</summary><ul>${(p.left || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul></details>` : `<p class="muted small">0 warnings were open when it was published</p>`) : ""}${p.compared_v ? ((p.fixes || []).length ? `<details><summary>${p.fixes.length} fix${p.fixes.length === 1 ? "" : "es"} made in the app</summary><ol class="fxlist">${p.fixes.map(x => `<li>${esc(x)}</li>`).join("")}</ol></details>` : `<p class="muted small">No fixes were made in the app.</p>`) : ""}${ruleReportHTML(p.rule_report || [], S.spec ? S.spec.rules.filter(r => r.rule === "In words").length : 0)}${choicesUsedHTML(p.choices_used || [], p.choice_problems || [], S.spec ? validChoices() : 0)}
      <h3>Downloads</h3><div class="links"><a href="/files/excel">Excel, every timetable</a><a href="/files/zip">PDFs, one per class, teacher, room and student (zip)</a>${f.db ? `<a href="/files/db" title="Every lesson, class, teacher and room as a SQLite database, for other systems to import. It also holds the setup, so Make printouts can rebuild everything from it.">Timetable database (.sqlite), for other systems</a>` : ""}
      ${Object.keys(f.books || {}).map(k => `<a href="/files/book/${k}">${k[0].toUpperCase() + k.slice(1)}: all in one PDF</a>`).join("")}</div>
      <h3>Personal student codes</h3>${p.students && !p.personal ? `<p class="issue">Personal codes are off until SECRET_KEY is set in Railway variables: without it, anyone who knows a Student ID could work out that student's code.</p>` : p.students ? `<div class="links"><a href="/api/code-slips.pdf">Code slips to print, by class (PDF)</a><a href="/api/codes.csv">Code list (CSV)</a></div>` : `<p class="muted small">Add students on the Students step to give each one a personal code.</p>`}`
    : `<p class="muted">Nothing published yet. Teachers and students see a "not published yet" page.</p>`) +
    `<h3>Access codes</h3><ul class="codes">${[["committee", "Committee"], ["teacher", "Teachers"], ["student", "Students"]].map(([k, t]) => `<li>${t}: ${st.codes && st.codes[k] ? "set" : "<b>not set</b>"}</li>`).join("")}<li>Department heads: ${st.codes && st.codes.head ? "set" : "not set (no heads' sign-in)"}</li></ul>
    ${(st.code_problems || []).map(x => `<p class="issue">${esc(x)}</p>`).join("")}${st.volume ? "" : `<p class="issue">No Railway volume: the published timetable will be lost on the next deploy. Add a volume (see README).</p>`}`;
}

/* ---------------- downloads */
document.addEventListener("change", e => {
  if (e.target.id === "exSetup" || e.target.id === "exTT") { const f = e.target.files[0]; $("#" + e.target.id + "Name").textContent = f ? f.name : "none chosen"; }
  if (e.target.id === "bdFind" && S.board) { S.board.find = e.target.value; bdDraw(); return; }
  if (e.target.dataset && e.target.dataset.dfilter) { S.dfilter = e.target.dataset.dfilter; drawDraft(); }
});
/* the chosen setup workbook and timetable as form data, or null (with a message) when something is missing */
function timetableForm() {
  const a = $("#exSetup").files[0], b = $("#exTT").files[0];
  const isDb = b && /\.(sqlite3?|db)$/i.test(b.name);
  if (!b || (!a && !isDb)) { toast(b ? "Choose the setup workbook too (a timetable database from this app can come alone)." : "Choose the timetable: a workbook or a timetable database."); return null; }
  const fd = new FormData(); if (a) fd.append("setup", a); fd.append("timetable", b); return fd;
}
async function makePrintouts() {   // step 9: the printouts of the draft, with the changes made in the app
  const msg = $("#pbPrintMsg"), fd = new FormData();
  fd.append("single", $("#pbSingle").checked ? "1" : "0");
  const go = $("#pbPrint"); go.disabled = true; msg.textContent = "Making printouts… a school with 600 students takes about a minute.";
  try {
    const r = await fetch("/api/draft/printouts", { method: "POST", body: fd });
    if (!r.ok) { const j = await r.json().catch(() => ({})); msg.textContent = ""; toast(j.error || "Could not make the printouts."); if (r.status === 409 && j.unplaced) await refreshDraft(); return; }   // a lesson waits: the step is drawn again with the sentence
    const name = (r.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)"?/);
    dl(await r.blob(), name ? name[1] : "Timetables.zip"); msg.textContent = r.headers.get("X-Checks") || "Done.";
  } catch (err) { msg.textContent = ""; toast("Could not make the printouts: " + err.message); }
  finally { go.disabled = false; }
}
async function downloadDraft() {   // step 9: the draft as a database; a refusal (a lesson waits in Not placed) says the server's sentence, and the step is drawn again
  try {
    const r = await fetch("/api/draft/download");
    if (r.status === 401) { location.href = "/login"; return; }
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast(j.error || "Could not download the draft."); if (r.status === 409 && j.unplaced) await refreshDraft(); return; }
    const cd = r.headers.get("Content-Disposition") || "", star = cd.match(/filename\*=UTF-8''([^;]+)/i), plain = cd.match(/filename="?([^";]+)"?/);
    let name = "draft.sqlite"; try { name = star ? decodeURIComponent(star[1]) : plain ? plain[1] : name; } catch (e) { }
    dl(await r.blob(), name);
  } catch (err) { toast("Could not reach the server: " + err.message); }
}
/* a timetable made outside the app: kept on the server as the draft and checked against the setup as it is now */
function drawDraft() {   // the upload card's head and the timetable card again (the typed box keeps its focus: fxKeep in bdDraw and bdSideDraw)
  const box = $("#imResult"); if (!box) return;
  box.innerHTML = S.draft ? draftHTML(S.draft).head : "";
  bdMount(); bdDraftDraw();
}
async function uploadDraft(replace) {
  const fd = timetableForm(); if (!fd) return;
  if (replace) fd.append("replace", "1");
  const box = $("#imResult"), btns = ["#imCheck"].map(q => $(q)).filter(Boolean);
  btns.forEach(x => x.disabled = true);
  box.innerHTML = `<p class="muted" style="margin-top:10px">Checking the timetable against the setup…</p>`;
  try {
    const r = await fetch("/api/draft", { method: "POST", body: fd }), j = await r.json().catch(() => ({}));
    if (r.status === 401) { location.href = "/login"; return; }
    if (r.status === 409 && j.fixes && !replace) {
      drawDraft();
      if (confirm(`${j.error || "The draft has changes that were never published."} Replace the draft with this file?`)) { btns.forEach(x => x.disabled = false); return uploadDraft(true); }   // the server's sentence counts the lessons waiting in Not placed
      return;
    }
    if (!r.ok) { drawDraft(); toast(j.error || "Could not check the timetable."); return; }
    S.draft = j; S.help = null; drawDraft(); poll();
  } catch (err) { drawDraft(); toast("Could not reach the server: " + err.message); }
  finally { btns.forEach(x => x.disabled = false); }
}
async function refreshDraft() {   // the draft again from the server, and the step drawn from it
  try {
    const r = await fetch("/api/draft"), j = await r.json().catch(() => ({}));
    if (r.status === 401) { location.href = "/login"; return; }
    if (r.ok && j.warnings) S.draft = j;
  } catch (e) { }
  if (STEPS[S.step][0] === "publish") render();
}
async function publishDraft() {   // step 9
  const btn = $("#pbPublish"), msg = $("#pbMsg"), again = () => { if (STEPS[S.step][0] === "publish") render(); };
  DR.hold = true; DR.gen++;   // no fetch of the draft, and no answer of one already sent, while the publish runs
  if (btn) btn.disabled = true;
  if (msg) msg.textContent = "Publishing: making the PDFs, the Excel workbook and the timetable pages (about a minute for a school with 600 students)…";
  try {
    const r = await fetch("/api/draft/publish", { method: "POST" }), j = await r.json().catch(() => ({}));
    if (r.status === 401) { location.href = "/login"; return; }
    if (r.status === 409 && (j.critical || j.unplaced)) { toast(j.error); await refreshDraft(); return; }   // a critical mistake, or a lesson not placed, arrived meanwhile: the step shows it now
    if (!r.ok) { again(); toast(j.error || "Could not publish the timetable."); return; }
    S.draft = j; S.help = null; again(); toast("Published. Teachers and students now see this timetable."); poll();
  } catch (err) { again(); toast("Could not reach the server: " + err.message); }
  finally { DR.hold = false; DR.seen = null; }   // the next status is taken as seen, so the same summary causes no fetch
}
async function decide(answer, key) {   // answer is step5, open or met; the key is the warning's (it may hold a "|")
  const j = await post("/api/draft/decide", { key, answer });
  if (!j) return;
  if (S.help && S.help.warn === key) fxShut(S.help);   // the warning is answered: its ways shut
  S.draft = j; drawDraft();   // only the result area: render() would reset the chosen file names
  poll();
}
/* the draft on steps 8 and 9: asked for the first time the page needs it, again each time the person opens either step, and again when
   the status poll shows the server's draft is not the one last fetched (another tab's fix, or a change to the setup). A fetch that
   brings the same draft back changes nothing on the page. */
const DR = { seen: null, busy: false, again: false, hold: false, gen: 0 };   // seen: the status's summary of the draft when the page last fetched it; busy: a fetch is under way; again: the person opened a step meanwhile
const onDraftStep = () => ["edit", "publish"].includes(STEPS[S.step][0]);
const draftSig = () => { const d = G.st && G.st.draft; return d ? JSON.stringify([d.upload_id, d.uploaded_at, d.open, d.critical, d.fixes]) : ""; };   // the draft summary alone: a change to the setup is picked up when the person opens the step
async function loadDraft(again) {   // again: the person has just opened step 8 or 9
  if (!G.st || !G.st.draft || DR.hold) return;   // hold: a publish is running
  if (DR.busy) { if (again) DR.again = true; return; }   // never two at once; an opening meanwhile is fetched for when this one is in
  if (!again && (S.draft || S.draftTried)) return;
  if (again) S.draftFailed = false;
  S.draftTried = true; DR.busy = true;
  const sig = draftSig(), had = !!S.draft, gen = DR.gen; let j = {}, ok = false;
  try {
    const r = await fetch("/api/draft"); j = await r.json().catch(() => ({}));
    if (r.status === 401) { location.href = "/login"; return; }
    ok = r.ok && !!j.warnings;
    if (!ok && !had && !r.ok && j.error) toast(j.error);
  } catch (e) { }
  finally { DR.busy = false; }
  if (DR.hold || gen !== DR.gen) return;   // a publish began meanwhile: this answer is older than its result
  if (FX.busy) return;   // a fix is being made: its own answer is the newer one, and the poll after it looks again
  if (DR.again) { DR.again = false; loadDraft(true); return; }
  if (!ok) {
    DR.seen = sig;   // this summary was tried: not again until it changes or the step is opened
    if (!S.draft) { S.draftFailed = true; if (onDraftStep()) render(); }   // nothing to show: say so; a draft already on the page stays, with no error
    return;
  }
  DR.seen = sig;
  if (S.draft && JSON.stringify(S.draft) === JSON.stringify(j)) { bdSync(); draftWatch(); return; }   // the same draft: nothing is redrawn (the board is fetched again if it is for another one)
  if (!onDraftStep() || !S.draft) { S.draft = j; if (onDraftStep()) render(); }
  else if (STEPS[S.step][0] === "publish") { S.draft = j; render(); }
  else if (S.help) await fxAfter(j);   // the open ways and the typed answer follow the new draft as they do after a change made here
  else { S.draft = j; drawDraft(); }
  draftWatch();
}
function draftWatch() {   // after each status: a draft that is not the one last fetched is fetched again while step 8 or 9 is on screen; elsewhere the next opening does it
  if (DR.busy || DR.hold || !G.st) return;
  const sig = draftSig();
  if (DR.seen === null) { if (!!S.draft === !!sig) { DR.seen = sig; return; } }   // the first status: a baseline unless the page lacks a draft the server has, or has one the server lacks
  else if (sig === DR.seen) return;
  if (!sig) {   // the draft has gone
    if (S.draft) { S.draft = null; S.help = null; if (onDraftStep()) render(); }
    DR.seen = sig; return;
  }
  if (onDraftStep() && !(S.draftFailed && !S.draft)) loadDraft(true);   // a first load that failed is tried again when the person opens the step, not every poll
}
const loadingDraft = () => !S.draft && !S.draftFailed && !!(G.st && G.st.draft);   // the server has a draft this page has not got yet
const LOADING = `<p class="muted" style="margin-top:10px">Loading the draft…</p>`;
const otherSchool = j => j.other_school ? `<p class="issue">This timetable is for <b>${esc(j.file_school)}</b>, but the setup saved in the app is for <b>${esc(j.school)}</b>. Check it is the right file.</p>` : "";
const fixList = (fl, newest) => `<ol class="fxlist"${newest ? " reversed" : ""}>${(newest ? Draft.batches(fl).reverse() : Draft.batches(fl)).map(b => `<li>${b.items.map(x => `<div>${esc(x.text)}</div>`).join("")}<span class="muted small">${esc(b.items[b.items.length - 1].at)}</span></li>`).join("")}</ol>`;
function warnHead(w) {   // a warning's first lines, the same on steps 8 and 9: its critical kind (unless the sentence starts with it), the sentence, then strength, the two sides and where
  const side = Draft.sideText(w), where = Draft.whereText(w).map(x => ` · ${esc(x)}`).join(""), kind = w.crit ? Draft.critWord(w.crit) : "";
  return `<div class="wt">${kind && String(w.text || "").indexOf(kind + ":") !== 0 ? `<span class="chip pbmark">${esc(kind)}</span>` : ""}${esc(w.text)}</div><div class="muted small">${esc(w.strength)}${side ? ` · ${esc(side)}` : ""}${where}</div>`;
}
function draftHead(j) { return `<h3 style="margin-top:14px">${esc(j.school)} · ${esc(j.timetable)}</h3><p class="muted small">${j.lessons} lessons · ${j.classes} classes · ${j.teachers} teachers · ${j.students} students</p>`; }
function publishedMsg(j) {   // what both steps show once the draft is published
  return draftHead(j) + `<div class="okmsg">Published. Teachers and students now see this timetable.</div>
    <div class="row" style="margin-top:8px"><a href="/timetable" target="_blank"><button class="primary">Open the timetable</button></a></div>`;
}
function draftHTML(j) {   // {head: the school, the counts, the configuration line (in the upload card); warns: the Warnings tab of the board's side panel; changes: its Changes tab; foot: the notes of the upload and the way to step 9, at the foot of the timetable card}
  const list = (xs, more) => `<ul>${xs.map(x => `<li>${esc(x)}</li>`).join("")}${more ? `<li>…and ${more} more</li>` : ""}</ul>`;
  const head = draftHead(j);
  if (j.published) return { head: publishedMsg(j) + `<p class="muted small">Its downloads and the personal student codes are on step 9.</p>`, warns: "", changes: "", foot: "" };
  const ws = j.warnings || [], c = Draft.counts(ws), f = S.dfilter === "all" ? "all" : "open", n = j.open ?? c.open, nc0 = j.critical ?? c.critical, n5 = j.step5 ?? c.step5;   // the server counts the step 5 decisions whose warning has gone
  const bd = S.board && S.board.data, mark = S.board ? S.board.wmark : null, hp = S.help;   // hp: the helper, its ways open under one warning
  const row = w => { const d = w.decision && w.decision.answer, ans = Draft.answerText(w);
    return `<li class="warn ${w.strength === "Prefer" ? "prefer" : ""}${mark === w.key ? " on" : ""}" data-wkey="${esc(w.key)}">${warnHead(w)}
      <div class="row warnbtns">${bd && bdWhere(w, bd) ? `<button data-bdshow="${esc(w.key)}">Show me</button>` : ""}${fxCan(w) ? `<button data-fxways="${esc(w.key)}"${hp && hp.warn === w.key ? ` class="on" aria-expanded="true"` : ` aria-expanded="false"`}>Ways to settle this</button>` : ""}${w.ops !== null && w.ops !== undefined && d !== "step5" ? `<button data-decide="step5|${esc(w.key)}">Update step 5</button>` : ""}${d === "met" ? `<button data-decide="open|${esc(w.key)}">Reopen</button>` : d === "step5" || d === "fixed" || !/:again$/.test(w.key) ? "" : `<button data-decide="met|${esc(w.key)}">Still met</button>`}${ans ? `<span class="chip decision ${esc(d)}">${esc(ans)}</span>` : ""}</div>${hp && hp.warn === w.key && !hp.settled ? fxWaysHTML(hp) : ""}</li>`; };
  const groups = Draft.group(ws, f), nc = (j.not_checked || []), listed = new Set([].concat(...groups.map(k => [].concat(...k.groups.map(g => g.items.map(w => w.key))))));
  const loose = hp && hp.warn && (hp.settled || !listed.has(hp.warn)) ? fxWaysHTML(hp) : "";   // the ways of a warning that has left the list (settled) or is not shown by the filter: at the top
  const kinds = groups.map(k => `<details open class="warnkind"><summary class="sev">${esc(k.title)} · ${k.groups.reduce((a, g) => a + g.items.length, 0)}</summary>
      ${k.groups.map(g => `<h4>${esc(g.name)}</h4><ul class="warnlist">${g.items.map(row).join("")}</ul>`).join("")}
      ${k.kind === "rule" && nc.length ? `<p class="muted small">Not checked here:</p><ul class="muted small">${nc.map(x => `<li>${esc(typeof x === "string" ? x : x.text || x.rule || JSON.stringify(x))}</li>`).join("")}</ul>` : ""}</details>`).join("")
    + (!groups.length && nc.length ? `<details open class="warnkind"><summary class="sev">Rules</summary><p class="muted small">Not checked here:</p><ul class="muted small">${nc.map(x => `<li>${esc(typeof x === "string" ? x : x.text || x.rule || JSON.stringify(x))}</li>`).join("")}</ul></details>` : "");
  const no = Draft.others(ws);   // the open warnings that are not critical, counted on their own
  const warns = `<p class="warnsum"><span class="${nc0 ? "pbcrit" : ""}">${nc0} critical</span> · <b>${no} other warning${no === 1 ? "" : "s"} open</b> · ${n5} settled on step 5</p>
      <div class="row warnfilter">${[["open", "Open"], ["all", "All"]].map(([v, l]) => `<label class="radio"><input type="radio" name="dfilter" data-dfilter="${v}"${v === f ? " checked" : ""}> ${l}</label>`).join("")}</div>`
    + loose + (kinds || (ws.length ? `<p class="muted">Nothing in this list.</p>` : `<div class="okmsg">No warnings: no teacher, class, room or student is double-booked, and the timetable matches the setup.</div>`))
    + (G.st && G.st.typed ? fxAskHTML(fxHelp()) : "");   // the typed request, at the foot of the tab
  const foot = (j.after && j.after.length ? `<details><summary>${j.after.length} lesson${j.after.length === 1 ? " is" : "s are"} after school</summary>${list(j.after)}</details>` : "")
    + (j.notes && j.notes.length ? `<details><summary>Notes</summary>${list(j.notes)}</details>` : "")
    + ruleReportHTML(j.rule_report || [], j.typed || 0) + choicesUsedHTML(j.choices_used || [], j.choice_problems || [], j.choices || 0)
    + `<p class="muted small" style="margin-top:8px">${esc(Draft.gateText(nc0))} Publish is on step 9.</p>
    <div class="row"><a href="/draft/preview" target="_blank" rel="noopener" title="Opens in a new tab: the timetable as teachers and students would see it, from the draft as it is now. Nothing is published."><button>Preview as it will be published</button></a><button class="primary" data-step="${stepAt("publish")}">Go to step 9</button></div>`;
  return { head: head + otherSchool(j) + configLine(j), warns, changes: fixesHTML(j), foot };
}
/* step 9: what will be published, read-only. Every critical mistake with a way back to step 8, every other open warning, the
   fixes, and the Publish button (off while a critical mistake remains; the server refuses as well) */
function publishHTML(j) {
  if (!j && loadingDraft()) return `<h2>The timetable to publish</h2>${LOADING}`;
  if (!j) return `<h2>The timetable to publish</h2><p class="muted">Nothing to publish yet. Upload a timetable on step 8.</p><div class="row"><button data-step="${stepAt("edit")}">Go to step 8</button></div>`;
  if (j.published) return publishedMsg(j);
  const ws = j.warnings || [], crit = Draft.critical(ws), nc = j.critical ?? crit.length, fl = j.fixes || [], pub = G.st && G.st.published, gate = Draft.gateText(nc);
  const row = (w, show) => `<li class="warn ${w.strength === "Prefer" ? "prefer" : ""}">${warnHead(w)}
      ${show ? `<div class="row warnbtns">${Draft.fixTarget(w) ? `<button data-pbshow="${esc(w.key)}">Show on step 8</button>` : `<button data-pbfind="${esc(w.key)}">Find it on step 8</button>`}</div>` : ""}</li>`;
  const groups = Draft.group(ws.filter(w => !w.crit), "open"), nw = groups.reduce((a, k) => a + k.groups.reduce((b, g) => b + g.items.length, 0), 0);
  const kinds = groups.map(k => { const m = k.groups.reduce((a, g) => a + g.items.length, 0);
    return `<details ${m > 20 ? "" : "open"} class="warnkind"><summary class="sev">${esc(k.title)} · ${m}</summary>${k.groups.map(g => `<h4>${esc(g.name)}</h4><ul class="warnlist">${g.items.map(w => row(w, false)).join("")}</ul>`).join("")}</details>`; }).join("");
  return draftHead(j) + otherSchool(j) + configLine(j)
    + `<h3 class="sev ${nc ? "crit" : ""}" style="margin-top:14px">Critical mistakes · ${nc}</h3>`
    + (nc ? `<ul class="warnlist">${crit.map(w => row(w, true)).join("")}</ul>` : `<p class="okmsg">Nothing critical.</p>`)
    + `<h3 class="sev">Warnings · ${nw}</h3>` + (kinds || `<p class="muted small">No open warnings.</p>`)
    + `<h3 class="sev">Changes made in the app · ${fl.length}</h3>` + (fl.length ? fixList(fl) : `<p class="muted small">No fixes have been made in the app.</p>`)
    + (nc ? `<p class="issue crit" style="margin-top:12px">${esc(gate)}</p>`
        : `<p class="muted small" style="margin-top:12px">${pub ? `Publishing replaces the timetable published ${esc(pub.at)}${pub.source ? ` (from ${esc(pub.source)})` : ""}.` : "Nothing is published yet."}</p>`)
    + `<div class="row"><button class="primary" id="pbPublish"${nc ? ` disabled title="${esc(gate)}"` : ""}>Publish this timetable</button><a href="/draft/preview" target="_blank" rel="noopener" title="Opens in a new tab: the timetable as teachers and students would see it, from the draft as it is now. Nothing is published."><button>Preview as it will be published</button></a></div><p class="muted small" id="pbMsg"></p>`;
}
const unplacedText = n => n === 1 ? "1 lesson is not placed. Place it or delete it on step 8 first." : `${n} lessons are not placed. Place them or delete them on step 8 first.`;   // the server's own sentence (draft.NotPlaced)
function printoutsCard() {   // while a lesson waits in Not placed, the printouts and the download are refused: the sentence stands in their place
  const n = (S.draft && S.draft.unplaced) || 0;
  if (n) return `<div class="card" style="margin-top:16px"><h2>Printouts</h2><p class="issue crit" id="pbUnplaced">${esc(unplacedText(n))}</p></div>`;
  return `<div class="card" style="margin-top:16px"><h2>Printouts</h2><p class="muted">Every timetable of the draft, with the changes made in the app, as PDFs (one page per class, teacher, room and student), one Excel file with them all, a searchable HTML page and the database, to keep or share.</p>
    <div class="row" style="margin-top:10px"><label><input type="checkbox" id="pbSingle" checked> Also a separate PDF for every class, teacher, room and student</label></div>
    <div class="row" style="margin-top:12px"><button class="primary" id="pbPrint">Make printouts (.zip)</button><span class="muted" id="pbPrintMsg"></span></div>
    <p class="small"><a href="/api/draft/download" id="pbDownload">Download the draft (.sqlite)</a> <span class="muted">to carry on elsewhere.</span></p></div>`;
}
/* ---------------- step 8: the helper ("Ways to settle this", under a warning of the board's Warnings tab) and the typed request (at the
   foot of that tab). S.help = {warn (the key of the warning whose ways are open, or null), was ({key, kind, where, text}: that warning,
   followed after each change with Draft.follow), changed (its new sentence when it changed), settled, ways ({key, answer}), waysFail,
   pre ({fixes, answer}: the open preview), preWant, preId (the way it is shown under), words, ans, pick, askN, askBusy, askWords}.
   Made when first needed (fxHelp); fetches happen in the handlers, drawing only reads it. */
const FX_BREAK = { F: "Assembly", R: "Recess", U: "Lunch", W: "Recess window", ".": "No lesson" };
const FX = { busy: false };
function fxBusy(v) { FX.busy = v; bdBusy(); }   // every sender sets it here, so the board's buttons that post follow it
const FX_BROKE = "Something went wrong working that out. The suggestions below still work.";   // the server's own sentence for a fault (typed.BROKE)
const fxShorts = () => { const m = {}; ((S.spec && S.spec.teachers) || []).forEach(t => { if (t.name && t.short) m[t.name] = t.short; }); return m; };
const fxDot = st => `<i class="dot ${esc(Grid.stateClass(st))}"></i>`;
const fxHelp = () => S.help || (S.help = { warn: null, was: null, changed: "", settled: false, ways: null, waysFail: false, waysN: 0, pre: null, preWant: null, preId: null, words: "", ans: null, pick: {}, askN: 0, askBusy: false, askWords: "" });
function fixesHTML(j) {   // the Changes tab: undo of the last change, the changes made in the app, newest first, and the fixes that could not be applied
  const fl = j.fixes || [], dis = FX.busy ? " disabled" : "";
  return (fl.length
      ? `<div class="row"><button data-bdundo="1"${dis}>Undo the last timetable change</button></div>${fixList(fl, true)}`
      : `<p class="muted small">No changes have been made in the app yet.</p>`)
    + (j.fix_problems || []).map(x => `<p class="issue">${esc(x)}</p>`).join("");
}
/* a warning the helper can work on: one about a class or a teacher (Draft.fixTarget), not a lesson waiting in Not placed, not settled on step 5 or marked met */
const fxCan = w => { const d = w.decision && w.decision.answer; return !!Draft.fixTarget(w) && w.crit !== "notplaced" && d !== "step5" && d !== "fixed" && d !== "met"; };
function fxSugHTML(f, x, id) {   // one checked suggestion: the sentence, what it disturbs, its state, Preview and Apply, and its preview under it when open. id finds it again in fxSuggestion
  return `<div class="fxway"><div class="small"><b>${esc(x.text)}</b></div>${(x.disturbs || []).length ? `<ul class="small muted">${x.disturbs.map(d => `<li>${esc(d)}</li>`).join("")}</ul>` : ""}
        <div class="row">${Draft.stateWord(x.state) ? `<span class="fxstate small">${fxDot(x.state)} ${esc(Draft.stateWord(x.state))}</span>` : ""}<button data-fxshow="${id}"${f.preId === id && f.preWant ? ` class="on" aria-expanded="true"` : ""}>Preview</button><button class="primary" data-fxapply="${id}">Apply</button></div>${f.preId === id ? fxPreHTML(f) : ""}</div>`;
}
/* the box for a typed request, at the foot of the Warnings tab, only when the server says it is on (G.st.typed). S.help holds words (the
   box's text), ans (the answer), pick (choices settled so far), askN (drops a late answer) and askBusy. Everything in the answer is text
   from the server: esc() everywhere. */
function fxAskHTML(f) {
  if (!(G.st && G.st.typed)) return "";
  const a = f.ans, bad = a && a.ok === false;
  let out = "";
  if (bad) out = `<p class="muted small">${esc(a.error)}</p>`;
  else if (a) {
    const hasSug = (a.groups || []).some(g => (g.suggestions || []).length);
    out = `<p class="small">${esc(Draft.askSummary(a))}</p>`
      + (a.problems || []).map(x => `<p class="small">${esc(x)}</p>`).join("")
      + (a.choices || []).map((c, ci) => `<div class="fxchoice"><p class="small">Which ${esc(Draft.choiceWord(c.field))} did you mean by "${esc(c.said)}"?</p><div class="row">${(c.options || []).map((o, oi) => `<button data-fxpick="${ci}|${oi}">${esc(o)}</button>`).join("")}</div></div>`).join("")
      + (a.groups || []).map((g, gi) => `<div class="fxgroup"><p class="small"><b>${esc(g.text)}</b></p>${(g.suggestions || []).map((x, si) => fxSugHTML(f, x, `a${gi}.${si}`)).join("")}${g.none ? `<p class="small">${esc(g.none)}</p>` : ""}</div>`).join("")
      + (a.narrow ? `<p class="small">${esc(a.narrow)}</p>` : "")
      + (hasSug ? `<p class="muted small">These are suggestions from your words. Nothing changes until you press Apply.</p>` : "");
  }
  return `<div class="fxask"><h4>Ask in words</h4><textarea id="fxAskIn" rows="3" maxlength="300" aria-label="Say what you want changed" placeholder="Say what you want changed, for example: move PE for 2A off Friday">${esc(f.words)}</textarea><div class="row fxaskgo"><button id="fxAsk"${f.askBusy ? " disabled" : ""}>${f.askBusy ? "Reading…" : "Ask"}</button></div>${out}</div>`;
}
function fxAskClear(f) { f.ans = null; f.pick = {}; f.askN++; f.askBusy = false; if (f.preId && f.preId[0] === "a") fxPreClear(f); }   // the answer goes (the timetable changed under it); the words stay
async function fxAsk(choice) {   // choice: [choice index, option index] when the lead answered a question: asked again with the same ask and the picks so far
  const f = fxHelp(); if (f.askBusy) return;
  let body;
  if (choice) {
    const c = f.ans && f.ans.ask && (f.ans.choices || [])[choice[0]], o = c && (c.options || [])[choice[1]]; if (o === undefined) return;
    f.pick = Object.assign({}, f.pick, { [c.id]: o }); body = { words: f.askWords, ask: f.ans.ask, pick: f.pick };
  } else {
    const w = String(f.words || "").trim(); if (!w) return;
    f.pick = {}; f.askWords = w; body = { words: w };
  }
  if (f.preId && f.preId[0] === "a") fxPreClear(f);   // a preview of the answer that goes
  const n = ++f.askN; f.askBusy = true; f.ans = null; fxDraw();
  let ans;
  try {
    const r = await fetch("/api/draft/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.status === 401) { location.href = "/login"; return; }
    const j = await r.json().catch(() => ({}));
    ans = r.status >= 500 ? { ok: false, error: "Could not reach the server." } : r.ok || j.error ? j : { ok: false, error: "Something went wrong." };
    if (!r.ok || (ans.ok !== true && ans.ok !== false)) ans.ok = false;
    if (ans.ok === false && !ans.error) ans.error = FX_BROKE;
  } catch (e) { ans = { ok: false, error: "Could not reach the server: " + e.message }; }
  if (S.help !== f || f.askN !== n) return;   // gone, or asked again, meanwhile
  f.askBusy = false; f.ans = ans; fxDraw();
}
function fxWaysHTML(f) {   // the helper's block under the warning it was opened on (or at the top of the tab once that warning has left the list): Close, then the ways, each already checked
  if (!f || !f.warn) return "";
  const a = fxWaysOf(f);
  let body;
  if (f.settled) body = `<p class="small"><b>Settled.</b></p>`;
  else if (!a) body = f.waysFail ? `<p class="issue small">Could not load the ways.</p>` : `<p class="muted small">Looking for ways…</p>`;
  else {
    const sg = a.suggestions || [], bl = a.blocked || [];
    body = sg.map((x, i) => fxSugHTML(f, x, String(i))).join("")
      + (a.none ? `<p class="small">${esc(a.none)}</p>` : "")
      + (!sg.length && bl.length ? `<p class="small">The nearest ways, and what each breaks:</p><ul class="small">${bl.map(x => `<li>${esc(x.text)} <span class="muted">${esc(x.why)}</span></li>`).join("")}</ul>` : "");
  }
  const said = f.settled && f.was ? `<p class="small muted">${esc(f.was.text)}</p>` : f.changed ? `<p class="small">This warning has changed: ${esc(f.changed)}</p>` : "";
  return `<div class="fxways" id="fxWays"><div class="row fxwaystop"><b>Ways to settle this</b><button data-fxwaysclose="1">Close</button></div>${said}${body}</div>`;
}
function fxSmallHTML(c) {   // one class's week as a read-only table (about 250 px a week; it scrolls sideways inside the panel), the lessons the preview marks outlined
  const shorts = fxShorts();
  return Grid.weeks(c.days).map(wk => {
    const cell = k => {
      if (k.covered) return "";
      if (k.lessons.length) return `<td class="fxc has" rowspan="${k.rowspan}">${k.lessons.map(r => { const mc = Grid.markClass(r), was = Grid.wasText(r, c.days);
        return `<div class="fxl${mc ? ` mk-${mc}` : ""}" title="${esc([Grid.fullLabel(r), was].filter(Boolean).join(" · "))}">${esc(Grid.label(r, shorts))}</div>`; }).join("")}</td>`;
      return `<td class="fxc${FX_BREAK[k.code] && k.code !== "." ? " brk" : ""}"></td>`;
    };
    return `<div class="fxsm"><h5>${esc(c.name)}${wk.name ? ` · ${esc(wk.name)} week` : ""}</h5><div class="fxwrap"><table class="fxgrid" style="min-width:${28 + wk.days.length * 44}px"><tr><th></th>${wk.days.map(d => `<th>${esc(d.label)}</th>`).join("")}</tr>${Grid.table(c, wk).map((r, p) => `<tr><th class="fxp">${p}</th>${r.map(cell).join("")}</tr>`).join("")}</table></div></div>`;
  }).join("");
}
function fxPreHTML(f) {   // Before you apply: what the fixes would do, drawn from the preview answer kept in S.help, under the way it is for
  if (!f.preWant) return "";
  if (!f.pre) return `<div class="fxpre"><h4>Before you apply</h4><p class="muted small">Loading the preview…</p></div>`;
  const a = f.pre.answer, ok = a.state === "ok" || a.state === "prefer", cls = a.classes || [], gone = a.gone || [];
  return `<div class="fxpre"><h4>Before you apply</h4>
    <ul class="small">${(a.texts || []).map(t => `<li>${esc(t)}</li>`).join("")}</ul>
    <p class="small">${fxDot(ok ? a.state : "no")} ${esc(ok ? Draft.stateWord(a.state) : a.why || "These fixes are not open.")}</p>
    ${cls.length || gone.length ? `<p class="muted small">Outlined: lessons that move, change or are new.</p>` : ""}
    ${cls.map(fxSmallHTML).join("")}
    ${gone.length ? `<ul class="small">${gone.map(g => `<li>${esc(g.what)} is deleted from ${esc(g.cls)}.</li>`).join("")}</ul>` : ""}
    <div class="row">${ok ? `<button class="primary" data-fxpreapply="1">Apply</button>` : ""}<button data-fxprecancel="1">Cancel</button></div></div>`;
}
const fxPreClear = f => { f.pre = null; f.preWant = null; f.preId = null; };
function fxDraw() { if (S.board) bdSideDraw(); else drawDraft(); }   // the panel again (the Warnings tab holds the ways and the typed box); the board's rows are not touched
function fxReveal(el) {   // el brought into view inside the panel's own scrolling body, its top first (the ways: with their warning and its buttons); the page and the board do not move for it
  if (el && el.id === "fxWays" && el.closest("li.warn")) el = el.closest("li.warn");
  const y = el && el.closest(".bdsbody"); if (!y) return;
  const r = el.getBoundingClientRect(), t = y.getBoundingClientRect();
  if (r.bottom > t.bottom) y.scrollTop += Math.min(r.bottom - t.bottom, r.top - t.top);
  else if (r.top < t.top) y.scrollTop += r.top - t.top;
}
async function fxGet(url) {
  try {
    const r = await fetch(url), j = await r.json().catch(() => ({}));
    if (r.status === 401) { location.href = "/login"; return null; }
    if (!r.ok) { toast(j.error || "Something went wrong."); return null; }
    return j;
  } catch (e) { toast("Could not reach the server: " + e.message); return null; }
}
const fxQ = o => Object.keys(o).map(k => `${k}=${encodeURIComponent(o[k])}`).join("&");
const fxWaysOf = f => f.ways && f.ways.key === f.warn ? f.ways.answer : null;   // the ways only while they are for the warning open now
async function fxWays(f) {   // the ways to settle the open warning; an answer for another warning, or older than the last fetch (waysN), is dropped
  const asked = f.warn, n = ++f.waysN; f.ways = null; f.waysFail = false; if (!asked) return;
  const j = await fxGet("/api/draft/suggest?" + fxQ({ key: asked }));
  if (S.help !== f || f.warn !== asked || f.waysN !== n) return;
  f.ways = j ? { key: asked, answer: j } : null; f.waysFail = !j;
}
function fxShut(f) { f.waysN++; f.warn = null; f.was = null; f.changed = ""; f.ways = null; f.waysFail = false; f.settled = false; if (f.preId && f.preId[0] !== "a") fxPreClear(f); }   // the ways closed (a preview of the typed answer stays)
function fxOpenWays(key) {   // "Ways to settle this": the ways open under that warning and are fetched; a second click shuts them; another warning's shuts the first
  const f = fxHelp(), w = ((S.draft && S.draft.warnings) || []).find(x => x.key === key), was = f.warn === key && !f.settled;
  fxShut(f);
  if (was || !w) { fxDraw(); return; }
  f.warn = key; f.was = { key, kind: w.kind, where: w.where || null, text: w.text };
  fxDraw(); fxReveal($("#fxWays"));
  fxWays(f).then(() => { if (S.help === f && f.warn === key) { fxDraw(); fxReveal($("#fxWays")); } });
}
async function fxPreview(fixes, id) {   // what the fixes would do, shown under the way id; nothing is changed. An answer for other fixes is dropped
  const f = fxHelp(); if (FX.busy) { toast(BDWHY.busy); return; }   // a change is being saved: the preview would be of the timetable before it
  const asked = JSON.stringify(fixes); f.preWant = asked; f.preId = id; f.pre = null; fxDraw();
  let j = null; try { j = await post("/api/draft/preview", { fixes }); } catch (e) { toast("Could not reach the server: " + e.message); }
  if (S.help !== f || f.preWant !== asked || f.preId !== id) return;
  if (j) f.pre = { fixes, answer: j }; else fxPreClear(f);
  fxDraw(); fxReveal($("#bdSide .fxpre"));
}
async function fxApply(fixes) {   // one or two fixes together, as received; all or nothing
  const f = fxHelp(); if (FX.busy) { toast(BDWHY.busy); return; }
  fxBusy(true);
  try {
    const j = await post("/api/draft/fixes", { fixes });
    if (j) { f.reveal = true; await fxAfter(j); if (S.help === f) fxReveal($("#fxWays")); if (f.settled || !f.warn) f.reveal = false; }   // the ways (or "Settled.") brought into view in the panel, again when the new ways come
    else {   // refused: the sentence is toasted; the draft and the ways are fetched again (the list may have changed under them)
      fxPreClear(f); f.ways = null; f.waysFail = false; fxAskClear(f);   // the typed answer too: it is as stale as the ways. The old Preview and Apply buttons are not live while the new ways load
      const d = await fxGet("/api/draft"); if (S.help !== f) return;
      if (d && d.warnings) { S.draft = d; poll(); bdSync(); fxFollow(f, d.warnings); }
      drawDraft();
      if (f.warn && !f.settled) fxWays(f).then(() => { if (S.help === f) fxDraw(); });
    }
  } catch (e) { toast("Could not reach the server: " + e.message); } finally { fxBusy(false); }
}
function fxFollow(f, warnings) {   // the warning the ways are open for, found again in the list: its key carried on, or the changed warning taken; false when it is gone (settled)
  if (!f.warn) return false;
  const r = Draft.follow(f.was, warnings); f.settled = !r;
  if (!r) return false;
  const w = warnings.find(x => x.key === r.key);
  f.warn = r.key; f.was = { key: w.key, kind: w.kind, where: w.where || null, text: w.text };
  if (r.how === "changed") f.changed = w.text;
  return true;
}
async function fxAfter(j) {   // every new draft answer comes here (the helper's, the board's senders', a colleague's change): the lists and the board, then the open ways followed and fetched again
  const f = S.help; S.draft = j; poll(); bdSync();
  if (f) {
    fxPreClear(f); fxAskClear(f);
    if (f.warn) { fxFollow(f, j.warnings); f.ways = null; f.waysFail = false; }
  }
  drawDraft();
  if (f && f.warn && !f.settled) fxWays(f).then(() => { if (S.help === f) { fxDraw(); if (f.reveal) fxReveal($("#fxWays")); } f.reveal = false; });   // not awaited: the board is free at once
}
function fxSuggestion(f, i) {   // "3": the ways' third; "a1.0": the typed answer's second lesson, first suggestion
  if (/^a\d+\.\d+$/.test(i)) { const [g, k] = i.slice(1).split(".").map(Number), a = f.ans && f.ans.ok !== false && f.ans.groups; return a && a[g] && (a[g].suggestions || [])[k] || null; }
  const a = fxWaysOf(f); return a && (a.suggestions || [])[Number(i)] || null;
}
function fxClick(b) {   // true when the click was the helper's or the typed request's
  const d = b.dataset;
  if (d.fxways !== undefined) { fxOpenWays(d.fxways); return true; }
  const f = S.help; if (!f) return false;
  if (b.id === "fxAsk") { fxAsk(); return true; }
  if (d.fxpick !== undefined) { fxAsk(d.fxpick.split("|").map(Number)); return true; }
  if (d.fxshow !== undefined) {   // Preview: opens Before you apply under that way; a second click shuts it
    if (f.preId === d.fxshow && f.preWant) { fxPreClear(f); fxDraw(); return true; }
    const x = fxSuggestion(f, d.fxshow); if (x) fxPreview(x.fixes, d.fxshow); return true;
  }
  if (d.fxapply !== undefined) { const x = fxSuggestion(f, d.fxapply); if (x) fxApply(x.fixes); return true; }
  if (d.fxwaysclose !== undefined) { fxShut(f); fxDraw(); return true; }
  if (d.fxpreapply !== undefined) { if (f.pre) fxApply(f.pre.fixes); return true; }
  if (d.fxprecancel !== undefined) { fxPreClear(f); fxDraw(); return true; }
  return false;
}
function fxKeep(draw) {   // the typed box (and the buttons that answer it) keeps the focus and the caret across a redraw; its text comes back from S.help.words
  const a = document.activeElement, mine = a && a.matches && a.matches("#fxAskIn, #fxAsk, [data-fxpick]"), caret = mine && a.id === "fxAskIn" ? [a.selectionStart, a.selectionEnd] : null;
  draw();
  const inp = mine && $("#fxAskIn");
  if (inp && document.activeElement !== inp) { inp.focus({ preventScroll: true }); const n = inp.value.length; try { inp.setSelectionRange(caret ? caret[0] : n, caret ? caret[1] : n); } catch (e) { } }
}
/* step 8's board: the whole school's timetable for one day (a row per class, the periods across), or one class's whole cycle
   (a row per day), drawn from the cards of GET /api/draft/board and laid out by Board (board.js). S.board lives while step 8 is
   open with a draft: {data, mode, find, fold, sel, slots, slotsFor, fail, ...}. The cycle mode also keeps d, the day to go back to.
   A card in the air (drag: dragged; wait: its drop waits for its slots) keeps the board drawn as it is: a board fetched meanwhile
   waits in next (changed: it came during this drag; lost: it is of another upload, so the card is gone) until the drag ends.
   The lessons not placed are cards of their own (d and p null) in the Not placed tray beside the rows; bdCard finds them too. ask: the
   question of a click or drop where another lesson is ({id, slot, q}); step: the counter being stepped through (its fade lasts while a
   card is selected). */
const BD = { gen: 0, sp: null, dragEl: null, tabT: 0, over: 0 };   // gen: the board fetch now; sp: the slots fetched for that board, by card id (bdSlotsP); dragEl: the element being dragged (kept in its place while the board is drawn again under it, bdKeep); tabT: the half second over a day's tab; over: when the last dragover came
/* the rows of the board are by class (the default: a mode or a row with no by), by teacher or by room (mode.by); the choice lives in
   S.board.mode, so it lasts through a redraw and a fetch and goes when step 8 is left */
const BDROWS = [["class", "Classes"], ["teacher", "Teachers"], ["room", "Rooms"]];
const BDALL = { class: "All classes", teacher: "All teachers", room: "All rooms" };
const BDKIND = { class: ["class", "classes"], teacher: ["teacher", "teachers"], room: ["room", "rooms"] };   // what a folded group hides
const bdBy = () => (S.board && S.board.mode.by) || "class";
const bdFoldKey = (by, name) => by === "class" ? name : `${by}:${name}`;   // a level folds by its name, a department or a kind of room by its own
const bdRowData = el => ({ cls: el.dataset.cls || "", by: el.dataset.by || "class", name: el.dataset.name || "" });   // what a row's element says it is
const bdInRow = (c, r) => r.by === "teacher" || r.by === "room" ? Board.of(c, r).length > 0 || (r.name === "" && !(c.rows || []).length) : Board.onRow(c, r, S.board.data);   // card c is in that row
function bdKeep(box) {   // the board drawn again under a drag (another day): Chromium ends a drag whose element leaves its place in the page (moved or removed), so the part holding it stays where it is, hidden and without its ids, until the drag ends; the rest is drawn anew after it
  [...box.children].forEach(x => {
    if (x.classList.contains("bdold")) return;
    if (x.contains(BD.dragEl)) { x.classList.add("bdold"); x.setAttribute("aria-hidden", "true"); x.querySelectorAll("[id]").forEach(y => y.removeAttribute("id")); }
    else x.remove();
  });
  box.insertAdjacentHTML("beforeend", bdHTML());
}
function bdUnkeep() { document.querySelectorAll("#bdBox .bdold").forEach(x => x.remove()); BD.dragEl = null; }
const bdShowable = () => !!(S.draft && !S.draft.published && !S.practice);
const bdSig = j => JSON.stringify([j.upload_id, j.uploaded_at, j.fixes, j.setup_version]);   // which draft a board was fetched for (upload_id: each upload's own; null for a draft saved before there were ids), and the setup it was checked against
function bdEnsure(id, opening) {   // the board exists on step 8 with a draft, and nowhere else; it is fetched again whenever it is not for the draft the page has (every place that takes a new draft ends here, through drawDraft, render, or bdSync); opening: the step is being drawn, so a failed fetch is tried again
  if (id !== "edit" || !bdShowable()) { if (S.board) { S.board = null; BD.gen++; } return; }
  if (!S.board) S.board = { data: null, mode: { kind: "day", d: 0 }, find: "", fold: {}, sel: null, slots: null, slotsFor: null, asking: null, failFor: null, held: null, drag: null, grab: 0, hv: "", ask: null, pt: "", note: "", fail: false, sig: null, up: undefined, loading: null, next: null, wait: null, changed: false, lost: false, step: null, del: null, mouse: null, tabHv: null, reveal: false, side: null, wmark: null, show: null, redraw: false, from: null };
  if (S.board.sig !== bdSig(S.draft) || (opening && S.board.fail)) bdLoad();
}
const bdWanted = () => { const b = S.board; return b.held !== null ? b.held : b.sel; };   // the card whose slots are wanted: the one pressed, else the one selected
const bdSync = () => { bdEnsure(STEPS[S.step][0], false); bdMount(); };
function bdMount() {   // the card is there when there is a board, and gone when there is not
  bdEnsure(STEPS[S.step][0], false);
  const box = $("#bdBox");
  if (!S.board) { if (box) box.remove(); return; }
  if (box) return;
  const at = $("#printouts"); if (!at) return;
  at.insertAdjacentHTML("afterend", `<div class="card" id="bdBox"></div>`); bdDraw();
}
const bdEntry = id => typeof id === "string" && id.slice(0, 2) === "a:";   // the id of an entry of the tray's "Step 5 asks for these": "a:" and its step 5 key (it is not a lesson, so it has no number)
const bdId = el => { const v = el.dataset.card; return bdEntry(v) ? v : Number(v); };   // the id a card's element carries
function bdCard(id) {   // a card on the board or in the Not placed tray; an entry of step 5's list is a card with no place (d and p null), its classes, n, what, and entry: the step 5 row
  const d = S.board && S.board.data; if (!d) return null;
  if (bdEntry(id)) { const s = (d.short || []).find(x => "a:" + x.key === id); return s ? { id, d: null, p: null, n: s.n, classes: s.classes || [], what: s.name, rows: [], entry: s } : null; }
  return d.cards.find(c => c.id === id) || (d.unplaced || []).find(c => c.id === id) || null;
}
const bdInTray = c => !!c && (c.d === null || c.d === undefined);
const bdClasses = d => [].concat(...(d.levels || []).map(lv => lv.classes));
async function bdLoad() {   // the board again for the draft the page has; with a card in the air the drag is kept, and the board is drawn when it ends (bdNext)
  const b = S.board; if (!b) return;
  const gen = ++BD.gen, up = S.draft.upload_id || null, air = b.drag !== null || !!b.wait, other = b.up !== undefined && b.up !== up;   // up: the upload the board is for (undefined: none yet)
  b.sig = bdSig(S.draft); b.up = up;
  if (b.ask || b.del) toast("The timetable changed. Ask again.");
  if (other) { b.sel = null; b.note = ""; if (air) b.lost = true; }   // lesson ids restart with each upload: the old id may now be another lesson
  b.slots = null; b.slotsFor = null; b.asking = null; b.ask = null; b.del = null; b.failFor = null; b.hv = "";   // the slots belong to the draft they were asked on; their colours go at once
  if (air) { b.changed = true; b.pt = b.lost ? BDWHY.gone : BDWHY.changed; bdOver(null); } else { b.drag = null; b.pt = ""; }
  bdPaint(); if (air) { bdLineDraw(); bdWant(); }   // in the air: the dragged card's slots for the new draft are fetched at once
  const pr = b.loading = fxGet("/api/draft/board"), j = await pr;
  if (b.loading === pr) b.loading = null;
  if (S.board !== b || gen !== BD.gen) return;   // the step was left, or a newer fetch is out
  const got = j && Array.isArray(j.cards) ? j : { fail: true };
  if (got.fail || b.drag !== null || b.wait) b.show = null;   // a Show me waiting for this board is dropped: it is not jumped to later, unasked
  if (b.drag !== null || b.wait) { b.next = got; return; }   // a redraw would end the drag: drawn when it ends
  bdTake(got); bdDraw(); bdWant(); bdReveal();
  if (b.show && b.data) bdShowWarning(b.show.key, b.show.stay);   // step 9's Show on step 8, waiting for the board
}
function bdShowTray(id) {   // step 9's "Show on step 8" on a lesson not placed: it is selected in the tray and the board scrolled into view, once the board is in
  const b = S.board; if (!b) return;
  b.sel = id; b.ask = null; b.del = null; b.note = ""; b.step = null; b.reveal = true; b.side = "tray";
  if (b.data && !b.loading) { if (!bdCard(id)) b.sel = null; else bdLessonOpen(id, false); bdDraw(); bdWant(); bdReveal(); }   // the tray stays shown; the Lesson tab is there to open
}
function bdReveal() {
  const b = S.board; if (!b || !b.reveal || !b.data) return;
  b.reveal = false;
  const box = $("#bdBox"); if (!box) return;
  box.scrollIntoView({ block: "start" });
  const el = box.querySelector("#bdTray .bdcard.sel"); if (el) el.scrollIntoView({ block: "nearest" });
}
function bdTake(j) {   // a fetched board becomes the one shown (j.fail: it could not be fetched)
  const b = S.board; b.next = null; b.changed = false; b.lost = false;
  if (j.fail) { b.data = null; b.fail = true; return; }
  b.data = j; b.fail = false;
  const last = (j.days || []).length - 1;
  if (b.mode.kind === "cycle" && bdBy() === "class" && !bdClasses(j).includes(b.mode.cls)) b.mode = { kind: "day", d: b.mode.d };   // a teacher's or room's cycle stays, its row empty when the name has gone
  if (!(b.mode.d >= 0 && b.mode.d <= last)) b.mode.d = 0;   // a day past the last (or none at all) becomes the first
  if (b.sel !== null && !bdCard(b.sel)) b.sel = null;
  if (!Board.finds(j).some(o => o.value === b.find)) b.find = "";
  if (bdLessonOn(b)) bdLessonFetch();   // a change (this page's or a colleague's): the selected lesson's choices again
}
function bdNext() {   // a drag has ended: the board that came during it is drawn, or the draft's lists and marks that changed during it
  const b = S.board; if (!b) return false;
  if (b.next) { bdTake(b.next); bdDraw(); bdWant(); return true; }
  if (b.redraw && b.drag === null) { bdDraw(); return true; }
  return false;
}
function bdDraw() {   // #bdBox again, the board kept where it was scrolled
  const box = $("#bdBox"); if (!box || !S.board) return;
  const w = box.querySelector(".bdmain:not(.bdold) .bdwrap"), pos = w ? [w.scrollLeft, w.scrollTop] : null, y = window.scrollY, side = bdSideAt();
  S.board.redraw = false;
  fxKeep(() => { if (S.board.drag !== null && BD.dragEl && box.contains(BD.dragEl)) bdKeep(box); else box.innerHTML = bdHTML(); });
  const w2 = box.querySelector(".bdmain:not(.bdold) .bdwrap"); if (w2 && pos) { w2.scrollLeft = pos[0]; w2.scrollTop = pos[1]; }
  bdSideBack(side);
  window.scrollTo(window.scrollX, y); bdPaint();
}
const bdPal = (d, ln) => { const p = (d.palette || [])[ln.color] || (d.palette || [])[0] || null; return p ? `background:#${esc(p[0])};border-left:3px solid #${esc(p[1])}` : ""; };
const bdWas = (d, c) => c.was && c.was.d !== null && c.was.d !== undefined ? `was ${(d.days || [])[c.was.d] || ""} period ${c.was.p}` : "";   // where a lesson in the tray was
function bdCardClass(c, d, b, hit) {   // a card's classes: selected, faded by Find or by the counter being stepped through (hit: the ids it counts), outlined red when critical
  return "bdcard" + (b.sel === c.id ? " sel" : "") + (Board.matches(c, b.find, d) ? "" : " fade") + (hit && !hit.has(c.id) ? " cfade" : "") + (!bdInTray(c) && Board.critical(c) ? " crit" : "");
}
function bdPieces(row, d, b, hit, warned) {   // warned: the open warnings by lesson id (Board.warned)
  const st = [];
  row.cards.forEach(x => {
    const c = x.card, bx = Board.box(c, d.NP), ln = Board.lines(c, d, row), pal = bdPal(d, ln), bg = Board.flag(c, warned);
    const time = ((d.times || [])[c.p] || [])[0] || "", day = (d.days || [])[c.d] || "";
    const tip = [c.what, `${day} period ${c.p}${time ? ` (${time})` : ""}`, ln.title].concat(ln.lines, [c.why || ""], (warned[c.id] || []).map(w => w.text)).filter(Boolean).join("\n");
    const badge = bg && bg.text ? `<em class="bdbadge${bg.crit ? " crit" : " warn"}">${esc(bg.text)}</em>` : "";
    st.push(`<button class="${bdCardClass(c, d, b, hit)}" data-card="${c.id}" draggable="true" title="${esc(tip)}" style="grid-column:${bx.from + 2}/${bx.to + 3};grid-row:${x.lane + 2}${pal ? `;${pal}` : ""}">${badge}<b>${esc(ln.title)}</b>${ln.lines.map(l => `<span>${esc(l)}</span>`).join("")}</button>`);
  });
  return st.join("");
}
function bdTrayHTML(b, hit) {   // the Not placed tray beside the rows: the lessons lifted or pushed out, a group per first class, each saying where it was
  const d = b.data, gs = Board.tray(d);
  const body = gs.length ? gs.map(g => `<div class="bdtgrp"><b>${esc(g.cls || "No class")}</b>${g.cards.map(c => {
    const ln = Board.lines(c, d), was = bdWas(d, c), pal = bdPal(d, ln);
    return `<button class="${bdCardClass(c, d, b, hit)} tray" data-card="${c.id}" draggable="true" title="${esc([c.what, was].filter(Boolean).join("\n"))}"${pal ? ` style="${pal}"` : ""}><b>${esc(ln.title)}</b>${ln.lines.map(l => `<span>${esc(l)}</span>`).join("")}${was ? `<span class="bdwas">${esc(was)}</span>` : ""}</button>`;
  }).join("")}</div>`).join("") : `<p class="muted small">Nothing is waiting.</p>`;
  const sh = d.short || [], asks = sh.length ? `<h3 class="bdshort">Step 5 asks for these</h3>${sh.map(s => {   // the lessons step 5 asks for that the timetable lacks: selected and dragged like a card of the tray, and added where they go
    const c = bdCard("a:" + s.key), per = `${s.n} period${s.n === 1 ? "" : "s"}`, has = `has ${s.have} of ${s.want}`;
    return `<button class="${bdCardClass(c, d, b, hit)} tray short" data-card="${esc(c.id)}" draggable="true" title="${esc(`${s.name} · ${per}\n${has}`)}"><b>${esc(s.name)} · ${esc(per)}</b><span>${esc(has)}</span></button>`;
  }).join("")}` : "";
  return `<div id="bdTray">${body}${asks}</div>`;
}
function bdRowHTML(row, b, cycle, hit, warned) {   // a class's row, or a teacher's or room's (by, name: "" for "No teacher" / "No room"); a row's label opens its whole cycle
  const d = b.data, by = row.by || "class", open = by === "class" ? `data-bdcls="${esc(row.cls)}"` : `data-bdname="${esc(row.name)}"`;
  const lab = cycle || row.key === "" ? `<span class="bdlab">${esc(row.label)}</span>` : `<button class="bdlab" ${open} title="Show ${esc(row.label)} for the whole cycle">${esc(row.label)}</button>`;
  let cells = "";
  let strip = "";
  for (let p = 0; p < d.NP; p++) {
    cells += `<i class="bdcell${Board.open(row.codes.charAt(p)) ? "" : " brk"}" data-p="${p}" style="grid-column:${p + 2};grid-row:2/span ${row.lanes}"></i>`;
    strip += `<i class="bdmark" data-p="${p}" style="grid-column:${p + 2};grid-row:1"></i>`;   // the fit strip: a mark a period, above the cards, coloured while a card is selected
  }
  return `<div class="bdrow" data-row="${esc(row.key)}" data-d="${row.d}" data-cls="${esc(row.cls)}" data-by="${by}" data-name="${esc(row.name || "")}" style="grid-template-columns:var(--bdlab) repeat(${d.NP},minmax(var(--bdw),1fr));grid-template-rows:var(--bdstrip) repeat(${row.lanes},minmax(var(--bdh),auto))">${lab}${strip}${cells}${bdPieces(row, d, b, hit, warned)}</div>`;
}
const bdHitSet = b => b.step && b.data ? new Set(Board.hits(b.data, b.step).map(c => c.id)) : null;   // the ids the counter being stepped through counts
const bdWarned = () => Board.warned((S.draft && S.draft.warnings) || []);
const bdParts = () => S.draft ? draftHTML(S.draft) : { head: "", warns: "", changes: "", foot: "" };
function bdHTML() {   // the timetable card: the board with its side panel, the notes of the upload and the way to step 9
  const b = S.board, d = b.data, parts = bdParts(), head = `<div class="bdtitle"><h2>The timetable</h2></div>`;
  const tail = `<div id="bdFoot">${parts.foot}</div>`;
  if (b.sel === null) b.step = null;   // a counter's fade lasts while its card is selected
  if (!d) return head + `<div class="bdmain"><p class="muted bdnone">${b.fail ? "The timetable could not be loaded. Open the step again." : "Loading the timetable…"}</p>${bdSideHTML(b, null, parts)}</div>` + tail;
  const weeks = Grid.weeks(d.days || []), m = b.mode, cycle = m.kind === "cycle";
  const hit = bdHitSet(b), warned = bdWarned();
  const tabs = weeks.map(w => `<span class="bdweek">${weeks.length > 1 ? `<span class="muted small">${esc(w.name)}</span>` : ""}${w.days.map(x => `<button class="bdtab${!cycle && x.i === m.d ? " on" : ""}" data-bdday="${x.i}">${esc(x.label)}</button>`).join("")}</span>`).join("");
  const finder = `<label class="bdfind">Find a subject: <select id="bdFind">${Board.finds(d).map(o => `<option value="${esc(o.value)}"${o.value === b.find ? " selected" : ""}>${esc(o.label)}</option>`).join("")}</select></label>`;
  const by = bdBy(), who = by === "class" ? m.cls : m.name ? m.name : by === "teacher" ? "No teacher" : "No room";
  const rows = `<div class="row bdrows"><span>Rows:</span>${BDROWS.map(([k, l]) => `<button data-bdrows="${k}" class="${k === by ? "on" : ""}" aria-pressed="${k === by}">${l}</button>`).join("")}</div>`;
  const controls = rows + `<div class="row bdctl">${cycle ? `<button data-bdall="1">${BDALL[by]}</button><b>${esc(who)}: the whole cycle</b>` : tabs}${finder}</div>`;
  const hdr = `<div class="bdhead" style="grid-template-columns:var(--bdlab) repeat(${d.NP},minmax(var(--bdw),1fr))"><span class="bdcorner"></span>${(d.times || []).slice(0, d.NP).map((t, p) => `<div class="bdph">${p}<small>${esc(t[0] || "")}</small></div>`).join("")}</div>`;
  const body = Board.groups(d, m, weeks).map(g => {
    const fk = bdFoldKey(by, g.name), folded = !cycle && !!b.fold[fk], k = g.rows.length, kind = BDKIND[by];
    const gh = cycle || (by !== "class" && !g.name) ? (cycle && g.name ? `<div class="bdgrp"><span>${esc(g.name)}</span></div>` : "")   // the "No teacher" / "No room" row has no heading
      : `<div class="bdgrp"><button data-bdfold="${esc(fk)}" aria-expanded="${!folded}">${folded ? "▸" : "▾"} ${esc(g.name)}${folded ? ` (${k} ${k === 1 ? kind[0] : kind[1]} hidden)` : ""}</button></div>`;
    return gh + (folded ? "" : g.rows.map(r => bdRowHTML(r, b, cycle, hit, warned)).join(""));
  }).join("");
  return head + controls + bdCountersHTML(d) + `<div class="bdsel" id="bdLine" aria-live="polite">${bdLineHTML()}</div>
    <div class="bdmain"><div class="bdwrap"><div class="bdin${by === "class" ? "" : " people"}" style="min-width:calc(var(--bdlab) + ${d.NP} * var(--bdw))">${hdr}${body}</div></div>${bdSideHTML(b, hit, parts)}</div>` + tail;
}
/* the side panel beside the board (under it on a narrow window): three tabs, and a fourth, Lesson, while a lesson is selected by a click
   (bdLessonOpen); the one chosen kept while step 8 is open; with none chosen,
   Not placed while lessons wait, else Warnings. It is as tall as the board and scrolls inside itself, so the rows never move. The whole
   panel takes a card dragged from the board as a lift, whatever tab is showing. */
function bdSideTab(b) {
  bdLessonSync(b);
  if (b.side) return b.side;
  const n = b.data ? (b.data.unplaced || []).length : (S.draft && S.draft.unplaced) || 0;
  return n ? "tray" : "warn";
}
function bdSideHTML(b, hit, parts) {
  const d = b.data, j = S.draft, tab = bdSideTab(b), ws = (j && j.warnings) || [];
  const nU = d ? (d.unplaced || []).length : (j && j.unplaced) || 0, nW = j ? (j.open ?? Draft.counts(ws).open) : 0, nC = j ? Draft.batches(j.fixes || []).length : 0;   // the entries the list shows (fixes made together are one)
  const all = [["tray", "Not placed", nU], ["warn", "Warnings", nW], ["changes", "Changes", nC]].concat(b.lesson ? [["lesson", "Lesson", null]] : []);   // Lesson only while its lesson is selected (bdSideTab)
  const tabs = all.map(([k, l, n]) => `<button role="tab" class="bdstab${k === tab ? " on" : ""}" data-bdside="${k}" aria-selected="${k === tab}">${esc(l)}${n === null ? "" : ` ${n}`}</button>`).join("");
  const body = tab === "lesson" ? bdLessonHTML(b) : tab === "tray" ? (d ? bdTrayHTML(b, hit) : `<p class="muted small">Loading the timetable…</p>`) : tab === "warn" ? parts.warns : parts.changes;
  return `<div id="bdSide" data-tab="${tab}"><div class="bdstabs" role="tablist">${tabs}</div><p class="bdtdrop">Drop here to lift it out.</p><div class="bdsbody">${body}</div></div>`;
}
const bdSideAt = () => { const el = $("#bdSide"), y = el && el.querySelector(".bdsbody"); return el && y ? { tab: el.dataset.tab, top: y.scrollTop } : null; };   // the tab shown and how far it is scrolled
function bdSideBack(at) { const el = $("#bdSide"), y = el && el.querySelector(".bdsbody"); if (at && y && el.dataset.tab === at.tab) y.scrollTop = at.top; }
function bdSideDraw() {   // the panel alone (a tab chosen, the draft's lists changed): the board's rows are not touched
  const b = S.board, el = $("#bdSide"); if (!b || !el) return;
  if (BD.dragEl && el.contains(BD.dragEl)) { b.redraw = true; return; }   // a card of the tray is in the air: drawn when it lands
  const at = bdSideAt(); fxKeep(() => { el.outerHTML = bdSideHTML(b, bdHitSet(b), bdParts()); bdSideBack(at); }); bdPaint();
}
/* the Lesson tab: the selected lesson's teachers and room chosen from lists, with "None"; a band has a block per group. b.lesson = {id, back
   (the tab open before it, shown again when the selection closes), order (its groups, the row it was clicked on first in the Teachers or
   Rooms rows), open (the blocks shown open: the first three), got (by group: GET /api/draft/lesson's answer, "loading" or "fail"), all (by
   group: "all this group's lessons" ticked, for the next room choice), n (the fetch round: an answer of an older round is dropped)} */
const bdLessonOn = b => !!(b && b.lesson && b.sel === b.lesson.id && bdCard(b.lesson.id));
function bdLessonSync(b) {   // the tab goes with its lesson: once that lesson is not selected (closed, another selected, gone) the tab open before it is shown again
  if (!b.lesson || bdLessonOn(b)) return;
  if (b.side === "lesson") b.side = b.lesson.back;
  b.lesson = null;
}
function bdLessonOpen(id, show) {   // a click, a counter's step or Show me selected lesson id: its tab, shown unless show is false; a step 5 entry has none
  const b = S.board, c = bdCard(id); if (!b || !c || c.entry) return;
  const back = b.lesson && b.side === "lesson" ? b.lesson.back : b.side, f = b.from, by = bdBy(), rows = c.rows || [];
  const first = by !== "class" && f && f.id === c.id && f.by === by ? Board.of(c, f) : [];
  const order = first.concat(rows.filter(r => !first.includes(r))).map(r => r.group);
  b.lesson = { id, back, order, open: {}, got: {}, all: {}, n: 0 };
  order.slice(0, 3).forEach(g => { b.lesson.open[g] = true; });
  if (show) b.side = "lesson";
  bdLessonFetch();
}
async function bdQuiet(url) {   // a GET whose failure the page says itself: the answer, or null
  try {
    const r = await fetch(url), j = await r.json().catch(() => null);
    if (r.status === 401) { location.href = "/login"; return null; }
    return r.ok ? j : null;
  } catch (e) { return null; }
}
function bdLessonFetch(one) {   // the open blocks' choices, a new round (one: that group alone, in this round, when its block is opened)
  const b = S.board, L = b && b.lesson; if (!L) return;
  if (!one) { L.n++; L.got = {}; }
  const n = L.n;
  (one ? [one] : L.order.filter(g => L.open[g])).forEach(g => {
    L.got[g] = "loading";
    bdQuiet(`/api/draft/lesson?id=${encodeURIComponent(L.id)}&group=${encodeURIComponent(g)}`).then(j => {
      if (S.board !== b || b.lesson !== L || L.n !== n || !bdLessonOn(b)) return;   // another lesson, another round, or the selection closed
      L.got[g] = j && Array.isArray(j.teachers) && Array.isArray(j.rooms) ? j : "fail"; bdSideDraw();
    });
  });
}
function bdLessonHTML(b) {
  const L = b.lesson, c = bdCard(L.id), d = b.data, rows = c.rows || [], band = !!c.band || rows.length > 1;
  const was = bdInTray(c) ? bdWas(d, c) : "", where = bdInTray(c) ? `Not placed${was ? ` (${was})` : ""}` : `${(d.days || [])[c.d] || ""} period ${c.p}`;
  const ws = bdLineWarnings(c, Infinity), blocks = L.order.map(g => { const r = rows.find(x => x.group === g); return r ? bdLessonBlock(L, r, band) : ""; }).join("");
  return `<div class="bdles"><p class="bdlname"><b>${esc(c.what)}</b><br><span class="muted">${esc(where)}</span></p>${ws ? `<div class="bdlws">${ws}</div>` : ""}${blocks}</div>`;
}
function bdLessonBlock(L, r, band) {   // one group's lists (a plain lesson's one block has no heading); a band's closed block is its heading alone
  const g = r.group, open = !!L.open[g], j = L.got[g];
  const head = band ? `<button class="bdlhead" data-bdlopen="${esc(g)}" aria-expanded="${open}">${open ? "▾" : "▸"} ${esc(g)} · ${esc(r.subject || "")}</button>` : "";
  if (band && !open) return `<div class="bdlblk">${head}</div>`;
  const body = j === "fail" ? `<p class="bdwhy">${esc(BDWHY.lessonFailed)}</p>` : j && typeof j === "object" ? bdLessonLists(L, r, j) : `<p class="muted">Loading…</p>`;
  return `<div class="bdlblk">${head}${body}</div>`;
}
function bdLessonLists(L, r, j) {   // a list a teacher, one more to add a teacher, the count a change of teacher touches; the room's list and its tick box
  const g = esc(r.group), ts = r.teachers || [], p = Board.people(j), v = Board.venues(j), dis = FX.busy ? " disabled" : "";
  const opt = (val, text, on) => `<option value="${esc(val)}"${on ? " selected" : ""}>${esc(text)}</option>`;
  const group = (label, list) => list ? `<optgroup label="${esc(label)}">${list}</optgroup>` : "";
  const tList = (i, now) => {   // now: the teacher in this place ("" for the list that adds one); the row's other teachers are not offered
    const name = now ? "Teacher" : "Add a teacher";
    const ok = t => !ts.some((x, k) => k !== i && x === t.name), mark = t => t.name === now;
    const known = now && !j.teachers.some(t => t.name === now) ? opt("n:" + now, now, true) : "";   // a teacher the setup no longer lists
    const free = p.free.filter(ok).map(t => opt("n:" + t.name, t.name, mark(t))).join("");
    const busy = p.busy.filter(ok).map(t => opt("n:" + t.name, t.doing ? `${t.name} · ${t.doing}` : t.name, mark(t))).join("");
    return `<select data-bdlt="${g}" data-i="${i}" aria-label="${name}"${dis}>${now ? opt("none", "None", false) : opt("pick", "Choose a teacher", true)}${known}${group("Free then", free)}${group("Busy then", busy)}</select>`;
  };
  const room = r.room && r.room !== "TBC" ? r.room : "", rOpt = x => opt("r:" + x.room, x.free || !x.holding ? x.room : `${x.room} · ${x.holding}`, x.room === room);
  const rList = `<select data-bdlr="${g}" aria-label="Room"${dis}>${room ? opt("none", "None", false) : opt("pick", "Choose a room", true)}${room && !j.rooms.some(x => x.room === room) ? opt("r:" + room, room, true) : ""}`
    + `${group("Free, the right kind", v.right.map(rOpt).join(""))}${group("Free, another kind", v.other.map(rOpt).join(""))}${group("In use then", v.busy.map(rOpt).join(""))}</select>`;
  const n = j.n_lessons;
  return `<p class="bdlh">Teacher</p>${ts.map((t, i) => `<label class="bdll">${tList(i, t)}</label>`).join("")}<label class="bdll"><span>Add a teacher</span>${tList(ts.length, "")}</label>`
    + `<p class="muted bdlnote">A change of teacher changes ${n === 1 ? "this one lesson" : `all ${n} lessons`} of ${esc(Board.keyName(null, j.key))}.</p>`
    + `<p class="bdlh">Room</p><label class="bdll">${rList}</label><label class="bdlall"><input type="checkbox" data-bdlall="${g}"${L.all[r.group] ? " checked" : ""}${dis}> all this group's lessons</label>`;
}
function bdLessonTeacher(c, r, j, i, v) {   // a teacher list's choice: a free one at once, a busy one or none at all after the line's question
  const name = v === "none" ? "" : v.slice(2), fix = Board.teacherFix(j, r, i, name);
  if (!name) {
    if (fix.teachers.length) { bdLessonPost(c, fix, ""); return; }   // another teacher stays on it
    bdYesNo({ id: c.id, lesson: true, text: `Leave ${j.what} with no teacher? It cannot be published until it has one.`, yes: "Yes, leave it", run: () => bdLessonPost(c, fix, "") });
    return;
  }
  const t = j.teachers.find(x => x.name === name);
  if (t && !t.free) { bdYesNo({ id: c.id, lesson: true, text: `${name} is teaching ${t.doing}.${j.n_lessons > 1 ? ` ${BDWHY.otherTimes}` : ""}`, ask: BDWHY.anyway, yes: "Yes, give it", run: () => bdLessonPost(c, fix, name) }); return; }
  bdLessonPost(c, fix, "");
}
function bdLessonRoom(c, r, j, v, all) {   // the room list's choice ("None" asks nothing); a room in use then after the line's question
  const room = v === "none" ? "" : v.slice(2), fix = Board.roomFix(j, r, room, all), x = room ? j.rooms.find(y => y.room === room) : null;
  if (x && !x.free) {
    const h = String(x.holding || ""), text = !h || /\.$/.test(h) ? h || `${room} is in use then.` : `${room} holds ${h} then.`;   // holding is the judgement's own sentence when no lesson is in it
    if (all) { const b = S.board; b.ask = null; b.del = null; b.note = `${text} ${BDWHY.untick}`; bdLineDraw(); bdSideDraw(); return; }   // a room for all the group's lessons is never forced: the list goes back
    bdYesNo({ id: c.id, lesson: true, text, ask: BDWHY.useAnyway, yes: "Yes, use it", run: () => bdLessonPost(c, fix, room) });
    return;
  }
  bdLessonPost(c, fix, "");
}
/* a choice of the Lesson tab is posted; who: the busy teacher or room the person said yes to. The server then refuses with its own sentence
   (it knows the reason): when that names who as busy, the fix goes again forced with that sentence, without asking twice; any other
   refusal is said, and the list goes back (the board is fetched again). A room for all the group's lessons is never forced: refused because
   the room is in use, it was at another of the group's lessons (this one's was free), and the page says so. The lesson stays selected and
   its lists are fetched again */
async function bdLessonPost(c, fix, who) {
  const b = S.board; let why = null, other = null;
  const refused = s => {
    if (fix.all) { if (Board.busyRefusal(s, fix.room, "room")) { other = `${s} ${BDWHY.allOther}`; return true; } return false; }
    if (Board.busyRefusal(s, who, fix.kind)) { why = s; return true; } return false;   // only "{who} is teaching ... then." or "{who} is in use then."
  };
  let ok = await bdSend("/api/draft/fix", fix, c, false, { stay: true, refused });
  if (other !== null) { toast(other); if (S.board === b) bdLoad(); return; }   // the list goes back
  if (why !== null && S.board === b) ok = await bdSend("/api/draft/fix", Object.assign({}, fix, { force: true, why }), c, false, { stay: true });
  if (ok && S.board === b && b.lesson && b.lesson.id === c.id) { b.lesson.all = {}; bdSideDraw(); }   // the tick box is for one change
}
function bdDraftDraw() {   // the draft changed (a fix, an answer, a filter): the card again; with a card in the air only what does not hold it, the rest when it lands
  const b = S.board, box = $("#bdBox"); if (!b || !box) return;
  if (b.drag === null) { bdDraw(); return; }
  b.redraw = true; bdSideDraw();
  const foot = $("#bdFoot"); if (foot) foot.remove();
  box.insertAdjacentHTML("beforeend", `<div id="bdFoot">${bdParts().foot}</div>`);
}
const bdOpenWarnings = () => Draft.others((S.draft && S.draft.warnings) || []);   // the draft's open warnings that are not critical mistakes
function bdCountersHTML(d) {   // above the hint: what is wrong on the board, a button a kind; a click steps through its cards
  const n = Board.counts(d), w = bdOpenWarnings(), has = !!bdLastFix();
  const undo = `<button data-bdundo="1" class="bdundo${has ? "" : " gone"}"${has ? "" : ` aria-hidden="true" tabindex="-1"`}${FX.busy ? " disabled" : ""}>Undo the last timetable change</button>`;   // always in the row, hidden with no change: the row never changes height
  return `<div class="row bdcount">${Board.COUNTERS.map(([k, label]) => `<button data-bdcount="${k}" class="${n[k] ? (k === "noroom" ? "warn" : "crit") : ""}"${n[k] ? "" : ` aria-disabled="true"`}>${esc(label)} ${n[k]}</button>`).join("")}<button data-bdwarn="1">Other warnings ${w}</button>${undo}</div>`;
}
const bdLastFix = () => { const l = S.draft && S.draft.fixes; return l && l.length ? l[l.length - 1] : null; };
function bdLineHTML() {   // the one status line under the hint: the swap question, else the place under the pointer, else the selected card, else the last change
  const b = S.board, d = b.data; if (!d) return "";
  const c = b.sel !== null ? bdCard(b.sel) : null, day = x => (d.days || [])[x] || "";
  if (b.ask && b.ask.yes) {   // a yes or no question (bdYesNo): its sentence, small lines under it, the question itself, its Yes and Cancel
    const a = b.ask, dis = FX.busy ? " disabled" : "";
    return `<span>${esc(a.text)}</span>${(a.also || []).map(t => `<span class="muted small">${esc(t)}</span>`).join("")}${a.ask ? `<span class="bdq">${esc(a.ask)}</span>` : ""}<button data-bdyes="1"${dis}>${esc(a.yes)}</button><button data-bdcancel="1">Cancel</button>`;
  }
  if (b.ask) {   // a lesson dropped where another is: Swap, Put it beside, Push out, Cancel, as the place allows
    const q = b.ask.q, dis = FX.busy ? " disabled" : "";
    return `<span>${esc(q.text)}</span>${q.also.map(t => `<span class="muted small">${esc(t)}</span>`).join("")}${q.swap ? `<button data-bdswap="1"${dis}>${esc(q.swap)}</button>` : ""}${q.beside ? `<button data-bdbeside="1"${dis}>${esc(q.beside)}</button>` : ""}${q.push ? `<button data-bdpush="1"${dis}>${esc(q.push)}</button>` : ""}<button data-bdcancel="1">Cancel</button>`;
  }
  const k = b.del ? bdCard(b.del.id) : null;
  if (k) {   // "Delete this lesson" asks first, saying why when the delete is a "no": step 5 asks for the lesson, or the rule it breaks
    const no = b.del.j.state === "no", dis = FX.busy ? " disabled" : "";
    const why = b.del.j.why ? esc(b.del.j.why) : "", said = !no ? "" : b.del.j.plan ? `<span class="bdwhy">Step 5 asks for this lesson.</span>${why ? `<span class="muted small">${why}</span>` : ""}` : why ? `<span class="bdwhy">${why}</span>` : "";   // "Step 5 asks" only when the plan is the reason
    return `<span>${esc(`Delete ${k.what}?`)}</span>${said}<button data-bddelgo="1"${dis}>Delete</button><button data-bdcancel="1">Cancel</button>`;
  }
  if (b.pt) return `<span>${esc(b.pt)}</span>`;
  if (c) {
    const n = (c.rows || []).length, grp = c.band ? ` · ${n} group${n === 1 ? "" : "s"}` : "", note = b.note ? `<span class="muted small">${esc(b.note)}</span>` : "";
    const why = c.why ? `<span class="bdwhy">${esc(c.why)}</span>` : "", del = `<button data-bddel="1"${FX.busy ? " disabled" : ""}>Delete this lesson</button>`;
    const sw = bdBy() === "class" ? "" : `<span class="bdwhy">${esc(BDWHY.switch)}</span>`;   // a lesson of the tray or of step 5's list is placed from the Classes rows only
    if (c.entry) { const s = c.entry; return `${note}<span>${esc(s.name)} · ${s.n} period${s.n === 1 ? "" : "s"} · has ${s.have} of ${s.want}</span>${sw}<button data-bdclose="1">Close</button>`; }
    if (bdInTray(c)) { const was = bdWas(d, c); return `${note}<span>${esc(c.what)} · Not placed${was ? ` (${esc(was)})` : ""}${grp}</span>${sw}${del}<button data-bdclose="1">Close</button>`; }   // its warnings are in the Lesson tab
    const time = ((d.times || [])[c.p] || [])[0];
    return `${note}<span>${esc(c.what)} · ${esc(day(c.d))} period ${c.p}${time ? ` (${esc(time)})` : ""}${grp}</span>${why}
      <button data-bdlift="1"${FX.busy ? " disabled" : ""}>Lift out</button>${del}<button data-bdclose="1">Close</button>`;
  }
  return b.note ? `<span>${esc(b.note)}</span>` : `<span class="muted small">${BDHINT}</span>`;   // with nothing to say, the line holds the hint
}
function bdLineWarnings(c, most) {   // the selected lesson's open warnings, a short line each (a critical one led by its kind), at most most (3)
  const ws = bdWarned()[c.id] || [], max = most || 3;
  const line = w => { const k = w.crit ? Draft.critWord(w.crit) : "", t = String(w.text || ""); return k && t.indexOf(k + ":") !== 0 ? `${k}: ${t}` : t; };   // a sentence that already starts with its kind is not led twice
  return ws.slice(0, max).map(w => `<span class="bdlw${w.crit ? " crit" : ""}">${esc(line(w))}</span>`).join("") + (ws.length > max ? `<span class="bdlw muted">and ${ws.length - max} more in Warnings</span>` : "");
}
const BDHINT = "Drag a lesson to another time on its row, or click it and then click a place. Green is clean, amber bends a rule, red lands with a problem, blue has another lesson there and asks, grey cannot take it. Ctrl or Cmd+X lifts the selected lesson out; Ctrl or Cmd+V puts it where the pointer is; Ctrl or Cmd+Z undoes the last change.";
function bdLineDraw() { const el = $("#bdLine"); if (el && S.board && S.board.data) el.innerHTML = bdLineHTML(); }
function bdBusy() {   // a post starts or ends: the board's buttons that post follow it, without a redraw
  const box = $("#bdBox"); if (!box) return;
  box.querySelectorAll("[data-bdundo], [data-bdswap], [data-bdbeside], [data-bdpush], [data-bdyes], [data-bdlift], [data-bddel], [data-bddelgo], [data-bdlt], [data-bdlr], [data-bdlall]").forEach(x => { x.disabled = FX.busy; });
}
const BDST = ["own", "ok", "prefer", "no", "na", "ask"];
function bdPaint() {   // the cells and the strip of every row take the state of the card selected or pressed, and the cards it can be swapped with get an outline (classes only, so a drag in the air is not cancelled); rows it cannot be dropped on are dimmed
  const b = S.board, box = $("#bdBox"); if (!b || !b.data || !box) return;
  const id = bdWanted(), c = id !== null ? bdCard(id) : null, d = b.data, slots = c && b.slotsFor === c.id ? b.slots : null, cycle = b.mode.kind === "cycle";
  box.querySelectorAll(".bdrow").forEach(r => {
    const rd = bdRowData(r), day = Number(r.dataset.d), people = rd.by !== "class", tray = !!c && bdInTray(c);
    const ok = !!c && (people ? !tray : Board.onRow(c, rd, d));   // a teacher's or room's row takes a drop of a lesson on the board (a hand-over on another row); a lesson of the tray is placed from the Classes rows
    r.classList.toggle("dim", !!c && !ok);
    const strip = ok && (!people || cycle || bdInRow(c, rd));   // in the day view only the rows the lesson is in show where it fits, on that row's day as its class's row would
    const st = strip && slots ? Board.states(c, slots, day, d.NP) : null;
    const paint = x => {
      BDST.forEach(k => x.classList.remove(k));
      const s = st && st[Number(x.dataset.p)]; if (s) x.classList.add(s);
      return s;
    };
    r.querySelectorAll(".bdcell").forEach(paint);
    r.querySelectorAll(".bdmark").forEach(x => {
      const s = paint(x);
      if (s) x.title = bdTell(Board.slot(c, slots, day, Number(x.dataset.p)), c); else x.removeAttribute("title");
    });
  });
  const tg = {};
  box.querySelectorAll(".bdcard").forEach(x => {
    const k = bdId(x), t = slots && !bdInTray(c) && k !== c.id ? (k in tg ? tg[k] : (tg[k] = Board.target(slots, k))) : null;
    x.classList.toggle("sel", b.sel !== null && k === b.sel);
    x.classList.toggle("swap", !!t); x.classList.toggle("swapok", !!t && t.state === "ok"); x.classList.toggle("swapprefer", !!t && t.state === "prefer");
  });
}
function bdSlotsP(id) {   // where card id may go in the draft of the board now: one fetch a card and board, shared by every asker (a press, a selection, a drop); null when it could not be had, and then asked again the next time
  if (!BD.sp || BD.sp.gen !== BD.gen) BD.sp = { gen: BD.gen, by: {}, got: {}, del: {} };
  const sp = BD.sp;
  if (!sp.by[id]) {
    const c = bdEntry(id) ? bdCard(id) : null; if (bdEntry(id) && !c) return Promise.resolve(null);
    const url = c ? `/api/draft/options?add=${encodeURIComponent(c.entry.key)}&n=${encodeURIComponent(c.entry.n)}` : "/api/draft/slots?id=" + encodeURIComponent(id);   // an entry of step 5's list: where a lesson of its row can be added
    sp.by[id] = fxGet(url).then(j => { if (!j || !Array.isArray(j.slots)) return null; if (j.delete) sp.del[id] = j.delete; return j.slots; }, () => null)
      .then(s => { if (s) sp.got[id] = s; else delete sp.by[id]; return s; });
  }
  return sp.by[id];
}
const bdSlotsHad = id => BD.sp && BD.sp.gen === BD.gen ? BD.sp.got[id] || null : null;
const bdDelOf = id => BD.sp && BD.sp.gen === BD.gen ? BD.sp.del[id] || null : null;   // the delete's judgement, which comes with the lesson's slots: {state, why}
function bdPre(id) {   // the slots of a pressed card, fetched aside (the selected card keeps its own) until the card is selected or dragged
  const b = S.board; if (!b) return;
  const gen = BD.gen;
  bdSlotsP(id).then(s => { if (s && S.board === b && gen === BD.gen && bdWanted() === id && b.slotsFor !== id) { b.slots = s; b.slotsFor = id; b.asking = null; b.failFor = null; bdPaint(); } });
}
async function bdWant() {   // fetch where the wanted card may go, unless it is already here for this draft; an answer for another card is dropped
  const b = S.board; if (!b || !b.data) return;
  const id = bdWanted();
  if (id === null) { b.slots = null; b.slotsFor = null; b.asking = null; bdPaint(); return; }
  if (b.slotsFor === id || b.asking === id) { bdPaint(); return; }
  const had = bdSlotsHad(id);
  if (had) { b.slots = had; b.slotsFor = id; b.asking = null; b.failFor = null; bdPaint(); return; }
  b.slots = null; b.slotsFor = null; b.asking = id; b.failFor = null; bdPaint();
  const gen = BD.gen, s = await bdSlotsP(id);
  if (S.board !== b || gen !== BD.gen || b.asking !== id) return;
  b.asking = null;
  if (bdWanted() !== id) { bdWant(); return; }
  if (!s) { b.failFor = id; return; }
  b.slots = s; b.slotsFor = id; bdPaint();
}
function bdPeriodAt(row, x) {   // the period under a pointer's x on a row, from where the row's cells are; -1 left of the row label's right edge (a sideways scroll hides periods under it)
  const cells = row.querySelectorAll(".bdcell"); if (!cells.length) return 0;
  const lab = row.querySelector(".bdlab"); if (lab && x < lab.getBoundingClientRect().right) return -1;
  const a = cells[0].getBoundingClientRect(), z = cells[cells.length - 1].getBoundingClientRect(), w = (z.right - a.left) / cells.length;
  return Math.max(0, Math.min(cells.length - 1, Math.floor((x - a.left) / (w || 1))));
}
const BDWHY = { class: "A lesson stays with its class. Drop it on its own row.", classClick: "A lesson stays with its class. Click a place on its own row.", wait: "Still working out where this lesson fits.", failed: "Where this lesson fits could not be loaded. Click the lesson again.", none: "That lesson cannot go there.",
  working: "Working out where this lesson fits…", changed: "The timetable changed. Working out where this lesson fits…", gone: "The timetable changed. Try again.", busy: "Wait for the last change to finish.", lift: "Drop here to lift it out.",
  taken: "Another lesson is there. Lift it out first.", paste: "Point at a place on its row, then paste.", delWait: "Still working out…",
  off: "Drop it on its row, or on the panel to lift it out.", offTray: "Drop it on its row.", noUndo: "There is nothing to undo on the timetable.",
  there: "Working out what can be done there…", thereTell: "Another lesson is there. Drop or click to see what can be done.", what: "Working out what changes…",
  switch: "Switch to Classes rows to place it.", nothing: "That changes nothing.", two: "Two changes were made; undo each.", anyway: "Give it anyway?",
  whatFailed: "What this changes could not be loaded. Try again.", handLost: "The timetable could not be loaded, so the lesson was not handed over.",
  lessonFailed: "The lesson's choices could not be loaded. Click the lesson again.", useAnyway: "Use it anyway?",
  untick: "Untick “all this group's lessons” to use it anyway.", allOther: "That is at another of this group's lessons.", otherTimes: "It may clash at other times too." };
const bdLen = c => Number(c.n) > 0 ? Number(c.n) : 1;
const bdTaken = (c, s) => S.board.data.cards.some(x => x.d === s.d && (x.classes || []).some(k => c.classes.includes(k)) && x.p < s.p + bdLen(c) && s.p < x.p + bdLen(x));   // another lesson of the classes of c is in the periods it would take
function bdSlotAt(c, at) {   // what the board knows of a place at = {cls, d, p, over} (over: the lesson under the pointer, or null): {slot, why}; why is the sentence's key when the lesson cannot go there
  const b = S.board, d = b.data;
  if (b.lost) return { slot: null, why: "gone" };
  if (bdInTray(c) && (at.by || "class") !== "class") return { slot: null, why: "switch" };   // a lesson of the tray or of step 5's list: from the Classes rows only
  if (!Board.onRow(c, { cls: at.cls, by: at.by }, d)) return { slot: null, why: "class" };
  if (b.slotsFor !== c.id || !b.slots) return { slot: null, why: b.failFor === c.id ? "failed" : "wait" };
  const slot = Board.aim(c, b.slots, at.d, at.p, bdInTray(c) ? null : at.over);   // a lesson from the tray is placed, never swapped
  return Object.assign({ slot }, bdJudge(c, slot));
}
const bdAsks = (c, s) => { const a = Board.asks(s); return a && bdInTray(c) ? Object.assign({}, a, { swap: false }) : a; };
function bdJudge(c, s) {   // what a click or a drop on place s does: act "ask" (another lesson is there: the question), "move" (it lands, forced when red), or why it is refused
  if (!s) return { why: "none" };
  if (s.state === "own") return { why: "own" };
  if (c.entry && bdTaken(c, s)) return { why: "taken" };   // a lesson of step 5's list is added only where its classes are free
  const a = bdAsks(c, s);
  if (a) { const q = Board.question(c, s, S.board.data); return (a.swap && q.swap) || (a.beside && q.beside) || (a.push && q.push) ? { act: "ask" } : { why: "stuck" }; }
  if (bdThere(s)) return { act: "fetch" };   // another lesson is there and what can be done is judged on request (bdPlace)
  if (Board.lands(s)) return { act: "move" };
  return { why: "slot" };
}
const bdThere = s => !!s && s.state !== "own" && !s.push && Array.isArray(s.there) && s.there.length > 0;   // a place with another lesson, not judged yet
const bdTell = (s, c) => bdThere(s) ? BDWHY.thereTell : Board.tell(s, S.board.data.days || [], c);   // what the line says over a place
const bdHit = e => { const t = e.target; if (!(t.closest && t.closest(".bdold"))) return t; return document.elementFromPoint(e.clientX, e.clientY) || t; };   // what is under a drag's pointer: Chromium may still send a drag's events to the board as it was before it was drawn again under the drag (hidden now), so then it is found by the point
const bdUnder = (row, e) => { const t = bdHit(e), el = t.closest && t.closest(".bdcard"); return el && row.contains(el) ? Number(el.dataset.card) : null; };   // the lesson under the pointer on this row
const bdPlaceAt = (row, p, e) => Object.assign(bdRowData(row), { d: Number(row.dataset.d), p, over: e ? bdUnder(row, e) : null });   // a place of the board {cls, by, name, d, p, over}, kept apart from the row's element (a redraw replaces it)
function bdWhyText(a, drag) {
  if (a.why === "class") return drag ? BDWHY.class : BDWHY.classClick;
  if (a.why === "own") return Board.tell(a.slot, S.board.data.days);
  if (a.why === "slot") return a.slot.why || BDWHY.none;
  if (a.why === "stuck") return `Another lesson is there and it cannot be moved out: ${(a.slot.push && a.slot.push.why) || a.slot.why || ""}`.trim();
  return BDWHY[a.why] || BDWHY.none;
}
/* hand: {from, to} when the place is on another teacher's (or room's) row than the one the lesson was taken from: the change of time
   is made first (its own question included) and the hand-over is asked after it (bdTimeThen) */
function bdAct(c, a, drag, end, hand) {   // a judged place: ask, make the change, or say why not; end: when a waiting drop's 8 seconds are up
  if (a.why) { if (a.why !== "own") toast(bdWhyText(a, drag)); return; }
  const b = S.board;
  if (a.act === "fetch") { bdAskPlace(c, a.slot, drag, end, hand); return; }
  if (a.act === "ask") { b.ask = { id: c.id, slot: a.slot, q: Board.question(c, a.slot, b.data), hand: hand || null }; b.del = null; bdLineDraw(); return; }
  bdTimeThen(c, c.entry ? Board.addFix(c.entry, a.slot, "move") : Board.fix(c, a.slot, "move"), hand);
}
function bdTry(c, at, drag, end, hand) { bdAct(c, bdSlotAt(c, at), drag, end, hand); }   // a change of time: a place was clicked or dropped on
const BD_STOP = {};   // a wait that ended without an answer to go on with (said already, or the step was left)
async function bdHold(text, pr, end, late) {   // the board takes no other change while pr is fetched, at most until end (else 8 seconds), and the line says text; the answer, or BD_STOP; late: what is said when time runs out
  const b = S.board, tok = {}, gen = BD.gen, until = end || Date.now() + 8000;
  b.wait = tok; b.pt = text; bdLineDraw();
  const r = await Promise.race([pr, new Promise(res => setTimeout(() => res(BD_STOP), Math.max(0, until - Date.now())))]);
  if (S.board !== b || b.wait !== tok) return BD_STOP;
  b.wait = null; b.pt = ""; if (!bdNext()) { bdLineDraw(); bdPaint(); }
  if (r === BD_STOP) { toast(late || BDWHY.failed); return BD_STOP; }
  if (gen !== BD.gen) { toast(BDWHY.gone); return BD_STOP; }   // another draft came meanwhile: the answer was for the old one
  return r;
}
async function bdPlace(card, d, p) {   // the one slot at (d, p) for the card with its push out and place beside judged (GET /api/draft/place), or null with the server's sentence said
  const j = await fxGet(`/api/draft/place?id=${encodeURIComponent(card.id)}&d=${encodeURIComponent(d)}&p=${encodeURIComponent(p)}`);
  return j && typeof j.state === "string" ? j : null;
}
async function bdAskPlace(c, s, drag, end, hand) {   // a click or a drop on a blue place: it is judged on request, then goes on as a judged place (the question, or why not)
  const r = await bdHold(BDWHY.there, bdPlace(c, s.d, s.p), end);
  if (r === BD_STOP || !r) return;
  const k = bdCard(c.id); if (!k) { toast(BDWHY.gone); return; }
  bdAct(k, Object.assign({ slot: r }, bdJudge(k, r)), drag, end, hand);
}
function bdYesNo(q) {   // the line asks a yes or no: q = {id (the lesson asked about), text, also (small lines), ask (the question itself, or none), yes (its button), run (on yes)}; Cancel and Escape withdraw it, as a new draft does
  const b = S.board; if (!b) return;
  b.ask = Object.assign({ also: [], ask: "" }, q); b.del = null; bdLineDraw();
}
const bdFromRow = c => {   // the teacher's or room's row lesson c was taken from (selected or dragged there), else its first teacher's or room's; null on class rows and for the tray
  const b = S.board, by = bdBy(); if (by === "class" || !c || bdInTray(c)) return null;
  const f = b.from; if (f && f.id === c.id && f.by === by && bdInRow(c, f)) return { by, name: f.name };
  const r = (c.rows || [])[0];
  return { by, name: !r ? "" : by === "teacher" ? (r.teachers || [])[0] || "" : r.room && r.room !== "TBC" ? r.room : "" };
};
const bdHandOf = (c, at) => {   // {from, to} when a place is on another row of the same kind and the lesson would change hands there, else null
  const from = bdFromRow(c), to = { by: at.by || "class", name: at.name || "" };
  return from && to.by === from.by && to.name !== from.name && Board.hand(c, from, to, S.board.data) ? { from, to } : null;
};
const bdHandOnly = (c, at) => !!bdHandOf(c, at) && at.d === c.d && at.p === c.p;   // on another row at the lesson's own time: a hand-over only
function bdGo(c, at, drag, end) {   // a place clicked or dropped on: along the lesson's own row a change of time; on another teacher's or room's row a hand-over, after the change of time when the period differs
  const hand = bdHandOf(c, at);
  if (!hand) {
    const from = bdFromRow(c);
    if (from && (at.by || "class") === from.by && at.name !== from.name && at.d === c.d && at.p === c.p) { toast(BDWHY.nothing); return; }   // a teacher already on it, the same room
    bdTry(c, at, drag, end); return;
  }
  if (at.d === c.d && at.p === c.p) { bdHandAsk(c, hand.from, hand.to, null, end, false); return; }
  bdTry(c, at, drag, end, hand);
}
function bdTimeThen(c, fix, hand) {   // a change of time; with hand, the hand-over is asked after it: a plain clean move waits for the answer and both go as one batch; a forced move, a swap or a push is made first on its own
  if (!hand) { bdSend("/api/draft/fix", fix, c); return; }
  if (fix.kind === "move" && !fix.force && !fix.push) { bdHandAsk(c, hand.from, hand.to, fix); return; }
  bdSend("/api/draft/fix", fix, c).then(ok => { if (ok) bdHandNext(c.id, hand); });
}
async function bdHandNext(id, hand) {   // the change of time was made: once the board has it, the hand-over is asked
  const b = S.board; if (!b) return;
  if (b.loading) {   // the board is held while the new board comes: bdLoad, which was waiting on it first, keeps it for the end of the hold, which draws it
    const r = await bdHold(BDWHY.what, b.loading.catch(() => null), undefined, BDWHY.handLost);
    if (r === BD_STOP) return;   // said already
  }
  if (S.board !== b || b.ask) return;
  if (!b.data) { toast(BDWHY.handLost); return; }
  const c = bdCard(id); if (!c || bdInTray(c)) return;
  if (!Board.hand(c, hand.from, hand.to, b.data)) { toast(BDWHY.nothing); return; }
  bdHandAsk(c, hand.from, hand.to, null, undefined, true);
}
/* the hand-over's question: Board.handText with the count of lessons a change of teacher touches (GET /api/draft/lesson); pending: a
   plain move posted with it as one batch; made: a change of time was made just before it, on its own */
async function bdHandAsk(c, from, to, pending, end, made) {
  const b = S.board, fix = Board.hand(c, from, to, b.data); if (!fix) { toast(BDWHY.nothing); return; }
  let n = 1;
  if (fix.kind === "teacher") {
    const r = Board.of(c, from)[0] || (c.rows || [])[0], j = await bdHold(BDWHY.what, fxGet(`/api/draft/lesson?id=${encodeURIComponent(c.id)}&group=${encodeURIComponent(r ? r.group : "")}`), end, BDWHY.whatFailed);
    if (j === BD_STOP || !j || typeof j.n_lessons !== "number") return;   // said already
    n = j.n_lessons;
  }
  const days = b.data.days || [], also = pending ? [`Yes also moves it to ${days[pending.d] || ""} period ${pending.p}.`] : [];
  bdYesNo({ id: c.id, text: Board.handText(c, from, to, n), also, yes: "Yes", run: () => bdHandGo(c, fix, pending, made) });
}
function bdHandGo(c, fix, pending, made) {   // Yes: the hand-over (with the pending move, as one batch); refused because that teacher or room is busy then, the line says why and asks again
  const refused = why => {
    const r = (c.rows || []).find(y => y.key === fix.key), who = fix.kind === "room" ? fix.room : fix.teachers.find(t => !(r ? r.teachers || [] : []).includes(t));
    if (!bdBusyFor(c, fix, pending) || !Board.busyRefusal(why, who, fix.kind)) return false;   // the server's own busy sentence for that teacher or room, not a rule
    bdYesNo({ id: c.id, text: why, ask: BDWHY.anyway, yes: "Yes, give it", run: () => bdHandForce(c, fix, why, pending, made) });
    return true;
  };
  if (pending) bdSend("/api/draft/fixes", { fixes: [pending, fix] }, c, false, { refused });
  else bdSend("/api/draft/fix", fix, c, false, { refused, note: made ? BDWHY.two : "" });
}
function bdHandForce(c, fix, why, pending, made) {   // "Yes, give it": the same fix forced with the sentence shown; a pending move is made first, on its own (a batch never forces)
  const forced = Object.assign({}, fix, { force: true, why });
  if (!pending) { bdSend("/api/draft/fix", forced, c, false, { note: made ? BDWHY.two : "" }); return; }
  bdSend("/api/draft/fix", pending, c).then(ok => { if (ok) bdSend("/api/draft/fix", forced, c, false, { note: BDWHY.two }); });
}
function bdBusyFor(c, fix, pending) {   // whether the teacher or room a hand-over gives is on another lesson at a time the fix touches, on the board as it is (pending: the lesson's new place)
  const d = S.board.data, cards = d.cards || [], when = x => x.id === c.id && pending ? { d: pending.d, p: pending.p } : { d: x.d, p: x.p };
  let mine, has;
  if (fix.kind === "teacher") {
    const r = (c.rows || []).find(y => y.key === fix.key), add = fix.teachers.filter(t => !(r ? r.teachers || [] : []).includes(t));
    if (!add.length) return false;
    mine = cards.filter(x => (x.rows || []).some(y => y.key === fix.key)); has = x => (x.rows || []).some(y => (y.teachers || []).some(t => add.includes(t)));
  } else {
    if (!fix.room) return false;
    mine = [c]; has = x => (x.rows || []).some(y => y.room === fix.room);
  }
  const ids = new Set(mine.map(x => x.id));
  const placed = x => x.d !== null && x.d !== undefined;   // a lesson in the tray has no time, so it is with no one then
  return mine.some(m => { const w = when(m); return placed(w) && cards.some(x => !ids.has(x.id) && placed(x) && x.d === w.d && has(x) && x.p < w.p + bdLen(m) && w.p < x.p + bdLen(x)); });
}
/* the board's own sender: one post at a time (with the helper's), the answer goes to fxAfter, which fetches the board again; keep: lesson c
   stays selected (a lift: it is then in the tray); o.refused(sentence): a refusal it takes up (true), else said as a toast; o.note: what the
   line says after it in place of the change's own sentence; o.stay: c stays selected (without the tray's tab). Resolves true when the change was made */
async function bdSend(url, body, c, keep, o) {
  const b = S.board; if (!b) return false;
  if (FX.busy) { toast(BDWHY.busy); return false; }
  fxBusy(true); b.ask = null; b.del = null;
  const undoing = url === "/api/draft/undo", was = bdLastFix(); let ok = false;
  try {
    const r = await postTry(url, body), j = r.j || null;
    if (S.board !== b) { if (j) await fxAfter(j); return !!j; }
    if (j) {
      b.sel = (keep || (o && o.stay)) && c ? c.id : null; b.held = null; b.pt = ""; b.hv = "";   // o.stay: a change made in the Lesson tab, which stays open on its lesson
      if (keep || (body && body.push)) b.side = "tray";   // a lift or a push: the lesson is shown where it now waits
      const l = (j.fixes || []), last = l.length ? l[l.length - 1] : null, batch = last && last.batch ? l.filter(f => f.batch === last.batch) : last ? [last] : [];
      b.note = undoing ? (was ? `Undone: ${was.text || ""}` : "") : o && o.note ? o.note : batch.map(f => f.text || "").filter(Boolean).join(" ");   // fixes made together are said together
      ok = true;
      await fxAfter(j);
    } else {
      const took = r.error !== undefined && !!(o && o.refused && o.refused(r.error));
      if (r.error !== undefined && !took) toast(r.error);
      if (!took) bdLoad();   // a question asked about the refusal is not withdrawn by a fetch of the same board
    }
  } catch (e) { toast("Could not reach the server: " + e.message); } finally { fxBusy(false); bdLineDraw(); }
  return ok;
}
function bdUndo() {   // the Undo buttons and Ctrl or Cmd+Z on step 8: the draft's last change taken back (the line then says which), one post at a time
  const b = S.board; if (!b || b.wait || b.drag !== null) return;
  if (!bdLastFix()) { toast(BDWHY.noUndo); return; }
  bdSend("/api/draft/undo", {}, null);
}
function bdClick(b) {   // true when the click was the board's
  const d = b.dataset, bd = S.board; if (!bd) return false;
  if (bd.wait && b.closest("#bdBox")) return true;   // a drop waits for its answer: the board takes nothing else
  if (d.bdrows !== undefined) {   // Rows: Classes, Teachers or Rooms; the day stays (a cycle goes to that day), the selection closes
    bd.mode = { kind: "day", d: bd.mode.d, by: d.bdrows }; bd.sel = null; bd.ask = null; bd.del = null; bd.note = ""; bd.held = null; bd.step = null; bd.from = null;
    bdDraw(); bdWant(); return true;
  }
  if (d.bdday !== undefined) { bd.mode = { kind: "day", d: Number(d.bdday), by: bdBy() }; bdDraw(); return true; }
  if (d.bdcls !== undefined) { bd.mode = { kind: "cycle", cls: d.bdcls, d: bd.mode.d }; bdDraw(); return true; }
  if (d.bdname !== undefined) { bd.mode = { kind: "cycle", by: bdBy(), name: d.bdname, d: bd.mode.d }; bdDraw(); return true; }   // a teacher's or room's whole cycle
  if (d.bdall !== undefined) { bd.mode = { kind: "day", d: bd.mode.d, by: bdBy() }; bdDraw(); return true; }
  if (d.bdyes !== undefined) { const a = bd.ask; if (a && a.run) { if (FX.busy) toast(BDWHY.busy); else a.run(); } return true; }   // a yes or no question's Yes
  if (d.bdfold !== undefined) { if (bd.fold[d.bdfold]) delete bd.fold[d.bdfold]; else bd.fold[d.bdfold] = true; bdDraw(); return true; }
  if (d.bdclose !== undefined) { bd.sel = null; bd.ask = null; bd.del = null; bdDraw(); bdWant(); return true; }
  if (d.bdundo !== undefined) { bdUndo(); return true; }
  if (d.bdcancel !== undefined) { const a = bd.ask; bd.ask = null; bd.del = null; bdLineDraw(); if (a && a.lesson) bdSideDraw(); return true; }   // a question about a list's choice: the list goes back to what the lesson has
  if (d.bddel !== undefined) {   // "Delete this lesson": the question, from the delete's judgement that came with the lesson's slots
    const c = bd.sel !== null ? bdCard(bd.sel) : null; if (!c || c.entry) return true;
    const j = bdDelOf(c.id);
    if (!j) { toast(BDWHY.delWait); bdWant(); return true; }
    if (j.state === "na") { toast(j.why || BDWHY.none); return true; }
    bd.ask = null; bd.del = { id: c.id, j }; bdLineDraw(); return true;
  }
  if (d.bddelgo !== undefined) {   // the delete is forced when its judgement was "no", with the sentence shown (the server keeps it only for that same reason)
    const x = bd.del, c = x && bdCard(x.id); if (!c) return true;
    bdSend("/api/draft/fix", Board.deleteFix(c, x.j), c); return true;
  }
  if (d.bdswap !== undefined || d.bdpush !== undefined || d.bdbeside !== undefined) {   // the question's answer: the fix of the lesson asked about, at the place asked about
    const a = bd.ask, c = a && bdCard(a.id), how = d.bdswap !== undefined ? "swap" : d.bdbeside !== undefined ? "beside" : "push";
    if (c) bdTimeThen(c, Board.fix(c, a.slot, how), a.hand); return true;   // dropped on another teacher's or room's row: the hand-over is asked after it
  }
  if (d.bdlift !== undefined) { const c = bd.sel !== null ? bdCard(bd.sel) : null; if (c && !bdInTray(c)) bdSend("/api/draft/fix", Board.liftFix(c), c, true); return true; }
  if (d.bdcount !== undefined) { bdStep(d.bdcount); return true; }
  if (d.bdwarn !== undefined) { bd.side = "warn"; bdSideDraw(); const el = $("#bdSide"); if (el) el.scrollIntoView({ block: "nearest" }); return true; }   // the counter opens the panel's Warnings
  if (d.bdside !== undefined) { bd.side = d.bdside; bdSideDraw(); return true; }
  if (d.bdshow !== undefined) { bdShowWarning(d.bdshow, false); return true; }
  if (d.bdlopen !== undefined) {   // a band's group in the Lesson tab: opened (its choices fetched) or closed
    const L = bd.lesson, g = d.bdlopen; if (!L) return true;
    if (L.open[g]) delete L.open[g]; else { L.open[g] = true; bdLessonFetch(g); }
    bdSideDraw(); return true;
  }
  if (d.card !== undefined && b.classList.contains("swap") && bd.sel !== null && Number(d.card) !== bd.sel) {   // a lesson that can be swapped with the selected one: the same question a drop gives
    const c = bdCard(bd.sel), t = c && bd.slotsFor === c.id ? Board.target(bd.slots, Number(d.card)) : null;
    if (t) { if (FX.busy) toast(BDWHY.busy); else bdAct(c, Object.assign({ slot: t }, bdJudge(c, t)), false); return true; }
  }
  if (d.card !== undefined) { const id = bdId(b), row = b.closest(".bdrow"); bd.sel = bd.sel === id ? null : id; bd.from = row ? Object.assign(bdRowData(row), { id }) : null; bd.ask = null; bd.del = null; bd.note = ""; bd.held = null; if (bd.sel !== null) bdLessonOpen(bd.sel, true); bdDraw(); bdWant(); return true; }   // a click that selects opens the Lesson tab
  return false;
}
function bdStep(k) {   // a counter's click: the next card it counts is selected and shown (its day, or its class's cycle), and the cards it does not count fade
  const bd = S.board, d = bd.data; if (!d || bd.drag !== null) return;
  const c = Board.step(Board.hits(d, k), bd.sel); if (!c) return;   // a count of zero does nothing
  bd.step = k; bd.sel = c.id; bd.ask = null; bd.del = null; bd.note = ""; bd.held = null;
  if (bdBy() !== "class") bd.mode = { kind: "day", d: bd.mode.d };   // the counters step through the Classes rows
  if (!bdInTray(c)) bdGoTo(c);
  bdLessonOpen(c.id, true);
  bdDraw(); bdWant();
  const el = $("#bdBox") && $("#bdBox").querySelector(`.bdcard[data-card="${c.id}"]`); if (el) el.scrollIntoView({ block: "nearest", inline: "center" });
}
function bdGoTo(c) {   // the board shows card c: its day, or its class's cycle when a class's cycle is shown; its level is opened
  const bd = S.board, d = bd.data, cls = c.classes || [], by = bdBy();
  if (by !== "class") {   // by teacher or room: that person's cycle when the lesson is in it, else its day; the groups holding it are opened
    if (!(bd.mode.kind === "cycle" && bdInRow(c, { by, name: bd.mode.name || "" }))) bd.mode = { kind: "day", d: c.d, by };
    bd.mode.d = c.d;
    Board.groups(d, { kind: "day", d: c.d, by }, null).forEach(g => { if (g.rows.some(r => r.cards.some(x => x.card.id === c.id))) delete bd.fold[bdFoldKey(by, g.name)]; });
    return;
  }
  if (bd.mode.kind === "cycle" && !cls.includes(bd.mode.cls)) bd.mode = bdClasses(d).includes(cls[0]) ? { kind: "cycle", cls: cls[0], d: c.d } : { kind: "day", d: c.d };
  bd.mode.d = c.d;   // the day shown, or the day the cycle view goes back to
  (d.levels || []).forEach(lv => { if (lv.classes.some(x => cls.includes(x))) delete bd.fold[lv.level]; });
}
/* where a warning's "Show me" goes: Board.at's lesson or class, else the teacher it names ({teacher, d, p, clash}: d the index of the day
   it names, p the period, null with none; a clash names them in its sentence, Board.clashPlace); null when there is nowhere */
function bdWhere(w, data) {
  const a = Board.at(w, data); if (a) return a;
  const h = w && w.where, t = h && h.teacher; if (!t) return null;
  const pl = w.kind === "clash" ? Board.clashPlace(w.text, data.days || []) : null, d = h.day ? (data.days || []).indexOf(h.day) : pl ? pl.d : -1;
  return { id: null, teacher: t, d: d < 0 ? null : d, p: pl && pl.d === d ? pl.p : null, clash: w.kind === "clash" };
}
function bdShowTeacher(a, stay) {   // a warning about a teacher: Teachers rows on its day, the lesson of that teacher's row at its period selected (one marked "In two
  // places" first; with no period, the first marked one); a clash whose sentence names no place: the day shown when that row has a marked lesson on it, else the first
  // day that has; any other warning about a teacher with no day: their whole cycle
  const b = S.board, d = b.data, by = "teacher", row = { by, name: a.teacher };
  const marked = x => (x.marks || []).includes("teacher") && Board.of(x, row).length > 0, shown = b.mode.d;
  b.from = null;
  if (a.d === null && !a.clash) { b.sel = null; b.mode = { kind: "cycle", by, name: a.teacher, d: shown }; return null; }
  const any = d.cards.filter(marked).sort((x, y) => x.d - y.d || x.p - y.p)[0];
  const day = a.d !== null ? a.d : d.cards.some(x => x.d === shown && marked(x)) || !any ? shown : any.d;
  b.mode = { kind: "day", d: day, by };
  Board.groups(d, b.mode, null).forEach(g => { if (g.rows.some(r => r.name === a.teacher)) delete b.fold[bdFoldKey(by, g.name)]; });
  const covers = x => a.p === null || a.p === undefined || (x.p <= a.p && a.p < x.p + (Number(x.n) > 0 ? Number(x.n) : 1));
  const mine = d.cards.filter(x => x.d === day && Board.of(x, row).length > 0 && covers(x)).sort((x, y) => x.p - y.p);
  const c = mine.find(marked) || (a.p !== null && a.p !== undefined ? mine[0] : null) || null;
  b.sel = c ? c.id : null;
  if (c) { b.from = { cls: "", by, name: a.teacher, id: c.id }; bdLessonOpen(c.id, !stay); }
  return c;
}
/* a warning's "Show me" (stay false), or step 9's Show on step 8 / Find it on step 8 (stay true: the panel stays on Warnings with the
   warning marked and scrolled to): the board goes to bdWhere's place, its card selected, shown and flashed once; a lesson in the tray
   is selected there (the panel then shows Not placed, unless stay); a warning about a class and no lesson opens that class's cycle; a
   warning about a teacher opens the Teachers rows on that teacher (bdShowTeacher) */
function bdShowWarning(key, stay) {
  const b = S.board; if (!b) return;
  b.wmark = key; if (stay) b.side = "warn";
  if (!b.data || b.loading) { b.show = { key, stay }; return; }   // done when the board comes (bdLoad)
  b.show = null;
  const w = ((S.draft && S.draft.warnings) || []).find(x => x.key === key), a = w ? bdWhere(w, b.data) : null;
  let c = a && a.id !== null ? bdCard(a.id) : null;
  if (a) { b.ask = null; b.del = null; b.note = ""; b.step = null; b.held = null; }
  if (c) { b.sel = c.id; if (!bdInTray(c)) bdGoTo(c); else if (!stay) b.side = "tray"; bdLessonOpen(c.id, !stay); }   // with stay the panel keeps Warnings; the Lesson tab is there to open
  else if (a && a.teacher) c = bdShowTeacher(a, stay);
  else if (a) { b.sel = null; b.mode = { kind: "cycle", cls: a.cls, d: a.d !== null ? a.d : b.mode.d }; }
  bdDraw(); bdWant();
  const box = $("#bdBox"); if (!box) return;
  const trow = a && a.teacher && b.mode.kind === "day" ? [...box.querySelectorAll(`.bdmain:not(.bdold) .bdrow[data-by="teacher"]`)].find(x => x.dataset.name === a.teacher) : null;
  if (c) {
    const els = [...box.querySelectorAll(`.bdmain:not(.bdold) .bdcard[data-card="${c.id}"]`)], first = (trow && trow.querySelector(`.bdcard[data-card="${c.id}"]`)) || els[0];   // on the teacher's own row when it is there
    if (first) first.scrollIntoView({ block: "nearest", inline: "center" });
    els.forEach(x => x.classList.add("flash")); setTimeout(() => els.forEach(x => x.classList.remove("flash")), 1200);
  } else if (trow) trow.scrollIntoView({ block: "nearest" });   // the teacher's row, with no lesson to select
  else if (a && a.teacher) box.scrollIntoView({ block: "nearest" });   // a teacher's whole cycle
  else if (a) { const r = a.d !== null ? box.querySelector(`.bdmain:not(.bdold) .bdrow[data-d="${a.d}"]`) : null; (r || box).scrollIntoView({ block: "nearest" }); }
  else if (stay) box.scrollIntoView({ block: "start" });
  const y = box.querySelector("#bdSide .bdsbody"), li = y && [...y.querySelectorAll("li.warn")].find(x => x.dataset.wkey === key);
  if (li && stay) y.scrollTop += li.getBoundingClientRect().top - y.getBoundingClientRect().top - y.clientHeight / 3;   // inside the panel: the page does not move for it
}
function bdCellClick(e) {   // a click on a place of the board: with a card selected the lesson goes there when it may; with none, nothing happens
  const cell = e.target.closest && e.target.closest(".bdcell, .bdmark"), b = S.board; if (!cell || !b || !b.data) return false;
  const c = b.sel !== null ? bdCard(b.sel) : null; if (!c || b.wait) return true;
  if (FX.busy) { toast(BDWHY.busy); return true; }
  bdGo(c, bdPlaceAt(cell.closest(".bdrow"), Number(cell.dataset.p), null), false); return true;
}
let BDOVER = [];
function bdOver(row, p, c) {   // the cells the dragged lesson would fill get "over" (classes only: a redraw would cancel the drag)
  BDOVER.forEach(x => x.classList.remove("over")); BDOVER = [];
  if (!row) return;
  const n = Number(c.n) > 0 ? Number(c.n) : 1, cells = row.querySelectorAll(".bdcell");
  for (let k = p; k < Math.min(p + n, cells.length); k++) { cells[k].classList.add("over"); BDOVER.push(cells[k]); }
}
function bdDragEnd() {
  const b = S.board; if (b) { b.drag = null; b.held = null; b.hv = ""; b.pt = ""; b.tabHv = null; } clearTimeout(BD.tabT); bdTabLit(); bdUnkeep(); bdOver(null); bdTrayLit(false);
  if (b && b.redraw) setTimeout(() => { if (S.board === b && b.drag === null && b.redraw) bdDraw(); }, 0);   // the draft changed during the drag: the card is drawn again once the drop has done its part (a question, a refusal, a change)
}
function bdLostDrag() { bdDragEnd(); if (!bdNext()) { bdLineDraw(); bdPaint(); } }   // a drag whose end never came (its element left the page): it is over now
function bdTabLit() { const b = S.board; document.querySelectorAll("#bdBox .bdtab").forEach(x => x.classList.toggle("hover", !!b && b.tabHv !== null && Number(x.dataset.bdday) === b.tabHv)); }
function bdTabHover(dd) {   // a card in the air over a day's tab (dd; null: over none): held there half a second, the board shows that day and the drag goes on
  const b = S.board; if (dd !== null && dd === b.mode.d) dd = null;   // the day shown already
  if (dd === b.tabHv) return;
  clearTimeout(BD.tabT); b.tabHv = dd; bdTabLit();
  if (dd === null) return;
  BD.tabT = setTimeout(() => {
    if (S.board !== b || b.drag === null || b.tabHv !== dd || b.mode.kind !== "day") return;
    b.tabHv = null; b.mode = { kind: "day", d: dd, by: bdBy() }; b.hv = ""; bdOver(null); bdDraw(); bdLineDraw();
  }, 500);
}
function bdTrayLit(on) { const t = $("#bdSide"); if (t) t.classList.toggle("lift", on); }   // the side panel says "Drop here to lift it out." while a card from the board is over it, whatever tab is showing
const bdAimed = (b, row, e) => { const q = bdPeriodAt(row, e.clientX); return q < 0 ? -1 : Math.min(b.data.NP - 1, Board.start(q, b.grab)); };   // the period the lesson would start at: the pointer's, less the part of the card that was held
document.addEventListener("pointerdown", e => {
  const b0 = S.board; if (b0 && b0.drag !== null) bdLostDrag();   // a press while a drag is still set: that drag ended without telling the page
  const el = e.target.closest && e.target.closest(".bdcard"), b = S.board; if (!el || !b || !b.data || b.wait || e.button > 0) return;
  const id = bdId(el);
  if (b.sel !== null && id !== b.sel && b.slotsFor === b.sel) { bdPre(id); return; }   // another card is selected and its slots are here: pressing must not drop them or its swap outlines; the pressed card's slots are fetched aside, for a drag or a click that takes it up
  b.held = id; bdWant();
});
document.addEventListener("pointerup", () => {
  const b0 = S.board; if (b0 && b0.drag !== null) bdLostDrag();
  const b = S.board; if (!b || b.held === null) return;
  b.held = null; setTimeout(() => { if (S.board === b) bdWant(); }, 30);   // a click that follows chooses the card itself
});
document.addEventListener("dragstart", e => {
  const el = e.target.closest && e.target.closest(".bdcard"), b = S.board; if (!el || !b || !b.data) return;
  const c = bdCard(bdId(el)); if (!c || FX.busy || b.wait) { e.preventDefault(); if (c && FX.busy) toast(BDWHY.busy); return; }
  const row = el.closest(".bdrow");
  b.sel = c.id; b.held = null; b.ask = null; b.del = null; b.note = ""; b.pt = ""; b.hv = ""; b.tabHv = null; b.drag = c.id; BD.dragEl = el; BD.over = Date.now();
  b.from = row ? Object.assign(bdRowData(row), { id: c.id }) : null;   // the teacher's or room's row it was taken from: a drop on another is a hand-over
  const q = row ? bdPeriodAt(row, e.clientX) : c.p; b.grab = row ? Board.grab(c, q < 0 ? c.p : q) : 0;   // a card from the tray is held by its start
  e.dataTransfer.setData("text/plain", "bd:" + c.id); e.dataTransfer.effectAllowed = "move";
  bdWant(); bdLineDraw();
  if (b.lesson && !bdLessonOn(b)) bdSideDraw();   // another lesson is taken up: the Lesson tab of the one selected before closes (back to the tab before it); with a tray card in the air bdSideDraw leaves the panel for the drag's end (b.redraw), so the dragged element stays in the page
});
const bdOffText = c => bdInTray(c) ? BDWHY.offTray : BDWHY.off;   // a card in the air over the timetable card but off its row and the panel
const bdAirText = b => b.lost ? BDWHY.gone : b.slotsFor === b.drag ? "" : b.changed ? BDWHY.changed : BDWHY.working;   // the line while the dragged card's slots are not here
document.addEventListener("dragover", e => {   // over a place: the cells it would fill, the line says what a drop would do; a drop is let through when allowed, or when the slots are still coming (then the drop waits for them)
  const b = S.board; if (!b || !b.data || b.drag === null) return;
  BD.over = Date.now();
  const t = bdHit(e), tab = t.closest && t.closest("#bdBox .bdtab");   // a day's tab (the day view only: in a class's cycle every day is a row)
  bdTabHover(tab && b.mode.kind === "day" ? Number(tab.dataset.bdday) : null);
  if (tab) { if (b.hv) { b.hv = ""; b.pt = ""; bdOver(null); bdTrayLit(false); bdLineDraw(); } return; }
  const c = bdCard(b.drag), row = t.closest && t.closest(".bdrow"), tray = t.closest && t.closest("#bdSide");
  if (c && tray && !bdInTray(c)) {   // a card from the board over the side panel: a drop lifts it out
    e.preventDefault(); e.dataTransfer.dropEffect = "move";
    if (b.hv !== "tray") { b.hv = "tray"; b.pt = BDWHY.lift; bdOver(null); bdTrayLit(true); bdLineDraw(); }
    return;
  }
  const p = c && row ? bdAimed(b, row, e) : -1;
  if (c && !row && t.closest && t.closest("#bdBox")) {   // elsewhere in the timetable card (the heading, the counters, the line, the notes): taken, so a release there says where to drop and nothing lands in a field
    e.preventDefault(); e.dataTransfer.dropEffect = "move";
    if (b.hv !== "off") { b.hv = "off"; b.pt = bdOffText(c); bdOver(null); bdTrayLit(false); bdLineDraw(); }
    return;
  }
  if (!c || !row || p < 0) { if (b.hv) { b.hv = ""; b.pt = b.changed ? bdAirText(b) : ""; bdOver(null); bdTrayLit(false); bdLineDraw(); } return; }
  const at = bdPlaceAt(row, p, e);
  e.preventDefault(); e.dataTransfer.dropEffect = "move";   // every place of a row takes the drop, which is judged where it is let go: a quick drag over a refused row must not leave the drop refused (the drop then says why)
  const hand = bdHandOf(c, at);
  if (hand && at.d === c.d && p === c.p) {   // another teacher's or room's row at the lesson's own time: a hand-over only
    const key = `${row.dataset.row}|${row.dataset.d}|${p}|hand`; if (key === b.hv) return;
    b.hv = key; bdOver(row, p, c); bdTrayLit(false); b.pt = bdHandHint(hand, true); bdLineDraw(); return;
  }
  const a = bdSlotAt(c, at), wait = a.why === "wait";
  const o = a.slot && at.over !== null && a.slot.swap === at.over ? bdCard(at.over) : null;   // aimed at the lesson under the pointer: the marks cover its periods
  const key = `${row.dataset.row}|${row.dataset.d}|${p}|${o ? o.id : ""}|${a.slot ? a.slot.state : a.why}`;
  if (key === b.hv) return;
  b.hv = key; bdOver(row, o ? o.p : p, o || c); bdTrayLit(false);
  b.pt = a.slot && a.why !== "stuck" && a.why !== "taken" ? bdTell(a.slot, c) : wait ? bdAirText(b) : bdWhyText(a, true);
  if (hand && (a.slot || wait)) b.pt = `${b.pt} ${bdHandHint(hand, false)}`.trim();
  bdLineDraw();
});
function bdHandHint(h, only) {   // what the line says over another teacher's or room's row: at the lesson's own time what a drop does, else that it asks after the change of time
  const t = h.to.by === "teacher", name = h.to.name;
  if (!only) return `Then it asks about ${name || (t ? "No teacher" : "No room")}.`;
  if (t) return name ? `Drop to give it to ${name}.` : `Drop to take ${h.from.name} off it.`;
  return name ? `Drop to move it to ${name}.` : "Drop to leave it with no room.";
}
document.addEventListener("drop", e => {
  const b = S.board; if (!b || !b.data || b.drag === null) return;
  const c = bdCard(b.drag), t = bdHit(e), row = t.closest && t.closest(".bdrow"), tray = t.closest && t.closest("#bdSide");
  if (c && tray && !bdInTray(c)) {   // a card from the board dropped on the side panel: it is lifted out, and stays selected in the tray
    e.preventDefault();
    const lost = b.lost; bdDragEnd(); if (!bdNext()) { bdLineDraw(); bdPaint(); }
    if (lost || FX.busy) { toast(lost ? BDWHY.gone : BDWHY.busy); return; }
    const k = bdCard(c.id); if (!k || bdInTray(k)) { toast(BDWHY.gone); return; }
    bdSend("/api/draft/fix", Board.liftFix(k), k, true); return;
  }
  if (c && !row && t.closest && t.closest("#bdBox") && !(t.closest("#bdBox .bdtab") && b.mode.kind === "day")) {   // let go off its row and off the panel: nothing changes, and the toast says where
    e.preventDefault();
    bdDragEnd(); if (!bdNext()) { bdLineDraw(); bdPaint(); }
    toast(bdOffText(c)); return;
  }
  if (!c || !row) return;
  e.preventDefault();
  const p = bdAimed(b, row, e); if (p < 0) return;
  const at = Object.assign(bdPlaceAt(row, p, e), { id: c.id, up: b.up }), lost = b.lost;
  bdDragEnd();
  if (lost || FX.busy) { if (!bdNext()) { bdLineDraw(); bdPaint(); } toast(lost ? BDWHY.gone : BDWHY.busy); return; }
  if (bdHandOnly(c, at) && !b.next && !b.loading) { bdLineDraw(); bdPaint(); bdGo(c, at, true); return; }   // a hand-over at its own time needs no slots
  if (b.next || b.loading || b.slotsFor !== c.id || !b.slots) { bdDropWait(at); return; }   // the slots, or the board, are still coming
  bdLineDraw(); bdGo(c, at, true);
});
async function bdDropWait(at) {   // a drop let go before its card's slots (or the board) came: wait for them, at most 8 seconds, then judge the place; the board takes nothing else meanwhile
  const b = S.board, end = Date.now() + 8000, LATE = {};
  const within = pr => Promise.race([pr, new Promise(r => setTimeout(() => r(LATE), Math.max(0, end - Date.now())))]);
  const done = say => { b.wait = null; b.pt = ""; if (!bdNext()) { bdLineDraw(); bdPaint(); } if (say) toast(say); };
  b.wait = at; b.pt = b.changed ? BDWHY.changed : BDWHY.working; bdLineDraw();
  for (;;) {
    if (b.loading) {   // a newer board is coming: its slots are the ones to judge by
      const r = await within(b.loading);
      if (S.board !== b || b.wait !== at) return;
      if (r === LATE) return done(BDWHY.failed);
      continue;
    }
    bdNext();
    if (!b.data || b.up !== at.up || !bdCard(at.id)) return done(BDWHY.gone);   // the board could not be had, or the lesson is not in it
    const gen = BD.gen, s = await within(bdSlotsP(at.id));
    if (S.board !== b || b.wait !== at) return;
    if (s === LATE || (!s && gen === BD.gen)) return done(BDWHY.failed);
    if (gen !== BD.gen) continue;   // another draft came meanwhile
    const c = bdCard(at.id);
    b.wait = null; b.pt = ""; b.sel = c.id;
    if (b.slotsFor !== c.id) { b.slots = s; b.slotsFor = c.id; b.asking = null; b.failFor = null; }
    bdPaint(); bdLineDraw(); bdGo(c, at, true, end); return;   // a blue place is then judged on request within the same 8 seconds
  }
}
document.addEventListener("dragend", () => {   // a drag let go outside every row (and outside the tray) says nothing; a drop on a row says itself why it is refused
  const b = S.board; if (!b || b.drag === null) return;
  bdDragEnd(); if (!bdNext()) { bdLineDraw(); bdPaint(); }
});
document.addEventListener("dragleave", e => {   // the pointer left a day's tab (to outside the page as well): its half second is off
  const b = S.board, tab = e.target.closest && e.target.closest("#bdBox .bdtab"); if (!b || b.drag === null || !tab) return;
  if (!(e.relatedTarget && tab.contains(e.relatedTarget))) bdTabHover(null);
});
document.addEventListener("mousemove", e => {   // where the pointer is, for a paste (the row and period under it are read at the key press, on the board as it is drawn then); a move with no button down after a drag means that drag has ended
  const b = S.board; if (!b) return;
  if (b.drag !== null && e.buttons === 0 && Date.now() - BD.over > 300) bdLostDrag();
  b.mouse = { x: e.clientX, y: e.clientY };
});
function bdPointed() {   // the place of the board under the pointer now -> {cls, d, p} or null
  const b = S.board, m = b && b.mouse; if (!m) return null;
  const el = document.elementFromPoint(m.x, m.y), row = el && el.closest && el.closest("#bdBox .bdrow"), p = row ? bdPeriodAt(row, m.x) : -1;
  return row && p >= 0 ? Object.assign(bdRowData(row), { d: Number(row.dataset.d), p }) : null;
}
const bdInField = e => !!(e.target.isContentEditable || (e.target.closest && e.target.closest("input, select, textarea, [contenteditable]")));
document.addEventListener("change", e => {   // the Lesson tab: a list's choice is acted on at once; the tick box is kept for the next room choice
  const el = e.target, ds = el.dataset || {}, b = S.board;
  if (ds.bdlt === undefined && ds.bdlr === undefined && ds.bdlall === undefined) return;
  if (!bdLessonOn(b)) { if (b) bdSideDraw(); return; }   // a list of a lesson no longer selected: the panel is drawn for the selection as it is
  const L = b.lesson;
  if (ds.bdlall !== undefined) { L.all[ds.bdlall] = el.checked; return; }
  el.blur();   // the keys (Escape, Ctrl or Cmd+Z) are the board's again at once
  const c = bdCard(L.id), g = ds.bdlt !== undefined ? ds.bdlt : ds.bdlr, r = (c.rows || []).find(x => x.group === g), j = L.got[g];
  if (FX.busy || b.wait || b.drag !== null || !r || !j || typeof j !== "object") { if (FX.busy) toast(BDWHY.busy); bdSideDraw(); return; }   // the list goes back
  if (el.value === "pick") return;
  if (ds.bdlt !== undefined) bdLessonTeacher(c, r, j, Number(ds.i), el.value); else bdLessonRoom(c, r, j, el.value, !!L.all[g]);
});
document.addEventListener("keydown", e => {   // Escape clears the board's selection and withdraws its question; in a field, Escape is the field's
  const b0 = S.board; if (e.key === "Escape" && b0 && b0.drag !== null) bdLostDrag();
  const b = S.board; if (e.key !== "Escape" || !b || b.wait || (b.sel === null && !b.ask && !b.del)) return;   // a waiting drop (a moment) is not cancelled by it
  if (bdInField(e)) return;
  e.preventDefault(); b.sel = null; b.ask = null; b.del = null; bdDraw(); bdWant();
});
document.addEventListener("keydown", e => {   // Ctrl+X / Cmd+X lifts the selected lesson out (then selected in the tray); Ctrl+V / Cmd+V puts the selected lesson of the tray where the pointer is, as a click there; in a field, or with no card selected, the browser's own cut and paste
  if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
  const k = (e.key || "").toLowerCase(); if (k !== "x" && k !== "v") return;
  const b = S.board; if (!b || !b.data || b.sel === null || b.wait || b.drag !== null || bdInField(e)) return;
  const c = bdCard(b.sel); if (!c) return;
  if (k === "x") { if (bdInTray(c)) return; e.preventDefault(); bdSend("/api/draft/fix", Board.liftFix(c), c, true); return; }
  if (!bdInTray(c)) return;
  e.preventDefault();
  if (FX.busy) { toast(BDWHY.busy); return; }
  const m = bdPointed();
  if (!m || !Board.onRow(c, m, b.data)) { toast(BDWHY.paste); return; }
  bdTry(c, Object.assign({}, m, { over: null }), false);   // in the Teachers or Rooms rows: "Switch to Classes rows to place it."
});
/* which configuration (the workbook's id) the timetable was made from, against the setup's version now */
function configLine(j) {
  const id = esc(j.config_id), now = esc(j.setup_version);
  return { same: `<p class="okmsg">Made from this configuration (${id}).</p>`,
    older: `<p class="issue">Made from configuration ${id}; the setup is now ${now}. Changes since then are not in this timetable.</p>`,
    unsaved: `<p class="issue">Made from a workbook that was downloaded with unsaved changes (${id}), so it may not match the setup saved here (${now}).</p>`,
    unknown: `<p class="muted small">The timetable does not say which configuration it was made from (an older workbook).</p>`,
    newer: `<p class="issue">The timetable's configuration ${id} is newer than this setup's ${now}: it was made from another copy.</p>` }[j.config_state] || "";
}
/* the Choices used list that came back (first or second choice for each item on the give-way list), and what is wrong with it */
function choicesUsedHTML(used, problems, n) {
  if (!used.length && !n) return "";
  const lc = t => t ? t[0].toLowerCase() + t.slice(1) : "", bad = problems.map(x => `<p class="issue">${esc(x)}</p>`).join("");
  if (!used.length) return `<h3 style="margin-top:14px">Choices used</h3><p class="issue">No Choices used list came back. The setup has ${n} second choice${n === 1 ? "" : "s"}; the timetable was checked against the first choices.</p>${bad}`;
  return `<h3 style="margin-top:14px">Choices used</h3><ul class="fitlist">${used.map(u => `<li>${esc(u.item)}: ${esc(String(u.used || "").toLowerCase())}${u.how ? `, ${esc(lc(String(u.how)))}` : ""}</li>`).join("")}</ul>${bad}`;
}
/* the agent's rule report (one line per typed rule: Met, Partly, Not met and how), and whether it matches the setup's typed rules */
function ruleReportHTML(report, typed) {
  if (!report.length && !typed) return "";
  const cls = r => ({ Met: "met", Partly: "partly", "Not met": "notmet" }[r.result] || "");
  const note = !report.length ? `<p class="issue">No rule report came back. The setup has ${typed} typed rule${typed === 1 ? "" : "s"}; ask the agent for the Rule report sheet.</p>`
    : typed && report.length !== typed ? `<p class="issue">The setup has ${typed} typed rule${typed === 1 ? "" : "s"}; the report has ${report.length}.</p>` : "";
  const rows = report.map(r => `<tr><td>${esc(r.no ?? "")}</td><td>${esc(r.strength)}</td><td>${esc(r.applies)}</td><td>${esc(r.rule)}</td><td class="${cls(r)}">${esc(r.result || "?")}</td><td>${esc(r.how)}</td></tr>`).join("");
  return `<h3 style="margin-top:14px">Rule report</h3>${note}${report.length ? `<div class="tablewrap" style="max-height:none"><table class="rr"><tr><th>No.</th><th>Must / Prefer</th><th>Applies to</th><th>Rule</th><th>Result</th><th>How</th></tr>${rows}</table></div>` : ""}`;
}
/* what the committee pastes into the chatbot with the workbook and the skill */
function starterPrompt() {
  const n = S.spec ? S.spec.rules.filter(r => r.rule === "In words").length : 0, v = (S.meta && S.meta.skill_version) || "", nch = S.spec ? (S.spec.choices || []).length : 0;
  return `Use the attached school-timetable-generator skill${v ? ` (version ${v})` : ""}, not an older installed copy. Make the timetable for ${sc().name || "the school"} ${sc().timetable || ""} from the attached setup workbook: run python -m ttgen check first and tell me every problem; then solve and export with python -m ttgen; hand back the timetable database (.sqlite) written by ttgen export, or, if you cannot run code, a workbook with a Lessons sheet in the hand-over format in SKILL.md.${n ? ` The setup has ${n} typed rule${n === 1 ? "" : "s"} (Rule "In words" on the More rules sheet): honour every Must, try every Prefer, then add a Rule report sheet to the timetable workbook (one line per typed rule: Met, Partly or Not met, and how) and run ttgen export on that workbook, so the database you hand back carries the report.` : ""}${nch ? ` The setup has ${nch} second choice${nch === 1 ? "" : "s"} on the Choices sheet: try the first choices; if no timetable fits, give way one item at a time from the top of the list and stop at the first that fits (python -m ttgen solve does this); never give way on anything that is not on the list; hand back the Choices used sheet beside the Rule report.${sc().choices_mode === "compare" ? " Make one timetable for each step of the list." : ""}` : ""} Do not change the setup.`.replace(/\s+/g, " ").trim();
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

"use strict";
/* Timetable Setup: a step-by-step editor for the timetable setup workbook. State lives in S.spec (same shape the
   server's ttgen package reads and writes); every list feeds the drop-downs of the later steps. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const KEY = "ttsetup.v1";
const S = { kind: null, spec: null, meta: null, step: 0, brush: "L", stu: { cls: "", q: "" }, tg: { lv: "", subj: "", t: "" }, tf: { dept: "", subj: "", q: "" }, pick: { lessons: new Set(), students: new Set(), teachers: new Set(), shown: {}, last: {}, t: "", g: "", c: "", s: "", v: "All", d: "", r: "", a: "" }, undo: [], redo: [], last: null, dirty: false, base: 0 };
const STEPS = [["start", "Start"], ["school", "School & day"], ["venues", "1 Venues"], ["classes", "2 Classes"], ["subjects", "3 Subjects"],
  ["teachers", "4 Teachers"], ["lessons", "5 TG & deployment"], ["rules", "6 Availability & rules"], ["students", "7 Students"], ["generate", "Generate & publish"], ["adjust", "Adjust timetable"], ["download", "Files"]];

/* ---------------- storage, server
   save() keeps this browser's copy after every change. A change to the setup also goes on the undo list (changes
   within a second count as one) and stays "unsaved" until Save progress puts it on the server (S.base: the server
   copy it came from), which is what opens on any browser after signing in. */
const UNDO_MAX = 20;
function save(o) {
  const js = S.spec ? JSON.stringify(S.spec) : null;
  if (js !== S.last) {
    if (S.last && js && !(o && o.quiet)) {
      if (Date.now() - (S.pushed || 0) > 1000) { S.undo.push(S.last); if (S.undo.length > UNDO_MAX) S.undo.shift(); S.redo = []; }
      S.pushed = Date.now(); S.dirty = true;
    }
    S.last = js;
  }
  try { localStorage.setItem(KEY, `{"kind":${JSON.stringify(S.kind)},"step":${S.step},"at":${JSON.stringify((STEPS[S.step] || [])[0] || "")},"dirty":${!!S.dirty},"base":${Number(S.base) || 0},"spec":${js}}`); } catch (e) { }
  saveState();
}
function saved() {   // the step is kept by name ("at"); a copy saved before Bands joined the teaching-groups step has only the old number
  try {
    const x = JSON.parse(localStorage.getItem(KEY) || "null"); if (!x || !x.spec) return null;
    const at = x.at || ["start", "school", "venues", "classes", "subjects", "teachers", "blocks", "lessons", "rules", "students", "generate", "adjust", "download"][x.step];
    if (at && stepAt(at) >= 0) x.step = stepAt(at); return x;
  } catch (e) { return null; }
}
function saveState() {
  const u = $("#undo"), r = $("#redo"), st = $("#saveState");
  if (u) { u.disabled = !S.spec || !S.undo.length; r.disabled = !S.spec || !S.redo.length; }
  if (st) { st.className = "savestate" + (S.dirty ? " warn" : ""); st.textContent = !S.spec ? "" : S.dirty ? "Unsaved changes" : S.base && G.server && G.server.saved_at ? `Saved ${G.server.saved_at}` : ""; }
}
function undo(back) {
  const from = back ? S.undo : S.redo, to = back ? S.redo : S.undo;
  if (!S.spec || !from.length) return;
  to.push(S.last); S.last = from.pop(); S.spec = JSON.parse(S.last); S.pushed = 0; S.dirty = true; unpick();
  ensureDays(); save({ quiet: true }); render(); toast(back ? "Undone." : "Redone.");
}
async function saveServer() {
  if (!S.spec) { toast("Open or start a setup first."); return; }
  try { G.server = await getJSON("/api/setup"); } catch (e) { }
  const srv = G.server && G.server.spec ? G.server : null;
  if (srv && srv.ts > (S.base || 0) + 1 && JSON.stringify(srv.spec) !== S.last
      && !confirm(`A newer setup was saved for the school on ${srv.saved_at} (another browser or committee member). Replace it with this one?`)) return;
  const r = await fetch("/api/setup", { method: "PUT", headers: { "Content-Type": "application/json" }, body: S.last || JSON.stringify(S.spec) });
  if (r.status === 401) { location.href = "/login"; return; }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { toast(j.error || "Could not save."); return; }
  S.base = j.ts; S.dirty = false; G.server = { spec: S.spec, saved_at: j.saved_at, ts: j.ts }; save({ quiet: true });
  toast(`Saved for the school (${j.saved_at}). It opens here next time anyone on the committee signs in.` +
    (G.st && G.st.volume === false ? " But this server has no Railway volume, so it is lost on the next deploy." : ""));
}
async function synced() {   // the server now has this setup (Generate saves it first)
  try { G.server = await getJSON("/api/setup"); if (G.server.ts && G.server.spec && JSON.stringify(G.server.spec) === S.last) { S.base = G.server.ts; S.dirty = false; save({ quiet: true }); } } catch (e) { }
}
async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(await r.text()); return r.json(); }
async function begin(kind, what) {
  S.kind = kind; S.meta = await getJSON(`/api/meta/${kind}`);
  S.spec = await getJSON(`/api/${what}/${kind}`); S.step = 1; S.base = 0; ensureDays(); save(); S.dirty = true; save({ quiet: true }); (async () => { try { G.server = await getJSON("/api/setup"); } catch (e) { } render(); poll(); })();
  toast(what === "sample" ? "Sample school loaded: edit it or use it to see how the template works." : "Blank template started.");
}
/* open a setup: o.base and o.dirty say whether it is the server copy (base = its ts, not dirty) */
async function adopt(spec, msg, o = {}) {
  S.kind = o.kind || (spec.school && spec.school.type) || "secondary"; S.meta = await getJSON(`/api/meta/${S.kind}`);
  unpick(); S.spec = spec; ["venues", "classes", "subjects", "teachers", "blocks", "lessons", "rules", "students", "combinations"].forEach(k => S.spec[k] = S.spec[k] || []);
  S.step = o.step || 1; ensureDays(); save();
  S.base = o.base || 0; S.dirty = "dirty" in o ? o.dirty : true; save({ quiet: true });
  render(); if (msg) toast(msg);
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
function placeRules() {
  const out = { settings: {}, availability: [], fixed: [], more: [] };
  S.spec.rules.forEach((r, i) => {
    const must = (r.strength || "Must") === "Must", s = SET().find(s => ruleIs(r, s)), has = r.from != null && r.from !== "";
    if (s && must && !(s.key in out.settings)) out.settings[s.key] = i;
    else if (r.rule === "Not available" && r.scope === "Teacher" && must && has) out.availability.push(i);
    else if (r.rule === "Fixed at" && ["Class", "Group"].includes(r.scope) && must && has) out.fixed.push(i);
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
  return `<label class="f" id="school-${i}">${esc(x[0])} ${field}${x[2] ? `<span class="muted small">${esc(x[2])}</span>` : ""}</label>`;
}
function recessSetting(label) {   // [row index, value] of a floating recess row on Settings
  const ex = sc().extra_settings || [], i = ex.findIndex(x => String(x[0]).toLowerCase().startsWith(label.toLowerCase()));
  return [i, i >= 0 ? ex[i][1] : null];
}

/* ---------------- derived values (same logic as the workbook formulas) */
function split(p, L) { p = Number(p) || 0; L = Number(L) || 1; if (p <= 0) return [0, 0]; if (L <= 1) return [p, 0]; let s = ((-p % L) + L) % L; if (s * (L - 1) > p) s = 0; return [(p - s * (L - 1)) / L, s]; }
function lessonInfo() {
  const seq = {}; const letter = Object.fromEntries((sc().tags || []).map(([a, b]) => [a, b]));
  return S.spec.lessons.map(x => {
    const s = subj(x.subject) || {}; const p = Number(x.periods_override) || Number((s.periods || {})[x.level]) || 0;
    const L = Number(s.lesson_length) || Number(sc().lesson_length) || 1;
    const pat = (x.pattern || []).map(Number), [full, short] = pat.length && pat.reduce((a, b) => a + b, 0) === p ? [pat.filter(v => v === L).length, pat.filter(v => v === L - 1).length] : split(p, L);   // pattern: lengths set on the Adjust page
    let code = "";
    if (x.subject) {
      const k = `${x.level}|${x.subject}`; if (x.block) seq[k] = (seq[k] || 0) + 1;
      code = x.code_override ? String(x.code_override) : !x.block ? "Entire Class" : `${String(x.level).slice(-1)}${s.code || "??"}${letter[s.tag] || ""}${seq[k]}`;
    }
    const tp = p * (x.block ? 1 : Math.max(1, (x.classes || []).length));
    return { p, L, full, short, code, tp, kind: s.room_kind || (x.block || x.code_override ? "classroom" : "home room") };
  });
}
function teachingGroups(subject) {   // groups or classes taught this subject on step 5: a banded row is one group, a whole-class row one per class
  return S.spec.lessons.filter(x => x.subject === subject).reduce((n, x) => n + (x.block || x.code_override ? 1 : (x.classes || []).length), 0);
}
function canTeach(t, subject, level) {
  const tt = S.spec.teachers.find(x => x.name === t); if (!tt) return false;
  return (tt.can_teach || []).some(c => c.subject === subject && (!c.levels || c.levels === "All" || c.levels === level || c.levels === bands()[level]));
}
function issues() {
  const out = { school: {}, lessons: {}, rules: {}, teachers: {}, blocks: {}, classes: {}, subjects: {}, venues: {}, students: {}, global: [] };
  const add = (k, i, m) => (out[k][i] = out[k][i] || []).push(m);
  (sc().extra_settings || []).forEach((x, i) => {   // 'Lessons end by (...)' rows on Settings
    if (!String(x[0]).toLowerCase().startsWith("lessons end by") || x[1] == null || x[1] === "") return;   // blank: no end time on those days
    if (!/^\d{1,2}:\d{2}$/.test(String(x[1]))) { add("school", i, `${x[0]}: give a time such as 12:40, or clear it for no end time.`); return; }
    if (Math.floor((mins(x[1]) - mins(sc().start_time)) / Number(sc().period_minutes || 20)) <= 0) add("school", i, `${x[0]}: ${x[1]} is before the first period ends, so no lesson fits on those days.`);
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
        add("school", bi, `${lv} has ${n} classes and its recess goes by level, so ${n} are at recess at once: more than the ${cap} allowed. Pick Class, or raise Most classes at recess at once.`);
    }
    if (short.length) add("school", li, `The recess window on ${short[0]}${short.length > 1 ? ` and ${short.length - 1} more` : ""} is shorter than the ${RL}-period recess: widen the W periods, or shorten the recess.`);
    const worst = Object.entries(at).sort((a, b) => b[1] - a[1])[0];
    if (Number(cap) && worst && worst[1] > Number(cap)) add("school", ci, `${worst[1]} classes have their fixed recess (R) together on ${worst[0].split("|")[0]} period ${worst[0].split("|")[1]}, more than the ${cap} allowed at once.`);
  }
  const info = lessonInfo(); const codes = {};
  info.forEach((x, i) => { if (x.code && x.code !== "Entire Class") codes[x.code] = (codes[x.code] || 0) + 1; });
  S.spec.lessons.forEach((x, i) => {
    if (!x.subject) { add("lessons", i, "Pick a subject."); return; }
    if (!info[i].p) add("lessons", i, `No periods for ${x.level} on Subjects.`);
    if (!(x.classes || []).length) add("lessons", i, "No class.");
    if (!(x.teachers || []).filter(Boolean).length) add("lessons", i, "No teacher.");
    for (const t of (x.teachers || []).filter(Boolean)) {
      if (!canTeach(t, x.subject, x.level)) add("lessons", i, `${t} is not set to teach this at ${x.level}.`);
      if (x.block && S.spec.lessons.filter(y => y.block === x.block && (y.teachers || []).includes(t)).length > 1) add("lessons", i, `${t} twice in this band.`);
    }
    if (x.block && !blockNames().includes(x.block)) add("lessons", i, "Band not on the Bands list (top of step 5).");
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
    const inG = gs.reduce((a, [x]) => a + (Number(x.students) || 0), 0), inC = (b.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
    if (gs.length && inG > inC) add("blocks", i, `${b.block}: ${inG} students in groups but ${inC} in its classes.`);
  });
  S.spec.subjects.forEach((s, i) => { if (!Object.values(s.periods || {}).some(Number)) add("subjects", i, `${s.subject || "Subject"}: no periods for any level.`); });
  S.spec.rules.forEach((r, i) => {
    const rt = (S.meta.rule_types || []).find(x => x.rule === r.rule);
    if (!rt) { add("rules", i, "Pick a rule."); return; }
    if (!r.target || !targetOptions(r.scope).includes(r.target)) add("rules", i, `Pick the ${String(r.scope || "").toLowerCase()} from the list.`);
    if (!rt.scopes.includes(r.scope)) add("rules", i, `${r.rule} does not apply to a ${String(r.scope).toLowerCase()}.`);
    if (rt.needs_time && r.from == null && r.to == null) add("rules", i, "Give the period(s).");
    if (r.from != null && r.to != null && r.to !== "" && Number(r.to) < Number(r.from)) add("rules", i, `${r.target || "Rule"}: the end is before the start.`);
    if (r.rule === "Fixed at" && r.subject && !subjectNames().includes(r.subject)) add("rules", i, `Fixed lesson: ${r.subject} is not on step 3.`);
    else if (r.rule === "Fixed at" && r.scope === "Class" && r.target && !S.spec.lessons.some(x => (x.classes || []).includes(r.target) && (!r.subject || x.subject === r.subject)))
      add("rules", i, `Fixed lesson: ${r.target} has no ${r.subject || "lesson"} on step 5, so this does nothing. Remove it (✕) or pick another.`);
    if (rt.needs_number && !r.number) add("rules", i, "Give the Number.");
    if (["Same time across classes", "Not on the same day as"].includes(r.rule) && !r.subject) add("rules", i, "Pick the Subject.");
  });
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
  S.spec.classes.forEach(c => {
    const l = per[c.class], size = Number(c.size) || 0; if (!l || !size) return;
    if (l.length < size) add("students", l[0], `${c.class}: ${l.length} of ${size} students listed. Once a class has a list, only the students on it are checked for clashes.`);
    if (l.length > size) add("students", l[0], `${c.class}: ${l.length} students listed but the class has ${size} on step 2.`);
  });
  return { out, load, info };
}
const stuKey = s => String(s.id || s.name || "").trim();
function targetOptions(scope) {
  return { School: ["Whole school"], Level: levels(), Class: classNames(), Teacher: teacherNames(), Department: sc().departments || [], Subject: subjectNames(), Block: blockNames(),
    Group: groupCodes(), Room: rooms() }[scope] || [];
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
  nav.innerHTML = STEPS.map(([id, label], i) => `<button data-step="${i}" class="${i === S.step ? "on" : ""}" ${!S.spec && i > 0 ? "disabled" : ""}><span>${label}</span><span class="n">${count(id)}</span></button>`).join("");
  $("#kindBadge").textContent = S.spec ? `${sc().type === "primary" ? "Primary" : "Secondary"} · ${sc().name}` : "No school yet";
  const id = STEPS[S.step][0]; const main = $("#main"); const y = window.scrollY;
  if (id === "adjust" && G.shown !== "adjust") { G.adj.data = null; G.adj.prop = null; G.adj.cut = null; }   // the timetable may have changed since
  G.shown = id;
  main.innerHTML = (VIEWS[id] || (() => ""))();
  renderIssues(); paintBanner(); saveState(); window.scrollTo(0, y);
  if (id === "generate") { paintGen(); poll(); }
}
/* the alert when the last generate found no timetable: on every step until a timetable is made or it is hidden */
function paintBanner() {
  const m = $("#main"); if (!m) return;
  let el = $("#alertBanner"); const a = G.alert, key = a ? `${G.runId}:${a.n}` : "";
  if (!a || !S.spec || G.dismissed === key || STEPS[S.step][0] === "generate") { if (el) el.remove(); return; }
  if (!el) { el = document.createElement("div"); el.id = "alertBanner"; m.prepend(el); }
  el.className = "banner";
  el.innerHTML = `<b>${esc(a.text)}</b> <span>See why, and what to change.</span><button class="small primary" data-step="${STEPS.findIndex(s => s[0] === "generate")}">How to fix it</button><button class="small ghost" data-dismiss="${esc(key)}" title="Hide this until the next generate">✕</button>`;
}
function fixesHTML(e) {   // the suggested fixes sent with a 'nosolution' event, each with a button to its step
  const f = (e.data && e.data.fixes) || []; if (!f.length) return "";
  const at = stepAt;
  return `<div class="fixes"><b>How to fix it</b><ol>${f.map(x => `<li>${esc(x.text)}${x.go && x.go !== "generate" && at(x.go) > 0 ? ` <button class="small" data-step="${at(x.go)}">Open ${esc(STEPS[at(x.go)][1].replace(/^\d+ /, ""))}</button>` : ""}</li>`).join("")}</ol></div>`;
}
const stepAt = id => STEPS.findIndex(s => s[0] === (id === "blocks" ? "lessons" : id));   // bands are a card on the teaching-groups step
function count(id) { if (!S.spec) return ""; const m = { venues: "venues", classes: "classes", subjects: "subjects", teachers: "teachers", blocks: "blocks", lessons: "lessons", rules: "rules", students: "students" }[id]; return m ? S.spec[m].length : ""; }
function renderIssues() {
  const el = $("#issues"); if (!S.spec) { el.innerHTML = ""; return; }
  const { out } = issues();
  const items = []; for (const [k, rows] of Object.entries(out)) if (k !== "global") for (const [i, ms] of Object.entries(rows)) for (const m of ms) items.push([k, i, m]);
  el.innerHTML = `<div class="card"><h2>Things to fix</h2>${items.length ? items.slice(0, 80).map(([k, i, m]) => `<div class="issue" data-go="${stepAt(k)}" data-row="${k}-${i}">${esc(m)}</div>`).join("") + (items.length > 80 ? `<div class="muted">…and ${items.length - 80} more</div>` : "")
    : '<div class="okmsg">Nothing to fix. The template is consistent.</div>'}</div>`;
}


function exportCard() {
  return `<div class="card" id="printouts"><h2>Printouts from a finished timetable</h2><p class="muted">Already have the timetable workbook the agent made? Upload it with its setup workbook to get every timetable as PDFs (one page per class, teacher, room and student), one Excel file with them all, and a searchable HTML page.</p>
    <div class="row" style="margin-top:10px"><label class="filebtn">Setup workbook (.xlsx)<input type="file" id="exSetup" accept=".xlsx" hidden></label><span class="muted" id="exSetupName">none chosen</span></div>
    <div class="row" style="margin-top:8px"><label class="filebtn">Timetable workbook (.xlsx)<input type="file" id="exTT" accept=".xlsx" hidden></label><span class="muted" id="exTTName">none chosen</span></div>
    <div class="row" style="margin-top:10px"><label><input type="checkbox" id="exSingle" checked> Also a separate PDF for every class, teacher, room and student</label></div>
    <div class="row" style="margin-top:12px"><button class="primary" id="exGo">Make printouts (.zip)</button><span class="muted" id="exMsg"></span></div></div>`;
}
const VIEWS = {
  start() {
    const sv = saved();
    return `<div class="card"><h1>Build your school's timetable setup</h1><p class="lead">This tool fills the timetable setup workbook step by step: rooms, classes, subjects, teachers, bands of groups, lessons, rules and students. Every list you make becomes the drop-down for the next step, so nothing is typed twice. At the end you download the workbook and the timetable skill, and an AI agent generates the timetable from them.</p>
      <div class="choice">
        <button data-begin="secondary|sample"><b>Secondary school · sample</b><span class="muted">A fictional 16-class secondary school with G1/G2/G3 banding, option bands and rules. Good for seeing how everything fits.</span></button>
        <button data-begin="primary|sample"><b>Primary school · sample</b><span class="muted">A fictional 18-class primary school, weekly timetable, Standard/Foundation banding at P5–P6.</span></button>
        <button data-begin="secondary|blank"><b>Secondary school · blank</b><span class="muted">Typical subjects and a day shape filled in; you add rooms, classes, teachers and lessons.</span></button>
        <button data-begin="primary|blank"><b>Primary school · blank</b><span class="muted">Typical subjects and day shape for P1–P6; you add the rest.</span></button>
      </div>
      <div class="row" style="margin-top:14px">
        ${G.server && G.server.spec ? `<button class="primary" id="serverSetup">Open the school's saved setup (${esc(G.server.spec.school.name)}, saved ${esc(G.server.saved_at)})</button>` : ""}
        ${sv ? `<button class="${G.server && G.server.spec ? "" : "primary"}" id="resume">Continue in this browser (${esc(sv.spec.school.name)})</button>` : ""}
        <label class="filebtn">Open a setup workbook (.xlsx)<input type="file" id="importX" accept=".xlsx" hidden></label>
      </div></div>
      <div class="card"><h2>How it works</h2><ol class="howto"><li>Fill the steps on the left. The panel on the right lists anything that does not add up (a teacher not set up for a subject, a teacher twice in a band, a lesson with no periods).</li><li>On <b>Generate &amp; publish</b>, make the timetable here: the AI timetabler checks, solves and asks you about conflicts in a chat. Publish when happy; teachers and students then sign in with their codes.</li><li>Or, on <b>Files</b>, download the setup workbook and the timetable skill to use with any AI agent.</li></ol></div>${exportCard()}`;
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
      <div class="card"><h2>Rules on the Settings sheet</h2><p class="muted">School-wide rules. Teacher block-outs, fixed lessons and any other rule are on step 6.</p>
      <div class="grid2">${SET().map(x => `<label class="f">${esc(x.label)} ${x.number
        ? `<input data-set="${x.key}" type="number" min="1" value="${esc(settingValue(x.key))}" placeholder="no limit">`
        : `<select data-set="${x.key}">${["Yes", "No"].map(v => opt(v, settingValue(x.key))).join("")}</select>`}</label>`).join("")}
      ${(s.extra_settings || []).map((x, i) => isRecessRow(x) ? "" : settingRow(x, i)).join("")}</div></div>
      <div class="card"><h2>Day structure</h2><div class="legend">Brush: ${["L", "R", "W", "U", "F", "A", ""].map(c => `<button class="small ${S.brush === c ? "primary" : ""}" data-brush="${c}"><i class="c-${c}" style="width:12px;height:12px;display:inline-block;border-radius:3px;vertical-align:-2px"></i> ${{ L: "Lesson", R: "Recess", W: "Recess window", U: "Lunch", F: "Flag / assembly", A: "After-school slot", "": "No school" }[c]}</button>`).join("")}</div>
      <p class="muted" style="margin:4px 0 10px">Click or drag across cells to paint them with the brush.</p>
      <div class="tablewrap"><table class="dsgrid">${head}${lvRows}</table></div>
      ${hasWindows() ? `<h3 style="margin:14px 0 4px">Floating recess</h3><p class="muted" style="margin:0 0 8px">For the W periods: the solver puts a recess of this length in each recess window. Make a window the recess plus whole lessons (for example 2 + 3 + 3 periods with 3-period lessons), so the lessons still fit wherever the recess goes.</p>
        <div class="grid2">${(s.extra_settings || []).map((x, i) => isRecessRow(x) ? settingRow(x, i) : "").join("")}</div>` : ""}</div>`;
  },
  venues() {
    const { out } = issues();
    return `<div class="card"><h1>Step 1 · Venues</h1><p class="lead">Every room. Its kind decides which subjects may use it (you set a subject's room kind on step 3). <b>Capacity</b> is seats: a group only goes in a room that seats it. <b>For</b> keeps a room for some subjects, departments or levels (for example "Chemistry G3, Sec 3"); blank = anyone. A room that holds two classes at once (a field, a hall) gets an "At most N at once" rule on step 6.</p>
      <div class="helper row"><b>Add rooms</b> prefix ${`<input id="hvPre" value="B1-" style="width:70px">`} from <input id="hvFrom" type="number" value="1" style="width:60px"> to <input id="hvTo" type="number" value="8" style="width:60px"> kind ${sel("_hv", "classroom", sc().room_kinds || [], false, 'id="hvKind" data-k=""')} <button data-helper="venues">Add</button></div>
      <div class="tablewrap"><table><tr><th>Room</th><th>Kind</th><th>Capacity</th><th>Block</th><th>Floor / level</th><th>Home room of</th><th>For</th><th>Note</th><th></th></tr>
      ${S.spec.venues.map((v, i) => `<tr id="venues-${i}" class="${out.venues[i] ? "bad" : ""}"><td>${inp(`spec.venues.${i}.room`, v.room)}</td><td>${sel(`spec.venues.${i}.kind`, v.kind, sc().room_kinds || [])}</td><td class="num">${inp(`spec.venues.${i}.capacity`, v.capacity, "number")}</td><td>${inp(`spec.venues.${i}.building`, v.building)}</td><td class="num">${inp(`spec.venues.${i}.floor`, v.floor)}</td><td class="calc">${esc(S.spec.classes.filter(c => c.home_room === v.room).map(c => c.class).join(", "))}</td><td style="min-width:170px"><input data-names="spec.venues.${i}.only_for" list="forNames" value="${esc((v.only_for || []).join(", "))}" placeholder="anyone"></td><td>${inp(`spec.venues.${i}.note`, v.note)}</td><td>${delBtn("venues", i)}</td></tr>`).join("")}
      </table></div><datalist id="forNames">${forNames().map(n => `<option value="${esc(n)}">`).join("")}</datalist><div class="row" style="margin-top:10px"><button data-add="venues">+ Add room</button></div></div>`;
  },
  classes() {
    const { out } = issues();
    return `<div class="card"><h1>Step 2 · Classes</h1><p class="lead">Form classes with their level, size and home room (picked from step 1).</p>
      <div class="helper row"><b>Add classes</b> level ${sel("_hc", levels()[0], levels(), false, 'id="hcLevel" data-k=""')} names <input id="hcNames" value="A, B, C, D" style="width:120px"> students <input id="hcSize" type="number" value="38" style="width:70px"> <button data-helper="classes">Add (home rooms filled from free classrooms)</button></div>
      <div class="tablewrap"><table><tr><th>Class</th><th>Level</th><th>Students</th><th>Home room</th><th>Lesson rows</th><th>Note</th><th></th></tr>
      ${S.spec.classes.map((c, i) => `<tr id="classes-${i}" class="${out.classes[i] ? "bad" : ""}"><td>${inp(`spec.classes.${i}.class`, c.class)}</td><td>${sel(`spec.classes.${i}.level`, c.level, levels())}</td><td class="num">${inp(`spec.classes.${i}.size`, c.size, "number")}</td><td>${sel(`spec.classes.${i}.home_room`, c.home_room, rooms())}</td><td class="calc">${S.spec.lessons.filter(x => (x.classes || []).includes(c.class)).length}</td><td>${inp(`spec.classes.${i}.note`, c.note)}</td><td>${delBtn("classes", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="classes">+ Add class</button></div></div>`;
  },
  subjects() {
    const { out } = issues(); const tags = (sc().tags || []).map(t => t[0]);
    return `<div class="card"><h1>Step 3 · Subjects</h1><p class="lead">Periods per ${Number(sc().weeks) === 2 ? "fortnight" : "week"} for each level that takes the subject (blank = not offered). Lessons are ${sc().lesson_length} periods long unless the subject says otherwise; leftovers become one or two shorter lessons. The code names the groups (1ELP1…). ${tagLabel()} is the level of study used for banding. <b>Teaching groups</b> fills in by itself: how many groups or classes are taught the subject on step 5 (each group in a band counts once, a whole-class subject once per class). 0 means no lessons yet, so it is not timetabled.</p>
      <div class="tablewrap"><table><tr><th>Subject</th><th>Code</th><th>${tagLabel()}</th><th>Department</th><th>Room kind</th><th>Lesson length</th>${levels().map(l => `<th>${esc(l)}</th>`).join("")}<th title="How many groups or classes have this subject on step 5 (Teaching groups & deployment): a banded group counts once, a whole-class subject once per class. 0: none yet, so it is not timetabled.">Teaching groups</th><th></th></tr>
      ${S.spec.subjects.map((s, i) => `<tr id="subjects-${i}" class="${out.subjects[i] ? "bad" : ""}"><td style="min-width:220px">${inp(`spec.subjects.${i}.subject`, s.subject)}</td><td class="num">${inp(`spec.subjects.${i}.code`, s.code, "text", 'style="width:54px"')}</td><td>${sel(`spec.subjects.${i}.tag`, s.tag, tags, false)}</td><td>${sel(`spec.subjects.${i}.dept`, s.dept, sc().departments || [])}</td><td>${sel(`spec.subjects.${i}.room_kind`, s.room_kind, sc().room_kinds || [])}</td><td class="num">${inp(`spec.subjects.${i}.lesson_length`, s.lesson_length, "number", 'style="width:56px"')}</td>${levels().map(l => `<td class="num">${inp(`spec.subjects.${i}.periods.${l}`, (s.periods || {})[l], "number", 'style="width:56px"')}</td>`).join("")}<td class="calc">${teachingGroups(s.subject)}</td><td>${delBtn("subjects", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="subjects">+ Add subject</button></div></div>`;
  },
  teachers() {
    const { out, load } = issues(), f = S.tf, P = S.pick, q = f.q.trim().toLowerCase();
    const rows = S.spec.teachers.map((t, i) => [t, i]).filter(([t]) => (!f.dept || t.dept === f.dept) && (!f.subj || (t.can_teach || []).some(c => c.subject === f.subj))
      && (!q || `${t.name || ""} ${t.short || ""}`.toLowerCase().includes(q)));
    P.shown.teachers = rows.map(([, i]) => i); const all = rows.length && rows.every(([, i]) => P.teachers.has(i));
    return `<div class="card"><h1>Step 4 · Teachers</h1><p class="lead">Each teacher with the subjects and levels they can teach (click the subjects cell). Lessons on step 5 are checked against this, and the teacher drop-down there lists the teachers who can teach the subject first. Tick teachers (shift-click for a run) to give them a subject, department, role or allowance together.</p>
      <div class="helper"><b>Add teachers</b> (one name per line) <div class="row" style="margin-top:6px"><textarea id="htNames" rows="3" style="width:280px;border:1px solid var(--line);border-radius:6px;padding:6px"></textarea> department ${sel("_ht", (sc().departments || [])[0], sc().departments || [], false, 'id="htDept" data-k=""')} allowance <input id="htAllow" type="number" value="${sc().type === "primary" ? 36 : 64}" style="width:70px"> <button data-helper="teachers">Add</button></div></div>
      <div class="row" style="margin:12px 0 8px"><b>Show</b> <select id="tfDept">${opt("", f.dept, "All departments")}${(sc().departments || []).map(d => opt(d, f.dept)).join("")}</select>
        <select id="tfSubj">${opt("", f.subj, "Any subject")}${subjectNames().map(n => opt(n, f.subj, `Can teach ${n}`)).join("")}</select>
        <input id="tfQ" type="search" placeholder="Search name" title="Type, then press Enter" value="${esc(f.q)}" style="width:160px">
        <span class="muted small">${rows.length === S.spec.teachers.length ? `${rows.length} teachers` : `${rows.length} of ${S.spec.teachers.length} teachers`}</span></div>
      ${teacherBar()}
      <div class="tablewrap"><table><tr><th><input type="checkbox" data-pickall="teachers" title="Tick every teacher shown (${rows.length})" ${all ? "checked" : ""}></th><th>Teacher</th><th>Short</th><th>Department</th><th>Allowance</th><th>Can teach</th><th>Given</th><th>Spare</th><th>Role</th><th>Other duties</th><th>Total load</th><th>Load check</th><th>Provisional</th><th></th></tr>
      ${(() => { const lc = loadChecks(load); return rows.map(([t, i]) => { const g = load[t.name] || 0; const sp = t.allowance ? Number(t.allowance) - g : ""; const tot = g + (Number(t.other_duties) || 0);
        return `<tr id="teachers-${i}" class="${out.teachers[i] ? "bad" : ""}${P.teachers.has(i) ? " picked" : ""}"><td><input type="checkbox" data-pick="teachers.${i}" ${P.teachers.has(i) ? "checked" : ""}></td><td style="min-width:180px">${inp(`spec.teachers.${i}.name`, t.name)}</td><td>${inp(`spec.teachers.${i}.short`, t.short, "text", 'style="width:90px"')}</td><td>${sel(`spec.teachers.${i}.dept`, t.dept, sc().departments || [])}</td><td class="num">${inp(`spec.teachers.${i}.allowance`, t.allowance, "number")}</td><td style="min-width:260px">${chips(`spec.teachers.${i}.can_teach`, (t.can_teach || []).map(c => `${c.subject} · ${c.levels || "All"}`), "canteach")}</td><td class="calc">${g}</td><td class="calc" style="${sp !== "" && sp < 0 ? "color:var(--warn);font-weight:600" : ""}">${sp}</td><td style="min-width:96px">${sel(`spec.teachers.${i}.role`, t.role, roles().map(r => r.role))}</td><td class="num">${inp(`spec.teachers.${i}.other_duties`, t.other_duties, "number", 'style="width:60px"')}</td><td class="calc" style="${t.allowance && tot > Number(t.allowance) ? "color:var(--warn);font-weight:600" : ""}">${tot}</td><td class="calc" style="white-space:normal;min-width:200px;${lc[i] ? "color:var(--warn)" : ""}">${esc(lc[i])}</td><td>${sel(`spec.teachers.${i}.provisional`, t.provisional, ["Yes", "No"])}</td><td>${delBtn("teachers", i)}</td></tr>`; }).join(""); })()}
      </table></div><div class="row" style="margin-top:10px"><button data-add="teachers">+ Add teacher</button></div></div>
      ${VIEWS.roles(load)}`;
  },
  roles(load) {   // the Roles sheet: guide allowance per role and the load of the teachers in it
    if (!S.spec.roles || !S.spec.roles.length) S.spec.roles = JSON.parse(JSON.stringify(S.meta.roles || []));
    const tot = t => (load[t.name] || 0) + (Number(t.other_duties) || 0), avg = a => a.length ? Math.round(a.reduce((x, y) => x + y, 0) / a.length) : "";
    const eo = avg(S.spec.teachers.filter(t => t.role === "EO" && tot(t) > 0).map(tot)), mgmt = avg(S.spec.teachers.filter(t => ["HOD", "SH"].includes(t.role) && tot(t) > 0).map(tot));
    return `<div class="card"><h2>Roles</h2><p class="muted">Management (HOD, SH) should teach fewer periods than teachers; teachers (EO) should be spread evenly. Teachers (EO) average load <b>${eo || "–"}</b> · management (HOD, SH) <b>${mgmt || "–"}</b>.
      Flag a teacher <input data-k="spec.school.role_spread" type="number" value="${esc(sc().role_spread ?? 15)}" style="width:56px"> periods or more from the teacher average.</p>
      <div class="tablewrap"><table><tr><th>Role</th><th>What it is</th><th>Guide allowance</th><th>Group</th><th>Teachers</th><th>Average load</th><th></th></tr>
      ${S.spec.roles.map((r, i) => { const ts = S.spec.teachers.filter(t => t.role === r.role);
        return `<tr><td>${inp(`spec.roles.${i}.role`, r.role, "text", 'style="width:80px"')}</td><td style="min-width:240px">${inp(`spec.roles.${i}.what`, r.what)}</td><td class="num">${inp(`spec.roles.${i}.allowance`, r.allowance, "number", 'style="width:64px"')}</td><td>${inp(`spec.roles.${i}.group`, r.group)}</td><td class="calc">${ts.length}</td><td class="calc">${avg(ts.map(tot))}</td><td>${delBtn("roles", i)}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="roles">+ Add role</button></div></div>`;
  },
  lessons() {
    const { out, info, load } = issues(); const T = teacherNames(), f = S.tg, P = S.pick;
    const tsel = (i, k, x) => { const path = `spec.lessons.${i}.teachers.${k}`; const cur = (x.teachers || [])[k] || ""; const yes = T.filter(t => canTeach(t, x.subject, x.level)), no = T.filter(t => !yes.includes(t));
      return `<select data-k="${path}">${opt("", cur, "")}<optgroup label="Can teach this">${yes.map(t => opt(t, cur)).join("")}</optgroup><optgroup label="Others">${no.map(t => opt(t, cur)).join("")}</optgroup></select>`; };
    const rows = S.spec.lessons.map((x, i) => [x, i]).filter(([x]) => (!f.lv || x.level === f.lv) && (!f.subj || x.subject === f.subj)
      && (!f.t || (f.t === "-" ? !(x.teachers || []).some(Boolean) : (x.teachers || []).includes(f.t))));
    P.shown.lessons = rows.map(([, i]) => i);
    const all = rows.length && rows.every(([, i]) => P.lessons.has(i));
    return `<div class="card"><h1>Step 5 · Teaching groups & deployment</h1><p class="lead">Every teaching group (TG) and the teachers deployed to it. A whole-class subject is one group per class; a band splits its classes into groups that all have lessons at the same time. Set up the bands first, then add the groups and deploy teachers below.</p>
      ${VIEWS._bands(out, info)}</div>
      <div class="card"><h2>Teaching groups</h2><p class="muted">One row per group, or per class for a whole-class subject. Pick level, subject and band (empty = whole class); choosing a band fills its classes. Group code, periods and lesson pattern fill in by themselves. Tick rows (shift-click for a run) to deploy a teacher to all of them at once.</p>
      <div class="helper row"><b>Add groups to a band</b> ${sel("_hb", "", blockNames(), true, 'id="hbBlock" data-k=""')} subject ${sel("_hbs", "", subjectNames(), true, 'id="hbSubj" data-k=""')} groups <input id="hbN" type="number" value="1" style="width:56px"> students each <input id="hbSt" type="number" style="width:64px"> <button data-helper="groups">Add</button></div>
      <div class="helper row"><b>Teachers for rows left blank</b> <span class="muted">${blankRows()} row${blankRows() === 1 ? "" : "s"} without a teacher</span> <button data-helper="allocate" ${blankRows() ? "" : "disabled"} title="Each row with Teacher 1 empty gets a teacher who can teach it, keeping everyone within their allowance and the load spread. Rows with a teacher are not changed. Undo takes it back.">Fill blank teachers</button>${S.alloc ? `<span class="muted small">${esc(S.alloc)}</span>` : ""}</div>
      <div class="helper row"><b>Add a whole-class subject</b> level ${sel("_hw", levels()[0], levels(), false, 'id="hwLevel" data-k=""')} subject ${sel("_hws", "", subjectNames(), true, 'id="hwSubj" data-k=""')} <button data-helper="whole">Add one row per class</button></div>
      <div class="row" style="margin:12px 0 8px"><b>Show</b> <select id="tgLv">${opt("", f.lv, "All levels")}${levels().map(l => opt(l, f.lv)).join("")}</select>
        <select id="tgSubj">${opt("", f.subj, "All subjects")}${subjectNames().map(n => opt(n, f.subj)).join("")}</select>
        <select id="tgT">${opt("", f.t, "Any teacher")}${opt("-", f.t, "No teacher yet")}${T.map(t => opt(t, f.t)).join("")}</select>
        <span class="muted small">${rows.length === S.spec.lessons.length ? `${rows.length} rows` : `${rows.length} of ${S.spec.lessons.length} rows`}</span></div>
      ${tgBar(load, info)}
      <div class="tablewrap"><table><tr><th><input type="checkbox" data-pickall="lessons" title="Tick every row shown (${rows.length})" ${all ? "checked" : ""}></th><th>Level</th><th>Subject</th><th>Band</th><th>Classes</th><th>Teacher 1</th><th>Teacher 2</th><th title="A third teacher in the room (co-teaching)">Teacher 3</th><th>Students</th><th>Periods override</th><th>Keep code</th>${Number(sc().weeks) === 2 ? '<th title="Odd or Even: the group uses its special room (lab, studio...) on that week only, and a classroom on the other">Special room weeks</th>' : ""}<th>Code</th><th>Periods</th><th>Lessons</th><th></th></tr>
      ${rows.map(([x, i]) => `<tr id="lessons-${i}" class="${out.lessons[i] ? "bad" : ""}${P.lessons.has(i) ? " picked" : ""}" title="${esc((out.lessons[i] || []).join(" "))}"><td><input type="checkbox" data-pick="lessons.${i}" ${P.lessons.has(i) ? "checked" : ""}></td><td class="lv">${sel(`spec.lessons.${i}.level`, x.level, levels())}</td><td style="min-width:200px">${sel(`spec.lessons.${i}.subject`, x.subject, subjectNames().filter(n => (subj(n).periods || {})[x.level] || n === x.subject))}</td><td style="min-width:160px">${sel(`spec.lessons.${i}.block`, x.block, S.spec.blocks.filter(b => !x.level || b.level === x.level).map(b => b.block))}</td><td style="min-width:120px">${chips(`spec.lessons.${i}.classes`, x.classes, "classes", `data-level="${esc(x.level || "")}"`)}</td><td style="min-width:150px">${tsel(i, 0, x)}</td><td style="min-width:120px">${tsel(i, 1, x)}</td><td style="min-width:120px">${tsel(i, 2, x)}</td><td class="num">${inp(`spec.lessons.${i}.students`, x.students, "number", 'style="width:60px"')}</td><td class="num">${inp(`spec.lessons.${i}.periods_override`, x.periods_override, "number", 'style="width:60px"')}</td><td class="num">${inp(`spec.lessons.${i}.code_override`, x.code_override, "text", 'style="width:70px"')}</td>${Number(sc().weeks) === 2 ? `<td><select data-k="spec.lessons.${i}.room_weeks" ${special(x) ? "" : "disabled title=\"Only for a subject with a special room kind, such as a lab (step 3)\""}>${opt("", x.room_weeks || "", "every week")}${opt("Odd", x.room_weeks, "Odd only")}${opt("Even", x.room_weeks, "Even only")}</select></td>` : ""}<td class="calc">${esc(info[i].code)}</td><td class="calc">${info[i].p || ""}</td><td class="calc">${info[i].p ? `${info[i].full}×${info[i].L}${info[i].short ? ` + ${info[i].short}×${info[i].L - 1}` : ""}` : ""}</td><td>${delBtn("lessons", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="lessons">+ Add teaching group</button></div></div>`;
  },
  _bands(out, info) {
    const open = S.bandsOpen ?? (!S.spec.blocks.length || Object.keys(out.blocks).length > 0);   // until the committee opens or closes it
    return `<details class="bands" ${open ? "open" : ""}><summary><h2>Bands <span class="muted" style="font-weight:400;font-size:14px">${S.spec.blocks.length} band${S.spec.blocks.length === 1 ? "" : "s"}${Object.keys(out.blocks).length ? ` · ${Object.keys(out.blocks).length} to fix` : ""}</span></h2></summary><p class="muted">A band takes the students of its classes and splits them into groups that all have lessons at the same time (for example, Sec 1 English for 1A–1D split by G3, G2 and G1). Name the band and pick its classes; then add its groups under Teaching groups.</p>
      <div class="tablewrap"><table><tr><th>Band</th><th>Level</th><th>Classes</th><th>Groups (from Teaching groups)</th><th>Students in groups / classes</th><th>Note</th><th></th></tr>
      ${S.spec.blocks.map((b, i) => { const gs = S.spec.lessons.map((x, j) => [x, j]).filter(([x]) => x.block === b.block); const inG = gs.reduce((a, [x]) => a + (Number(x.students) || 0), 0), inC = (b.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
        return `<tr id="blocks-${i}" class="${out.blocks[i] ? "bad" : ""}"><td style="min-width:200px">${inp(`spec.blocks.${i}.block`, b.block)}</td><td>${sel(`spec.blocks.${i}.level`, b.level, levels())}</td><td style="min-width:180px">${chips(`spec.blocks.${i}.classes`, b.classes, "classes", `data-level="${esc(b.level || "")}"`)}</td><td class="calc" style="white-space:normal">${esc(gs.map(([x, j]) => info[j].code).join(", "))}</td><td class="calc">${inG} / ${inC}</td><td>${inp(`spec.blocks.${i}.note`, b.note)}</td><td>${delBtn("blocks", i)}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="blocks">+ Add band</button></div></details>`;
  },
  rules() {
    const { out } = issues(); const RT = S.meta.rule_types || []; const NP = Number(sc().periods_per_day); const P = Array.from({ length: NP }, (_, p) => p);
    const psel = (path, cur) => `<select data-k="${path}">${opt("", cur ?? "", "")}${P.map(p => opt(p, cur, `${p} (${clock(p)})`)).join("")}</select>`;
    const weeks = Number(sc().weeks) === 2 ? ["Both", "Odd", "Even"] : ["Both"], days = ["All", "Mon", "Tue", "Wed", "Thu", "Fri"];
    const where = placeRules(), bad = i => out.rules[i] ? "bad" : "", tip = i => esc((out.rules[i] || []).join(" "));
    const avail = where.availability.map(i => { const r = S.spec.rules[i], [a, b] = ruleTimes(r);
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td style="min-width:180px">${sel(`spec.rules.${i}.target`, r.target, teacherNames())}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td>
        <td><input data-time="${i}|0" type="time" value="${esc(a)}"></td><td><input data-time="${i}|1" type="time" value="${esc(b)}"></td><td class="calc">${r.from === r.to || r.to == null ? `period ${r.from}` : `periods ${r.from}–${r.to}`}</td><td class="note">${inp(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>`; }).join("");
    const codes = groupCodes();
    const fixed = where.fixed.map(i => { const r = S.spec.rules[i], lv = r.level || clsLevel(r.target);
      const who = [...classNames().filter(c => !lv || clsLevel(c) === lv), ...codes.filter(c => !lv || String(lv).slice(-1) === c[0])];
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td>${sel(`spec.rules.${i}.level`, lv, levels())}</td><td style="min-width:110px">${sel(`spec.rules.${i}.target`, r.target, who)}</td><td style="min-width:180px">${sel(`spec.rules.${i}.subject`, r.subject, subjectNames())}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td><td>${psel(`spec.rules.${i}.from`, r.from)}</td><td class="note">${inp(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>`; }).join("");
    const more = where.more.map(i => { const r = S.spec.rules[i];
      return `<tr id="rules-${i}" class="${bad(i)}" title="${tip(i)}"><td><select data-k="spec.rules.${i}.scope">${opt("", r.scope, "")}${S.meta.scopes.map(v => opt(v, r.scope, v === "Block" ? "Band" : v)).join("")}</select></td><td style="min-width:150px">${sel(`spec.rules.${i}.target`, r.target, targetOptions(r.scope))}</td><td style="min-width:150px">${sel(`spec.rules.${i}.subject`, r.subject, subjectNames())}</td><td style="min-width:180px">${sel(`spec.rules.${i}.rule`, r.rule, RT.filter(t => !r.scope || t.scopes.includes(r.scope)).map(t => t.rule))}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", weeks, false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", days, false)}</td><td>${psel(`spec.rules.${i}.from`, r.from)}</td><td>${psel(`spec.rules.${i}.to`, r.to)}</td><td class="num">${inp(`spec.rules.${i}.number`, r.number, "number", 'style="width:56px"')}</td><td>${sel(`spec.rules.${i}.strength`, r.strength || "Must", ["Must", "Prefer"], false)}</td><td class="note">${inp(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>`; }).join("");
    return `<div class="card"><h1>Step 6 · Teacher availability</h1><p class="lead">Times a teacher cannot teach (part-time days, a centre or programme after school). Times are clock times; every period they overlap is blocked. School-wide rules are on <b>School &amp; day</b>.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Teacher</th><th>Week</th><th>Day</th><th>From</th><th>To</th><th>Blocks</th><th>Reason</th><th></th></tr>${avail}</table></div>
      <div class="row" style="margin-top:10px"><button data-add="avail">+ Add block-out</button></div></div>
      <div class="card"><h2>Fixed lessons</h2><p class="muted">Lessons that must start at a set time (optional): a class with a subject, or a group code from step 5. Leave empty to let the timetable place everything.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Level</th><th>Class or group</th><th>Subject</th><th>Week</th><th>Day</th><th>Start period</th><th>Note</th><th></th></tr>${fixed}</table></div>
      <div class="row" style="margin-top:10px"><button data-add="fixed">+ Add fixed lesson</button></div></div>
      <div class="card"><h2>More rules</h2><p class="muted">Any other constraint: rooms, levels, subjects, Prefer rules and so on. First pick what the rule applies to; the next drop-down lists only those. <b>Must</b> is never broken; <b>Prefer</b> is kept where possible.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Applies to</th><th>Which</th><th>Subject (optional)</th><th>Rule</th><th>Week</th><th>Day</th><th>From</th><th>To</th><th>Number</th><th>Must / Prefer</th><th>Note</th><th></th></tr>${more}</table></div>
      <div class="row" style="margin-top:10px"><button data-add="rules">+ Add rule</button></div></div>
      <div class="card"><h2>Rule types</h2><div class="tablewrap" style="max-height:none"><table><tr><th>Rule</th><th>Applies to</th><th>What it means</th><th>Example</th></tr>${RT.map(t => `<tr><td><b>${esc(t.rule)}</b></td><td>${esc(t.scopes)}</td><td>${esc(t.meaning)}</td><td class="muted">${esc(t.example)}</td></tr>`).join("")}</table></div></div>`;
  },
  students() {
    const { out } = issues(); const L = S.spec.students, f = S.stu, q = f.q.trim().toLowerCase(), MAX = 200;
    const combos = (S.spec.combinations || []).map(c => c.code).filter(Boolean);
    const per = {}; L.forEach(s => per[s.class] = (per[s.class] || 0) + 1);
    const rows = L.map((s, i) => [s, i]).filter(([s]) => (!f.cls || s.class === f.cls) && (!q || `${s.id || ""} ${s.name || ""}`.toLowerCase().includes(q)));
    const P = S.pick; P.shown.students = rows.map(([, i]) => i); const all = rows.length && rows.every(([, i]) => P.students.has(i));
    const clsOpts = [opt("", f.cls, `All classes (${L.length})`), ...S.spec.classes.map(c => opt(c.class, f.cls, `${c.class} · ${per[c.class] || 0} of ${c.size || "?"}`)),
      ...[...new Set(L.map(s => s.class || ""))].filter(c => !classNames().includes(c)).map(c => opt(c, f.cls, c ? `${c} (not on step 2) · ${per[c]}` : `No class · ${L.filter(s => !s.class).length}`))].join("");
    return `<div class="card"><h1>Step 7 · Students <span class="muted" style="font-weight:400;font-size:15px">(optional)</span></h1><p class="lead">List each student with their class and the codes of the groups they are in (from step 5). The solver then makes sure no student has two lessons at once, and every student gets their own timetable and a personal sign-in code. Without a list, the students of a class are assumed to be in the same level tag (all G3, all Foundation) in every band, so students on mixed combinations are not checked. To fill groups here, tick students (shift-click for a run, or the box at the top for everyone shown) and add them to a group or move them to a class together.</p>
      <div class="helper"><b>Paste or upload the student list</b>
        <p class="muted small" style="margin:4px 0 8px">Copy the rows from Excel or a CSV file, with a header row: <b>Student ID</b>, <b>Name</b>, <b>Class</b> and <b>Groups</b> (codes in one cell separated by commas, or one code per column). Without a header, the columns are read as ID, name, class, then groups. Whole-class subjects need no codes: a student has those with their class. Use an ID that stays the same (an admission number, say): personal codes are made from it.</p>
        <textarea id="stuPaste" rows="5" spellcheck="false" placeholder="Student ID&#9;Name&#9;Class&#9;Groups&#10;S001&#9;Tan Wei Ming&#9;1A&#9;1ELP1, 1MAP1, 1SCP1"></textarea>
        <div class="row" style="margin-top:8px"><label class="filebtn">Choose a file (.xlsx or .csv)<input type="file" id="stuFile" accept=".xlsx,.csv,.tsv,.txt" hidden></label><button class="primary" data-stu="replace">Replace the list</button><button data-stu="add">Add to the list</button><span class="muted small" id="stuMsg"></span></div></div></div>
      <div class="card"><div class="row" style="justify-content:space-between"><h2 style="margin:0">The list</h2>
        <div class="row"><select id="stuCls">${clsOpts}</select><input id="stuQ" type="search" placeholder="Search ID or name" title="Type, then press Enter" value="${esc(f.q)}" style="width:190px"><span class="muted small">${rows.length === L.length ? `${L.length} students` : `${rows.length} of ${L.length}`}</span>${L.length ? `<button class="small danger" data-stu="clear">Remove all</button>` : ""}</div></div>
      ${stuBar()}${L.length ? `<div class="tablewrap" style="margin-top:10px"><table><tr><th><input type="checkbox" data-pickall="students" title="Tick every student shown (${rows.length})" ${all ? "checked" : ""}></th><th>Student ID</th><th>Name</th><th>Class</th><th>Level</th>${combos.length ? "<th>Combination</th>" : ""}<th>Groups (click to pick)</th><th>Note</th><th></th></tr>
      ${rows.slice(0, MAX).map(([s, i]) => `<tr id="students-${i}" class="${out.students[i] ? "bad" : ""}${P.students.has(i) ? " picked" : ""}" title="${esc((out.students[i] || []).join(" "))}"><td><input type="checkbox" data-pick="students.${i}" ${P.students.has(i) ? "checked" : ""}></td><td>${inp(`spec.students.${i}.id`, s.id, "text", 'style="width:110px"')}</td><td style="min-width:190px">${inp(`spec.students.${i}.name`, s.name)}</td><td style="min-width:88px">${sel(`spec.students.${i}.class`, s.class, classNames())}</td><td class="calc">${esc(clsLevel(s.class) || s.level || "")}</td>${combos.length ? `<td>${sel(`spec.students.${i}.combination`, s.combination, combos)}</td>` : ""}<td style="min-width:260px">${chips(`spec.students.${i}.groups`, s.groups, "groups", `data-cls="${esc(s.class || "")}"`)}</td><td>${inp(`spec.students.${i}.note`, s.note)}</td><td>${delBtn("students", i)}</td></tr>`).join("")}
      </table></div>${rows.length > MAX ? `<p class="muted small">Showing the first ${MAX}. Pick a class or search to see the rest.</p>` : ""}`
        : `<p class="muted" style="margin-top:10px">No students yet. Paste or upload a list above, or add students one by one.</p>`}
      <div class="row" style="margin-top:10px"><button data-add="students">+ Add student</button></div></div>`;
  },
  generate() {
    const st = G.st || {}, off = st.ai && !st.ai.ok;
    const facts = [st.ai && st.ai.ok ? `AI: ${esc(st.ai.provider)} · ${esc(st.ai.model)}${st.ai.effort ? ` · effort ${esc({ xhigh: "extra high" }[st.ai.effort] || st.ai.effort)}` : ""}` : ""].filter(Boolean);
    const secs = solveSecs(), mins = [5, 20, 60, 120, 240, 480].filter(m => m * 60 <= (st.solve_max || 28800));
    if (!mins.includes(secs / 60)) mins.push(secs / 60), mins.sort((a, b) => a - b);
    const long = `<label class="row" style="gap:6px" title="A tight timetable can take a long time to find. The best timetable so far is kept if you press Stop.">Solve for up to
      <select id="solveSecs">${mins.map(m => opt(m * 60, secs, m < 60 ? `${m} min` : `${m / 60} hour${m > 60 ? "s" : ""}`)).join("")}</select></label>`;
    return `<div class="card"><h1>Generate & publish</h1><p class="lead">Generate makes the timetable from this setup (it is saved to the server first). With the AI timetabler, it checks the setup, runs the solver and asks you in the chat about anything that does not fit; without AI, it checks and solves, and you read the results. Nothing is visible to teachers or students until you publish.</p>
      ${off ? `<div class="notice"><b>The AI timetabler is off.</b> ${/AI_API_KEY/.test(st.ai.why) ? "No AI API key has been added yet." : esc(st.ai.why)} You can still use <b>Generate without AI</b>: it checks the setup and runs the solver, then you read the results and change the setup yourself. The chat, where the AI explains problems and makes tweaks for you, needs the key: whoever runs the app adds it in Railway (service → Variables → <code>AI_API_KEY</code>, with <code>AI_PROVIDER</code>).</div>` : ""}
      <div class="row"><button class="${off ? "" : "primary"}" id="genAI"${off ? ` title="Needs an AI API key. Generate without AI still works."` : ""}>Generate with the AI timetabler</button><button class="${off ? "primary" : ""}" id="genPlain">Generate without AI</button><button class="danger" id="genStop" hidden>Stop</button>${long}</div>
      <p class="muted small">${facts.join(" · ")}</p></div>
      <div class="gen"><div class="card chat"><h2>Timetabler</h2><div id="chatlog" class="chatlog"></div><div id="progress" class="progress"></div>
        <form id="chatform" class="chatform" onsubmit="event.preventDefault(); sendChat(document.getElementById('chatin').value)"><input id="chatin" autocomplete="off"><button class="primary" id="chatsend">Send</button></form></div>
        <div class="side"><div class="card" id="resultCard"></div><div class="card" id="pubCard"></div></div></div>`;
  },
  adjust() {
    const A = G.adj, gen = STEPS.findIndex(s => s[0] === "generate");
    const head = `<h1>Adjust the timetable</h1><p class="lead">Teachers' changes before publishing. Pick a class, teacher or room, click a lesson, then move it <b>earlier</b> or <b>later</b>, or <b>cut</b> it and click where it should go. A move that clashes shows why and the ways out: a free time, a swap, letting the solver make room, or asking the AI. Lessons you move are pinned (📌): later solves keep them there.</p>`;
    if (!A.data) { if (!A.loading) loadAdjust(); return `<div class="card">${head}<p class="muted">${esc(A.error || "Loading the latest timetable…")}</p>${A.error ? `<button data-step="${gen}">Go to Generate & publish</button>` : ""}</div>`; }
    const D = A.data, busy = G.st && G.st.run && G.st.run.busy, sm = D.summary;
    const lists = { class: D.classes, teacher: D.teachers, room: D.rooms };
    if (!lists[A.kind].includes(A.who)) A.who = lists[A.kind][0] || "";
    const sel = A.sel && D.lessons.find(l => l.key === A.sel), cut = A.cut && D.lessons.find(l => l.key === A.cut);
    const status = `<p class="${sm.ok ? "okmsg" : "issue"}" style="margin:0">${sm.ok ? "All checks pass" : `${sm.problems.length} problem${sm.problems.length === 1 ? "" : "s"}`} · ${sm.lessons} lessons${sm.after.length ? ` · ${sm.after.length} after school` : ""}${D.moves ? ` · ${D.moves} change${D.moves === 1 ? "" : "s"} by hand` : ""}</p>`;
    const bar = `<div class="row" style="justify-content:space-between;margin-top:10px">${status}<div class="row">
        <button data-adj="undo" ${D.can_undo && !busy ? "" : "disabled"} title="${esc(D.last ? "Undo: " + D.last : "")}">↶ Undo move</button><button data-adj="redo" ${D.can_redo && !busy ? "" : "disabled"}>↷ Redo</button>
        ${G.st && G.st.run && G.st.run.changes ? `<button id="keepChanges" ${busy ? "disabled" : ""} title="Lessons made shorter or longer change the plan: this puts them in your setup too">Keep these changes in my setup</button>` : ""}
        <a href="/preview" target="_blank"><button>Preview</button></a><button class="primary" id="publish" ${busy ? "disabled" : ""}>Publish</button></div></div>
      ${sm.problems.length ? `<details style="margin-top:6px"><summary class="small">The problems</summary><ul class="small">${sm.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></details>` : ""}`;
    const pick = `<div class="row" style="margin-top:12px"><label class="row" style="gap:6px">Show <select id="adjKind">${["class", "teacher", "room"].map(k => opt(k, A.kind, k[0].toUpperCase() + k.slice(1))).join("")}</select></label>
      <select id="adjWho">${lists[A.kind].map(x => opt(x, A.who)).join("")}</select>
      ${busy ? `<span class="muted small">${esc((G.st.run.progress) || "Working…")} Changes wait until it finishes.</span>` : ""}</div>`;
    const act = cut ? `<div class="adjbar"><b>✂ ${esc(cut.name)}</b> <span class="muted">${esc(adjWhen(cut.start, cut.ln))}</span> · click where it should go (you can switch class, teacher or room first) <button class="small" data-adj="cancel">Cancel</button></div>`
      : sel ? `<div class="adjbar"><b>${esc(sel.name)}</b> <span class="muted">${esc(adjWhen(sel.start, sel.ln))} · ${esc(sel.teachers.join(", ") || "no teacher")} · ${esc([...new Set(sel.rows.map(r => r.room).filter(Boolean))].join(", ") || "no room")}</span>${sel.pinned ? " 📌" : ""}
          <button class="small" data-adj="earlier" ${busy ? "disabled" : ""}>◀ Earlier</button><button class="small" data-adj="later" ${busy ? "disabled" : ""}>Later ▶</button><button class="small" data-adj="cut" ${busy ? "disabled" : ""}>✂ Cut</button><button class="small" data-adj="shorter" ${busy || sel.ln < 2 ? "disabled" : ""} title="One period shorter, where it is: its group then has one period fewer a cycle">− 1 period</button><button class="small" data-adj="longer" ${busy ? "disabled" : ""} title="One period longer, where it is (the next period must be free): its group then has one period more a cycle">+ 1 period</button>${sel.pinned ? `<button class="small" data-adj="unpin" ${busy ? "disabled" : ""} title="Let later solves move it again">Unpin</button>` : ""}<button class="small ghost" data-adj="cancel">✕</button></div>`
      : `<p class="muted small" style="margin:8px 0 0">Click a lesson to move it. Keys: ← → move it, Esc lets go.</p>`;
    return `<div class="card">${head}${bar}${pick}${act}${adjPanel()}<div class="tablewrap" style="margin-top:10px;max-height:none"><table class="adjgrid">${adjGrid(D, A)}</table></div></div>`;
  },
  download() {
    const { out } = issues(); const n = Object.entries(out).filter(([k]) => k !== "global").reduce((a, [, v]) => a + Object.keys(v).length, 0);
    return `<div class="card"><h1>Files</h1><p class="lead">Your setup workbook keeps the drop-downs and formulas, so it can still be edited in Excel. To generate here, use <b>Generate &amp; publish</b>; to generate elsewhere, give the workbook and the timetable skill to an AI agent that can run code.</p>
      <div><span class="stat"><b>${S.spec.classes.length}</b> classes</span><span class="stat"><b>${S.spec.teachers.length}</b> teachers</span><span class="stat"><b>${S.spec.blocks.length}</b> bands</span><span class="stat"><b>${S.spec.lessons.length}</b> lesson rows</span><span class="stat"><b>${S.spec.rules.length}</b> rules</span><span class="stat"><b>${S.spec.students.length}</b> students</span></div>
      ${n ? `<p class="issue" style="margin-top:12px">${n} rows still have something to fix (see the right-hand panel). You can download anyway; the agent will report them.</p>` : '<p class="okmsg" style="margin-top:12px">Everything checks out.</p>'}</div>
      <div class="dl">
        <div class="card"><h2>1 · Your setup workbook</h2><p class="muted">Everything you entered, as the .xlsx template.</p><button class="primary" id="build">Download setup workbook (.xlsx)</button></div>
        <div class="card"><h2>2 · The timetable skill</h2><p class="muted">SKILL.md plus the solver scripts and sample templates. SKILL.md alone also works: it tells the agent how to build the solver.</p><div class="row"><a href="/download/skill.zip"><button class="primary">Skill bundle (.zip)</button></a><a href="/download/SKILL.md"><button>SKILL.md only</button></a></div></div>
        <div class="card"><h2>Templates to share</h2><p class="muted">Ready-made workbooks for others to fill in Excel.</p><div class="row"><a href="/download/template/secondary"><button>Sample secondary</button></a><a href="/download/template/primary"><button>Sample primary</button></a><a href="/download/blank/secondary"><button>Blank secondary</button></a><a href="/download/blank/primary"><button>Blank primary</button></a></div></div>
      </div>
      <div class="card" style="margin-top:16px"><h2>Generate the timetable with an AI agent</h2><ol class="howto">
        <li>In Claude (or another agent that can run Python), add the skill: upload the .zip as a skill, or attach SKILL.md to the conversation.</li>
        <li>Upload your setup workbook and ask: <i>"Generate our timetable from this setup. Report anything that does not fit."</i></li>
        <li>The agent checks the inputs, solves (a few minutes for a typical school), and returns the timetables: one Excel workbook with every class, teacher, room and student, PDFs (one page each) to print or send, and a searchable HTML page, plus what (if anything) had to go after school.</li>
        <li>Change the setup here or in Excel and ask again: the agent re-solves from the new file.</li></ol></div>${exportCard()}`;
  },
};

/* ---------------- events */
document.addEventListener("click", async e => {
  const pop = $("#pop");
  if (!pop.hidden && !pop.contains(e.target)) commitPop();
  if (e.target.dataset && (e.target.dataset.pick || e.target.dataset.pickall)) { pick(e.target, e.shiftKey); return; }
  const b = e.target.closest("button, [data-pop], .issue, td.c, td.as"); if (!b) return;
  if (b.dataset.step) { S.step = Number(b.dataset.step); save(); render(); window.scrollTo(0, 0); return; }
  if (b.id === "undo" || b.id === "redo") { undo(b.id === "undo"); return; }
  if (b.dataset.adj) { adjAction(b.dataset.adj); return; }
  if (b.dataset.adjgo) { const P = G.adj.prop; if (P) adjMove({ [P.key]: Number(b.dataset.adjgo) }); return; }
  if (b.dataset.adjswap) {
    const P = G.adj.prop, L = G.adj.data.lessons, o = L.find(l => l.key === b.dataset.adjswap), me = P && L.find(l => l.key === P.key);
    if (o && me) adjMove({ [me.key]: o.start, [o.key]: me.start }, `Swapped ${me.name} and ${o.name}`); return; }
  if (b.dataset.lesson) {   // a lesson: select it, or (with one cut) paste the cut lesson at its time
    const A = G.adj, k = b.dataset.lesson;
    if (A.cut && A.cut !== k) adjCheck(A.cut, { start: A.data.lessons.find(l => l.key === k).start });
    else { if (!A.cut) A.sel = A.sel === k ? null : k; A.prop = null; A.ai = ""; render(); }
    return; }
  if (b.classList.contains("as")) { if (G.adj.cut) adjCheck(G.adj.cut, { start: Number(b.dataset.start) }); return; }
  if (b.id === "saveServer") { saveServer(); return; }
  if (b.dataset.dismiss) { G.dismissed = b.dataset.dismiss; paintBanner(); return; }
  if (b.dataset.clear) { setPath(b.dataset.clear, ""); save(); render(); return; }
  if (b.dataset.begin) { const [k, w] = b.dataset.begin.split("|"); try { await begin(k, w); } catch (err) { toast("Could not load: " + err.message); } return; }
  if (b.id === "resume") { const sv = saved(); await adopt(sv.spec, "", { kind: sv.kind, step: sv.step, base: sv.base, dirty: sv.dirty !== false }); return; }
  if (b.dataset.add) { addRow(b.dataset.add); return; }
  if (b.dataset.del) { const [k, i] = b.dataset.del.split("."); S.spec[k].splice(Number(i), 1); unpick(); save(); render(); return; }
  if (b.dataset.helper) { helper(b.dataset.helper); return; }
  if (b.dataset.brush !== undefined) { S.brush = b.dataset.brush; render(); return; }
  if (b.dataset.copyday) { const lv = b.dataset.copyday; const ds = S.spec.day_structure[lv]; const f = ds[dayNames()[0]]; dayNames().forEach(d => ds[d] = f); save(); render(); return; }
  if (b.dataset.copylevel) { const src = S.spec.day_structure[b.dataset.copylevel]; levels().forEach(l => S.spec.day_structure[l] = { ...src }); save(); render(); return; }
  if (b.dataset.pop) { openPop(b); return; }
  if (b.dataset.stu) { stuApply(b.dataset.stu); return; }
  if (b.dataset.bulk) { bulk(b.dataset.bulk); return; }
  if (b.classList.contains("issue") && b.dataset.go) {
    const s = /^students-/.test(b.dataset.row) && S.spec.students[Number(b.dataset.row.slice(9))];
    if (s) S.stu = classNames().includes(s.class) ? { cls: s.class, q: "" } : { cls: "", q: stuKey(s) };
    if (/^lessons-/.test(b.dataset.row)) S.tg = { lv: "", subj: "", t: "" };
    if (/^teachers-/.test(b.dataset.row)) S.tf = { dept: "", subj: "", q: "" };
    S.step = Number(b.dataset.go); render(); const r = document.getElementById(b.dataset.row); if (r) r.scrollIntoView({ block: "center" }); return; }
  if (b.id === "build") { buildXlsx(); return; }
  if (b.id === "serverSetup") { await adopt(G.server.spec, "Opened the school's saved setup.", { base: G.server.ts, dirty: false }); return; }
  if (b.id === "genAI" || b.id === "genPlain") { generate(b.id === "genAI"); return; }
  if (b.id === "genStop") { await post("/api/stop"); poll(); return; }
  if (b.id === "publish") { if (!confirm("Publish this timetable? Teachers and students will see it straight away.")) return; const j = await post("/api/publish"); if (j) { toast("Publishing… about a minute."); poll(); } return; }
  if (b.id === "keepChanges") { const j = await post("/api/keep-changes"); if (j && j.spec) { S.spec = j.spec; save(); await synced(); toast("The changes are now in your setup."); poll(); } return; }
  if (b.dataset.answer !== undefined) { sendChat(b.dataset.answer); return; }
  if (b.id === "exGo") { makePrintouts(); return; }
  if (b.id === "saveJson") { if (!S.spec) { toast("Open or start a setup first."); return; } const blob = new Blob([JSON.stringify(S.spec, null, 1)], { type: "application/json" }); dl(blob, `${sc().name || "timetable"}_setup.json`); return; }
});
document.addEventListener("toggle", e => { if (e.target.classList && e.target.classList.contains("bands")) S.bandsOpen = e.target.open; }, true);
document.addEventListener("keydown", e => {   // ⌘Z / Ctrl+Z undo, ⇧⌘Z / Ctrl+Y redo; inside a text box the browser's own undo applies
  if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
  const k = e.key.toLowerCase(); if (k !== "z" && k !== "y") return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable]")) return;
  e.preventDefault(); undo(k === "z" && !e.shiftKey);
});
document.addEventListener("keydown", e => {   // Adjust page: ← → move the selected lesson, Esc lets go
  if (STEPS[S.step][0] !== "adjust" || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.target.closest && e.target.closest("input, textarea, select")) return;
  if (e.key === "Escape") { adjAction("cancel"); return; }
  if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && G.adj.sel && !G.adj.cut) { e.preventDefault(); adjAction(e.key === "ArrowLeft" ? "earlier" : "later"); }
});
let painting = false;
document.addEventListener("mousedown", e => { const c = e.target.closest("td.c"); if (!c) return; painting = true; paint(c); e.preventDefault(); });
document.addEventListener("mouseover", e => { if (!painting) return; const c = e.target.closest("td.c"); if (c) paint(c); });
document.addEventListener("mouseup", () => { if (painting) { painting = false; const added = ensureRecessRows(); save(); if (added) render(); else renderIssues(); } });
function paint(c) {
  const [lv, d, p] = c.dataset.cell.split("|"); const row = S.spec.day_structure[lv][d].split(""); row[Number(p)] = S.brush || "."; S.spec.day_structure[lv][d] = row.join("");
  c.className = `c c-${S.brush}`; c.textContent = S.brush;
}
document.addEventListener("change", async e => {
  const el = e.target;
  if (el.id === "importX") { const f = el.files[0]; if (!f) return; const fd = new FormData(); fd.append("file", f); const r = await fetch("/api/import", { method: "POST", body: fd }); const j = await r.json(); if (!r.ok) { toast(j.error || "Could not read that file."); return; } await adopt(j, "Workbook opened. Press Save progress to keep it for the school."); return; }
  if (el.id === "adjKind") { G.adj.kind = el.value; G.adj.who = ""; render(); return; }
  if (el.id === "adjWho") { G.adj.who = el.value; render(); return; }
  if (el.id === "solveSecs") { try { localStorage.setItem("ttsolve", el.value); } catch (err) { } toast(`Each solve may now run up to ${$("#solveSecs").selectedOptions[0].textContent}. Stop keeps the best timetable so far.`); return; }
  if (el.id === "loadJson") { const f = el.files[0]; if (!f) return; el.value = ""; try { await adopt(JSON.parse(await f.text()), "Progress loaded from the file. Press Save progress to keep it for the school."); } catch (err) { toast("That file is not a progress file."); } return; }
  if (el.dataset.names) { setPath(el.dataset.names, el.value.split(",").map(t => t.trim()).filter(Boolean)); save(); render(); return; }
  if (el.dataset.list) { sc()[el.dataset.list] = el.value.split(",").map(s => s.trim()).filter(Boolean); if (el.dataset.list === "levels") ensureDays(); save(); render(); return; }
  if (el.id === "stuFile") { stuFile(el); return; }
  if (el.id === "stuCls" || el.id === "stuQ") { S.stu[el.id === "stuCls" ? "cls" : "q"] = el.value; render(); return; }
  if (["tgLv", "tgSubj", "tgT"].includes(el.id)) { S.tg[{ tgLv: "lv", tgSubj: "subj", tgT: "t" }[el.id]] = el.value; render(); return; }
  if (["pickT", "pickG", "pickC", "pickS", "pickV", "pickD", "pickR", "pickA"].includes(el.id)) { S.pick[el.id.slice(4).toLowerCase()] = el.value; render(); return; }
  if (["tfDept", "tfSubj", "tfQ"].includes(el.id)) { S.tf[{ tfDept: "dept", tfSubj: "subj", tfQ: "q" }[el.id]] = el.value; render(); return; }
  if (el.dataset.pick || el.dataset.pickall) return;
  if (el.dataset.set) { setSetting(el.dataset.set, el.value); save(); render(); return; }
  if (el.dataset.time) {   // a block-out's clock time: keep the times and block every period they overlap
    const [i, k] = el.dataset.time.split("|").map(Number), r = S.spec.rules[i];
    r.times = [...ruleTimes(r)]; r.times[k] = el.value; [r.from, r.to] = periodsBetween(r.times[0], r.times[1]); save(); render(); return; }
  const path = el.dataset.k; if (!path) return;
  let v = el.value; if (el.type === "number") v = v === "" ? null : Number(v); if (v === "") v = null;
  if (/\.(from|to)$/.test(path) && v !== null) v = Number(v);
  if (/^spec\.school\.(weeks|periods_per_day|period_minutes|lesson_length)$/.test(path)) v = Number(v);
  setPath(path, v);
  const m = path.match(/^spec\.lessons\.(\d+)\.block$/);
  if (m && v) { const b = S.spec.blocks.find(x => x.block === v); if (b) { S.spec.lessons[m[1]].classes = [...(b.classes || [])]; S.spec.lessons[m[1]].level = b.level || S.spec.lessons[m[1]].level; } }
  const t = path.match(/^spec\.lessons\.(\d+)\.teachers\.(\d+)$/); if (t) S.spec.lessons[t[1]].teachers = (S.spec.lessons[t[1]].teachers || []).map(x => x || null);
  const sm = path.match(/^spec\.students\.(\d+)\.class$/); if (sm) S.spec.students[sm[1]].level = clsLevel(v) || null;
  const fx = path.match(/^spec\.rules\.(\d+)\.target$/);   // a fixed lesson names a class or a group code
  if (fx) { const r = S.spec.rules[fx[1]]; if (r.rule === "Fixed at" && ["Class", "Group"].includes(r.scope)) r.scope = classNames().includes(v) ? "Class" : "Group"; }
  if (/^spec\.school\.(weeks|periods_per_day)$/.test(path)) ensureDays();
  if (/\.(room|class|subject|name|block)$/.test(path)) renameRefs(e.target, path, v);
  save(); (async () => { try { G.server = await getJSON("/api/setup"); } catch (e) { } render(); poll(); })();
});
function renameRefs() { /* references are by name; renaming leaves old names flagged as "(not on list)" for the user to fix */ }

/* ---------------- rows and helpers */
function addRow(k) {
  const lv = levels()[0];
  const blank = { venues: { room: "", kind: "classroom", capacity: 40 }, classes: { class: "", level: lv, size: 38, home_room: null },
    subjects: { subject: "", code: "", tag: "-", dept: (sc().departments || [])[0], periods: {} }, teachers: { name: "", short: "", dept: (sc().departments || [])[0], allowance: sc().type === "primary" ? 36 : 64, provisional: "No", can_teach: [] },
    blocks: { block: "", level: lv, classes: [] }, lessons: { level: lv, subject: null, block: null, classes: [], teachers: [], students: null },
    rules: { scope: "Level", target: null, rule: "Not in periods", week: "Both", day: "All", strength: "Must" },
    avail: { scope: "Teacher", target: null, rule: "Not available", week: "Both", day: "All", from: 0, to: 0, strength: "Must", times: [hhmm(0), hhmm(1)] },
    fixed: { scope: "Class", target: null, subject: null, rule: "Fixed at", level: lv, week: "Both", day: "Mon", from: 0, strength: "Must" },
    roles: { role: "", what: "", allowance: null, group: "" },
    students: { id: "", name: "", level: clsLevel(S.stu.cls) || null, class: S.stu.cls || null, groups: [] } }[k];
  if (k === "students") S.stu.q = "";
  const into = { avail: "rules", fixed: "rules" }[k] || k; S.spec[into] = S.spec[into] || [];
  S.spec[into].push(JSON.parse(JSON.stringify(blank))); save(); (async () => { try { G.server = await getJSON("/api/setup"); } catch (e) { } render(); poll(); })();
  const last = document.getElementById(`${into}-${S.spec[into].length - 1}`); if (last) { last.scrollIntoView({ block: "center" }); const f = last.querySelector("input,select"); if (f) f.focus(); }
}
const blankRows = () => S.spec.lessons.filter(x => x.subject && !(x.teachers || []).some(Boolean)).length;
async function allocateTeachers() {   // a teacher for every row left blank (ttgen.allocate), as one change Undo takes back
  toast("Choosing teachers…");
  const r = await post("/api/allocate", S.spec); if (!r) return;
  const n = Object.keys(r.assign).length;
  for (const [i, t] of Object.entries(r.assign)) S.spec.lessons[Number(i)].teachers = [t];
  const tight = r.loads.filter(l => l.allowance && l.after > l.allowance).map(l => `${l.teacher} ${l.after}/${l.allowance}`);
  S.alloc = `Filled ${n} row${n === 1 ? "" : "s"}` + (r.unfilled.length ? `; ${r.unfilled.length} left blank (${r.unfilled.slice(0, 3).map(u => u.why).join("; ")})` : "") +
    (tight.length ? `; over allowance: ${tight.join(", ")}` : n ? "; everyone within their allowance" : "") + ". Undo takes it back.";
  save(); render(); toast(S.alloc);
}
function helper(k) {
  if (k === "allocate") { allocateTeachers(); return; }
  if (k === "venues") { const pre = $("#hvPre").value, a = Number($("#hvFrom").value), b = Number($("#hvTo").value), kind = $("#hvKind").value; for (let i = a; i <= b; i++) S.spec.venues.push({ room: `${pre}${String(i).padStart(2, "0")}`, kind, capacity: 40 }); }
  if (k === "classes") {
    const lv = $("#hcLevel").value, size = Number($("#hcSize").value) || 38; const used = new Set(S.spec.classes.map(c => c.home_room)); const free = S.spec.venues.filter(v => (v.kind || "classroom") === "classroom" && !used.has(v.room)).map(v => v.room);
    $("#hcNames").value.split(",").map(s => s.trim()).filter(Boolean).forEach(n => S.spec.classes.push({ class: `${String(lv).slice(-1)}${n}`, level: lv, size, home_room: free.shift() || null }));
  }
  if (k === "teachers") { const dept = $("#htDept").value, allow = Number($("#htAllow").value) || null; $("#htNames").value.split("\n").map(s => s.trim()).filter(Boolean).forEach(n => S.spec.teachers.push({ name: n, short: n.split(" ")[0], dept, allowance: allow, provisional: "No", can_teach: [] })); }
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
    ${line ? `<span class="small ${over ? "over" : "muted"}">${esc(line)}</span>` : ""}<button class="small ghost" data-bulk="tnone">Clear ticks</button></div>`;
}
function teacherBar() {
  const P = S.pick, ix = [...P.teachers].filter(i => S.spec.teachers[i]); if (!ix.length) return "";
  const s = P.s, has = ix.filter(i => (S.spec.teachers[i].can_teach || []).some(c => c.subject === s)).length;
  return `<div class="bulk"><div class="row"><b>${ix.length} ticked</b> can teach <select id="pickS">${opt("", s, "pick a subject…")}${subjectNames().map(n => opt(n, s)).join("")}</select> at <select id="pickV">${scopes().map(v => opt(v, P.v)).join("")}</select>
    <button data-bulk="tc-add" ${s ? "" : "disabled"}>Add</button><button data-bulk="tc-rm" ${s && has ? "" : "disabled"} title="Takes the subject off them at every level">Remove subject</button>${s ? `<span class="muted small">${has} of ${ix.length} can teach it now</span>` : ""}</div>
    <div class="row" style="margin-top:6px">department <select id="pickD">${opt("", P.d, "")}${(sc().departments || []).map(d => opt(d, P.d)).join("")}</select><button data-bulk="tc-dept" ${P.d ? "" : "disabled"}>Set</button>
    <span class="muted">·</span> role <select id="pickR">${opt("", P.r, "")}${roles().map(r => opt(r.role, P.r)).join("")}</select><button data-bulk="tc-role" ${P.r ? "" : "disabled"}>Set</button>
    <span class="muted">·</span> allowance <input id="pickA" type="number" value="${esc(P.a)}" style="width:64px"><button data-bulk="tc-allow" ${P.a !== "" ? "" : "disabled"}>Set</button>
    <button class="small ghost" data-bulk="tc-none">Clear ticks</button></div></div>`;
}
function bulkTeachers(k) {   // step 4: one change for every ticked teacher
  const P = S.pick, T = S.spec.teachers, ix = [...P.teachers].filter(i => T[i]), n = ix.length, s1 = n === 1 ? "" : "s";
  if (k === "tc-none") { P.teachers.clear(); render(); return; }
  if (!n) return;
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
  if (k === "tc-allow") { const a = Number(P.a); if (P.a === "" || !(a >= 0)) return; ix.forEach(i => T[i].allowance = a); msg = `Allowance ${a} for ${n} teacher${s1}`; }
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
    const cur = getPath(path) || [], c = anchor.dataset.cls, info = lessonInfo(), blocks = new Map(), other = [];
    S.spec.lessons.forEach((x, i) => {
      const code = info[i].code; if (!code || code === "Entire Class" || !(x.classes || []).includes(c)) return;
      if (x.block) { if (!blocks.has(x.block)) blocks.set(x.block, []); blocks.get(x.block).push([code, x.subject]); } else other.push([code, x.subject]);
    });
    const known = new Set([...[...blocks.values()].flat(), ...other].map(([g]) => g)), lost = cur.filter(g => !known.has(g));
    const lab = (type, name, g, s, on) => `<label title="${esc(s || "")}"><input type="${type}" name="${name}" value="${esc(g)}" ${on ? "checked" : ""}><span>${esc(g)}${s ? ` <span class="muted">${esc(s)}</span>` : ""}</span></label>`;
    pop.innerHTML = `<h3>Groups${c ? ` for ${esc(c)}` : ""}</h3>` + (!c ? `<p class="muted">Pick the student's class first.</p>` : "")
      + [...blocks].map(([b, gs], k) => `<div class="gblock"><div class="muted small">${esc(b)}</div><div class="opts wide">${lab("radio", `gb${k}`, "", "none", !gs.some(([g]) => cur.includes(g)))}${gs.map(([g, s]) => lab("radio", `gb${k}`, g, s, cur.includes(g))).join("")}</div></div>`).join("")
      + (other.length ? `<div class="gblock"><div class="muted small">Groups outside a band</div><div class="opts wide">${other.map(([g, s]) => lab("checkbox", "", g, s, cur.includes(g))).join("")}</div></div>` : "")
      + (lost.length ? `<div class="gblock"><div class="muted small">Not on step 5 for ${esc(c || "this class")} (untick to remove)</div><div class="opts wide">${lost.map(g => lab("checkbox", "", g, "", true)).join("")}</div></div>` : "")
      + (c && !blocks.size && !other.length ? `<p class="muted">No groups on step 5 include ${esc(c)} yet.</p>` : "")
      + `<div class="row"><button class="small primary" data-popdone="1">Done</button></div>`;
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
  else if (pop.dataset.what === "groups") setPath(path, [...pop.querySelectorAll("input:checked")].map(x => x.value).filter(Boolean));
  else setPath(path, readCt().filter(c => c.subject));
  pop.hidden = true; save(); (async () => { try { G.server = await getJSON("/api/setup"); } catch (e) { } render(); poll(); })();
}

/* ---------------- generate, chat, publish */
const G = { server: null, st: null, after: 0, events: [], timer: null,
  adj: { kind: "class", who: "", data: null, sel: null, cut: null, prop: null, ai: "" } };   // adj: the Adjust page
async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { location.href = "/login"; return null; }
  if (!r.ok) { toast(j.error || "Something went wrong."); return null; }
  return j;
}
function solveSecs() {   // this browser's choice of how long each solve may run (Generate page), else the server's default
  let v = 0; try { v = Number(localStorage.getItem("ttsolve")) || 0; } catch (e) { }
  return v || (G.st && G.st.solve_seconds) || 1200;
}
async function generate(withAI) {
  if (!S.spec) { toast("Open or start a setup first."); return; }
  G.events = []; G.after = 0; G.alert = null;
  const j = await post("/api/generate", { spec: S.spec, ai: withAI, seconds: solveSecs() });
  if (j) { toast(withAI ? "The AI timetabler has started." : "Generating…"); synced(); poll(); }
}
async function sendChat(text) {
  text = (text || "").trim(); if (!text) return;
  const j = await post("/api/message", { text }); if (j) { const i = $("#chatin"); if (i) i.value = ""; poll(); }
}
async function poll() {
  clearTimeout(G.timer);
  if (G.inflight) { G.timer = setTimeout(poll, 500); return; }
  G.inflight = true;
  try {
    const r = await fetch(`/api/status?after=${G.after}`);
    if (r.status === 401) { location.href = "/login"; return; }
    const st = await r.json(); G.st = st;
    if (st.run) {
      if (G.runId !== st.run.id) { G.runId = st.run.id; G.events = []; if (G.after) { G.after = 0; G.inflight = false; return poll(); } }
      const fresh = G.after > 0;   // not the first load of this run's events
      G.events.push(...st.run.events); if (st.run.events.length) G.after = st.run.events[st.run.events.length - 1].n;
      const out = [...st.run.events].reverse().find(e => e.type === "nosolution" || e.type === "timetable");
      if (out) {   // the latest solve's outcome: a 'nosolution' raises the alert until a timetable is made
        G.alert = out.type === "nosolution" ? out : null;
        if (G.alert && fresh) toast(`${G.alert.text} See why and how to fix it on Generate & publish.`);
        paintBanner();
      }
    }
    if (STEPS[S.step][0] === "generate") paintGen();
    const nowBusy = !!(st.run && st.run.busy);
    if (STEPS[S.step][0] === "adjust" && (G.wasBusy || G.adj.waiting) && !nowBusy) { G.adj.waiting = false; loadAdjust(); }
    else if (STEPS[S.step][0] === "adjust" && nowBusy && G.adj.data) render();
    G.wasBusy = nowBusy;
  } catch (e) { }
  G.inflight = false;
  const busy = G.st && G.st.run && G.st.run.busy;
  G.timer = setTimeout(poll, ["generate", "adjust"].includes(STEPS[S.step][0]) ? (busy ? 1500 : 5000) : 15000);
}
const md = t => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>");
function eventHTML(e, last) {
  const items = e.items && e.items.length ? `<ul>${e.items.map(i => `<li>${esc(i)}</li>`).join("")}</ul>` : "";
  switch (e.type) {
    case "assistant": return `<div class="msg ai">${md(e.text)}</div>`;
    case "user": return `<div class="msg me">${md(e.text)}</div>`;
    case "summary": return `<div class="msg ai sum"><b>Summary</b><br>${md(e.text)}</div>`;
    case "question": {
      const open = G.st && G.st.run && G.st.run.waiting && e.n === last;
      return `<div class="msg ai q">${md(e.text)}${open ? `<div class="opts">${(e.options || []).map(o => `<button class="small" data-answer="${esc(o)}">${esc(o)}</button>`).join("")}</div><div class="muted small">Pick one or type your own answer below.</div>` : ""}</div>`;
    }
    case "change": return `<div class="ev change"><b>Setup changed:</b> ${esc(e.text)}${items}</div>`;
    case "timetable": return `<div class="ev tt ${e.data && e.data.ok ? "good" : "warn"}"><b>Timetable ${e.data ? "#" + e.data.n : ""}</b> · ${esc(e.text)} <a href="/preview" target="_blank">Preview</a></div>`;
    case "nosolution": return `<div class="ev bad"><b>${esc(e.text)}</b>${items ? `<div class="small" style="margin-top:6px"><b>Why</b></div>${items}` : ""}${fixesHTML(e)}</div>`;
    case "error": return `<div class="ev bad">${esc(e.text)}</div>`;
    case "published": return `<div class="ev good"><b>${esc(e.text)}</b></div>`;
    case "check": return `<div class="ev">${esc(e.text)}${items ? `<details><summary>Details</summary>${items}</details>` : ""}</div>`;
    case "moved": return `<div class="ev">${esc(e.text)}${items ? `<details><summary>Which lessons moved</summary>${items}</details>` : ""}</div>`;
    case "allocation": return `<div class="ev whatif"><b>${esc(e.text)}</b>${items ? `<details><summary>Who gets which row</summary>${items}</details>` : ""}${e.data && e.data.loads ? `<details><summary>Teacher loads</summary><ul>${e.data.loads.map(l => `<li>${esc(l)}</li>`).join("")}</ul></details>` : ""}${e.data && e.data.unfilled && e.data.unfilled.length ? `<details open><summary>Cannot be filled</summary><ul>${e.data.unfilled.map(l => `<li>${esc(l)}</li>`).join("")}</ul></details>` : ""}</div>`;
    case "whatif": return `<div class="ev whatif"><b>What-if:</b> ${esc(e.text)}${items}</div>`;
    case "compare": {   // a what-if against the latest timetable: the committee keeps or drops it (the question below)
      const d = e.data || {}, tone = r => typeof r[1] === "number" && typeof r[2] === "number" && r[1] !== r[2] ? (r[2] < r[1] ? "good" : "bad") : "";
      return `<div class="ev compare"><b>What-if: ${esc(e.text)}</b><table><tr><th></th><th>Now (#${esc(d.before)})</th><th>With the change (#${esc(d.after)})</th></tr>${(d.rows || []).map((r, i) => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td class="${tone(r)}">${esc(r[2])}</td></tr>`).join("")}</table><a href="/preview" target="_blank">Preview the what-if</a></div>`;
    }
    default: return `<div class="ev">${esc(e.text || "")}</div>`;
  }
}
function paintGen() {
  const st = G.st; if (!st || !$("#chatlog")) return;
  const run = st.run, busy = run && run.busy, aiok = st.ai && st.ai.ok;
  const lastQ = [...G.events].reverse().find(e => e.type === "question");
  const log = $("#chatlog"), atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  log.innerHTML = G.events.length ? G.events.map(e => eventHTML(e, lastQ && lastQ.n)).join("") : `<div class="muted">Nothing generated yet. Press a Generate button above.</div>`;
  if (atBottom) log.scrollTop = log.scrollHeight;
  $("#progress").textContent = run && run.waiting ? "Waiting for your answer." : run && run.progress ? run.progress : (busy ? "Working…" : "");
  $("#genAI").disabled = !aiok || busy; $("#genPlain").disabled = busy; $("#genStop").hidden = !busy;
  const chatOn = run && run.ai; $("#chatin").disabled = !chatOn; $("#chatsend").disabled = !chatOn;
  $("#chatin").placeholder = chatOn ? (run.waiting ? "Type your answer…" : "Ask or tell the timetabler something…") : "The chat works when you generate with the AI timetabler.";
  const s = run && run.solved, a = G.alert;
  $("#resultCard").innerHTML = `<h2>Latest timetable</h2>` + (a ? `<div class="alertbox"><b>${esc(a.text)}</b>${fixesHTML(a)}${a.items && a.items.length ? `<details><summary>Why</summary><ul>${a.items.map(i => `<li>${esc(i)}</li>`).join("")}</ul></details>` : ""}</div>` : "") + (s ?`<p class="${s.ok ? "okmsg" : "issue"}">${s.ok ? "All checks passed" : `${s.problems.length} problems`} · ${s.lessons} lessons · ${s.after.length ? `${s.after.length} after school` : "nothing after school"}</p>
      ${s.after.length ? `<details><summary>After-school lessons</summary><ul>${s.after.map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}
      ${s.problems.length ? `<details open><summary>Problems</summary><ul>${s.problems.map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}
      ${s.notes.length ? `<details><summary>Notes</summary><ul>${s.notes.map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}
      <p class="muted small">Made ${esc(s.at)}${run.changes ? ` · the setup was changed ${run.changes} time${run.changes > 1 ? "s" : ""} (by the AI or on Adjust)` : ""}.</p>
      <div class="row"><a href="/preview" target="_blank"><button>Preview</button></a><button class="primary" id="publish" ${busy ? "disabled" : ""}>Publish</button>
      ${run.changes ? `<button id="keepChanges" ${busy ? "disabled" : ""}>Keep these changes in my setup</button>` : ""}</div>`
    : `<p class="muted">No timetable yet.</p>`);
  const p = st.published, f = p ? p.files || {} : {};
  $("#pubCard").innerHTML = `<h2>Published</h2>` + (p ? `<p class="${p.ok ? "okmsg" : "issue"}">Published ${esc(p.at)} · ${p.classes} classes · ${p.students} students${p.after ? ` · ${p.after} after school` : ""}</p>
      <div class="row"><a href="/timetable" target="_blank"><button class="primary">Open the timetable</button></a></div>
      <h3>Downloads</h3><div class="links"><a href="/files/excel">Excel, every timetable</a><a href="/files/zip">PDFs, one per class, teacher, room and student (zip)</a>
      ${Object.keys(f.books || {}).map(k => `<a href="/files/book/${k}">${k[0].toUpperCase() + k.slice(1)}: all in one PDF</a>`).join("")}</div>
      <h3>Personal student codes</h3>${p.students ? `<div class="links"><a href="/api/code-slips.pdf">Code slips to print, by class (PDF)</a><a href="/api/codes.csv">Code list (CSV)</a></div>` : `<p class="muted small">Add students on step 7 to give each one a personal code.</p>`}`
    : `<p class="muted">Nothing published yet. Teachers and students see a "not published yet" page.</p>`) +
    `<h3>Access codes</h3><ul class="codes">${[["committee", "Committee"], ["teacher", "Teachers"], ["student", "Students"]].map(([k, t]) => `<li>${t}: ${st.codes && st.codes[k] ? "set" : "<b>not set</b>"}</li>`).join("")}</ul>
    ${(st.code_problems || []).map(x => `<p class="issue">${esc(x)}</p>`).join("")}${st.volume ? "" : `<p class="issue">No Railway volume: the published timetable will be lost on the next deploy. Add a volume (see README).</p>`}`;
}

/* ---------------- downloads */
document.addEventListener("change", e => {
  if (e.target.id === "exSetup" || e.target.id === "exTT") { const f = e.target.files[0]; $("#" + e.target.id + "Name").textContent = f ? f.name : "none chosen"; }
});
async function makePrintouts() {
  const a = $("#exSetup").files[0], b = $("#exTT").files[0], msg = $("#exMsg");
  if (!a || !b) { toast("Choose the setup workbook and the timetable workbook."); return; }
  const fd = new FormData(); fd.append("setup", a); fd.append("timetable", b); fd.append("single", $("#exSingle").checked ? "1" : "0");
  const go = $("#exGo"); go.disabled = true; msg.textContent = "Making printouts… a school with 600 students takes about a minute.";
  try {
    const r = await fetch("/api/export", { method: "POST", body: fd });
    if (!r.ok) { const j = await r.json().catch(() => ({})); msg.textContent = ""; toast(j.error || "Could not make the printouts."); return; }
    const name = (r.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)"?/);
    dl(await r.blob(), name ? name[1] : "Timetables.zip"); msg.textContent = r.headers.get("X-Checks") || "Done.";
  } catch (err) { msg.textContent = ""; toast("Could not make the printouts: " + err.message); }
  finally { go.disabled = false; }
}
function dl(blob, name) { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); }
async function buildXlsx() {
  toast("Building your workbook…");
  const r = await fetch("/api/build", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.spec) });
  if (!r.ok) { const j = await r.json().catch(() => ({})); toast(j.error || "Could not build the workbook."); return; }
  dl(await r.blob(), `${(sc().name || "School").replace(/[^\w -]/g, "").trim().replace(/ /g, "_")}_Timetable_Setup.xlsx`);
}

/* ---------------- Adjust timetable: move lessons by hand before publishing */
const adjWhen = (start, ln) => { const D = G.adj.data, d = Math.floor(start / D.NP), p = start % D.NP; return `${D.days[d]} ${D.clock[p]}–${D.clock[p + ln]}`; };
async function loadAdjust() {
  const A = G.adj; A.loading = true;
  try { const r = await fetch("/api/adjust"); const j = await r.json(); if (r.status === 401) { location.href = "/login"; return; }
    if (!r.ok) { A.data = null; A.error = j.error || "Could not load the timetable."; } else { A.data = j; A.error = ""; } }
  catch (e) { A.error = "Could not load the timetable."; }
  A.loading = false; if (STEPS[S.step][0] === "adjust") render();
}
function adjShows(l, A) {   // is this lesson in the class, teacher or room being shown?
  return A.kind === "class" ? l.classes.includes(A.who) : A.kind === "teacher" ? l.teachers.includes(A.who) : l.rows.some(r => r.room === A.who);
}
function adjChip(l, A) {
  const rows = A.kind === "teacher" ? l.rows.filter(r => r.teachers.includes(A.who)) : A.kind === "room" ? l.rows.filter(r => r.room === A.who) : l.rows;
  const one = rows[0] || l.rows[0] || {};
  const title = l.kind === "block" && A.kind === "class" ? l.name.replace(/ band$/, "") : A.kind === "class" ? (l.kind === "class" ? one.subject : `${one.subject} ${one.code}`) : `${l.kind === "class" ? l.name : `${one.subject} ${one.code}`}`;
  const sub = A.kind === "class" ? (l.kind === "block" ? `${l.rows.length} group${l.rows.length === 1 ? "" : "s"}` : `${(one.teachers || []).join(", ")}${one.room ? " · " + one.room : ""}`)
    : A.kind === "teacher" ? `${l.kind === "class" ? "" : l.classes.join(" ") + " · "}${one.room || ""}` : `${(one.teachers || []).join(", ")}${l.kind === "class" ? "" : " · " + l.classes.join(" ")}`;
  const tip = `${l.name} · ${adjWhen(l.start, l.ln)}\n` + l.rows.map(r => `${r.subject} ${r.code} · ${r.teachers.join(", ")} · ${r.room || "no room"}${r.students ? ` · ${r.students} students` : ""}`).join("\n");
  return `<button class="adjl${A.sel === l.key ? " sel" : ""}${A.cut === l.key ? " cut" : ""}" data-lesson="${esc(l.key)}" title="${esc(tip)}"><b>${l.pinned ? "📌 " : ""}${esc(title)}</b><span>${esc(sub)}</span></button>`;
}
function adjGrid(D, A) {
  const mine = D.lessons.filter(l => adjShows(l, A)), NP = D.NP;
  const lvs = A.kind === "class" ? [D.level_of[A.who]] : [...new Set(mine.map(l => l.level))];
  const grid = (A.kind === "class" && (D.cgrid || {})[A.who]) || D.grid[lvs[0]] || Object.values(D.grid)[0];   // breaks shaded from the class's own day, else the (first) level shown
  let html = `<tr><th></th>${Array.from({ length: NP }, (_, p) => `<th class="t">${esc(D.clock[p])}</th>`).join("")}</tr>`;
  D.days.forEach((day, d) => {
    const ls = mine.filter(l => Math.floor(l.start / NP) === d).sort((a, b) => a.start - b.start);
    const groups = [];   // lessons that overlap share one cell
    for (const l of ls) { const g = groups[groups.length - 1]; if (g && l.start < g.end) { g.ls.push(l); g.end = Math.max(g.end, l.start + l.ln); } else groups.push({ start: l.start, end: l.start + l.ln, ls: [l] }); }
    let row = `<tr><th style="text-align:left">${esc(day)}</th>`, p = 0;
    for (const g of groups) {
      const gp = g.start % NP;
      for (; p < gp; p++) row += `<td class="as c-${(grid[d] || "")[p] === "." ? "" : (grid[d] || "")[p] || ""}" data-start="${d * NP + p}"></td>`;
      row += `<td class="al${g.ls.length > 1 ? " many" : ""}" colspan="${g.end - g.start}">${g.ls.map(l => adjChip(l, A)).join("")}</td>`; p = gp + (g.end - g.start);
    }
    for (; p < NP; p++) row += `<td class="as c-${(grid[d] || "")[p] === "." ? "" : (grid[d] || "")[p] || ""}" data-start="${d * NP + p}"></td>`;
    html += row + "</tr>";
  });
  return html;
}
function adjPanel() {   // a move that clashes: why, and the ways out
  const P = G.adj.prop; if (!P) return "";
  const aiOn = G.st && G.st.ai && G.st.ai.ok;
  return `<div class="alertbox" style="margin-top:10px"><b>Moving ${esc(P.name)} to ${esc(P.to)} clashes:</b><ul>${P.conflicts.map(c => `<li>${esc(c.text)}</li>`).join("")}</ul>
    <div class="fixes"><b>Ways out</b>
      ${P.free.length ? `<div style="margin-top:4px">Free times for it: ${P.free.map(f => `<button class="small" data-adjgo="${f.start}">${esc(f.label)}</button>`).join(" ")}</div>` : `<div class="muted" style="margin-top:4px">No free time without a clash.</div>`}
      ${P.swaps.length ? `<div style="margin-top:4px">${P.swaps.map(s => `<button class="small" data-adjswap="${esc(s.key)}">${esc(s.label)}</button>`).join(" ")}</div>` : ""}
      <div class="row" style="margin-top:8px">${P.allowed ? `<button class="small primary" data-adj="room" title="Keeps it at ${esc(P.to)} and moves as few other lessons as it can">Let the solver make room</button>` : ""}
        ${aiOn ? `<button class="small" data-adj="ask">Ask the AI for other ways</button>` : ""}
        ${P.allowed ? `<button class="small" data-adj="anyway" title="Keeps the clash: it shows as a problem until you fix it">Place it anyway</button>` : ""}<button class="small ghost" data-adj="nomove">Cancel</button></div>
      ${G.adj.ai ? `<div class="aisays">${md(G.adj.ai)}</div>` : ""}</div></div>`;
}
async function adjPost(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  if (r.status === 401) { location.href = "/login"; return null; }
  const j = await r.json().catch(() => ({})); if (!r.ok) { toast(j.error || "Something went wrong."); return null; }
  return j;
}
async function adjCheck(key, where) {   // where: {start} or {dir: -1 | 1}
  const A = G.adj; A.ai = "";
  const p = await adjPost("/api/adjust/check", { key, ...where }); if (!p) return;
  if (p.ok) { await adjMove({ [key]: p.start }); return; }
  A.prop = p; A.cut = null; A.sel = key; render();
}
async function adjMove(moves, label) {
  const A = G.adj, j = await adjPost("/api/adjust/move", { moves, label }); if (!j) return;
  A.data = j; A.prop = null; A.cut = null; A.ai = ""; render(); toast(j.last ? `${j.last}.` : "Moved.");
}
async function adjAction(what) {
  const A = G.adj, key = A.sel;
  if (what === "cancel") { A.sel = A.cut = null; A.prop = null; render(); return; }
  if (what === "nomove") { A.prop = null; A.ai = ""; render(); return; }
  if (what === "undo" || what === "redo") { const j = await adjPost("/api/adjust/undo", { redo: what === "redo" }); if (j) { A.data = j; A.prop = null; render(); toast(what === "undo" ? "Move undone." : "Move redone."); } return; }
  if (!key) return;
  if (what === "earlier" || what === "later") { await adjCheck(key, { dir: what === "earlier" ? -1 : 1 }); return; }
  if (what === "cut") { A.cut = key; A.prop = null; render(); toast("Now click where it should go."); return; }
  if (what === "shorter" || what === "longer") {   // a new latest timetable: keys change, so find the lesson again by name and time
    const was = A.data.lessons.find(l => l.key === key), j = await adjPost("/api/adjust/resize", { key, delta: what === "shorter" ? -1 : 1 }); if (!j) return;
    A.data = j; A.prop = null; const now = j.lessons.find(l => l.name === was.name && l.start === was.start); A.sel = now ? now.key : null; render(); toast(j.message); return; }
  if (what === "unpin") { const j = await adjPost("/api/adjust/unpin", { key }); if (j) { A.data = j; render(); } return; }
  const P = A.prop; if (!P) return;
  if (what === "anyway") { await adjMove({ [P.key]: P.start }, `Placed ${P.name} at ${P.to} with a clash`); return; }
  if (what === "room") { const j = await adjPost("/api/adjust/make-room", { key: P.key, start: P.start, seconds: Math.max(120, Math.min(solveSecs(), 600)) });   // 2 to 10 minutes
    if (j) { A.prop = null; A.waiting = true; toast("The solver is making room. This page updates when it is done."); render(); poll(); } return; }
  if (what === "ask") { A.ai = "Asking the AI…"; render(); const j = await adjPost("/api/adjust/ask", { key: P.key, start: P.start }); A.ai = j ? j.text : ""; render(); return; }
}

/* on opening the page: this browser's unsaved work if it has any, else the setup saved for the school, else this
   browser's last copy; with none of these, the Start page */
(async () => {
  try { G.server = await getJSON("/api/setup"); } catch (e) { }
  const local = saved(), srv = G.server && G.server.spec ? G.server : null;
  const unsaved = local && (local.dirty || (local.dirty === undefined && (!srv || JSON.stringify(local.spec) !== JSON.stringify(srv.spec))));
  try {
    if (local && (unsaved || !srv)) {
      await adopt(local.spec, "", { kind: local.kind, step: local.step, base: local.base, dirty: !!unsaved });
      if (srv && srv.ts > (local.base || 0) + 1) toast(`This browser has changes that are not saved for the school. A newer setup was saved on ${srv.saved_at}: open it from Start if you want that one instead.`);
    } else if (srv) {
      const same = local && local.spec.school && srv.spec.school && local.spec.school.name === srv.spec.school.name;
      await adopt(srv.spec, `Opened the school's saved setup (saved ${srv.saved_at}).`, { step: same ? local.step : 1, base: srv.ts, dirty: false });
    }
  } catch (e) { }
  render(); poll();
})();

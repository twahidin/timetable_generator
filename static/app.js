"use strict";
/* Timetable Setup: a step-by-step editor for the timetable setup workbook. State lives in S.spec (same shape the
   server's ttgen package reads and writes); every list feeds the drop-downs of the later steps. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const KEY = "ttsetup.v1";
const S = { kind: null, spec: null, meta: null, step: 0, brush: "L" };
const STEPS = [["start", "Start"], ["school", "School & day"], ["venues", "1 Venues"], ["classes", "2 Classes"], ["subjects", "3 Subjects"],
  ["teachers", "4 Teachers"], ["blocks", "5 Blocks"], ["lessons", "6 Lessons"], ["rules", "7 Rules"], ["generate", "Generate & publish"], ["download", "Files"]];

/* ---------------- storage, server */
function save() { try { localStorage.setItem(KEY, JSON.stringify({ kind: S.kind, spec: S.spec, step: S.step })); } catch (e) { } }
function saved() { try { const x = JSON.parse(localStorage.getItem(KEY) || "null"); return x && x.spec ? x : null; } catch (e) { return null; } }
async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(await r.text()); return r.json(); }
async function begin(kind, what) {
  S.kind = kind; S.meta = await getJSON(`/api/meta/${kind}`);
  S.spec = await getJSON(`/api/${what}/${kind}`); S.step = 1; ensureDays(); save(); (async () => { try { G.server = await getJSON("/api/setup"); } catch (e) { } render(); poll(); })();
  toast(what === "sample" ? "Sample school loaded: edit it or use it to see how the template works." : "Blank template started.");
}
async function adopt(spec, msg) {
  S.kind = (spec.school && spec.school.type) || "secondary"; S.meta = await getJSON(`/api/meta/${S.kind}`);
  S.spec = spec; ["venues", "classes", "subjects", "teachers", "blocks", "lessons", "rules", "students"].forEach(k => S.spec[k] = S.spec[k] || []);
  S.step = 1; ensureDays(); save(); render(); toast(msg);
}
function toast(m) { const t = $("#toast"); t.textContent = m; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => t.hidden = true, 3200); }

/* ---------------- lists */
const sc = () => S.spec.school;
const levels = () => sc().levels || [];
const bands = () => sc().bands || {};
const dayNames = () => Number(sc().weeks) === 2 ? ["Odd", "Even"].flatMap(w => ["Mon", "Tue", "Wed", "Thu", "Fri"].map(d => `${w} ${d}`)) : ["Mon", "Tue", "Wed", "Thu", "Fri"];
const rooms = () => S.spec.venues.map(v => v.room).filter(Boolean);
const classNames = () => S.spec.classes.map(c => c.class).filter(Boolean);
const subjectNames = () => S.spec.subjects.map(s => s.subject).filter(Boolean);
const teacherNames = () => S.spec.teachers.map(t => t.name).filter(Boolean);
const blockNames = () => S.spec.blocks.map(b => b.block).filter(Boolean);
const scopes = () => ["All", ...levels(), ...[...new Set(Object.values(bands()))]];
const subj = n => S.spec.subjects.find(s => s.subject === n);
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
}

/* ---------------- derived values (same logic as the workbook formulas) */
function split(p, L) { p = Number(p) || 0; L = Number(L) || 1; if (p <= 0) return [0, 0]; if (L <= 1) return [p, 0]; let s = ((-p % L) + L) % L; if (s * (L - 1) > p) s = 0; return [(p - s * (L - 1)) / L, s]; }
function lessonInfo() {
  const seq = {}; const letter = Object.fromEntries((sc().tags || []).map(([a, b]) => [a, b]));
  return S.spec.lessons.map(x => {
    const s = subj(x.subject) || {}; const p = Number(x.periods_override) || Number((s.periods || {})[x.level]) || 0;
    const L = Number(s.lesson_length) || Number(sc().lesson_length) || 1; const [full, short] = split(p, L);
    let code = "";
    if (x.subject) {
      const k = `${x.level}|${x.subject}`; if (x.block) seq[k] = (seq[k] || 0) + 1;
      code = x.code_override ? String(x.code_override) : !x.block ? "Entire Class" : `${String(x.level).slice(-1)}${s.code || "??"}${letter[s.tag] || ""}${seq[k]}`;
    }
    const tp = p * (x.block ? 1 : Math.max(1, (x.classes || []).length));
    return { p, L, full, short, code, tp, kind: s.room_kind || (x.block || x.code_override ? "classroom" : "home room") };
  });
}
function canTeach(t, subject, level) {
  const tt = S.spec.teachers.find(x => x.name === t); if (!tt) return false;
  return (tt.can_teach || []).some(c => c.subject === subject && (!c.levels || c.levels === "All" || c.levels === level || c.levels === bands()[level]));
}
function issues() {
  const out = { lessons: {}, rules: {}, teachers: {}, blocks: {}, classes: {}, subjects: {}, venues: {}, global: [] };
  const add = (k, i, m) => (out[k][i] = out[k][i] || []).push(m);
  const info = lessonInfo(); const codes = {};
  info.forEach((x, i) => { if (x.code && x.code !== "Entire Class") codes[x.code] = (codes[x.code] || 0) + 1; });
  S.spec.lessons.forEach((x, i) => {
    if (!x.subject) { add("lessons", i, "Pick a subject."); return; }
    if (!info[i].p) add("lessons", i, `No periods for ${x.level} on Subjects.`);
    if (!(x.classes || []).length) add("lessons", i, "No class.");
    if (!(x.teachers || []).filter(Boolean).length) add("lessons", i, "No teacher.");
    for (const t of (x.teachers || []).filter(Boolean)) {
      if (!canTeach(t, x.subject, x.level)) add("lessons", i, `${t} is not set to teach this at ${x.level}.`);
      if (x.block && S.spec.lessons.filter(y => y.block === x.block && (y.teachers || []).includes(t)).length > 1) add("lessons", i, `${t} twice in this block.`);
    }
    if (x.block && !blockNames().includes(x.block)) add("lessons", i, "Block not on step 5.");
    if (codes[info[i].code] > 1) add("lessons", i, "Code used twice.");
  });
  const load = {}; S.spec.lessons.forEach((x, i) => (x.teachers || []).filter(Boolean).forEach(t => load[t] = (load[t] || 0) + info[i].tp));
  S.spec.teachers.forEach((t, i) => { if (t.allowance && (load[t.name] || 0) > Number(t.allowance)) add("teachers", i, `${t.name}: ${load[t.name]} periods given, allowance ${t.allowance}.`); if (!t.name) add("teachers", i, "Name missing."); });
  S.spec.classes.forEach((c, i) => { if (c.home_room && !rooms().includes(c.home_room)) add("classes", i, `${c.class}: home room ${c.home_room} is not on Venues.`); });
  S.spec.blocks.forEach((b, i) => {
    const gs = S.spec.lessons.map((x, j) => [x, j]).filter(([x]) => x.block === b.block);
    if (!gs.length) add("blocks", i, `${b.block}: no groups yet (add them on step 6).`);
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
    if (rt.needs_number && !r.number) add("rules", i, "Give the Number.");
    if (["Same time across classes", "Not on the same day as"].includes(r.rule) && !r.subject) add("rules", i, "Pick the Subject.");
  });
  return { out, load, info };
}
function targetOptions(scope) {
  return { School: ["Whole school"], Level: levels(), Class: classNames(), Teacher: teacherNames(), Department: sc().departments || [], Subject: subjectNames(), Block: blockNames(), Room: rooms() }[scope] || [];
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
  main.innerHTML = (VIEWS[id] || (() => ""))();
  renderIssues(); window.scrollTo(0, y);
  if (id === "generate") { paintGen(); poll(); }
}
function count(id) { if (!S.spec) return ""; const m = { venues: "venues", classes: "classes", subjects: "subjects", teachers: "teachers", blocks: "blocks", lessons: "lessons", rules: "rules" }[id]; return m ? S.spec[m].length : ""; }
function renderIssues() {
  const el = $("#issues"); if (!S.spec) { el.innerHTML = ""; return; }
  const { out } = issues(); const steps = { venues: 2, classes: 3, subjects: 4, teachers: 5, blocks: 6, lessons: 7, rules: 8 };
  const items = []; for (const [k, rows] of Object.entries(out)) if (k !== "global") for (const [i, ms] of Object.entries(rows)) for (const m of ms) items.push([k, i, m]);
  el.innerHTML = `<div class="card"><h2>Things to fix</h2>${items.length ? items.slice(0, 80).map(([k, i, m]) => `<div class="issue" data-go="${steps[k]}" data-row="${k}-${i}">${esc(m)}</div>`).join("") + (items.length > 80 ? `<div class="muted">…and ${items.length - 80} more</div>` : "")
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
    return `<div class="card"><h1>Build your school's timetable setup</h1><p class="lead">This tool fills the timetable setup workbook step by step: rooms, classes, subjects, teachers, blocks of groups, lessons and rules. Every list you make becomes the drop-down for the next step, so nothing is typed twice. At the end you download the workbook and the timetable skill, and an AI agent generates the timetable from them.</p>
      <div class="choice">
        <button data-begin="secondary|sample"><b>Secondary school · sample</b><span class="muted">A fictional 16-class secondary school with G1/G2/G3 banding, option blocks and rules. Good for seeing how everything fits.</span></button>
        <button data-begin="primary|sample"><b>Primary school · sample</b><span class="muted">A fictional 18-class primary school, weekly timetable, Standard/Foundation banding at P5–P6.</span></button>
        <button data-begin="secondary|blank"><b>Secondary school · blank</b><span class="muted">Typical subjects and a day shape filled in; you add rooms, classes, teachers and lessons.</span></button>
        <button data-begin="primary|blank"><b>Primary school · blank</b><span class="muted">Typical subjects and day shape for P1–P6; you add the rest.</span></button>
      </div>
      <div class="row" style="margin-top:14px">
        ${G.server && G.server.spec ? `<button class="primary" id="serverSetup">Open the school's saved setup (${esc(G.server.spec.school.name)}, saved ${esc(G.server.saved_at)})</button>` : ""}
        ${sv ? `<button class="${G.server && G.server.spec ? "" : "primary"}" id="resume">Continue in this browser (${esc(sv.spec.school.name)})</button>` : ""}
        <label class="filebtn">Open a setup workbook (.xlsx)<input type="file" id="importX" accept=".xlsx" hidden></label>
      </div></div>
      <div class="card"><h2>How it works</h2><ol class="howto"><li>Fill the steps on the left. The panel on the right lists anything that does not add up (a teacher not set up for a subject, a teacher twice in a block, a lesson with no periods).</li><li>On <b>Generate &amp; publish</b>, make the timetable here: the AI timetabler checks, solves and asks you about conflicts in a chat. Publish when happy; teachers and students then sign in with their codes.</li><li>Or, on <b>Files</b>, download the setup workbook and the timetable skill to use with any AI agent.</li></ol></div>${exportCard()}`;
  },
  school() {
    const s = sc(); const NP = Number(s.periods_per_day); const days = dayNames();
    const head = `<tr><th></th>${Array.from({ length: NP }, (_, p) => `<th class="t">${p} · ${clock(p)}</th>`).join("")}</tr>`;
    const lvRows = levels().map(lv => `<tr><th colspan="${NP + 1}" style="text-align:left;background:#fff">${esc(lv)} <button class="small" data-copyday="${esc(lv)}">Copy first day to all days</button> <button class="small" data-copylevel="${esc(lv)}">Copy to all levels</button></th></tr>` +
      days.map(d => `<tr><th style="text-align:left">${esc(d)}</th>${Array.from({ length: NP }, (_, p) => { const c = (S.spec.day_structure[lv][d] || "")[p]; const v = c === "." ? "" : c; return `<td class="c c-${v}" data-cell="${esc(lv)}|${esc(d)}|${p}">${v}</td>`; }).join("")}</tr>`).join("")).join("");
    return `<div class="card"><h1>School and school day</h1><p class="lead">Basic settings, then what each period is for each level and day. Lessons can only go in <b>L</b> periods; <b>A</b> periods are an after-school slot used only when a class cannot fit.</p>
      <div class="grid2">
        <label class="f">School name ${inp("spec.school.name", s.name)}</label>
        <label class="f">Timetable ${inp("spec.school.timetable", s.timetable)}</label>
        <label class="f">Weeks in cycle ${sel("spec.school.weeks", s.weeks, [1, 2], false)}</label>
        <label class="f">Period length (minutes) ${inp("spec.school.period_minutes", s.period_minutes, "number", 'min="5" max="90"')}</label>
        <label class="f">Period 0 starts at ${inp("spec.school.start_time", s.start_time, "time")}</label>
        <label class="f">Periods in a day ${inp("spec.school.periods_per_day", s.periods_per_day, "number", 'min="4" max="40"')}</label>
        <label class="f">Standard lesson length (periods) ${inp("spec.school.lesson_length", s.lesson_length, "number", 'min="1" max="6"')}</label>
        <label class="f">Levels (comma separated) <input data-list="levels" value="${esc(levels().join(", "))}"></label>
        <label class="f">Departments <input data-list="departments" value="${esc((s.departments || []).join(", "))}"></label>
        <label class="f">Room kinds <input data-list="room_kinds" value="${esc((s.room_kinds || []).join(", "))}"></label>
      </div></div>
      <div class="card"><h2>Day structure</h2><div class="legend">Brush: ${["L", "R", "U", "F", "A", ""].map(c => `<button class="small ${S.brush === c ? "primary" : ""}" data-brush="${c}"><i class="c-${c}" style="width:12px;height:12px;display:inline-block;border-radius:3px;vertical-align:-2px"></i> ${{ L: "Lesson", R: "Recess", U: "Lunch", F: "Flag / assembly", A: "After-school slot", "": "No school" }[c]}</button>`).join("")}</div>
      <p class="muted" style="margin:4px 0 10px">Click or drag across cells to paint them with the brush.</p>
      <div class="tablewrap"><table class="dsgrid">${head}${lvRows}</table></div></div>`;
  },
  venues() {
    const { out } = issues();
    return `<div class="card"><h1>Step 1 · Venues</h1><p class="lead">Every room. Its kind decides which subjects may use it (you set a subject's room kind on step 3). A room that holds two classes at once (a field, a hall) gets an "At most N at once" rule on step 7.</p>
      <div class="helper row"><b>Add rooms</b> prefix ${`<input id="hvPre" value="B1-" style="width:70px">`} from <input id="hvFrom" type="number" value="1" style="width:60px"> to <input id="hvTo" type="number" value="8" style="width:60px"> kind ${sel("_hv", "classroom", sc().room_kinds || [], false, 'id="hvKind" data-k=""')} <button data-helper="venues">Add</button></div>
      <div class="tablewrap"><table><tr><th>Room</th><th>Kind</th><th>Capacity</th><th>Building</th><th>Floor</th><th>Home room of</th><th>Note</th><th></th></tr>
      ${S.spec.venues.map((v, i) => `<tr id="venues-${i}" class="${out.venues[i] ? "bad" : ""}"><td>${inp(`spec.venues.${i}.room`, v.room)}</td><td>${sel(`spec.venues.${i}.kind`, v.kind, sc().room_kinds || [])}</td><td class="num">${inp(`spec.venues.${i}.capacity`, v.capacity, "number")}</td><td>${inp(`spec.venues.${i}.building`, v.building)}</td><td class="num">${inp(`spec.venues.${i}.floor`, v.floor)}</td><td class="calc">${esc(S.spec.classes.filter(c => c.home_room === v.room).map(c => c.class).join(", "))}</td><td>${inp(`spec.venues.${i}.note`, v.note)}</td><td>${delBtn("venues", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="venues">+ Add room</button></div></div>`;
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
    return `<div class="card"><h1>Step 3 · Subjects</h1><p class="lead">Periods per ${Number(sc().weeks) === 2 ? "fortnight" : "week"} for each level that takes the subject (blank = not offered). Lessons are ${sc().lesson_length} periods long unless the subject says otherwise; leftovers become one or two shorter lessons. The code names the groups (1ELP1…). Level tag is the level of study used for banding.</p>
      <div class="tablewrap"><table><tr><th>Subject</th><th>Code</th><th>Level tag</th><th>Department</th><th>Room kind</th><th>Lesson length</th>${levels().map(l => `<th>${esc(l)}</th>`).join("")}<th>Rows</th><th></th></tr>
      ${S.spec.subjects.map((s, i) => `<tr id="subjects-${i}" class="${out.subjects[i] ? "bad" : ""}"><td style="min-width:220px">${inp(`spec.subjects.${i}.subject`, s.subject)}</td><td class="num">${inp(`spec.subjects.${i}.code`, s.code, "text", 'style="width:54px"')}</td><td>${sel(`spec.subjects.${i}.tag`, s.tag, tags, false)}</td><td>${sel(`spec.subjects.${i}.dept`, s.dept, sc().departments || [])}</td><td>${sel(`spec.subjects.${i}.room_kind`, s.room_kind, sc().room_kinds || [])}</td><td class="num">${inp(`spec.subjects.${i}.lesson_length`, s.lesson_length, "number", 'style="width:56px"')}</td>${levels().map(l => `<td class="num">${inp(`spec.subjects.${i}.periods.${l}`, (s.periods || {})[l], "number", 'style="width:56px"')}</td>`).join("")}<td class="calc">${S.spec.lessons.filter(x => x.subject === s.subject).length}</td><td>${delBtn("subjects", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="subjects">+ Add subject</button></div></div>`;
  },
  teachers() {
    const { out, load } = issues();
    return `<div class="card"><h1>Step 4 · Teachers</h1><p class="lead">Each teacher with the subjects and levels they can teach (click the subjects cell). Lessons on step 6 are checked against this, and the teacher drop-down there lists the teachers who can teach the subject first.</p>
      <div class="helper"><b>Add teachers</b> (one name per line) <div class="row" style="margin-top:6px"><textarea id="htNames" rows="3" style="width:280px;border:1px solid var(--line);border-radius:6px;padding:6px"></textarea> department ${sel("_ht", (sc().departments || [])[0], sc().departments || [], false, 'id="htDept" data-k=""')} allowance <input id="htAllow" type="number" value="${sc().type === "primary" ? 36 : 64}" style="width:70px"> <button data-helper="teachers">Add</button></div></div>
      <div class="tablewrap"><table><tr><th>Teacher</th><th>Short</th><th>Department</th><th>Allowance</th><th>Can teach</th><th>Given</th><th>Spare</th><th>Provisional</th><th></th></tr>
      ${S.spec.teachers.map((t, i) => { const g = load[t.name] || 0; const sp = t.allowance ? Number(t.allowance) - g : ""; return `<tr id="teachers-${i}" class="${out.teachers[i] ? "bad" : ""}"><td style="min-width:180px">${inp(`spec.teachers.${i}.name`, t.name)}</td><td>${inp(`spec.teachers.${i}.short`, t.short, "text", 'style="width:90px"')}</td><td>${sel(`spec.teachers.${i}.dept`, t.dept, sc().departments || [])}</td><td class="num">${inp(`spec.teachers.${i}.allowance`, t.allowance, "number")}</td><td style="min-width:260px">${chips(`spec.teachers.${i}.can_teach`, (t.can_teach || []).map(c => `${c.subject} · ${c.levels || "All"}`), "canteach")}</td><td class="calc">${g}</td><td class="calc" style="${sp !== "" && sp < 0 ? "color:var(--warn);font-weight:600" : ""}">${sp}</td><td>${sel(`spec.teachers.${i}.provisional`, t.provisional, ["Yes", "No"])}</td><td>${delBtn("teachers", i)}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="teachers">+ Add teacher</button></div></div>`;
  },
  blocks() {
    const { out } = issues(); const info = lessonInfo();
    return `<div class="card"><h1>Step 5 · Blocks</h1><p class="lead">A block takes the students of its classes and splits them into groups that all have lessons at the same time (for example, Sec 1 English for 1A–1D split by G3, G2 and G1). Name the block and pick its classes; then add its groups on step 6.</p>
      <div class="tablewrap"><table><tr><th>Block</th><th>Level</th><th>Classes</th><th>Groups (from step 6)</th><th>Students in groups / classes</th><th>Note</th><th></th></tr>
      ${S.spec.blocks.map((b, i) => { const gs = S.spec.lessons.map((x, j) => [x, j]).filter(([x]) => x.block === b.block); const inG = gs.reduce((a, [x]) => a + (Number(x.students) || 0), 0), inC = (b.classes || []).reduce((a, c) => a + (Number((S.spec.classes.find(y => y.class === c) || {}).size) || 0), 0);
        return `<tr id="blocks-${i}" class="${out.blocks[i] ? "bad" : ""}"><td style="min-width:200px">${inp(`spec.blocks.${i}.block`, b.block)}</td><td>${sel(`spec.blocks.${i}.level`, b.level, levels())}</td><td style="min-width:180px">${chips(`spec.blocks.${i}.classes`, b.classes, "classes", `data-level="${esc(b.level || "")}"`)}</td><td class="calc" style="white-space:normal">${esc(gs.map(([x, j]) => info[j].code).join(", "))}</td><td class="calc">${inG} / ${inC}</td><td>${inp(`spec.blocks.${i}.note`, b.note)}</td><td>${delBtn("blocks", i)}</td></tr>`; }).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="blocks">+ Add block</button></div></div>`;
  },
  lessons() {
    const { out, info } = issues(); const T = teacherNames();
    const tsel = (i, k, x) => { const path = `spec.lessons.${i}.teachers.${k}`; const cur = (x.teachers || [])[k] || ""; const yes = T.filter(t => canTeach(t, x.subject, x.level)), no = T.filter(t => !yes.includes(t));
      return `<select data-k="${path}">${opt("", cur, "")}<optgroup label="Can teach this">${yes.map(t => opt(t, cur)).join("")}</optgroup><optgroup label="Others">${no.map(t => opt(t, cur)).join("")}</optgroup></select>`; };
    return `<div class="card"><h1>Step 6 · Lessons</h1><p class="lead">One row per group, or per class for a whole-class subject. Pick level, subject and block (empty = whole class); choosing a block fills its classes. Group code, periods and lesson pattern fill in by themselves.</p>
      <div class="helper row"><b>Add groups to a block</b> ${sel("_hb", "", blockNames(), true, 'id="hbBlock" data-k=""')} subject ${sel("_hbs", "", subjectNames(), true, 'id="hbSubj" data-k=""')} groups <input id="hbN" type="number" value="1" style="width:56px"> students each <input id="hbSt" type="number" style="width:64px"> <button data-helper="groups">Add</button></div>
      <div class="helper row"><b>Add a whole-class subject</b> level ${sel("_hw", levels()[0], levels(), false, 'id="hwLevel" data-k=""')} subject ${sel("_hws", "", subjectNames(), true, 'id="hwSubj" data-k=""')} <button data-helper="whole">Add one row per class</button></div>
      <div class="tablewrap"><table><tr><th>Level</th><th>Subject</th><th>Block</th><th>Classes</th><th>Teacher 1</th><th>Teacher 2</th><th>Students</th><th>Periods override</th><th>Keep code</th><th>Code</th><th>Periods</th><th>Lessons</th><th></th></tr>
      ${S.spec.lessons.map((x, i) => `<tr id="lessons-${i}" class="${out.lessons[i] ? "bad" : ""}" title="${esc((out.lessons[i] || []).join(" "))}"><td class="lv">${sel(`spec.lessons.${i}.level`, x.level, levels())}</td><td style="min-width:200px">${sel(`spec.lessons.${i}.subject`, x.subject, subjectNames().filter(n => (subj(n).periods || {})[x.level] || n === x.subject))}</td><td style="min-width:160px">${sel(`spec.lessons.${i}.block`, x.block, S.spec.blocks.filter(b => !x.level || b.level === x.level).map(b => b.block))}</td><td style="min-width:120px">${chips(`spec.lessons.${i}.classes`, x.classes, "classes", `data-level="${esc(x.level || "")}"`)}</td><td style="min-width:150px">${tsel(i, 0, x)}</td><td style="min-width:120px">${tsel(i, 1, x)}</td><td class="num">${inp(`spec.lessons.${i}.students`, x.students, "number", 'style="width:60px"')}</td><td class="num">${inp(`spec.lessons.${i}.periods_override`, x.periods_override, "number", 'style="width:60px"')}</td><td class="num">${inp(`spec.lessons.${i}.code_override`, x.code_override, "text", 'style="width:70px"')}</td><td class="calc">${esc(info[i].code)}</td><td class="calc">${info[i].p || ""}</td><td class="calc">${info[i].p ? `${info[i].full}×${info[i].L}${info[i].short ? ` + ${info[i].short}×${info[i].L - 1}` : ""}` : ""}</td><td>${delBtn("lessons", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="lessons">+ Add lesson row</button></div></div>`;
  },
  rules() {
    const { out } = issues(); const RT = S.meta.rule_types || []; const NP = Number(sc().periods_per_day); const P = Array.from({ length: NP }, (_, p) => p);
    const psel = (path, cur) => `<select data-k="${path}">${opt("", cur ?? "", "")}${P.map(p => opt(p, cur, `${p} (${clock(p)})`)).join("")}</select>`;
    return `<div class="card"><h1>Step 7 · Rules</h1><p class="lead">Constraints on when things can happen. First pick what the rule applies to; the next drop-down lists only those. <b>Must</b> is never broken; <b>Prefer</b> is kept where possible.</p>
      <div class="tablewrap"><table class="ruletable"><tr><th>Applies to</th><th>Which</th><th>Subject (optional)</th><th>Rule</th><th>Week</th><th>Day</th><th>From</th><th>To</th><th>Number</th><th>Must / Prefer</th><th>Note</th><th></th></tr>
      ${S.spec.rules.map((r, i) => `<tr id="rules-${i}" class="${out.rules[i] ? "bad" : ""}" title="${esc((out.rules[i] || []).join(" "))}"><td>${sel(`spec.rules.${i}.scope`, r.scope, S.meta.scopes)}</td><td style="min-width:150px">${sel(`spec.rules.${i}.target`, r.target, targetOptions(r.scope))}</td><td style="min-width:150px">${sel(`spec.rules.${i}.subject`, r.subject, subjectNames())}</td><td style="min-width:180px">${sel(`spec.rules.${i}.rule`, r.rule, RT.filter(t => !r.scope || t.scopes.includes(r.scope)).map(t => t.rule))}</td><td>${sel(`spec.rules.${i}.week`, r.week || "Both", Number(sc().weeks) === 2 ? ["Both", "Odd", "Even"] : ["Both"], false)}</td><td>${sel(`spec.rules.${i}.day`, r.day || "All", ["All", "Mon", "Tue", "Wed", "Thu", "Fri"], false)}</td><td>${psel(`spec.rules.${i}.from`, r.from)}</td><td>${psel(`spec.rules.${i}.to`, r.to)}</td><td class="num">${inp(`spec.rules.${i}.number`, r.number, "number", 'style="width:56px"')}</td><td>${sel(`spec.rules.${i}.strength`, r.strength || "Must", ["Must", "Prefer"], false)}</td><td class="note">${inp(`spec.rules.${i}.note`, r.note)}</td><td>${delBtn("rules", i)}</td></tr>`).join("")}
      </table></div><div class="row" style="margin-top:10px"><button data-add="rules">+ Add rule</button></div></div>
      <div class="card"><h2>Rule types</h2><div class="tablewrap" style="max-height:none"><table><tr><th>Rule</th><th>Applies to</th><th>What it means</th><th>Example</th></tr>${RT.map(t => `<tr><td><b>${esc(t.rule)}</b></td><td>${esc(t.scopes)}</td><td>${esc(t.meaning)}</td><td class="muted">${esc(t.example)}</td></tr>`).join("")}</table></div></div>`;
  },
  generate() {
    const st = G.st || {}, off = st.ai && !st.ai.ok;
    const facts = [st.ai && st.ai.ok ? `AI: ${esc(st.ai.provider)} · ${esc(st.ai.model)}` : "", st.solve_seconds ? `each solve runs up to ${Math.round(st.solve_seconds / 60)} min` : ""].filter(Boolean);
    return `<div class="card"><h1>Generate & publish</h1><p class="lead">Generate makes the timetable from this setup (it is saved to the server first). With the AI timetabler, it checks the setup, runs the solver and asks you in the chat about anything that does not fit; without AI, it checks and solves, and you read the results. Nothing is visible to teachers or students until you publish.</p>
      ${off ? `<div class="notice"><b>The AI timetabler is off.</b> ${/AI_API_KEY/.test(st.ai.why) ? "No AI API key has been added yet." : esc(st.ai.why)} You can still use <b>Generate without AI</b>: it checks the setup and runs the solver, then you read the results and change the setup yourself. The chat, where the AI explains problems and makes tweaks for you, needs the key: whoever runs the app adds it in Railway (service → Variables → <code>AI_API_KEY</code>, with <code>AI_PROVIDER</code>).</div>` : ""}
      <div class="row"><button class="${off ? "" : "primary"}" id="genAI"${off ? ` title="Needs an AI API key. Generate without AI still works."` : ""}>Generate with the AI timetabler</button><button class="${off ? "primary" : ""}" id="genPlain">Generate without AI</button><button class="danger" id="genStop" hidden>Stop</button></div>
      <p class="muted small">${facts.join(" · ")}</p></div>
      <div class="gen"><div class="card chat"><h2>Timetabler</h2><div id="chatlog" class="chatlog"></div><div id="progress" class="progress"></div>
        <form id="chatform" class="chatform" onsubmit="event.preventDefault(); sendChat(document.getElementById('chatin').value)"><input id="chatin" autocomplete="off"><button class="primary" id="chatsend">Send</button></form></div>
        <div class="side"><div class="card" id="resultCard"></div><div class="card" id="pubCard"></div></div></div>`;
  },
  download() {
    const { out } = issues(); const n = Object.entries(out).filter(([k]) => k !== "global").reduce((a, [, v]) => a + Object.keys(v).length, 0);
    return `<div class="card"><h1>Files</h1><p class="lead">Your setup workbook keeps the drop-downs and formulas, so it can still be edited in Excel. To generate here, use <b>Generate &amp; publish</b>; to generate elsewhere, give the workbook and the timetable skill to an AI agent that can run code.</p>
      <div><span class="stat"><b>${S.spec.classes.length}</b> classes</span><span class="stat"><b>${S.spec.teachers.length}</b> teachers</span><span class="stat"><b>${S.spec.blocks.length}</b> blocks</span><span class="stat"><b>${S.spec.lessons.length}</b> lesson rows</span><span class="stat"><b>${S.spec.rules.length}</b> rules</span></div>
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
  const b = e.target.closest("button, [data-pop], .issue, td.c"); if (!b) return;
  if (b.dataset.step) { S.step = Number(b.dataset.step); save(); render(); window.scrollTo(0, 0); return; }
  if (b.dataset.begin) { const [k, w] = b.dataset.begin.split("|"); try { await begin(k, w); } catch (err) { toast("Could not load: " + err.message); } return; }
  if (b.id === "resume") { const sv = saved(); S.kind = sv.kind; S.meta = await getJSON(`/api/meta/${sv.kind}`); S.spec = sv.spec; S.step = sv.step || 1; ensureDays(); render(); return; }
  if (b.dataset.add) { addRow(b.dataset.add); return; }
  if (b.dataset.del) { const [k, i] = b.dataset.del.split("."); S.spec[k].splice(Number(i), 1); save(); render(); return; }
  if (b.dataset.helper) { helper(b.dataset.helper); return; }
  if (b.dataset.brush !== undefined) { S.brush = b.dataset.brush; render(); return; }
  if (b.dataset.copyday) { const lv = b.dataset.copyday; const ds = S.spec.day_structure[lv]; const f = ds[dayNames()[0]]; dayNames().forEach(d => ds[d] = f); save(); render(); return; }
  if (b.dataset.copylevel) { const src = S.spec.day_structure[b.dataset.copylevel]; levels().forEach(l => S.spec.day_structure[l] = { ...src }); save(); render(); return; }
  if (b.dataset.pop) { openPop(b); return; }
  if (b.classList.contains("issue") && b.dataset.go) { S.step = Number(b.dataset.go); render(); const r = document.getElementById(b.dataset.row); if (r) r.scrollIntoView({ block: "center" }); return; }
  if (b.id === "build") { buildXlsx(); return; }
  if (b.id === "serverSetup") { await adopt(G.server.spec, "Opened the school's saved setup."); return; }
  if (b.id === "genAI" || b.id === "genPlain") { generate(b.id === "genAI"); return; }
  if (b.id === "genStop") { await post("/api/stop"); poll(); return; }
  if (b.id === "publish") { if (!confirm("Publish this timetable? Teachers and students will see it straight away.")) return; const j = await post("/api/publish"); if (j) { toast("Publishing… about a minute."); poll(); } return; }
  if (b.id === "keepChanges") { const j = await post("/api/keep-changes"); if (j && j.spec) { S.spec = j.spec; save(); toast("The AI's changes are now in your setup."); poll(); } return; }
  if (b.dataset.answer !== undefined) { sendChat(b.dataset.answer); return; }
  if (b.id === "exGo") { makePrintouts(); return; }
  if (b.id === "saveJson") { const blob = new Blob([JSON.stringify(S.spec, null, 1)], { type: "application/json" }); dl(blob, `${(S.spec && sc().name) || "timetable"}_setup.json`); return; }
});
let painting = false;
document.addEventListener("mousedown", e => { const c = e.target.closest("td.c"); if (!c) return; painting = true; paint(c); e.preventDefault(); });
document.addEventListener("mouseover", e => { if (!painting) return; const c = e.target.closest("td.c"); if (c) paint(c); });
document.addEventListener("mouseup", () => { if (painting) { painting = false; save(); renderIssues(); } });
function paint(c) {
  const [lv, d, p] = c.dataset.cell.split("|"); const row = S.spec.day_structure[lv][d].split(""); row[Number(p)] = S.brush || "."; S.spec.day_structure[lv][d] = row.join("");
  c.className = `c c-${S.brush}`; c.textContent = S.brush;
}
document.addEventListener("change", async e => {
  const el = e.target;
  if (el.id === "importX") { const f = el.files[0]; if (!f) return; const fd = new FormData(); fd.append("file", f); const r = await fetch("/api/import", { method: "POST", body: fd }); const j = await r.json(); if (!r.ok) { toast(j.error || "Could not read that file."); return; } await adopt(j, "Workbook opened."); return; }
  if (el.id === "loadJson") { const f = el.files[0]; if (!f) return; try { await adopt(JSON.parse(await f.text()), "Progress loaded."); } catch (err) { toast("That file is not a progress file."); } return; }
  if (el.dataset.list) { sc()[el.dataset.list] = el.value.split(",").map(s => s.trim()).filter(Boolean); if (el.dataset.list === "levels") ensureDays(); save(); render(); return; }
  const path = el.dataset.k; if (!path) return;
  let v = el.value; if (el.type === "number") v = v === "" ? null : Number(v); if (v === "") v = null;
  if (/\.(from|to)$/.test(path) && v !== null) v = Number(v);
  if (/^spec\.school\.(weeks|periods_per_day|period_minutes|lesson_length)$/.test(path)) v = Number(v);
  setPath(path, v);
  const m = path.match(/^spec\.lessons\.(\d+)\.block$/);
  if (m && v) { const b = S.spec.blocks.find(x => x.block === v); if (b) { S.spec.lessons[m[1]].classes = [...(b.classes || [])]; S.spec.lessons[m[1]].level = b.level || S.spec.lessons[m[1]].level; } }
  const t = path.match(/^spec\.lessons\.(\d+)\.teachers\.(\d+)$/); if (t) S.spec.lessons[t[1]].teachers = (S.spec.lessons[t[1]].teachers || []).map(x => x || null);
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
    rules: { scope: "Teacher", target: null, rule: "Not available", week: "Both", day: "All", strength: "Must" } }[k];
  S.spec[k].push(JSON.parse(JSON.stringify(blank))); save(); (async () => { try { G.server = await getJSON("/api/setup"); } catch (e) { } render(); poll(); })();
  const rows = document.querySelectorAll(`tr[id^="${k}-"]`); const last = rows[rows.length - 1]; if (last) { last.scrollIntoView({ block: "center" }); const f = last.querySelector("input,select"); if (f) f.focus(); }
}
function helper(k) {
  if (k === "venues") { const pre = $("#hvPre").value, a = Number($("#hvFrom").value), b = Number($("#hvTo").value), kind = $("#hvKind").value; for (let i = a; i <= b; i++) S.spec.venues.push({ room: `${pre}${String(i).padStart(2, "0")}`, kind, capacity: 40 }); }
  if (k === "classes") {
    const lv = $("#hcLevel").value, size = Number($("#hcSize").value) || 38; const used = new Set(S.spec.classes.map(c => c.home_room)); const free = S.spec.venues.filter(v => (v.kind || "classroom") === "classroom" && !used.has(v.room)).map(v => v.room);
    $("#hcNames").value.split(",").map(s => s.trim()).filter(Boolean).forEach(n => S.spec.classes.push({ class: `${String(lv).slice(-1)}${n}`, level: lv, size, home_room: free.shift() || null }));
  }
  if (k === "teachers") { const dept = $("#htDept").value, allow = Number($("#htAllow").value) || null; $("#htNames").value.split("\n").map(s => s.trim()).filter(Boolean).forEach(n => S.spec.teachers.push({ name: n, short: n.split(" ")[0], dept, allowance: allow, provisional: "No", can_teach: [] })); }
  if (k === "groups") { const b = S.spec.blocks.find(x => x.block === $("#hbBlock").value), s = $("#hbSubj").value, n = Number($("#hbN").value) || 1, st = Number($("#hbSt").value) || null; if (!b || !s) { toast("Pick a block and a subject."); return; } for (let i = 0; i < n; i++) S.spec.lessons.push({ level: b.level, subject: s, block: b.block, classes: [...(b.classes || [])], teachers: [], students: st }); }
  if (k === "whole") { const lv = $("#hwLevel").value, s = $("#hwSubj").value; if (!s) { toast("Pick a subject."); return; } S.spec.classes.filter(c => c.level === lv).forEach(c => S.spec.lessons.push({ level: lv, subject: s, block: null, classes: [c.class], teachers: [], students: c.size })); }
  save(); render(); toast("Added.");
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
  else setPath(path, readCt().filter(c => c.subject));
  pop.hidden = true; save(); (async () => { try { G.server = await getJSON("/api/setup"); } catch (e) { } render(); poll(); })();
}

/* ---------------- generate, chat, publish */
const G = { server: null, st: null, after: 0, events: [], timer: null };
async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { location.href = "/login"; return null; }
  if (!r.ok) { toast(j.error || "Something went wrong."); return null; }
  return j;
}
async function generate(withAI) {
  if (!S.spec) { toast("Open or start a setup first."); return; }
  G.events = []; G.after = 0;
  const j = await post("/api/generate", { spec: S.spec, ai: withAI });
  if (j) { toast(withAI ? "The AI timetabler has started." : "Generating…"); poll(); }
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
      G.events.push(...st.run.events); if (st.run.events.length) G.after = st.run.events[st.run.events.length - 1].n;
    }
    if (STEPS[S.step][0] === "generate") paintGen();
  } catch (e) { }
  G.inflight = false;
  const busy = G.st && G.st.run && G.st.run.busy;
  G.timer = setTimeout(poll, STEPS[S.step][0] === "generate" ? (busy ? 1500 : 5000) : 15000);
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
    case "nosolution": return `<div class="ev bad"><b>${esc(e.text)}</b>${items}</div>`;
    case "error": return `<div class="ev bad">${esc(e.text)}</div>`;
    case "published": return `<div class="ev good"><b>${esc(e.text)}</b></div>`;
    case "check": return `<div class="ev">${esc(e.text)}${items ? `<details><summary>Details</summary>${items}</details>` : ""}</div>`;
    case "moved": return `<div class="ev">${esc(e.text)}${items ? `<details><summary>Which lessons moved</summary>${items}</details>` : ""}</div>`;
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
  const s = run && run.solved;
  $("#resultCard").innerHTML = `<h2>Latest timetable</h2>` + (s ? `<p class="${s.ok ? "okmsg" : "issue"}">${s.ok ? "All checks passed" : `${s.problems.length} problems`} · ${s.lessons} lessons · ${s.after.length ? `${s.after.length} after school` : "nothing after school"}</p>
      ${s.after.length ? `<details><summary>After-school lessons</summary><ul>${s.after.map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}
      ${s.problems.length ? `<details open><summary>Problems</summary><ul>${s.problems.map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}
      ${s.notes.length ? `<details><summary>Notes</summary><ul>${s.notes.map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}
      <p class="muted small">Made ${esc(s.at)}${run.changes ? ` · the AI changed the setup ${run.changes} time${run.changes > 1 ? "s" : ""}` : ""}.</p>
      <div class="row"><a href="/preview" target="_blank"><button>Preview</button></a><button class="primary" id="publish" ${busy ? "disabled" : ""}>Publish</button>
      ${run.changes ? `<button id="keepChanges" ${busy ? "disabled" : ""}>Keep the AI's changes in my setup</button>` : ""}</div>`
    : `<p class="muted">No timetable yet.</p>`);
  const p = st.published, f = p ? p.files || {} : {};
  $("#pubCard").innerHTML = `<h2>Published</h2>` + (p ? `<p class="${p.ok ? "okmsg" : "issue"}">Published ${esc(p.at)} · ${p.classes} classes · ${p.students} students${p.after ? ` · ${p.after} after school` : ""}</p>
      <div class="row"><a href="/timetable" target="_blank"><button class="primary">Open the timetable</button></a></div>
      <h3>Downloads</h3><div class="links"><a href="/files/excel">Excel, every timetable</a><a href="/files/zip">PDFs, one per class, teacher, room and student (zip)</a>
      ${Object.keys(f.books || {}).map(k => `<a href="/files/book/${k}">${k[0].toUpperCase() + k.slice(1)}: all in one PDF</a>`).join("")}</div>
      <h3>Personal student codes</h3>${p.students ? `<div class="links"><a href="/api/code-slips.pdf">Code slips to print, by class (PDF)</a><a href="/api/codes.csv">Code list (CSV)</a></div>` : `<p class="muted small">Add students (Students sheet) to give each one a personal code.</p>`}`
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

(async () => { try { G.server = await getJSON("/api/setup"); } catch (e) { } render(); poll(); })();

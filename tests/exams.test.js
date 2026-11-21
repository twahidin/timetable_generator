// Plain-assert tests for static/exams.js's Approval tab checks: run with `node tests/exams.test.js`.
// The page is one closure, so the function under test is cut out of the file by its braces and run on its own.
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(path.join(__dirname, "..", "static", "exams.js"), "utf8");
function cut(name) {
  const at = SRC.indexOf(`function ${name}(`); assert(at >= 0, name);
  let i = SRC.indexOf("{", at), depth = 0;
  for (; i < SRC.length; i++) { if (SRC[i] === "{") depth++; else if (SRC[i] === "}" && --depth === 0) break; }
  return SRC.slice(at, i + 1);
}
const uniq = a => a.filter((x, i) => a.indexOf(x) === i);
const checkLines = new Function("uniq", `${cut("checkLines")}; return checkLines;`)(uniq);

let n = 0; const t = (name, f) => { f(); n++; };
const free = lines => ({ key: "free", ok: !lines.length, lines });
const others = lines => ({ key: "others", ok: !lines.length, lines });
const TAKES2 = "Sec 4 Exam (approved) takes 2 of these invigilators on Mon 5 Oct.";
const USES = "Sec 4 Exam (approved) uses Hall on Mon 5 Oct too.";
const busy = (who, date) => `${who}, 3-01 on ${date} 07:35–09:00: is on Sec 4 Exam then (Hall).`;

t("a takes line goes when the free lines name that schedule for as many people that day", () => {
  const all = [free([busy("Ms A", "Mon 5 Oct"), busy("Mr B", "Mon 5 Oct")]), others([TAKES2, USES])];
  assert.deepStrictEqual(checkLines(all[1], all), [USES]);
});
t("it stays when the free lines name fewer people than it counts", () => {
  const all = [free([busy("Ms A", "Mon 5 Oct"), busy("Ms A", "Mon 5 Oct").replace("3-01", "3-02")]), others([TAKES2])];
  assert.deepStrictEqual(checkLines(all[1], all), [TAKES2], "one person twice is one person");
});
t("a clash on another date or with another schedule does not count", () => {
  const all = [free([busy("Ms A", "Tue 6 Oct"), busy("Mr B", "Mon 5 Oct").replace("Sec 4 Exam", "Sec 2 Exam")]), others([TAKES2])];
  assert.deepStrictEqual(checkLines(all[1], all), [TAKES2]);
  const own = [free(["Ms A, 3-01 on Mon 5 Oct 07:35–09:00: is on another duty then (3-02).", busy("Mr B", "Mon 5 Oct")]), others([TAKES2])];
  assert.deepStrictEqual(checkLines(own[1], own), [TAKES2], "the own-duty clash is not the other schedule");
});
t("other checks pass through as they are", () => {
  const all = [free([busy("Ms A", "Mon 5 Oct")]), others([])];
  assert.deepStrictEqual(checkLines(all[0], all), all[0].lines);
  assert.deepStrictEqual(checkLines(all[1], all), []);
});
t("an event's free line has no room in brackets", () => {
  const ev = who => `${who}, 3-01 on Mon 5 Oct 07:35–09:00: is on Sec 3 Learning Journey then.`;
  const TAKES = "Sec 3 Learning Journey (waiting) takes 2 of these invigilators on Mon 5 Oct.";
  const all = [free([ev("Ms A"), ev("Mr B")]), others([TAKES])];
  assert.deepStrictEqual(checkLines(all[1], all), []);
});
/* the Lessons tab: one backup item of each state, its sentence and its "Handled ourselves" box */
const esc = x => String(x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const stateCode = SRC.slice(SRC.indexOf("const BACKUP_STATE"), SRC.indexOf("function lessonList("));   /* the state table, the box rule and backupState */
const lessonsTab = view => new Function("esc", "S", "fmtDate", `${stateCode}\n${cut("lessonList")}\n${cut("tabLessons")}; return tabLessons();`)(esc, { view, open: {}, busy: false }, d => d);
const STATES = [["later", "Goes to the relief team when approved", true], ["sent", "Sent to the relief team", true], ["relief", "Relief: Mr Ben Ong", true],
  ["handled", "Handled ourselves", true], ["stopped", "Not happening: 3A is on Sec 3 End-of-Year Exam", false], ["past", "In the past", false], ["elsewhere", "Sent by another schedule", false]];
t("the Lessons tab says where each backup stands and offers Handled ourselves only where it can", () => {
  const backup = STATES.map(([state], i) => ({ date: "2027-01-04", start: "07:40", end: "08:20", classes: ["3A"], subject: "English", teachers: ["Ms Z"], teacher: "Ms Z" + i, key: "k" + i, state,
    relief: state === "relief" ? "Mr Ben Ong" : null, stopped: state === "stopped" ? "3A is on Sec 3 End-of-Year Exam" : "" }));
  const html = lessonsTab({ lessons: { none: [], backup, runs: [] } });
  STATES.forEach(([state, text, box], i) => {
    assert(html.includes(`>${text}`), state + ": " + text);
    const has = html.includes(`data-t="Ms Z${i}" data-k="k${i}"`);
    assert.strictEqual(has, box, state + " box");
  });
  assert.strictEqual((html.match(/Handled ourselves<\/label>/g) || []).length, 4);
  assert(/data-k="k3" checked/.test(html), "only the handled one is ticked");
  assert(!/data-k="k0" checked/.test(html));
  assert(html.includes("Backups go to the relief team as planned relief when the schedule is approved."));
});
t("the exams page no longer says that sending comes in a later stage", () => {
  assert(!SRC.includes("arrives in a later stage") && !SRC.includes("comes in a later stage"));
});
/* onHandled: the click path with a stubbed api */
const runHandled = async (S, reply) => {
  const calls = [];
  const f = new Function("S", "api", "paint", "paintSave", `async ${cut("onHandled")}; return onHandled;`)(S, async (m, u, b) => { calls.push([m, u, b]); return reply; }, () => {}, () => {});
  return [f, calls];
};
const box = (checked, teacher = "Ms Z", key = "k1") => ({ checked, dataset: { t: teacher, k: key } });
(async () => {
  let S = { base: "/api/exams", id: "x1", busy: false, view: { old: 1 }, rv: {}, hpend: {} };
  let [f, calls] = await runHandled(S, { ok: true, status: 200, j: { lessons: { backup: [] } } });
  const el = box(true), p = f(el);
  assert.deepStrictEqual(S.hpend, { "Ms Z|k1": true }, "the chosen value shows while in flight");
  assert.strictEqual(S.busy, true);
  const el2 = box(true); await f(el2);
  assert.strictEqual(el2.checked, false, "a second click while busy is put back");
  assert.strictEqual(calls.length, 1, "and posts nothing");
  await p;
  assert.deepStrictEqual(calls[0], ["POST", "/api/exams/x1/handled", { teacher: "Ms Z", key: "k1", handled: true }]);
  assert.deepStrictEqual(S.view, { lessons: { backup: [] } }); assert.strictEqual(S.rv, null); assert.deepStrictEqual(S.hpend, {}); assert.strictEqual(S.busy, false);
  S = { base: "/api/events", id: "e1", busy: false, view: { old: 1 }, rv: { keep: 1 }, hpend: {}, msg: "", bad: false };
  [f, calls] = await runHandled(S, { ok: false, status: 400, j: { error: "That lesson no longer needs a backup." } });
  await f(box(true));
  assert.strictEqual(calls[0][1], "/api/events/e1/handled");
  assert.strictEqual(S.msg, "That lesson no longer needs a backup."); assert.strictEqual(S.bad, true);
  assert.deepStrictEqual(S.view, { old: 1 }); assert.deepStrictEqual(S.hpend, {});
  console.log("onHandled cases passed");
})().catch(e => { console.error(e); process.exit(1); });
console.log(`${n} exams page tests passed`);

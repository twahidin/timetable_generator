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
console.log(`${n} exams page tests passed`);

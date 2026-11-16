// Plain-assert tests for static/grid.js (the week grid layout): run with `node tests/grid.test.js`
const assert = require("assert");
const Grid = require("../static/grid.js");
let n = 0; const t = (name, f) => { try { f(); } catch (e) { console.error("FAILED: " + name); throw e; } n++; };

const lz = (id, group, d, p, k, extra) => Object.assign({ id: id, group: group, subject: "Maths", classes: ["1A"], teachers: ["Mr Tan"], room: "R1", d: d, p: p, n: k, block: false, what: "" }, extra || {});
const payload = (days, lessons, codes) => ({ view: "class", name: "1A", days: days, NP: 5, times: [], codes: codes || days.map(() => "LLLRL"), lessons: lessons });

t("weeks: one-week school gives one unnamed week", () => {
  assert.deepStrictEqual(Grid.weeks(["Mon", "Tue", "Wed"]), [{ name: "", days: [{ i: 0, label: "Mon" }, { i: 1, label: "Tue" }, { i: 2, label: "Wed" }] }]);
  assert.deepStrictEqual(Grid.weeks([]), [{ name: "", days: [] }]);
});

t("weeks: two-week school gives Odd and Even with the day indexes kept", () => {
  assert.deepStrictEqual(Grid.weeks(["Odd Mon", "Odd Tue", "Even Mon", "Even Tue"]), [
    { name: "Odd", days: [{ i: 0, label: "Mon" }, { i: 1, label: "Tue" }] },
    { name: "Even", days: [{ i: 2, label: "Mon" }, { i: 3, label: "Tue" }] }]);
});

t("table: a two-period lesson spans two rows and the cell below is covered", () => {
  const p = payload(["Mon", "Tue"], [lz("a", "1A", 0, 1, 2)]);
  const rows = Grid.table(p, Grid.weeks(p.days)[0]);
  assert.strictEqual(rows.length, 5);
  assert.ok(rows.every(r => r.length === 2));
  assert.deepStrictEqual(rows[1][0], { d: 0, p: 1, code: "L", lessons: [p.lessons[0]], rowspan: 2, covered: false });
  assert.deepStrictEqual(rows[2][0], { d: 0, p: 2, code: "L", lessons: [], rowspan: 1, covered: true });
  assert.strictEqual(rows[3][0].covered, false);
  assert.strictEqual(rows[1][1].covered, false);   // the other day is untouched
  assert.strictEqual(rows[2][1].covered, false);
});

t("table: three periods cover two cells; a span into a break still covers it", () => {
  const p = payload(["Mon"], [lz("a", "1A", 0, 1, 3)]);   // periods 1,2,3; period 3 is recess
  const rows = Grid.table(p, Grid.weeks(p.days)[0]);
  assert.deepStrictEqual(rows.map(r => r[0].covered), [false, false, true, true, false]);
  assert.strictEqual(rows[3][0].code, "R");
  assert.strictEqual(rows[1][0].rowspan, 3);
});

t("table: parallel group rows share a cell; the rowspan is the longest", () => {
  const rs = [lz("b", "1A-g1", 0, 0, 1, { block: true }), lz("b", "1A-g2", 0, 0, 1, { block: true }), lz("c", "1A", 0, 0, 2)];
  const p = payload(["Mon"], rs);
  const rows = Grid.table(p, Grid.weeks(p.days)[0]);
  assert.deepStrictEqual(rows[0][0].lessons, rs);
  assert.strictEqual(rows[0][0].rowspan, 2);
  assert.strictEqual(rows[1][0].covered, true);
});

t("table: a break period carries its code and no lessons; empty and na codes", () => {
  const p = payload(["Mon"], [], ["LURF."]);
  const rows = Grid.table(p, Grid.weeks(p.days)[0]);
  assert.deepStrictEqual(rows.map(r => r[0].code), ["L", "U", "R", "F", "."]);
  assert.ok(rows.every(r => r[0].lessons.length === 0 && r[0].rowspan === 1 && r[0].covered === false));
});

t("table: a two-week school lays out one week at a time", () => {
  const p = payload(["Odd Mon", "Even Mon"], [lz("a", "1A", 1, 0, 1)], ["LLLLL", "ALLLL"]);
  const [odd, even] = Grid.weeks(p.days);
  const o = Grid.table(p, odd), e = Grid.table(p, even);
  assert.strictEqual(o[0][0].d, 0); assert.strictEqual(o[0][0].lessons.length, 0);
  assert.strictEqual(e[0][0].d, 1); assert.strictEqual(e[0][0].lessons.length, 1); assert.strictEqual(e[0][0].code, "A");
});

t("stateClass", () => {
  assert.deepStrictEqual(["ok", "prefer", "no", "na", "x", undefined].map(Grid.stateClass), ["ok", "prefer", "no", "na", "", ""]);
});

t("table: a lesson starting under another's span joins its top cell", () => {
  const A = lz("a", "g1", 0, 2, 2), B = lz("b", "g2", 0, 3, 2);
  const p = payload(["Mon"], [B, A]);
  const rows = Grid.table(p, Grid.weeks(p.days)[0]);
  assert.deepStrictEqual(rows[2][0].lessons, [A, B]);
  assert.strictEqual(rows[2][0].rowspan, 3);
  assert.deepStrictEqual([3, 4].map(i => [rows[i][0].covered, rows[i][0].lessons.length]), [[true, 0], [true, 0]]);
  assert.strictEqual(A.p, 2); assert.strictEqual(B.p, 3);
});

t("table: a chain of three overlapping lessons merges into one cell", () => {
  const A = lz("a", "g1", 0, 0, 2), B = lz("b", "g2", 0, 1, 2), C = lz("c", "g3", 0, 2, 2);
  const p = payload(["Mon"], [A, B, C]); p.NP = 6;
  const rows = Grid.table(p, Grid.weeks(p.days)[0]);
  assert.deepStrictEqual(rows[0][0].lessons, [A, B, C]);
  assert.strictEqual(rows[0][0].rowspan, 4);
  assert.deepStrictEqual(rows.map(r => r[0].covered), [false, true, true, true, false, false]);
  assert.ok(rows.slice(1).every(r => r[0].lessons.length === 0));
});

t("table: rowspan stops at the end of the day", () => {
  const p = payload(["Mon"], [lz("a", "g1", 0, 1, 5)]); p.NP = 3;
  const rows = Grid.table(p, Grid.weeks(p.days)[0]);
  assert.strictEqual(rows[1][0].rowspan, 2);
  assert.strictEqual(rows[2][0].covered, true);
});

t("table: missing codes and a lesson with no length", () => {
  const rs = [lz("a", "g1", 0, 0, 0), lz("b", "g2", 0, 1, null), lz("c", "g3", 0, 2, undefined)];
  const p = payload(["Mon"], rs); delete p.codes;
  const rows = Grid.table(p, Grid.weeks(p.days)[0]);
  assert.deepStrictEqual(rows.map(r => r[0].code), [".", ".", ".", ".", "."]);
  assert.deepStrictEqual(rows.slice(0, 3).map(r => r[0].rowspan), [1, 1, 1]);
});

t("label: short subject, the group unless it is the whole class, teacher shorts; falls back to full words", () => {
  assert.strictEqual(Grid.label(lz(1, "1MAA1", 0, 0, 1, { short: "Mat", tshorts: ["TAN", "LIM"], teachers: ["Mr Tan", "Ms Lim"] })), "Mat · 1MAA1 · TAN, LIM");
  assert.strictEqual(Grid.label(lz(1, "Entire Class", 0, 0, 1, { short: "Art", tshorts: ["UT"], teachers: ["Umairah Tan"] })), "Art · UT");
  assert.strictEqual(Grid.label(lz(1, "1A", 0, 0, 1, { teachers: ["Mr Tan", "Ms Lim"] }), { "Mr Tan": "TAN" }), "Maths · 1A · TAN, Ms Lim");
  assert.strictEqual(Grid.fullLabel(lz(1, "1A", 0, 0, 1, { teachers: ["Mr Tan"] })), "Maths · 1A · Mr Tan · R1");
});

t("markClass and wasText: the mark, and where a moved row was", () => {
  const days = ["Mon", "Tue"];
  assert.strictEqual(Grid.markClass({ mark: "moved" }), "moved");
  assert.strictEqual(Grid.markClass({ mark: "changed" }), "changed");
  assert.strictEqual(Grid.markClass({ mark: "new" }), "new");
  assert.strictEqual(Grid.markClass({ mark: "" }), "");
  assert.strictEqual(Grid.markClass({}), "");
  assert.strictEqual(Grid.markClass({ mark: "weird" }), "");
  assert.strictEqual(Grid.wasText({ mark: "moved", was: { d: 1, p: 3 } }, days), "was Tue period 3");
  assert.strictEqual(Grid.wasText({ mark: "moved", was: { d: 0, p: 0 } }, days), "was Mon period 0");
  assert.strictEqual(Grid.wasText({ mark: "moved" }, days), "");   // a mark but no was
  assert.strictEqual(Grid.wasText({ mark: "changed", was: { d: 1, p: 3 } }, days), "");
  assert.strictEqual(Grid.wasText({ mark: "" }, days), "");
});

console.log(`${n} cases passed`);

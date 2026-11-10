// Plain-assert tests for static/grid.js (the week grid layout): run with `node tests/grid.test.js`
const assert = require("assert");
const Grid = require("../static/grid.js");
let n = 0; const t = (name, f) => { f(); n++; };

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

t("lesson and same", () => {
  const rs = [lz("b", "g1", 0, 0, 1), lz("b", "g2", 0, 0, 1)];
  const p = payload(["Mon"], rs);
  assert.strictEqual(Grid.lesson(p, "b", "g2"), rs[1]);
  assert.strictEqual(Grid.lesson(p, "b", "g3"), null);
  assert.strictEqual(Grid.lesson(p, "zz", "g1"), null);
  assert.ok(Grid.same({ id: "b", group: "g1" }, { id: "b", group: "g1", d: 3 }));
  assert.ok(!Grid.same({ id: "b", group: "g1" }, { id: "b", group: "g2" }));
  assert.ok(!Grid.same({ id: "b", group: "g1" }, { id: "c", group: "g1" }));
  assert.ok(!Grid.same(null, { id: "b", group: "g1" }));
});

t("slotAt, stateClass", () => {
  const s = [{ d: 0, p: 1, state: "ok" }, { d: 1, p: 2, state: "no" }];
  assert.strictEqual(Grid.slotAt(s, 1, 2), s[1]);
  assert.strictEqual(Grid.slotAt(s, 1, 1), null);
  assert.strictEqual(Grid.slotAt([], 0, 0), null);
  assert.deepStrictEqual(["ok", "prefer", "no", "na", "x", undefined].map(Grid.stateClass), ["ok", "prefer", "no", "na", "", ""]);
});

t("slotText: move or swap, with and without why", () => {
  const days = ["Odd Mon", "Odd Tue"];
  assert.strictEqual(Grid.slotText({ d: 1, p: 3, swap: null, why: null }, days), "Move to Odd Tue period 3");
  assert.strictEqual(Grid.slotText({ d: 0, p: 0, swap: "x", why: "" }, days), "Swap with the lesson on Odd Mon period 0");
  assert.strictEqual(Grid.slotText({ d: 0, p: 2, swap: "x", why: "Mr Tan is teaching then." }, days), "Swap with the lesson on Odd Mon period 2 — Mr Tan is teaching then.");
  assert.strictEqual(Grid.slotText({ d: 0, p: 2, swap: null, why: "Not ideal." }, days), "Move to Odd Mon period 2 — Not ideal.");
});

t("sorted: ok, prefer, no; na dropped; by day then period; new list", () => {
  const s = [{ d: 1, p: 0, state: "no" }, { d: 0, p: 4, state: "na" }, { d: 1, p: 2, state: "ok" }, { d: 0, p: 3, state: "prefer" }, { d: 0, p: 5, state: "ok" }, { d: 1, p: 1, state: "ok" }];
  const copy = s.slice();
  const out = Grid.sorted(s);
  assert.deepStrictEqual(out.map(x => x.state + x.d + x.p), ["ok05", "ok11", "ok12", "prefer03", "no10"]);
  assert.deepStrictEqual(s, copy);
  assert.deepStrictEqual(Grid.sorted([{ d: 0, p: 0, state: "na" }]), []);
  assert.deepStrictEqual(Grid.sorted([]), []);
});

console.log(`${n} cases passed`);

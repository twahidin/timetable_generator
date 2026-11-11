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

t("wanted: an answer counts only for the same view, name, lesson and add key", () => {
  const a = { view: "class", name: "1A", id: 5, group: "G" };
  assert.ok(Grid.wanted(a, { view: "class", name: "1A", id: 5, group: "G" }));
  assert.ok(!Grid.wanted(a, { view: "class", name: "1A", id: 6, group: "G" }));
  assert.ok(!Grid.wanted(a, { view: "class", name: "1B", id: 5, group: "G" }));
  assert.ok(!Grid.wanted(a, { view: "class", name: "1A", key: "C:1A:Art" }));
  assert.ok(!Grid.wanted(a, null));
});

t("fixFor: a slot with a swap posts the swap, any other slot a move", () => {
  const sel = { id: 5, group: "Entire Class" };
  assert.deepStrictEqual(Grid.fixFor(sel, { d: 2, p: 3, state: "ok", why: "", swap: 9, also: [] }), { kind: "swap", a: 5, b: 9 });
  assert.deepStrictEqual(Grid.fixFor(sel, { d: 2, p: 3, state: "ok", why: "", swap: 0, also: [] }), { kind: "swap", a: 5, b: 0 });   // an id of 0 is still a swap
  assert.deepStrictEqual(Grid.fixFor(sel, { d: 2, p: 3, state: "ok", why: "", swap: null, also: [] }), { kind: "move", id: 5, d: 2, p: 3 });
  assert.deepStrictEqual(Grid.fixFor(sel, { d: 0, p: 0, state: "prefer" }), { kind: "move", id: 5, d: 0, p: 0 });
});

t("addFor: the key, the slot and the length", () => {
  assert.deepStrictEqual(Grid.addFor("C:1A:Art", { d: 1, p: 4, state: "ok" }, 2), { kind: "add", key: "C:1A:Art", d: 1, p: 4, n: 2 });
  assert.deepStrictEqual(Grid.addFor("G:1ML1", { d: 0, p: 0 }, "1"), { kind: "add", key: "G:1ML1", d: 0, p: 0, n: 1 });
});

t("deleteFor: the group is posted when the lesson has more than one row in the grid, or is a block", () => {
  const one = payload(["Mon"], [lz(3, "Entire Class", 0, 1, 1), lz(4, "1MAA1", 0, 2, 1), lz(4, "1MAA2", 0, 2, 1), lz(6, "1ART1", 0, 3, 1, { block: "Art band" })]);
  assert.deepStrictEqual(Grid.deleteFor(one, { id: 3, group: "Entire Class" }), { kind: "delete", id: 3 });
  assert.deepStrictEqual(Grid.deleteFor(one, { id: 4, group: "1MAA2" }), { kind: "delete", id: 4, group: "1MAA2" });   // two rows and no block
  assert.deepStrictEqual(Grid.deleteFor(one, { id: 6, group: "1ART1" }), { kind: "delete", id: 6, group: "1ART1" });
});

t("slotText: a swap slot names the swap", () => {
  assert.strictEqual(Grid.slotText({ d: 1, p: 2, swap: 7, why: "" }, ["Mon", "Tue"]), "Swap with the lesson on Tue period 2");
  assert.strictEqual(Grid.slotText({ d: 0, p: 2, swap: null, why: "Not ideal." }, ["Mon", "Tue"]), "Move to Mon period 2 — Not ideal.");
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

t("others: a class view drops the shown class, a teacher view keeps all", () => {
  const pv = { classes: [{ view: "class", name: "1A" }, { view: "class", name: "1B" }, { view: "class", name: "2C" }] };
  assert.deepStrictEqual(Grid.others(pv, { view: "class", name: "1B" }).map(c => c.name), ["1A", "2C"]);
  assert.deepStrictEqual(Grid.others(pv, { view: "teacher", name: "1B" }).map(c => c.name), ["1A", "1B", "2C"]);
  assert.deepStrictEqual(Grid.others(pv, { view: "class", name: "9Z" }).map(c => c.name), ["1A", "1B", "2C"]);
  assert.deepStrictEqual(Grid.others({ classes: [] }, { view: "class", name: "1A" }), []);
  assert.deepStrictEqual(Grid.others({}, { view: "teacher", name: "Mr Tan" }), []);
  assert.deepStrictEqual(Grid.others(null, { view: "class", name: "1A" }), []);
});

t("previewFor: the one fix a click on a slot posts, as a list", () => {
  const sel = { id: 5, group: "Entire Class" };
  assert.deepStrictEqual(Grid.previewFor(sel, { d: 2, p: 3, swap: null }), [{ kind: "move", id: 5, d: 2, p: 3 }]);
  assert.deepStrictEqual(Grid.previewFor(sel, { d: 2, p: 3, swap: 9 }), [{ kind: "swap", a: 5, b: 9 }]);
});

t("marks: the marked rows the main grid can show, by id and group", () => {
  const pv = { classes: [
    { view: "class", name: "1A", lessons: [{ id: 1, group: "Entire Class", mark: "moved" }, { id: 2, group: "Entire Class", mark: "" }] },
    { view: "class", name: "1B", lessons: [{ id: 3, group: "G1", mark: "changed" }, { id: 4, group: "Entire Class", mark: "new" }] }] };
  assert.deepStrictEqual(Object.keys(Grid.marks(pv, { view: "class", name: "1A" })), ["1|Entire Class"]);
  assert.deepStrictEqual(Object.keys(Grid.marks(pv, { view: "class", name: "1B" })), ["3|G1", "4|Entire Class"]);
  assert.deepStrictEqual(Object.keys(Grid.marks(pv, { view: "teacher", name: "Mr Tan" })), ["1|Entire Class", "3|G1", "4|Entire Class"]);
  assert.deepStrictEqual(Grid.marks(null, { view: "class", name: "1A" }), {});
});

console.log(`${n} cases passed`);

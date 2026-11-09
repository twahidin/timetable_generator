// Plain-assert tests for static/map.js (the department map's logic): run with `node tests/map.test.js`
const assert = require("assert");
const DeptMap = require("../static/map.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { levels: ["Sec 1", "Sec 2"], departments: ["MA", "EL"], bands: {} },
  classes: [{ class: "1A", level: "Sec 1", size: 30 }, { class: "1B", level: "Sec 1", size: 30 }, { class: "2A", level: "Sec 2", size: 30 }],
  subjects: [{ subject: "Mathematics", code: "MA", dept: "MA", periods: { "Sec 1": 6, "Sec 2": 6 } }, { subject: "English Language", code: "EL", dept: "EL", periods: { "Sec 1": 6 } }],
  teachers: [{ _id: "ta", name: "Arjun Nair", short: "Arjun", dept: "MA", role: "EO", allowance: 20, can_teach: [{ subject: "Mathematics", levels: "All" }] },
             { _id: "tb", name: "Priya Menon", short: "Priya", dept: "MA", role: "HOD", allowance: 12, other_duties: 4, can_teach: [] },
             { _id: "tc", name: "Wei Lin Tan", short: "Wei Lin", dept: "EL", role: "EO", allowance: 20, can_teach: [{ subject: "English Language", levels: "All" }, { subject: "Mathematics", levels: "Sec 1" }] },
             { _id: "td", name: "Hafiz Osman", short: "Hafiz", dept: "EL", role: "EO", allowance: 20, can_teach: [] }],
  blocks: [{ _id: "b1", block: "Sec 2 Mathematics", level: "Sec 2", classes: ["2A"] }],
  lessons: [{ _id: "l1", level: "Sec 1", subject: "Mathematics", block: null, classes: ["1A", "1B"], teachers: ["Arjun Nair"], students: 30 },
            { _id: "l2", level: "Sec 2", subject: "Mathematics", block: "Sec 2 Mathematics", classes: ["2A"], teachers: ["Arjun Nair"], students: 15 },
            { _id: "l3", level: "Sec 2", subject: "Mathematics", block: "Sec 2 Mathematics", classes: ["2A"], teachers: ["Arjun Nair", "Wei Lin Tan"], students: 15 },
            { _id: "l4", level: "Sec 1", subject: "English Language", block: null, classes: ["1A"], teachers: [], students: 30 }],
  rules: [], students: [], roles: [{ role: "EO", allowance: 20 }, { role: "HOD", allowance: 12 }] });
const infoOf = spec => spec.lessons.map((x, i) => ({ p: 6, tp: 6 * (x.block ? 1 : x.classes.length), code: x.block ? `2MA${i}` : "Entire Class" }));

t("loads: periods deployed plus other duties against the allowance", () => {
  const L = DeptMap.loads(fixture(), infoOf(fixture()));
  assert.deepStrictEqual(L["Arjun Nair"], { lessons: 24, duties: 0, allowance: 20, total: 24, over: true });
  assert.deepStrictEqual(L["Priya Menon"], { lessons: 0, duties: 4, allowance: 12, total: 4, over: false });
  assert.strictEqual(L["Hafiz Osman"].total, 0);
});
t("roster: the department's teachers in setup order, then the visitors", () => {
  assert.deepStrictEqual(DeptMap.roster(fixture(), "MA", []), [0, 1]);
  assert.deepStrictEqual(DeptMap.roster(fixture(), "MA", ["td", "ta", "nobody"]), [0, 1, 3]);
  assert.deepStrictEqual(DeptMap.unplaced(fixture(), [0, 1, 3]), [1, 3]);
});
t("search finds teachers of other departments by name or short name", () => {
  assert.deepStrictEqual(DeptMap.search(fixture(), "wei", "MA"), [2]);
  assert.deepStrictEqual(DeptMap.search(fixture(), "arjun", "MA"), []);
  assert.deepStrictEqual(DeptMap.search(fixture(), "  ", "MA"), []);
});
t("baskets: one per subject of the department, with teachers from any department", () => {
  assert.deepStrictEqual(DeptMap.baskets(fixture(), "MA"), [{ subject: "Mathematics", teachers: [0, 2] }]);
  assert.deepStrictEqual(DeptMap.staffRoom(fixture(), [0, 1]), [1]);
});
t("classes tab: one card per class of a whole-class row, in level then class order", () => {
  const c = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "classes", "");
  assert.deepStrictEqual(c.map(x => [x.kind, x.li, x.cls, x.periods, x.teachers]), [["class", 0, "1A", 6, ["Arjun Nair"]], ["class", 0, "1B", 6, ["Arjun Nair"]]]);
  assert.deepStrictEqual(DeptMap.cards(fixture(), infoOf(fixture()), "EL", "classes", "Sec 2"), []);
});
t("groups and bands tabs", () => {
  const g = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "groups", "");
  assert.deepStrictEqual(g.map(x => [x.kind, x.li, x.title, x.block]), [["group", 1, "2MA1", "Sec 2 Mathematics"], ["group", 2, "2MA2", "Sec 2 Mathematics"]]);
  const b = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "bands", "");
  assert.strictEqual(b.length, 1); assert.strictEqual(b[0].kind, "band"); assert.strictEqual(b[0].groups.length, 2);
  assert.deepStrictEqual(b[0].twice, ["Arjun Nair"]);
  assert.deepStrictEqual(DeptMap.cards(fixture(), infoOf(fixture()), "EL", "bands", ""), []);
});
t("prune keeps only ids that are still teachers", () => { assert.deepStrictEqual(DeptMap.prune(["tb", "gone", "ta"], fixture()), ["tb", "ta"]); });
console.log(`${n} cases passed`);

// Plain-assert tests for static/groups.js (groups and bands on step 5): run with `node tests/groups.test.js`
const assert = require("assert");
const Groups = require("../static/groups.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { levels: ["Sec 1", "Sec 2"], departments: ["MA", "EL"], tags: [["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]] },
  classes: [{ class: "1A", level: "Sec 1", size: 30 }, { class: "1B", level: "Sec 1", size: 32 }, { class: "1C", level: "Sec 1", size: 31 }, { class: "2A", level: "Sec 2", size: 30 }],
  subjects: [{ subject: "Mathematics G3", code: "MA", tag: "G3", dept: "MA", periods: { "Sec 1": 6, "Sec 2": 6 } }, { subject: "Mathematics G2", code: "MA", tag: "G2", dept: "MA", periods: { "Sec 1": 6 } },
             { subject: "English Language G3", code: "EL", tag: "G3", dept: "EL", periods: { "Sec 1": 6 } }, { subject: "Art", code: "AR", tag: "-", dept: "AE", periods: { "Sec 1": 2 } }, { subject: "Music", code: "MU", tag: "-", dept: "AE", periods: { "Sec 1": 2 } }],
  teachers: [{ _id: "ta", name: "Arjun Nair", dept: "MA", can_teach: [{ subject: "Mathematics G3", levels: "All" }] }],
  blocks: [{ _id: "b1", block: "Sec 1 Mathematics", level: "Sec 1", classes: ["1A", "1B"] }, { _id: "b2", block: "Sec 1 Option A", level: "Sec 1", classes: ["1A", "1B", "1C"], everyone: false }],
  lessons: [{ _id: "l1", level: "Sec 1", subject: "Mathematics G3", block: "Sec 1 Mathematics", classes: ["1A", "1B"], teachers: ["Arjun Nair"], students: 30 },
            { _id: "l2", level: "Sec 1", subject: "Mathematics G3", block: "Sec 1 Option A", classes: ["1A", "1B", "1C"], teachers: [], students: 20 },
            { _id: "l3", level: "Sec 1", subject: "Mathematics G2", block: "Sec 1 Mathematics", classes: ["1A", "1B"], teachers: [], students: 32 },
            { _id: "l4", level: "Sec 1", subject: "Art", block: null, classes: ["1A", "1B"], teachers: [], students: 62 },
            { _id: "l5", level: "Sec 1", subject: "Art", block: null, classes: ["1C"], teachers: [], students: 31 },
            { _id: "l6", level: "Sec 1", subject: "Music", block: null, classes: ["1C"], teachers: [], students: 9, code_override: "1MU1" },
            { _id: "l7", level: "Sec 1", subject: "", block: null, classes: [], teachers: [] }],
  rules: [], students: [{ id: "s1", name: "Student One", class: "1A", groups: ["1MAP1"] }, { id: "s2", name: "Student Two", class: "1B", groups: ["1MAP2", "1MAA1"] }, { id: "s3", name: "Student Three", class: "1C", groups: [] }], roles: [] });

t("untag strips the level-of-study tag", () => {
  assert.strictEqual(Groups.untag("English Language G3"), "English Language"); assert.strictEqual(Groups.untag("Mathematics Fdn "), "Mathematics");
  assert.strictEqual(Groups.untag("Art"), "Art");
});
t("a band's suggested name: one family, several families, letters and numbers already taken", () => {
  assert.strictEqual(Groups.bandName("Sec 2", ["Mathematics G3", "Mathematics G2"], []), "Sec 2 Mathematics");
  assert.strictEqual(Groups.bandName("Sec 3", ["Geography", "Literature in English"], []), "Sec 3 Option A");
  assert.strictEqual(Groups.bandName("Sec 3", ["Geography", "Literature in English"], ["sec 3 option a ", "Sec 3 Option B"]), "Sec 3 Option C");
  assert.strictEqual(Groups.bandName("Sec 1", ["Mathematics G3"], ["Sec 1 Mathematics"]), "Sec 1 Mathematics 2");
  assert.strictEqual(Groups.bandName("Sec 1", [], []), "Sec 1 Band");
});
t("codes: as the table numbers them, per level and subject in row order", () => {
  assert.deepStrictEqual(Groups.codes(fixture()), ["1MAP1", "1MAP2", "1MAA1", "Entire Class", "Entire Class", "1MU1", ""]);
});
t("the code a new row would get", () => {
  assert.strictEqual(Groups.codeFor(fixture(), "Sec 1", "Mathematics G3", "Sec 1 Option A"), "1MAP3");
  assert.strictEqual(Groups.codeFor(fixture(), "Sec 1", "English Language G3", "Sec 1 Option A"), "1ELP1");
  assert.strictEqual(Groups.codeFor(fixture(), "Sec 1", "Art", null), "Entire Class");
  assert.strictEqual(Groups.codeFor(fixture(), "", "Art", "Sec 1 Option A"), "");
});
console.log(`${n} cases passed`);

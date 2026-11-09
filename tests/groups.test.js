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
t("a new group: fields, the band's classes by default, and refusals", () => {
  const s = fixture(); const r = Groups.newGroup(s, { level: "Sec 1", subject: "Mathematics G3", block: "Sec 1 Option A", classes: [], students: "18" });
  assert.deepStrictEqual(r, { i: 7 }); assert.deepStrictEqual(s.lessons[7], { level: "Sec 1", subject: "Mathematics G3", block: "Sec 1 Option A", classes: ["1A", "1B", "1C"], teachers: [], students: 18 });
  assert.deepStrictEqual(Groups.newGroup(s, { level: "", subject: "Art" }), { error: "Pick a level and a subject." });
  assert.deepStrictEqual(Groups.newGroup(s, { level: "Sec 2", subject: "Mathematics G3", block: "Sec 1 Mathematics", classes: ["2A"] }), { error: "Sec 1 Mathematics is a Sec 1 band, not Sec 2." });
  assert.deepStrictEqual(Groups.newGroup(s, { level: "Sec 1", subject: "Art", block: "Nope", classes: ["1A"] }), { error: "There is no band called Nope." });
  assert.deepStrictEqual(Groups.newGroup(s, { level: "Sec 1", subject: "Art", block: "", classes: [] }), { error: "Pick the classes." });
  assert.strictEqual(s.lessons.length, 8);
});
t("one row per class, skipping classes that have the subject already", () => {
  const s = fixture(); assert.strictEqual(Groups.addOnePerClass(s, "Sec 1", "Art", ["1A", "1B", "1C"]), 0);
  assert.strictEqual(Groups.addOnePerClass(s, "Sec 1", "Music", ["1A", "1B", "1C"]), 3);
  assert.deepStrictEqual(s.lessons.slice(7).map(x => [x.classes, x.students, x.block]), [[["1A"], 30, null], [["1B"], 32, null], [["1C"], 31, null]]);
});
t("a new band: name, duplicates, level and classes", () => {
  const s = fixture(); assert.deepStrictEqual(Groups.newBand(s, { block: " Sec 1 English ", level: "Sec 1", classes: ["1A", "1B", "1C"], everyone: true }), { i: 2 });
  assert.deepStrictEqual(s.blocks[2], { block: "Sec 1 English", level: "Sec 1", classes: ["1A", "1B", "1C"], everyone: true });
  assert.deepStrictEqual(Groups.newBand(s, { block: "sec 1  mathematics", level: "Sec 1", classes: ["1A"] }), { error: "Sec 1 Mathematics exists already." });
  assert.deepStrictEqual(Groups.newBand(s, { block: "", level: "Sec 1", classes: ["1A"] }), { error: "Give the band a name." });
  assert.deepStrictEqual(Groups.newBand(s, { block: "Sec 1 Science", level: "", classes: ["1A"] }), { error: "Pick a level." });
  assert.deepStrictEqual(Groups.newBand(s, { block: "Sec 1 Science", level: "Sec 1", classes: [] }), { error: "Pick the band's classes." });
  assert.strictEqual(s.blocks.length, 3);
});
t("into a band: whole classes become groups, the band's classes widen, other levels are skipped", () => {
  const s = fixture(); s.lessons.push({ _id: "l8", level: "Sec 2", subject: "Mathematics G3", block: null, classes: ["2A"], teachers: [], students: 30 });
  const r = Groups.toBand(s, [3, 4, 7], "Sec 1 Mathematics");
  assert.deepStrictEqual(r, { moved: 2, skipped: 1, widened: ["1C"] });
  assert.deepStrictEqual([s.lessons[3].block, s.lessons[4].block, s.lessons[7].block], ["Sec 1 Mathematics", "Sec 1 Mathematics", null]);
  assert.deepStrictEqual(s.blocks[0].classes, ["1A", "1B", "1C"]); assert.deepStrictEqual(s.lessons[3].classes, ["1A", "1B"]);   // the shared row is one group of two classes
  assert.deepStrictEqual(Groups.codes(s).slice(3, 5), ["1AR1", "1AR2"]);
});
t("out of a band, and what moving renumbers", () => {
  const s = fixture(); assert.strictEqual(Groups.fromBand(s, 3), false);
  const r = Groups.shift(s, c => Groups.fromBand(c, 0));
  assert.deepStrictEqual(r, { changes: [["l1", "1MAP1", "Entire Class"], ["l2", "1MAP2", "1MAP1"]], students: 2 });
  assert.strictEqual(s.lessons[0].block, "Sec 1 Mathematics");   // the real setup is untouched
  assert.strictEqual(Groups.fromBand(s, 0), true); assert.strictEqual(s.lessons[0].block, null);
  assert.deepStrictEqual(Groups.shift(s, c => Groups.toBand(c, [4], "Sec 1 Mathematics")), { changes: [["l5", "Entire Class", "1AR1"]], students: 0 });
});
t("lanes: each band of the level with its groups and anyone on two of them", () => {
  const s = fixture(); s.lessons[1].teachers = ["Arjun Nair"];
  const L = Groups.lanes(s, "Sec 1");
  assert.deepStrictEqual(L.map(l => [l.block, l.groups.map(g => g.code), l.twice]), [["Sec 1 Mathematics", ["1MAP1", "1MAA1"], []], ["Sec 1 Option A", ["1MAP2"], []]]);
  s.lessons[2].teachers = ["Arjun Nair"]; assert.deepStrictEqual(Groups.lanes(s, "Sec 1")[0].twice, ["Arjun Nair"]);
  assert.deepStrictEqual(Groups.lanes(s, "Sec 2"), []); assert.strictEqual(Groups.lanes(s, "").length, 2);
});
t("the pool: unbanded rows of the level, by subject", () => {
  assert.deepStrictEqual(Groups.pool(fixture(), "Sec 1", "").map(p => [p.li, p.kind, p.code, p.title]), [[3, "class", "Entire Class", "1A, 1B · Art"], [4, "class", "Entire Class", "1C · Art"], [5, "group", "1MU1", "1C · Music"]]);
  assert.deepStrictEqual(Groups.pool(fixture(), "Sec 1", "Music").map(p => p.li), [5]); assert.deepStrictEqual(Groups.pool(fixture(), "Sec 2", ""), []);
});
console.log(`${n} cases passed`);

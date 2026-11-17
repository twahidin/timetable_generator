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
  assert.deepStrictEqual(r, { changes: [["l1", "1MAP1", "Entire Class"], ["l2", "1MAP2", "1MAP1"]], students: 2, rules: 0 });
  assert.strictEqual(s.lessons[0].block, "Sec 1 Mathematics");   // the real setup is untouched
  assert.strictEqual(Groups.fromBand(s, 0), true); assert.strictEqual(s.lessons[0].block, null);
  assert.deepStrictEqual(Groups.shift(s, c => Groups.toBand(c, [4], "Sec 1 Mathematics")), { changes: [["l5", "Entire Class", "1AR1"]], students: 0, rules: 0 });
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
t("a banded row with a kept code still takes a number, as the table counts it", () => {
  const s = fixture(); s.lessons[1].code_override = "1MAX9";
  assert.deepStrictEqual(Groups.codes(s).slice(0, 3), ["1MAP1", "1MAX9", "1MAA1"]);
  assert.strictEqual(Groups.codeFor(s, "Sec 1", "Mathematics G3", "Sec 1 Option A"), "1MAP3");
});
t("a kept code is dropped when its group joins a band, and the move says so", () => {
  const s = fixture(); const r = Groups.shift(s, c => Groups.toBand(c, [5], "Sec 1 Option A"));
  assert.deepStrictEqual(r.changes, [["l6", "1MU1", "1MU1"]].filter(() => false).concat([]));   // same code, so no change listed
  Groups.toBand(s, [5], "Sec 1 Option A"); assert.ok(!("code_override" in s.lessons[5])); assert.strictEqual(Groups.codes(s)[5], "1MU1");
  s.lessons[5].code_override = undefined; s.lessons[5].block = null; s.lessons[5].code_override = "1MUZ";
  const r2 = Groups.shift(s, c => Groups.toBand(c, [5], "Sec 1 Option A")); assert.deepStrictEqual(r2.changes, [["l6", "1MUZ", "1MU1"]]);
});
t("the code of a pull-out group with no band: the next free number, as Keep code does", () => {
  const s = fixture(); assert.strictEqual(Groups.codeFor(s, "Sec 1", "Music", "", 9, ["1C"]), "1MU2");
  assert.strictEqual(Groups.codeFor(s, "Sec 1", "Music", "", 31, ["1C"]), "Entire Class");
  assert.strictEqual(Groups.pullOutCode(s, 4), null);   // Art for all 31 of 1C: whole class
  s.lessons[4].students = 9; assert.strictEqual(Groups.pullOutCode(s, 4), "1AR1"); assert.strictEqual(s.lessons[4].code_override, "1AR1");
  assert.strictEqual(Groups.pullOutCode(s, 4), null);   // it has its code now
});
t("a new band stores Everyone takes one only when it was chosen", () => {
  const s = fixture(); Groups.newBand(s, { block: "Sec 1 Science", level: "Sec 1", classes: ["1A"] });
  assert.ok(!("everyone" in s.blocks[2]));
  Groups.newBand(s, { block: "Sec 1 Elective", level: "Sec 1", classes: ["1A"], everyone: false }); assert.strictEqual(s.blocks[3].everyone, false);
});
t("shift counts the Group rules that name a code about to change", () => {
  const s = fixture(); s.rules = [{ scope: "Group", target: "1MAP2", rule: "Fixed at" }, { scope: "Class", target: "1A", rule: "Fixed at" }];
  assert.deepStrictEqual(Groups.shift(s, c => Groups.fromBand(c, 0)).rules, 1);
  assert.deepStrictEqual(Groups.shift(s, c => Groups.fromBand(c, 2)).rules, 0);
});
t("the pool: every row says its level and who teaches it", () => {
  const s = fixture(); s.lessons[3].teachers = ["Arjun Nair", ""];
  assert.deepStrictEqual(Groups.pool(s, "Sec 1", "").map(p => [p.li, p.level, p.teachers]), [[3, "Sec 1", ["Arjun Nair"]], [4, "Sec 1", []], [5, "Sec 1", []]]);
});
const wide = () => { const s = fixture();   // a second teacher the setup does not list, a Sec 2 row, a Sec 2 band with no groups
  s.teachers.push({ _id: "tb", name: "Bala Menon", dept: "AE" });
  s.lessons[3].teachers = ["Bala Menon"]; s.lessons[5].teachers = ["Visiting Coach"];
  s.lessons.push({ _id: "l8", level: "Sec 2", subject: "Mathematics G3", block: null, classes: ["2A"], teachers: ["Arjun Nair"], students: 30 });
  s.blocks.push({ _id: "b3", block: "Sec 2 Option A", level: "Sec 2", classes: ["2A"], everyone: false });
  return s; };
t("view: with no filter, every row and every band of the level, and what the filter can offer", () => {
  const v = Groups.view(wide(), { level: "Sec 1", subject: "", teacher: "" });
  assert.deepStrictEqual(v.pool.map(p => p.li), [3, 4, 5]);
  assert.deepStrictEqual(v.lanes.map(l => [l.block, l.groups.map(g => g.match)]), [["Sec 1 Mathematics", [true, true]], ["Sec 1 Option A", [true]]]);
  assert.deepStrictEqual(v.subjects, ["Mathematics G3", "Mathematics G2", "Art", "Music"]);   // the setup's order
  assert.deepStrictEqual(v.teachers, ["Arjun Nair", "Bala Menon", "Visiting Coach"]);   // the setup's teachers first, then a name only a row carries
  assert.strictEqual(v.none, true); assert.deepStrictEqual(v.f, { level: "Sec 1", subject: "", teacher: "", band: "" });
  assert.strictEqual(v.filtered, false);
});
t("view: all levels", () => {
  const v = Groups.view(wide(), { level: "", subject: "", teacher: "" });
  assert.deepStrictEqual(v.pool.map(p => [p.li, p.level]), [[3, "Sec 1"], [4, "Sec 1"], [5, "Sec 1"], [7, "Sec 2"]]);
  assert.deepStrictEqual(v.lanes.map(l => [l.block, l.level]), [["Sec 1 Mathematics", "Sec 1"], ["Sec 1 Option A", "Sec 1"], ["Sec 2 Option A", "Sec 2"]]);   // a band with no groups is shown while nothing is filtered
});
t("view: one teacher's groups, in and out of bands; a band is shown whole and says which groups match", () => {
  const v = Groups.view(wide(), { level: "", subject: "", teacher: "Arjun Nair" });
  assert.deepStrictEqual(v.pool.map(p => p.li), [7]);
  assert.deepStrictEqual(v.lanes.map(l => [l.block, l.groups.map(g => [g.code, g.match])]), [["Sec 1 Mathematics", [["1MAP1", true], ["1MAA1", false]]]]);
  assert.strictEqual(v.filtered, true);
});
t("view: the rows with no teacher", () => {
  const v = Groups.view(wide(), { level: "Sec 1", subject: "", teacher: Groups.NONE });
  assert.deepStrictEqual(v.pool.map(p => p.li), [4]);
  assert.deepStrictEqual(v.lanes.map(l => [l.block, l.groups.map(g => g.match)]), [["Sec 1 Mathematics", [false, true]], ["Sec 1 Option A", [true]]]);
  const s = wide(); s.lessons.forEach(x => { if (x.subject && !x.teachers.length) x.teachers = ["Arjun Nair"]; });
  const w = Groups.view(s, { level: "", subject: "", teacher: Groups.NONE });   // nobody is without a teacher: the choice is not offered and counts as all
  assert.strictEqual(w.none, false); assert.strictEqual(w.f.teacher, ""); assert.strictEqual(w.pool.length, 4);
});
t("view: one subject, with a teacher too; a band with no group that matches is not shown", () => {
  const v = Groups.view(wide(), { level: "Sec 1", subject: "Art", teacher: "" });
  assert.deepStrictEqual(v.pool.map(p => p.li), [3, 4]); assert.deepStrictEqual(v.lanes, []);
  const w = Groups.view(wide(), { level: "", subject: "Mathematics G3", teacher: "Arjun Nair" });
  assert.deepStrictEqual(w.pool.map(p => p.li), [7]); assert.deepStrictEqual(w.lanes.map(l => l.block), ["Sec 1 Mathematics"]);
  assert.deepStrictEqual(w.lanes[0].groups.map(g => g.match), [true, false]);
});
t("view: a subject or a teacher that is not at the level shown counts as all, and the view says what it used", () => {
  const v = Groups.view(wide(), { level: "Sec 2", subject: "Art", teacher: "Bala Menon" });
  assert.deepStrictEqual(v.f, { level: "Sec 2", subject: "", teacher: "", band: "" }); assert.deepStrictEqual(v.pool.map(p => p.li), [7]);
  assert.deepStrictEqual(v.subjects, ["Mathematics G3"]); assert.deepStrictEqual(v.teachers, ["Arjun Nair"]); assert.strictEqual(v.filtered, false);
  const w = Groups.view(wide(), { level: "Sec 9" });   // a level the school does not have, and nothing else said
  assert.deepStrictEqual([w.pool, w.lanes, w.subjects, w.teachers, w.none], [[], [], [], [], false]);
  const e = Groups.view({}, {}); assert.deepStrictEqual([e.pool, e.lanes], [[], []]);
});
t("view: a name the setup lists twice is offered once; a teacher whose name is a dash is a teacher, not \"No teacher\"", () => {
  const s = wide(); s.subjects.push({ subject: "Art", code: "AR2", tag: "-", dept: "AE", periods: { "Sec 1": 2 } }); s.teachers.push({ _id: "tc", name: "Bala Menon", dept: "MA" });
  s.lessons[4].teachers = ["-"];
  const v = Groups.view(s, { level: "Sec 1", subject: "", teacher: "-" });
  assert.deepStrictEqual(v.subjects, ["Mathematics G3", "Mathematics G2", "Art", "Music"]); assert.deepStrictEqual(v.teachers, ["Arjun Nair", "Bala Menon", "-", "Visiting Coach"]);   // the two the setup does not list, as the rows have them
  assert.deepStrictEqual(v.pool.map(p => p.li), [4]); assert.strictEqual(v.f.teacher, "-"); assert.notStrictEqual(Groups.NONE, "-");
});
t("view: one band alone; the rows not in a band are as the other choices say", () => {
  const v = Groups.view(wide(), { level: "Sec 1", subject: "", teacher: "", band: "Sec 1 Option A" });
  assert.deepStrictEqual(v.bands, ["Sec 1 Mathematics", "Sec 1 Option A"]); assert.strictEqual(v.f.band, "Sec 1 Option A");
  assert.deepStrictEqual(v.lanes.map(l => [l.block, l.groups.map(g => g.match)]), [["Sec 1 Option A", [true]]]); assert.deepStrictEqual(v.pool.map(p => p.li), [3, 4, 5]);
  assert.strictEqual(v.filtered, false);   // a band alone does not fade a group
  const w = Groups.view(wide(), { level: "Sec 1", subject: "", teacher: "Arjun Nair", band: "Sec 1 Option A" });   // nobody of that name in that band
  assert.deepStrictEqual(w.lanes, []); assert.strictEqual(w.f.band, "Sec 1 Option A");
  const x = Groups.view(wide(), { level: "Sec 2", band: "Sec 1 Option A" });   // not a band of the level shown: counts as all
  assert.strictEqual(x.f.band, ""); assert.deepStrictEqual(x.lanes.map(l => l.block), ["Sec 2 Option A"]); assert.deepStrictEqual(x.bands, ["Sec 2 Option A"]);
});
t("dropRow: a row is deleted, in a band or not", () => {
  const s = fixture(); assert.deepStrictEqual(Groups.dropRow(s, 3), { subject: "Art", classes: ["1A", "1B"], block: null, code: "Entire Class" });
  assert.deepStrictEqual(s.lessons.map(x => x._id), ["l1", "l2", "l3", "l5", "l6", "l7"]);
  assert.deepStrictEqual(Groups.dropRow(s, 0), { subject: "Mathematics G3", classes: ["1A", "1B"], block: "Sec 1 Mathematics", code: "1MAP1" });
  assert.strictEqual(Groups.dropRow(s, 99), null); assert.strictEqual(Groups.dropRow({}, 0), null); assert.strictEqual(s.lessons.length, 5);
});
t("shift: a deleted row's code counts as changed, with the codes that renumber after it", () => {
  const s = fixture(); s.rules = [{ scope: "Group", target: "1MAP1", rule: "Fixed at" }];
  assert.deepStrictEqual(Groups.shift(s, c => Groups.dropRow(c, 0)), { changes: [["l2", "1MAP2", "1MAP1"], ["l1", "1MAP1", null]], students: 2, rules: 1 });
  assert.deepStrictEqual(Groups.shift(s, c => Groups.dropRow(c, 3)), { changes: [], students: 0, rules: 0 });   // a whole-class row has no code to lose
});
t("dropBand: the band goes; its groups go with it, or stay as rows not in a band", () => {
  const s = fixture(); s.rules = [{ scope: "Block", target: "Sec 1 Mathematics", rule: "Fixed at" }, { scope: "Block", target: "Sec 1 Option A", rule: "Fixed at" }, { scope: "Class", target: "Sec 1 Mathematics", rule: "Fixed at" }];
  assert.strictEqual(Groups.bandRules(s, "Sec 1 Mathematics"), 1); assert.strictEqual(Groups.bandRules(s, "No such band"), 0);
  assert.deepStrictEqual(Groups.dropBand(s, "Sec 1 Mathematics", true), { groups: 2, kept: 2 });   // 30 and 32 of the 62 in 1A and 1B: each a group of its own, with a kept code
  assert.deepStrictEqual(s.blocks.map(b => b.block), ["Sec 1 Option A"]);
  assert.deepStrictEqual(s.lessons.slice(0, 3).map(x => [x._id, x.block, !!x.code_override]), [["l1", null, true], ["l2", "Sec 1 Option A", false], ["l3", null, true]]);
  assert.deepStrictEqual([s.lessons[0].code_override, s.lessons[2].code_override], ["1MAP2", "1MAA1"]);   // 1MAA1 is kept; 1MAP1 is now the other band's group, so the first free one
  const k = fixture(); k.lessons[1].block = null;   // no other band has the subject: every kept group keeps the code it had
  Groups.dropBand(k, "Sec 1 Mathematics", true); assert.deepStrictEqual([k.lessons[0].code_override, k.lessons[2].code_override], ["1MAP1", "1MAA1"]);
  assert.deepStrictEqual(Groups.shift(fixture(), c => { c.lessons[1].block = null; }).changes.length, 1);
  const k2 = fixture(); k2.lessons[1].block = null; assert.deepStrictEqual(Groups.shift(k2, c => Groups.dropBand(c, "Sec 1 Mathematics", true)).changes, []);   // so nothing is renumbered
  const d = fixture(); assert.deepStrictEqual(Groups.dropBand(d, "Sec 1 Mathematics", false), { groups: 2, kept: 0 });
  assert.deepStrictEqual(d.lessons.map(x => x._id), ["l2", "l4", "l5", "l6", "l7"]); assert.deepStrictEqual(d.blocks.map(b => b.block), ["Sec 1 Option A"]);
  assert.strictEqual(Groups.dropBand(d, "No such band", true), null); assert.strictEqual(Groups.dropBand({}, "x", false), null);
  const e = fixture(); e.blocks.push({ _id: "b9", block: "Sec 1 Empty", level: "Sec 1", classes: ["1A"] });
  assert.deepStrictEqual(Groups.dropBand(e, "Sec 1 Empty", false), { groups: 0, kept: 0 }); assert.strictEqual(e.blocks.length, 2); assert.strictEqual(e.lessons.length, 7);
});
console.log(`${n} cases passed`);

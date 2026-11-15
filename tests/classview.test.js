const assert = require("assert");
const ClassView = require("../static/classview.js");
let n = 0; const t = (name, f) => { f(); n++; };
const W = (subject, cls) => ({ level: "Sec 3", subject, classes: [cls], students: 40 });
const fixture = () => ({
  school: { levels: ["Sec 1", "Sec 3"], departments: ["EL", "MA", "HU", "PE"], tags: [["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]], parents_max: 4 },
  classes: [{ class: "3A", level: "Sec 3", size: 40, home_room: "B3-1", parents: ["Arjun Nair", "Mei Tan"] }, { class: "3B", level: "Sec 3", size: 38, home_room: "B3-2" },
            { class: "3C", level: "Sec 3", size: 39 }, { class: "3D", level: "Sec 3", size: 37 }, { class: "1A", level: "Sec 1", size: 40 }],
  subjects: [{ subject: "English Language G3", code: "EL", tag: "G3", dept: "EL" }, { subject: "Mathematics G3", code: "MA", tag: "G3", dept: "MA" }, { subject: "Mathematics G2", code: "MA", tag: "G2", dept: "MA" },
             { subject: "Geography G3", code: "GE", tag: "G3", dept: "HU" }, { subject: "History G3", code: "HI", tag: "G3", dept: "HU" }, { subject: "Physical Education", code: "PE", tag: "-", dept: "PE" }],
  teachers: [{ name: "Arjun Nair", short: "Arjun" }, { name: "Mei Tan", short: "Mei" }],
  blocks: [{ block: "Sec 3 Mathematics", level: "Sec 3", classes: ["3A", "3B", "3C", "3D"] }, { block: "Sec 3 Option A", level: "Sec 3", classes: ["3A", "3B"] }, { block: "Sec 3 Option B", level: "Sec 3", classes: ["3C", "3D"] }],
  lessons: [W("Physical Education", "3A"), W("Physical Education", "3B"), W("Physical Education", "3C"), W("Physical Education", "3D"),
            W("English Language G3", "3A"), W("English Language G3", "3B"), W("English Language G3", "3C"), W("English Language G3", "3D"),
            { level: "Sec 3", subject: "Mathematics G3", block: "Sec 3 Mathematics", classes: ["3A", "3B", "3C", "3D"], students: 30 },   // 3MAP1
            { level: "Sec 3", subject: "Mathematics G3", block: "Sec 3 Mathematics", classes: ["3A", "3B", "3C", "3D"], students: 30 },   // 3MAP2
            { level: "Sec 3", subject: "Mathematics G2", block: "Sec 3 Mathematics", classes: ["3A", "3B", "3C", "3D"], students: 24 },   // 3MAA1
            { level: "Sec 3", subject: "Geography G3", block: "Sec 3 Option A", classes: ["3A", "3B"], students: 38 },                    // 3GEP1
            { level: "Sec 3", subject: "History G3", block: "Sec 3 Option A", classes: ["3A", "3B"], students: 37 },                      // 3HIP1
            { level: "Sec 3", subject: "Geography G3", block: "Sec 3 Option B", classes: ["3C", "3D"], students: 41 },                    // 3GEP2
            { level: "Sec 3", subject: "History G3", block: "Sec 3 Option B", classes: ["3C", "3D"], students: 33 },                      // 3HIP2
            { level: "Sec 1", subject: "English Language G3", classes: ["1A"], students: 40 }],
  students: [{ id: "S1", name: "Student One", class: "3A", groups: ["3MAP1", "3GEP1"] }, { id: "S2", name: "Student Two", class: "3A", groups: ["3MAP1", "3HIP1"] },
             { id: "S3", name: "Student Three", class: "3A", groups: ["3MAA1", "3GEP1"] }]
});

t("levels_in_the_schools_order_with_their_sums", () => {
  const L = ClassView.cards(fixture());
  assert.deepStrictEqual(L.map(x => [x.level, x.planned, x.real, x.cards.length]), [["Sec 1", 40, null, 1], ["Sec 3", 154, 3, 4]]);
  assert.deepStrictEqual(ClassView.levels(fixture()), ["Sec 1", "Sec 3"]);
});
t("a_card_has_the_class_its_room_its_parents_and_its_index", () => {
  const c = ClassView.cards(fixture())[1].cards[0];
  assert.deepStrictEqual([c.ci, c.class, c.planned, c.real, c.home_room, c.parents], [0, "3A", 40, 3, "B3-1", ["Arjun Nair", "Mei Tan"]]);
});
t("whole_subjects_first_then_the_rest_each_in_step_3_order", () => {
  const c = ClassView.cards(fixture())[1].cards[0];
  assert.deepStrictEqual(c.subjects.map(s => [s.subject, s.whole]), [["English Language G3", true], ["Physical Education", true],
    ["Mathematics G3", false], ["Mathematics G2", false], ["Geography G3", false], ["History G3", false]]);
});
t("a_part_subject_counts_this_classs_students_once_each", () => {
  const c = ClassView.cards(fixture())[1].cards[0], by = Object.fromEntries(c.subjects.map(s => [s.subject, s.count]));
  assert.deepStrictEqual(by, { "English Language G3": null, "Physical Education": null, "Mathematics G3": 2, "Mathematics G2": 1, "Geography G3": 2, "History G3": 1 });
  const s = fixture(); s.students[0].groups.push("3MAP2");            // one student in two groups of the same subject is still one
  assert.strictEqual(ClassView.cards(s)[1].cards[0].subjects.find(x => x.subject === "Mathematics G3").count, 2);
});
t("counts_only_where_the_list_has_the_class", () => {
  const b = ClassView.cards(fixture())[1].cards[1];
  assert.strictEqual(b.real, null); assert.ok(b.subjects.length === 6 && b.subjects.every(s => s.count === null));
  const s = fixture(); s.students = [];
  assert.ok(ClassView.cards(s).every(l => l.real === null && l.cards.every(c => c.real === null)));
  delete s.students; assert.strictEqual(ClassView.cards(s)[1].cards[0].real, null);
});
t("a_kept_code_counts_as_part_of_the_class", () => {
  const s = fixture(); s.lessons.push({ level: "Sec 3", subject: "History G3", classes: ["3A"], students: 6, code_override: "3HI-X" }); s.students[2].groups.push("3HI-X");
  const h = ClassView.cards(s)[1].cards[0].subjects.find(x => x.subject === "History G3");
  assert.deepStrictEqual([h.whole, h.count], [false, 2]);
});
t("untidy_rows_do_not_throw", () => {
  const s = fixture();
  s.lessons.push(null, { level: "Sec 3", subject: "Art", classes: ["9Z"] }, { level: "Sec 3", subject: "Art" }, { level: "Sec 3", classes: ["3A"] }, { level: "Sec 3", subject: "Art", classes: ["3A"] });
  s.classes.push(null, { class: "X1" }, { class: "5A", level: "Sec 5", size: "" }); s.students.push(null, { id: "S9", class: "9Z" }, { id: "S8", class: "3A" });
  const L = ClassView.cards(s);
  assert.deepStrictEqual(L.map(x => x.level), ["Sec 1", "Sec 3", "Sec 5", ""]);
  const a = L[1].cards[0]; assert.strictEqual(a.real, 4); assert.deepStrictEqual(a.subjects[2], { subject: "Art", whole: true, count: null });   // not on step 3: after the other whole subjects, before the part ones
  assert.deepStrictEqual([L[2].cards[0].planned, L[3].cards[0].class, L[3].cards[0].subjects], [null, "X1", []]);
  assert.deepStrictEqual(ClassView.cards({}), []); assert.deepStrictEqual(ClassView.levels({}), []);
});
const cellKinds = r => r.cells.map(c => c ? c.kind : null);
t("whole_class_subjects_are_cells_and_a_one_subject_band_is_a_bar_on_its_row", () => {
  const B = ClassView.bands(fixture(), "Sec 3");
  assert.deepStrictEqual(B.classes, ["3A", "3B", "3C", "3D"]);
  assert.deepStrictEqual(B.rows.map(r => r.label), ["English Language", "Mathematics", "Physical Education", "Sec 3 Option A", "Sec 3 Option B"]);
  assert.deepStrictEqual(cellKinds(B.rows[0]), ["whole", "whole", "whole", "whole"]); assert.deepStrictEqual(B.rows[0].bars, []);
  const m = B.rows[1]; assert.deepStrictEqual(cellKinds(m), [null, null, null, null]);
  assert.deepStrictEqual(m.bars.map(b => [b.block, b.bi, b.classes, b.spans]), [["Sec 3 Mathematics", 0, ["3A", "3B", "3C", "3D"], [[0, 4]]]]);
  assert.deepStrictEqual(m.bars[0].groups, [{ code: "3MAP1", subject: "Mathematics G3", students: 30 }, { code: "3MAP2", subject: "Mathematics G3", students: 30 }, { code: "3MAA1", subject: "Mathematics G2", students: 24 }]);
});
t("a_band_of_several_subjects_has_a_row_named_as_the_band", () => {
  const B = ClassView.bands(fixture(), "Sec 3"), a = B.rows[3], b = B.rows[4];
  assert.deepStrictEqual([a.label, a.bars[0].spans, a.bars[0].groups.map(g => g.code)], ["Sec 3 Option A", [[0, 2]], ["3GEP1", "3HIP1"]]);
  assert.deepStrictEqual([b.label, b.bars[0].spans, cellKinds(b)], ["Sec 3 Option B", [[2, 2]], [null, null, null, null]]);
});
t("one_subject_bands_on_different_classes_share_a_row", () => {
  const s = fixture(); s.blocks[0].classes = ["3A", "3B"]; s.blocks.push({ block: "Sec 3 Mathematics 2", level: "Sec 3", classes: ["3C", "3D"] });
  s.lessons.push({ level: "Sec 3", subject: "Mathematics G3", block: "Sec 3 Mathematics 2", classes: ["3C", "3D"], students: 28 });
  const m = ClassView.bands(s, "Sec 3").rows.filter(r => r.label === "Mathematics");
  assert.strictEqual(m.length, 1); assert.deepStrictEqual(m[0].bars.map(b => [b.block, b.spans]), [["Sec 3 Mathematics", [[0, 2]]], ["Sec 3 Mathematics 2", [[2, 2]]]]);
});
t("bands_sharing_a_class_take_rows_of_their_own", () => {
  const s = fixture(); s.blocks.push({ block: "Sec 3 Mathematics 2", level: "Sec 3", classes: ["3A", "3D"] });
  s.lessons.push({ level: "Sec 3", subject: "Mathematics G1", block: "Sec 3 Mathematics 2", classes: ["3A", "3D"], students: 12 });
  const rows = ClassView.bands(s, "Sec 3").rows, at = rows.map(r => r.label);
  assert.deepStrictEqual(at.slice(0, 4), ["English Language", "Mathematics", "Mathematics", "Physical Education"]);   // the new row sits straight after the first
  assert.deepStrictEqual(rows[2].bars.map(b => [b.block, b.spans]), [["Sec 3 Mathematics 2", [[0, 1], [3, 1]]]]);
});
t("a_bar_is_cut_where_its_classes_are_apart", () => {
  const s = fixture(); s.blocks[1].classes = ["3A", "3C", "3D"];
  assert.deepStrictEqual(ClassView.bands(s, "Sec 3").rows.find(r => r.label === "Sec 3 Option A").bars[0].spans, [[0, 1], [2, 2]]);
});
t("a_class_taking_a_subject_whole_beside_a_band_of_it", () => {
  const s = fixture(); s.blocks[0].classes = ["3A", "3B", "3C"]; s.lessons.forEach(x => { if (x.block === "Sec 3 Mathematics") x.classes = ["3A", "3B", "3C"]; });
  s.lessons.push({ level: "Sec 3", subject: "Mathematics G3", classes: ["3D"], students: 37 });
  const m = ClassView.bands(s, "Sec 3").rows.filter(r => r.label === "Mathematics");
  assert.strictEqual(m.length, 1); assert.deepStrictEqual(cellKinds(m[0]), [null, null, null, "whole"]); assert.deepStrictEqual(m[0].bars[0].spans, [[0, 3]]);
});
t("a_kept_code_with_no_band_is_a_part_cell_and_whole_wins", () => {
  const s = fixture(); s.lessons.push({ level: "Sec 3", subject: "History G3", classes: ["3A", "3B"], students: 6, code_override: "3HI-X" }, { level: "Sec 3", subject: "English Language G2", classes: ["3A"], students: 5, code_override: "3EL-X" });
  const rows = ClassView.bands(s, "Sec 3").rows, h = rows.find(r => r.label === "History");
  assert.deepStrictEqual(h.cells, [{ kind: "part", code: "3HI-X" }, { kind: "part", code: "3HI-X" }, null, null]);
  assert.deepStrictEqual(cellKinds(rows.find(r => r.label === "English Language")), ["whole", "whole", "whole", "whole"]);
});
t("untidy_bands_do_not_throw", () => {
  const s = fixture();
  s.blocks.push(null, { block: "Sec 3 Empty", level: "Sec 3", classes: ["3A"] }, { block: "Sec 3 Stray", level: "Sec 3", classes: ["1A", "9Z"] }, { block: "Sec 3 Unlisted", level: "Sec 3" });
  s.lessons.push({ level: "Sec 3", subject: "Art", block: "Sec 3 Stray", classes: ["1A"], students: 9 }, { level: "Sec 3", subject: "Art", block: "Sec 3 Unlisted", classes: ["3B", "3C"] });
  const B = ClassView.bands(s, "Sec 3"), by = Object.fromEntries(B.rows.map(r => [r.label, r]));
  assert.deepStrictEqual(by["Sec 3 Empty"].bars[0].groups, []); assert.ok(!("Sec 3 Stray" in by));               // no class of this level: not drawn
  assert.deepStrictEqual([by["Art"].bars[0].classes, by["Art"].bars[0].groups[0].students], [["3B", "3C"], null]);   // listed no classes: its groups' classes
  assert.deepStrictEqual(ClassView.bands(s, "Sec 9"), { level: "Sec 9", classes: [], rows: [] });
  assert.deepStrictEqual(ClassView.bands({}, "Sec 1"), { level: "Sec 1", classes: [], rows: [] });
});
t("a_school_sized_setup_is_quick", () => {
  const s = { school: { levels: ["Sec 1", "Sec 2", "Sec 3", "Sec 4"], tags: [["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]] }, classes: [], subjects: [], blocks: [], lessons: [], students: [] };
  for (let k = 0; k < 34; k++) ["G3", "G2", "G1"].forEach(g => s.subjects.push({ subject: `Subject ${k} ${g}`, code: `S${k}`, tag: g }));
  s.school.levels.forEach((lv, li) => {
    const cls = Array.from({ length: 8 }, (_, i) => `${li + 1}C${i + 1}`); cls.forEach(c => s.classes.push({ class: c, level: lv, size: 40 }));
    for (let k = 0; k < 12; k++) cls.forEach(c => s.lessons.push({ level: lv, subject: `Subject ${k} G3`, classes: [c], students: 40 }));          // 96 whole-class rows a level
    for (let k = 12; k < 34; k++) { s.blocks.push({ block: `${lv} Band ${k}`, level: lv, classes: cls });
      for (let g = 0; g < 7; g++) s.lessons.push({ level: lv, subject: `Subject ${k} ${["G3", "G2", "G1"][g % 3]}`, block: `${lv} Band ${k}`, classes: cls, students: 30 }); }   // 154 banded rows a level
    cls.forEach((c, ci) => { for (let i = 0; i < 40; i++) s.students.push({ id: `${c}-${i}`, class: c, groups: Array.from({ length: 10 }, (_, k) => `${li + 1}S${12 + k}P${1 + (i + ci) % 3}`) }); });
  });
  assert.strictEqual(s.lessons.length, 1000); assert.strictEqual(s.students.length, 1280);
  const t0 = Date.now(); const L = ClassView.cards(s); const B = s.school.levels.map(lv => ClassView.bands(s, lv)); const ms = Date.now() - t0;
  assert.strictEqual(L.reduce((a, l) => a + l.cards.length, 0), 32); assert.ok(B.every(b => b.rows.length >= 34)); assert.ok(ms < 300, `took ${ms} ms`);
});
t("a_band_with_no_name_yet_is_not_drawn", () => {
  const s = fixture(); s.blocks.push({ block: "", level: "Sec 3", classes: ["3A"] }, { level: "Sec 3", classes: ["3B"] });
  s.lessons.push({ level: "Sec 3", subject: "Art", block: "", classes: ["3A"], students: 5 });
  const B = ClassView.bands(s, "Sec 3"), bars = B.rows.reduce((a, r) => a.concat(r.bars), []);
  assert.ok(bars.every(b => b.block)); assert.strictEqual(bars.length, 3);                 // the three named bands of the fixture, nothing else
  assert.deepStrictEqual(cellKinds(B.rows.find(r => r.label === "Art")), ["whole", null, null, null]);   // the row with an empty band box is a whole-class cell, once
});
t("a_group_with_no_subject_yet_does_not_change_its_bands_label", () => {
  const s = fixture(); s.lessons.push({ level: "Sec 3", block: "Sec 3 Mathematics", classes: ["3A"], students: 3 }, { level: "Sec 3", subject: null, block: "Sec 3 Option A", classes: ["3A"] });
  const B = ClassView.bands(s, "Sec 3"), m = B.rows.find(r => r.label === "Mathematics"), a = B.rows.find(r => r.label === "Sec 3 Option A");
  assert.deepStrictEqual(m.bars[0].groups[m.bars[0].groups.length - 1], { code: "", subject: "", students: 3 });
  assert.deepStrictEqual(a.bars[0].groups[a.bars[0].groups.length - 1], { code: "", subject: "", students: null });
  const only = fixture(); only.blocks = only.blocks.slice(0, 1); only.lessons = [{ level: "Sec 3", block: "Sec 3 Mathematics", classes: ["3A"], students: 3 }];
  assert.deepStrictEqual(ClassView.bands(only, "Sec 3").rows.map(r => r.label), ["Sec 3 Mathematics"]);   // no group has a subject: the band's own name
});
console.log(n + " cases passed");

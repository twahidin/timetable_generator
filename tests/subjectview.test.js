// Plain-assert tests for static/subjectview.js (step 3's Cards view): run with `node tests/subjectview.test.js`
const assert = require("assert");
const SubjectView = require("../static/subjectview.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { departments: ["Mathematics", "Science", "PE & CCA", "Humanities"], tags: [["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]], levels: ["Sec 1", "Sec 2"] },
  subjects: [
    /*0*/ { _id: "s1", subject: "Mathematics G3", code: "MA", tag: "G3", dept: "Mathematics", room_kind: null, lesson_length: null, periods: { "Sec 1": 6, "Sec 2": 6 } },
    /*1*/ { _id: "s2", subject: "Mathematics G2", code: "MA", tag: "G2", dept: "Mathematics", periods: { "Sec 1": 6 } },
    /*2*/ { _id: "s3", subject: "PE", code: "PE", tag: "-", dept: "PE & CCA", room_kind: "pe venue", lesson_length: 2, periods: { "Sec 1": 4 } },
    /*3*/ { _id: "s4", subject: "Science G1", code: "SC", tag: "G1", dept: "Science", room_kind: "lab", periods: {} },
    /*4*/ { _id: "s5", subject: "Mathematics G1", code: "MA", tag: "G1", dept: "Mathematics", periods: {} },
    /*5*/ { _id: "s6", subject: "Science", code: "SC", tag: "-", dept: "Science", room_kind: "science room", lesson_length: 3, periods: { "Sec 1": 5 } },
    /*6*/ { _id: "s7", subject: "Science G3", code: "SC", tag: "G3", dept: "Science", room_kind: "lab", periods: {} },
    /*7*/ { _id: "s8", subject: "Art", code: "AR", tag: "", dept: "Aesthetics", periods: { "Sec 2": 2 } },
    /*8*/ { _id: "s9", subject: "CP Time", code: "CP", dept: null, periods: {} }],
  lessons: [{ level: "Sec 1", subject: "Mathematics G3", block: "1 Math", classes: ["1A", "1B"] }, { level: "Sec 1", subject: "Mathematics G3", block: "1 Math", classes: ["1A", "1B"] },
            { level: "Sec 1", subject: "Science", classes: ["1A", "1B", "1C"] }, { level: "Sec 1", subject: "PE", classes: ["1A"] },
            { level: "Sec 1", subject: "PE", classes: ["1B"], code_override: "PE1" }, null, { level: "Sec 1", subject: null }]
});
const all = s => SubjectView.columns(s).reduce((a, c) => a.concat(c.cards), []).sort((a, b) => a.ri - b.ri);   // every card, in the order of the list
const card = (s, name) => all(s).find(c => c.name === name);
const same = (s, f) => { const before = JSON.stringify(s); f(); assert.strictEqual(JSON.stringify(s), before); };
/* ---- the model ---- */
t("a_column_per_department_in_the_schools_order_then_the_others", () => {
  assert.deepStrictEqual(SubjectView.columns(fixture()).map(c => [c.dept, c.cards.map(k => k.name)]),
    [["Mathematics", ["Mathematics"]], ["Science", ["Science"]], ["PE & CCA", ["PE"]], ["Humanities", []], ["Aesthetics", ["Art"]], ["", ["CP Time"]]]);
  assert.deepStrictEqual(SubjectView.columns({}), []); assert.deepStrictEqual(SubjectView.columns({ subjects: [null] }), []);
  assert.deepStrictEqual(SubjectView.tags(fixture()), ["G3", "G2", "G1"]); assert.deepStrictEqual(SubjectView.tags({}), []);
});
t("a_card_is_the_rows_of_one_subject_with_its_g_levels_in_the_schools_order", () => {
  const row = (ri, tag, subject, lessons, groups) => ({ ri, tag, subject, room_kind: "", lesson_length: null, lessons, groups });
  assert.deepStrictEqual(card(fixture(), "Mathematics"), { ri: 0, dept: "Mathematics", code: "MA", name: "Mathematics", odd: "",
    rows: [row(0, "G3", "Mathematics G3", 2, 2), row(1, "G2", "Mathematics G2", 0, 0), row(4, "G1", "Mathematics G1", 0, 0)],
    ticked: ["G3", "G2", "G1"], plain: null, same_kind: true, same_length: true });
});
t("a_row_with_no_tag_beside_tagged_rows_is_on_the_same_card", () => {
  const k = card(fixture(), "Science");
  assert.deepStrictEqual([k.ri, k.plain, k.ticked, k.rows.map(r => [r.ri, r.tag])], [3, 5, ["G3", "G1"], [[5, ""], [6, "G3"], [3, "G1"]]]);
  assert.deepStrictEqual([k.same_kind, k.same_length, k.rows.map(r => r.room_kind), k.rows.map(r => r.lesson_length)], [false, false, ["science room", "lab", "lab"], [3, null, null]]);
  assert.deepStrictEqual([k.rows[0].lessons, k.rows[0].groups], [1, 3]);                                    // one whole-class lesson row of three classes
  const pe = card(fixture(), "PE");
  assert.deepStrictEqual([pe.ticked, pe.plain, pe.same_kind, pe.rows[0].lessons, pe.rows[0].groups, pe.rows[0].lesson_length], [[], 2, true, 2, 2, 2]);
});
t("every_row_shows_on_exactly_one_card_whatever_it_is", () => {
  const s = fixture();
  s.subjects.push({ subject: "Chemistry", tag: "G3", dept: "Science", code: "CH" },            // 9: its G-level is not the end of its name
                  { subject: "Physics G3", tag: "-", dept: "Science", code: "PH" },             // 10: its name ends in a G-level it does not have
                  { subject: "Biology Std", tag: "Std", dept: "Science", code: "BI" },          // 11: a tag the school does not have
                  { subject: "Mathematics G3", tag: "G3", dept: "Mathematics", code: "MA" },    // 12: the same subject twice
                  { subject: "", tag: "-", dept: "Mathematics", code: "" }, { subject: "", tag: "-", dept: "Mathematics", code: "" },   // 13, 14: two new cards with no name yet
                  { subject: "G2", tag: "G2", dept: "Mathematics", code: "" },                 // 15: a tag and no name
                  null, "x", {},                                                                // 16, 17 are not rows; 18 is a row with nothing in it
                  { subject: "  Geography   G3 ", tag: " G3 ", dept: " Humanities ", code: " GE " }, { subject: "Geography G2", tag: "G2", dept: "Humanities", code: "GE" });   // 19, 20
  const A = all(s), ris = A.reduce((a, c) => a.concat(c.rows.map(r => r.ri)), []).sort((a, b) => a - b);
  assert.deepStrictEqual(ris, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20]);
  const odd = A.filter(c => c.odd).map(c => [c.ri, c.odd, c.name, c.rows.length, c.ticked, c.plain]);
  assert.deepStrictEqual(odd, [[9, "tag", "Chemistry", 1, [], null], [10, "tag", "Physics G3", 1, [], null], [11, "tag", "Biology Std", 1, [], null], [12, "twin", "Mathematics G3", 1, [], null]]);
  assert.deepStrictEqual(A.filter(c => !c.name).map(c => [c.ri, c.odd, c.ticked, c.plain, c.dept]), [[13, "", [], 13, "Mathematics"], [14, "", [], 14, "Mathematics"], [15, "", ["G2"], null, "Mathematics"], [18, "", [], 18, ""]]);
  const g = card(s, "Geography"); assert.deepStrictEqual([g.ri, g.dept, g.code, g.ticked, g.rows.map(r => r.subject)], [19, "Humanities", "GE", ["G3", "G2"], ["Geography   G3", "Geography G2"]]);
  assert.strictEqual(card(s, "Mathematics").rows.length, 3);                                    // the twin did not join it
});
t("a_tag_is_plain_text_not_a_pattern_and_a_school_with_no_tags_has_plain_cards", () => {
  const s = { school: { tags: [["G3+", "P"], ["(H)", "H"], ["-", ""]] }, subjects: [{ subject: "Chinese (H)", tag: "(H)", code: "CL" }, { subject: "Chinese G3+", tag: "G3+", code: "CL" }, { subject: "ChineseG3+", tag: "G3+", code: "CL" }] };
  assert.deepStrictEqual(all(s).map(c => [c.name, c.odd, c.ticked]), [["Chinese", "", ["G3+", "(H)"]], ["ChineseG3+", "tag", []]]);
  const p = { school: { tags: [["-", ""]] }, subjects: [{ subject: "English", tag: "-" }, { subject: "English G3", tag: "G3" }] };
  assert.deepStrictEqual(all(p).map(c => [c.name, c.odd]), [["English", ""], ["English G3", "tag"]]);
});
t("how_many_lesson_rows_name_a_subject", () => {
  const s = fixture();
  assert.deepStrictEqual([SubjectView.uses(s, "Mathematics G3"), SubjectView.uses(s, "PE"), SubjectView.uses(s, "Art"), SubjectView.uses(s, ""), SubjectView.uses({}, "PE")], [2, 2, 0, 0, 0]);
});
t("names_like_proto_are_names_like_any_other_and_lists_that_are_not_lists_are_empty", () => {
  const s = { school: { departments: ["toString"], tags: [["__proto__", "P"], ["toString", "T"], ["-", ""]] },
    subjects: [{ subject: "constructor __proto__", tag: "__proto__", code: "constructor", dept: "toString" }, { subject: "constructor toString", tag: "toString", code: "constructor", dept: "toString" }],
    lessons: [{ subject: "__proto__", classes: ["1A"] }, { subject: "__proto__" }, { subject: "constructor __proto__", classes: ["1A", "1B"] }] };
  assert.deepStrictEqual(SubjectView.tags(s), ["__proto__", "toString"]);
  assert.deepStrictEqual(SubjectView.columns(s).map(c => [c.dept, c.cards.map(k => [k.name, k.code, k.odd, k.ticked, k.rows.map(r => r.ri)])]), [["toString", [["constructor", "constructor", "", ["__proto__", "toString"], [0, 1]]]]]);
  assert.deepStrictEqual([SubjectView.uses(s, "__proto__"), SubjectView.uses(s, "constructor"), SubjectView.uses(s, "toString")], [2, 0, 0]);
  assert.deepStrictEqual([SubjectView.columns(s)[0].cards[0].rows.map(r => r.lessons), SubjectView.columns(s)[0].cards[0].rows.map(r => r.groups)], [[1, 0], [2, 0]]);
  const bad = [{ school: 5 }, { school: { tags: "G3", departments: 7 }, subjects: "a", lessons: {} }, null];
  bad.forEach(b => { assert.deepStrictEqual(SubjectView.columns(b), []); assert.deepStrictEqual(SubjectView.tags(b), []); });
  const q = { subjects: [{ subject: "7", tag: "-", code: "S", dept: "Maths" }], lessons: [{ subject: 7, classes: ["1A"] }] };            // a lesson that names a subject by a number
  assert.deepStrictEqual([SubjectView.columns(q)[0].cards[0].rows[0].lessons, SubjectView.uses(q, "7"), SubjectView.uses(q, 7)], [1, 1, 1]);
});
/* ---- the changes ---- */
t("ticking_adds_the_row_named_name_and_tag_after_the_cards_last_row", () => {
  const s = fixture(), before = s.subjects.slice();
  assert.deepStrictEqual(SubjectView.tick(s, 5, "G2"), { ri: 7, how: "added" });                             // Science: its rows are 3, 5 and 6
  assert.deepStrictEqual(s.subjects[7], { subject: "Science G2", code: "SC", tag: "G2", dept: "Science", periods: {}, room_kind: "lab" });   // room kind and lesson length as the card's first row has them
  assert.deepStrictEqual(s.subjects.filter(r => r !== s.subjects[7]), before);                              // every other row is the same row, in the same order
  assert.deepStrictEqual(card(s, "Science").rows.map(r => [r.ri, r.tag]), [[5, ""], [6, "G3"], [7, "G2"], [3, "G1"]]);
  assert.deepStrictEqual([card(s, "Art").ri, card(s, "CP Time").ri], [8, 9]);                               // the cards below moved down one place and are still themselves
});
t("the_first_tag_of_a_plain_subject_changes_its_row_when_no_lesson_uses_it_and_adds_one_when_lessons_do", () => {
  const s = fixture(), art = s.subjects[7], pe = s.subjects[2];
  assert.deepStrictEqual(SubjectView.tick(s, 7, "G3"), { ri: 7, how: "changed" });
  assert.strictEqual(s.subjects[7], art); assert.deepStrictEqual(art, { _id: "s8", subject: "Art G3", code: "AR", tag: "G3", dept: "Aesthetics", periods: { "Sec 2": 2 } });   // its periods came across
  assert.strictEqual(s.subjects.length, 9);
  assert.deepStrictEqual(SubjectView.tick(s, 2, "G3"), { ri: 3, how: "added" });                             // PE has lessons: it stays, as the row with no G-level
  assert.strictEqual(s.subjects[2], pe); assert.strictEqual(pe.subject, "PE");
  assert.deepStrictEqual(s.subjects[3], { subject: "PE G3", code: "PE", tag: "G3", dept: "PE & CCA", periods: {}, room_kind: "pe venue", lesson_length: 2 });
  assert.deepStrictEqual([card(s, "PE").plain, card(s, "PE").ticked], [2, ["G3"]]);
});
t("a_tick_that_cannot_be_made_changes_nothing", () => {
  const s = fixture(); s.subjects.push({ subject: "Chemistry", tag: "G3", dept: "Science", code: "CH" }, { subject: "", tag: "-", dept: "Science", code: "" });
  same(s, () => assert.deepStrictEqual([SubjectView.tick(s, 0, "G3"), SubjectView.tick(s, 0, "G9"), SubjectView.tick(s, 0, "-"), SubjectView.tick(s, 0, ""), SubjectView.tick(s, 9, "G2"), SubjectView.tick(s, 10, "G3"), SubjectView.tick(s, 99, "G3"), SubjectView.tick({}, 0, "G3")],
    [null, null, null, null, null, null, null, null]));   // ticked already; not one of the school's tags; a row shown as it is; a card with no name; no such row
});
t("unticking_removes_the_row_and_the_last_tag_leaves_the_subject_with_no_tag_and_no_periods", () => {
  const s = fixture(), g3 = s.subjects[0];
  assert.deepStrictEqual(SubjectView.untick(s, 0, "G2"), { how: "removed" });
  assert.deepStrictEqual(s.subjects.map(r => r.subject).slice(0, 4), ["Mathematics G3", "PE", "Science G1", "Mathematics G1"]);
  assert.deepStrictEqual(SubjectView.untick(s, 0, "G1"), { how: "removed" });
  assert.deepStrictEqual(SubjectView.untick(s, 0, "G3"), { how: "emptied" });
  assert.strictEqual(s.subjects[0], g3); assert.deepStrictEqual(g3, { _id: "s1", subject: "Mathematics", code: "MA", tag: "-", dept: "Mathematics", room_kind: null, lesson_length: null, periods: {} });
  const m = fixture(); assert.deepStrictEqual(SubjectView.untick(m, 3, ""), { how: "removed" });              // Science's row with no G-level
  assert.deepStrictEqual([card(m, "Science").plain, card(m, "Science").ticked, m.subjects.length], [null, ["G3", "G1"], 8]);
  const z = fixture(); same(z, () => assert.deepStrictEqual([SubjectView.untick(z, 2, ""), SubjectView.untick(z, 0, "G9"), SubjectView.untick(z, 2, "G3"), SubjectView.untick(z, 99, "G3")], [null, null, null, null]));   // PE's only row is the card; tags not on the card; no such row
});
t("a_name_a_code_a_department_a_room_kind_or_a_lesson_length_goes_to_every_row_of_the_card", () => {
  const s = fixture(), lessons = JSON.stringify(s.lessons);
  assert.strictEqual(SubjectView.rename(s, 4, "  Maths "), true);
  assert.deepStrictEqual([0, 1, 4].map(i => s.subjects[i].subject), ["Maths G3", "Maths G2", "Maths G1"]);
  assert.strictEqual(JSON.stringify(s.lessons), lessons);                                                    // the lessons keep the name they had, as after a change of name in the table
  same(s, () => assert.strictEqual(SubjectView.rename(s, 0, "  "), false));                                  // a subject with G-levels needs a name
  assert.strictEqual(SubjectView.rename(s, 2, ""), true); assert.strictEqual(s.subjects[2].subject, "");     // one with none may lose it
  assert.strictEqual(SubjectView.set(s, 0, "code", "MT"), true); assert.deepStrictEqual([0, 1, 4].map(i => s.subjects[i].code), ["MT", "MT", "MT"]);
  assert.strictEqual(SubjectView.set(s, 3, "room_kind", "lab"), true); assert.strictEqual(SubjectView.set(s, 3, "lesson_length", null), true);
  assert.deepStrictEqual([card(s, "Science").same_kind, card(s, "Science").same_length], [true, true]);
  assert.strictEqual(SubjectView.set(s, 0, "dept", "Science"), true);
  assert.deepStrictEqual(SubjectView.columns(s).slice(0, 2).map(c => [c.dept, c.cards.map(k => k.name)]), [["Mathematics", []], ["Science", ["Maths", "Science"]]]);
  same(s, () => assert.deepStrictEqual([SubjectView.set(s, 0, "subject", "x"), SubjectView.set(s, 0, "periods", {}), SubjectView.set(s, 99, "code", "x"), SubjectView.rename(s, 99, "x")], [false, false, false, false]));
  const o = fixture(); o.subjects.push({ subject: "Chemistry", tag: "G3", dept: "Science", code: "CH" });
  same(o, () => assert.deepStrictEqual([SubjectView.rename(o, 9, "Chemistry G3"), SubjectView.set(o, 9, "code", "X")], [false, false]));   // a row shown as it is is changed through the table's own boxes
});
t("a_card_is_removed_with_all_its_rows_and_a_new_one_starts_empty_in_its_department", () => {
  const s = fixture();
  assert.strictEqual(SubjectView.remove(s, 1), 3); assert.deepStrictEqual(s.subjects.map(r => r.subject), ["PE", "Science G1", "Science", "Science G3", "Art", "CP Time"]);
  assert.strictEqual(SubjectView.remove(s, 99), 0); assert.strictEqual(s.subjects.length, 6);
  assert.strictEqual(SubjectView.add(s, "Humanities"), 6); assert.deepStrictEqual(s.subjects[6], { subject: "", code: "", tag: "-", dept: "Humanities", periods: {} });
  assert.strictEqual(SubjectView.add(s, ""), 7); assert.strictEqual(s.subjects[7].dept, null);
  const e = {}; assert.strictEqual(SubjectView.add(e, "Science"), 0); assert.strictEqual(e.subjects.length, 1);
});
console.log(n + " cases passed");

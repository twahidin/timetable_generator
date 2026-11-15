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
console.log(n + " cases passed");

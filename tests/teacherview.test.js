// Plain-assert tests for static/teacherview.js (step 4's Cards view): run with `node tests/teacherview.test.js`
const assert = require("assert");
const TeacherView = require("../static/teacherview.js");
let n = 0; const t = (name, f) => { f(); n++; };
const spec = () => ({ school: { departments: ["MA", "SC", "PE"] }, teachers: [
  { _id: "a", name: "Arjun Nair", short: "Arjun", dept: "MA", role: "EO" },
  { _id: "b", name: "Lim Hui Min", short: "Hui Min", dept: "SC", dept2: "MA", provisional: "Yes" },
  { _id: "c", name: "Tan Wei Ming", short: "Wei Ming", dept: "SC", dept2: "SC" },
  null,
  { _id: "d", name: "Siti Rahman", short: "Siti", dept: " HU ", dept2: "" },
  { _id: "e", name: "", dept: null, can_teach: [{ subject: "Mathematics", levels: "All" }] }] });

t("a column per department of the school, then others found, then no department", () => {
  const C = TeacherView.columns(spec());
  assert.deepStrictEqual(C.map(c => c.dept), ["MA", "SC", "PE", "HU", ""]);
  assert.deepStrictEqual(C.map(c => c.cards.map(x => x.ti)), [[0, 1], [1, 2], [], [4], [5]]);
});
t("a teacher with two departments has a card in both, marked home in one", () => {
  const C = TeacherView.columns(spec()), inMA = C[0].cards[1], inSC = C[1].cards[0];
  assert.deepStrictEqual([inMA.ti, inMA.home, inMA.dept, inMA.dept2, inMA.provisional], [1, false, "SC", "MA", true]);
  assert.deepStrictEqual([inSC.ti, inSC.home, inSC.dept2], [1, true, "MA"]);
});
t("every teacher shows once in each of their departments whatever the row holds", () => {
  const C = TeacherView.columns(spec()), seen = {};
  C.forEach(c => c.cards.forEach(x => { seen[x.ti] = (seen[x.ti] || 0) + 1; }));
  assert.deepStrictEqual(seen, { 0: 1, 1: 2, 2: 1, 4: 1, 5: 1 });           // a second equal to the home is one department; a null row is no card
  assert.strictEqual(C[1].cards[1].dept2, "");
  assert.doesNotThrow(() => TeacherView.columns({}) && TeacherView.columns({ school: { departments: "x" }, teachers: "y" }));
});
t("the filter: one department's column, and a search by name or short name", () => {
  assert.deepStrictEqual(TeacherView.columns(spec(), { dept: "MA" }).map(c => [c.dept, c.cards.map(x => x.ti)]), [["MA", [0, 1]]]);
  assert.deepStrictEqual(TeacherView.columns(spec(), { q: "hui" }).map(c => c.cards.map(x => x.ti)), [[1], [1], [], [], []]);
});
t("giving, changing and taking off a second department", () => {
  const s = spec();
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, "SC"), { how: "set", was: "" }); assert.strictEqual(s.teachers[0].dept2, "SC");
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, "PE"), { how: "changed", was: "SC" });
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, " PE "), { how: "same", was: "PE" });
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, "MA"), { how: "home", was: "PE" }); assert.strictEqual(s.teachers[0].dept2, "PE");
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, ""), { how: "off", was: "PE" }); assert.ok(!("dept2" in s.teachers[0]));
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, ""), { how: "none", was: "" });
  assert.strictEqual(TeacherView.setSecond(s, 3, "MA"), null); assert.strictEqual(TeacherView.setSecond(s, 99, "MA"), null);
});
t("tidy takes off a second department that is empty or the home", () => {
  const s = spec();
  assert.strictEqual(TeacherView.tidy(s.teachers[2]), true); assert.ok(!("dept2" in s.teachers[2]));
  assert.strictEqual(TeacherView.tidy(s.teachers[1]), false); assert.strictEqual(s.teachers[1].dept2, "MA");
  assert.strictEqual(TeacherView.tidy(s.teachers[4]), true); assert.strictEqual(TeacherView.tidy(null), false);
});
t("nothing here reads or writes a stored can_teach", () => {
  const s = spec(), was = JSON.stringify(s.teachers[5].can_teach);
  TeacherView.columns(s); TeacherView.setSecond(s, 5, "MA"); TeacherView.tidy(s.teachers[5]);
  assert.strictEqual(JSON.stringify(s.teachers[5].can_teach), was);
});
t("a teacher whose only department is the second one has one home card", () => {
  const s = { school: { departments: ["MA", "SC"] }, teachers: [{ name: "Only Second", dept: "", dept2: "SC" }, { name: "" }] };
  const C = TeacherView.columns(s), all = [];
  C.forEach(c => c.cards.forEach(x => all.push([c.dept, x])));
  assert.strictEqual(all.length, 2);
  const [d, x] = all[0];
  assert.deepStrictEqual([d, x.ti, x.home, x.dept, x.dept2], ["SC", 0, true, "", "SC"]);
  assert.deepStrictEqual([all[1][0], all[1][1].home], ["", true]);
});
console.log(n + " cases passed");

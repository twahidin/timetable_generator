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
const rspec = () => ({ school: {}, teachers: [
  { _id: "a", name: "New Teacher 3", short: "NT3", dept: "MA" },
  { _id: "b", name: "Arjun Nair", short: "Arjun", dept: "MA" },
  { _id: "c", name: "Lim Hui Min", short: "Hui Min", dept: "SC", earlier_names: ["Miss Lim"] }],
  classes: [{ class: "2A", parents: ["New Teacher 3", "Arjun Nair"] }, { class: "2B", parents: ["Arjun Nair"] }, { class: "2C" }],
  lessons: [{ subject: "Maths", teachers: ["New Teacher 3", null] }, { subject: "Maths", teachers: [null, "Arjun Nair", "New Teacher 3"] },
    { subject: "Science", teachers: ["Lim Hui Min"], note: "ask New Teacher 3 first" }, { subject: "Art" }, null],
  rules: [{ scope: "Teacher", target: "New Teacher 3", rule: "Not available" }, { scope: "Class", target: "New Teacher 3", rule: "Fixed at" },
    { scope: "School", rule: "In words", text: "no PE after lunch" }, { scope: "School", rule: "In words", text: "New Teacher 3 is free on Fridays" }] });

t("uses finds every place that names a teacher exactly", () => {
  assert.deepStrictEqual(TeacherView.uses(rspec(), "New Teacher 3"), { lessons: [0, 1], classes: [0], rules: [0], staff: [], typed: [2], notes: 1, twice: false });
  assert.deepStrictEqual(TeacherView.uses(rspec(), ""), { lessons: [], classes: [], rules: [], staff: [], typed: [], notes: 0, twice: false });
  assert.deepStrictEqual(TeacherView.uses({}, "X"), { lessons: [], classes: [], rules: [], staff: [], typed: [], notes: 0, twice: false });
});
t("a rename carries to groups, form teachers and Teacher rules, and keeps the old name", () => {
  const s = rspec(), r = TeacherView.rename(s, 0, "  Mdm   Lee ");
  assert.deepStrictEqual(r, { was: "New Teacher 3", now: "Mdm Lee", groups: 2, classes: ["2A"], rules: 1, staff: 0, typed: [2], notes: 1, twice: false, short: "NT3" });
  assert.strictEqual(s.teachers[0].name, "Mdm Lee");
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["New Teacher 3"]);
  assert.deepStrictEqual(s.lessons[0].teachers, ["Mdm Lee", null]);            // the empty place stays where it is
  assert.deepStrictEqual(s.lessons[1].teachers, [null, "Arjun Nair", "Mdm Lee"]);
  assert.deepStrictEqual(s.classes[0].parents, ["Mdm Lee", "Arjun Nair"]);
  assert.strictEqual(s.rules[0].target, "Mdm Lee");
  assert.strictEqual(s.rules[1].target, "New Teacher 3");                      // not a Teacher rule: left
  assert.strictEqual(s.rules[3].text, "New Teacher 3 is free on Fridays");     // free text is never rewritten
  assert.strictEqual(s.lessons[2].note, "ask New Teacher 3 first");
});
t("not a rename: a blank new name, a row with no name yet, the same name, no such row", () => {
  const s = rspec(), before = JSON.stringify(s);
  for (const to of ["", "   ", null]) assert.strictEqual(TeacherView.rename(s, 0, to), null);
  for (const to of ["New Teacher 3", " New Teacher 3 ", "New  Teacher   3"]) { assert.deepStrictEqual(TeacherView.rename(s, 0, to), { same: true }); assert.strictEqual(JSON.stringify(s), before); }
  assert.strictEqual(TeacherView.rename(s, 9, "X"), null);
  s.teachers.push({ _id: "z", name: "" }); const b2 = JSON.stringify(s);
  assert.strictEqual(TeacherView.rename(s, 3, "Somebody"), null); assert.strictEqual(JSON.stringify(s), b2);
  s.teachers.pop(); assert.strictEqual(JSON.stringify(s), before);
});
t("cleanName trims and makes runs of spaces one", () => {
  assert.strictEqual(TeacherView.cleanName("  Mdm   Lee "), "Mdm Lee");
  assert.strictEqual(TeacherView.cleanName(null), ""); assert.strictEqual(TeacherView.cleanName(undefined), ""); assert.strictEqual(TeacherView.cleanName(""), "");
  assert.strictEqual(TeacherView.cleanName(7), "7");
});
t("a name another teacher has is refused; a change of only case or spacing is a rename", () => {
  const s = rspec(), before = JSON.stringify(s);
  assert.deepStrictEqual(TeacherView.rename(s, 0, "arjun  nair"), { error: "Arjun Nair is already a teacher." });
  assert.strictEqual(JSON.stringify(s), before);
  const r = TeacherView.rename(s, 0, "new teacher 3");
  assert.strictEqual(r.now, "new teacher 3"); assert.strictEqual(r.groups, 2); assert.deepStrictEqual(s.lessons[0].teachers, ["new teacher 3", null]);
});
t("earlier names: renaming back clears it, the latest rename wins, a name in use is nobody's", () => {
  const s = rspec();
  TeacherView.rename(s, 0, "Mdm Lee"); TeacherView.rename(s, 0, "Mdm Lee Mei");
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["New Teacher 3", "Mdm Lee"]);
  TeacherView.rename(s, 0, "New Teacher 3");
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["Mdm Lee", "Mdm Lee Mei"]);
  TeacherView.rename(s, 1, "Miss Lim");                                         // Hui Min's earlier name is taken as a name
  assert.ok(!("earlier_names" in s.teachers[2]));
  TeacherView.rename(s, 1, "Mdm Lee");                                         // row 0's earlier name is taken as a name
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["Mdm Lee Mei"]);
  assert.deepStrictEqual(s.teachers[1].earlier_names, ["Arjun Nair", "Miss Lim"]);
});
t("the renaming row takes the old name even when a later row also lists it", () => {
  const s = rspec(); s.teachers[2].earlier_names = ["New Teacher 3"];
  TeacherView.rename(s, 0, "Mdm Lee");
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["New Teacher 3"]);
  assert.ok(!("earlier_names" in s.teachers[2]));
});
t("two rows of the old name: the name changes and nothing follows", () => {
  const s = rspec(); s.teachers.push({ _id: "d", name: "New Teacher 3", dept: "SC" });
  const r = TeacherView.rename(s, 0, "Mdm Lee");
  assert.deepStrictEqual([r.twice, r.groups, r.classes, r.rules], [true, 0, [], 0]);
  assert.deepStrictEqual(s.lessons[0].teachers, ["New Teacher 3", null]); assert.strictEqual(s.rules[0].target, "New Teacher 3");
  assert.ok(!("earlier_names" in s.teachers[0]));                               // the other row still has the name
});
t("a short name that was the name follows it; any other short name stays", () => {
  const s = rspec(); s.teachers[0].short = "New Teacher 3";
  assert.strictEqual(TeacherView.rename(s, 0, "Mdm Lee").short, null); assert.strictEqual(s.teachers[0].short, "Mdm Lee");
  assert.strictEqual(TeacherView.rename(s, 1, "Mr Arjun").short, "Arjun"); assert.strictEqual(s.teachers[1].short, "Arjun");          // a short name of its own is left
  const u = rspec(); delete u.teachers[0].short; TeacherView.rename(u, 0, "Mdm Lee"); assert.ok(!("short" in u.teachers[0]));
  const v = rspec(); v.teachers[0].short = "New Teacher 3"; v.teachers.push({ _id: "d", name: "New Teacher 3", short: "New Teacher 3" });
  TeacherView.rename(v, 0, "Mdm Lee"); assert.deepStrictEqual([v.teachers[0].short, v.teachers[3].short], ["Mdm Lee", "New Teacher 3"]);   // only the renamed row's
  const w = rspec(); w.teachers[0].short = "New Teacher 3"; assert.strictEqual(TeacherView.rename(w, 0, "arjun nair").error, "Arjun Nair is already a teacher."); assert.strictEqual(w.teachers[0].short, "New Teacher 3");   // refused: nothing changes
});
t("a rename carries to the teacher-only periods", () => {
  const s = rspec(); s.staff_periods = [{ name: "Zone class", teachers: ["New Teacher 3", "Arjun Nair"] }, { name: "Briefing", teachers: ["Arjun Nair"] }];
  assert.deepStrictEqual(TeacherView.uses(s, "New Teacher 3").staff, [0]);
  const r = TeacherView.rename(s, 0, "Mdm Lee");
  assert.deepStrictEqual(s.staff_periods[0].teachers, ["Mdm Lee", "Arjun Nair"]); assert.strictEqual(r.staff, 1);
  assert.ok(TeacherView.renameText(r).includes("1 teacher-only period"));
  assert.ok(!TeacherView.renameText({ ...r, staff: 2 }).includes("1 teacher-only period") && TeacherView.renameText({ ...r, staff: 2 }).includes("2 teacher-only periods"));
});
t("settle puts earlier names right whatever wrote them", () => {
  const s = rspec();
  s.teachers[0].earlier_names = ["Old A", "Old A", "", null, 7, "Arjun Nair", "Shared"];
  s.teachers[1].earlier_names = "nope";
  s.teachers[2].earlier_names = ["Shared", "Miss Lim"];
  assert.strictEqual(TeacherView.settle(s), true);
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["Old A"]);              // a name two rows claim stays on the last of them
  assert.ok(!("earlier_names" in s.teachers[1]));
  assert.deepStrictEqual(s.teachers[2].earlier_names, ["Shared", "Miss Lim"]);
  assert.strictEqual(TeacherView.settle(s), false);
  s.teachers.push({ _id: "n", name: "Old A" }); assert.strictEqual(TeacherView.settle(s), true);   // a placeholder name used again
  assert.ok(!("earlier_names" in s.teachers[0]));
  assert.strictEqual(TeacherView.settle({}), false); assert.strictEqual(TeacherView.settle(null), false);
});
t("the toast says what followed", () => {
  const T = TeacherView.renameText, base = { was: "New Teacher 3", now: "Mdm Lee", groups: 0, classes: [], rules: 0, typed: [], notes: 0, twice: false, short: null };
  assert.strictEqual(T(base), "New Teacher 3 is now Mdm Lee.");
  assert.strictEqual(T({ ...base, groups: 6, classes: ["2A"], rules: 1 }), "New Teacher 3 is now Mdm Lee: on 6 groups, form teacher of 2A, 1 rule. Undo, at the top, brings it back.");
  assert.strictEqual(T({ ...base, groups: 1, classes: ["2A", "2B", "2C"], rules: 2 }), "New Teacher 3 is now Mdm Lee: on 1 group, form teacher of 2A, 2B and 2C, 2 rules. Undo, at the top, brings it back.");
  assert.strictEqual(T({ ...base, classes: ["2A", "2B"] }), "New Teacher 3 is now Mdm Lee: form teacher of 2A and 2B. Undo, at the top, brings it back.");
  assert.strictEqual(T({ ...base, twice: true }), "New Teacher 3 is now Mdm Lee. Two teachers were called New Teacher 3, so their groups were not changed: pick the right teacher on each.");
  assert.strictEqual(T({ ...base, groups: 2, typed: [3], notes: 1 }), "New Teacher 3 is now Mdm Lee: on 2 groups. Undo, at the top, brings it back. Typed rule T3 still says New Teacher 3: check it. 1 note still says New Teacher 3: check it.");
  assert.strictEqual(T({ ...base, groups: 2, short: "NT3" }), "New Teacher 3 is now Mdm Lee: on 2 groups. Undo, at the top, brings it back. The short name is still NT3: change it too if it should be different.");
  assert.strictEqual(T({ ...base, short: "New", typed: [3] }), "New Teacher 3 is now Mdm Lee. The short name is still New: change it too if it should be different. Typed rule T3 still says New Teacher 3: check it.");
  assert.strictEqual(T({ ...base, typed: [3, 5], notes: 2 }), "New Teacher 3 is now Mdm Lee. Typed rules T3 and T5 still say New Teacher 3: check them. 2 notes still say New Teacher 3: check them.");
});
t("a head is told what stands in the way of a rename", () => {
  const s = rspec(), no = () => false, before = JSON.stringify(s);
  assert.strictEqual(TeacherView.blocked(s, "Lim Hui Min", no, no), "");
  assert.strictEqual(TeacherView.blocked(s, "New Teacher 3", no, no), "Only the committee can rename New Teacher 3: they are a form teacher of 2A and named in 1 rule.");
  assert.strictEqual(TeacherView.blocked(s, "New Teacher 3", x => x.subject === "Maths", () => true), "Only the committee can rename New Teacher 3: they are a form teacher of 2A, named in 1 rule and on 2 groups of other departments.");
  assert.strictEqual(TeacherView.blocked(s, "Arjun Nair", no, () => true), "Only the committee can rename Arjun Nair: they are a form teacher of 2A and 2B and on 1 lesson the form teachers take.");
  s.rules.push({ scope: "Teacher", target: "Lim Hui Min", rule: "Not available" }, { scope: "Teacher", target: "Lim Hui Min", rule: "Max periods a day" });
  assert.strictEqual(TeacherView.blocked(s, "Lim Hui Min", () => true, no), "Only the committee can rename Lim Hui Min: they are named in 2 rules and on 1 group of other departments.");
  s.rules.length -= 2; assert.strictEqual(JSON.stringify(s), before);
});
console.log(n + " cases passed");

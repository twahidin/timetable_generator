const assert = require("assert");
const People = require("../static/people.js");
let n = 0; const t = (name, f) => { f(); n++; };
const NAMES = Array.from({ length: 200 }, (_, i) => `Teacher ${["Tan", "Lim", "Nair", "Osman", "Koh", "Menon", "Ong", "Lee"][i % 8]} ${i}`);
const sig = p => JSON.stringify(p);

t("the same name gives the same avatar, whatever its capitals or spacing", () => {
  assert.strictEqual(People.key("  TAN   Wei Ming "), "tan wei ming");
  assert.deepStrictEqual(People.avatarParts("TAN  Wei Ming "), People.avatarParts("Tan Wei Ming"));
  assert.strictEqual(People.avatar("Tan Wei Ming", 0, 32), People.avatar(" tan wei  ming", 0, 32));
});
t("hash is 32-bit FNV-1a", () => { assert.strictEqual(People.hash(""), 2166136261); assert.strictEqual(People.hash("a"), 3826002220); });
t("there are enough combinations to tell a staff room apart", () => {
  assert.ok(People.AVATAR_COMBOS >= 100000);
  assert.ok(new Set(NAMES.map(x => sig(People.avatarParts(x)))).size >= 195);
});
t("every part index is inside its list", () => {
  for (const x of NAMES) for (const [k, v] of Object.entries(People.avatarParts(x))) assert.ok(Number.isInteger(v) && v >= 0 && v < People.AVATAR[k].length, `${k} ${v}`);
});
t("a new look changes the avatar and is itself repeatable", () => {
  const changed = NAMES.filter(x => sig(People.avatarParts(x, 1)) !== sig(People.avatarParts(x, 0))).length;
  assert.ok(changed >= 195);
  assert.deepStrictEqual(People.avatarParts("Tan Wei Ming", 3), People.avatarParts("Tan Wei Ming", 3));
});
t("the drawing is one svg of the asked size, with no script and no outside link", () => {
  const s = People.avatar("Tan Wei Ming", 0, 48);
  assert.ok(s.startsWith("<svg") && s.endsWith("</svg>") && s.includes('width="48"') && s.includes('viewBox="0 0 36 36"') && s.includes('aria-hidden="true"'));
  assert.ok(!/script|href|http/i.test(s));
});
t("no name gives a plain disc, not a face", () => {
  for (const x of ["", "   ", null, undefined]) { const s = People.avatar(x); assert.ok(s.startsWith("<svg") && !s.includes("<path")); }
});
t("nothing random is used", () => { const r = Math.random; Math.random = () => { throw new Error("random"); }; try { People.avatar("Lim Hui Min", 2); } finally { Math.random = r; } });
const EX = [{ _id: "t1", name: "Tan Wei Ming", short: "Tan", dept: "MA", role: "EO", allowance: 104, can_teach: [{ subject: "Mathematics", levels: "All" }] },
            { _id: "t2", name: "Lim Hui Min", short: "Lim", dept: "MA", role: "HOD", allowance: 67, can_teach: [] }];
const ROLES = [{ role: "EO", allowance: 104 }, { role: "HOD", allowance: 67 }, { role: "ST", allowance: 86 }], DEPTS = ["MA", "SC"];

t("a list with a header, in any column order", () => {
  const r = People.readTeachers("Department\tTeacher Name\tRole\tAllowance (periods)\nSC\tArjun Nair\tST\t86\nMA\tPriya Menon\tEO\t\n");
  assert.deepStrictEqual(r.columns.sort(), ["allowance", "dept", "name", "role"]);
  assert.deepStrictEqual(r.teachers, [{ dept: "SC", name: "Arjun Nair", role: "ST", allowance: 86 }, { dept: "MA", name: "Priya Menon", role: "EO" }]);
});
t("title rows above the header and extra columns are ignored", () => {
  const r = People.readTeachers("Step 4 · Teachers\t\t\n\t\t\nTeacher\tShort\tGiven\tSpare\tDepartment\nArjun Nair\tArjun\t40\t46\tSC\n");
  assert.deepStrictEqual(r.teachers, [{ name: "Arjun Nair", short: "Arjun", dept: "SC" }]);
});
t("names only, one per line, with no header", () => {
  assert.deepStrictEqual(People.readTeachers("Arjun Nair\nPriya Menon\n").teachers, [{ name: "Arjun Nair" }, { name: "Priya Menon" }]);
});
t("comma-separated, with a quoted name that has a comma", () => {
  assert.deepStrictEqual(People.readTeachers('Name,Role\n"Nair, Arjun",ST\n').teachers, [{ name: "Nair, Arjun", role: "ST" }]);
});
t("a name twice in the list: the second row is left out and said", () => {
  const r = People.readTeachers("Name\tRole\nArjun Nair\tST\narjun  nair\tEO\n");
  assert.strictEqual(r.teachers.length, 1); assert.strictEqual(r.teachers[0].role, "ST");
  assert.deepStrictEqual(r.skipped, ["arjun  nair is in the list twice: the second row was left out."]);
});
t("an allowance that is not a number is left out and said", () => {
  const r = People.readTeachers("Name\tAllowance\nArjun Nair\tfull\n");
  assert.deepStrictEqual(r.teachers, [{ name: "Arjun Nair" }]); assert.strictEqual(r.skipped.length, 1);
});
t("nothing that looks like a teacher", () => { assert.ok(People.readTeachers("\n\n").error); });
t("an existing teacher is matched whatever the capitals and spacing, and only differences change", () => {
  const p = People.planTeachers(EX, [{ name: "TAN  Wei Ming ", role: "ST" }, { name: "Lim Hui Min", role: "HOD" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.update, [{ i: 0, changes: { role: "ST" } }]);
  assert.deepStrictEqual(p.add, []); assert.deepStrictEqual(p.missing, []);
});
t("a list without allowance or role blanks nothing", () => {
  assert.deepStrictEqual(People.planTeachers(EX, [{ name: "Tan Wei Ming" }, { name: "Lim Hui Min" }], ROLES, DEPTS).update, []);
});
t("a new teacher takes the role's guide allowance, a short name, and is not provisional", () => {
  const p = People.planTeachers(EX, [{ name: "Arjun Nair", role: "ST", dept: "SC" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.add, [{ name: "Arjun Nair", role: "ST", dept: "SC", short: "Arjun", allowance: 86, can_teach: [], provisional: "No" }]);
  assert.deepStrictEqual(p.missing, [0, 1]);
});
t("roles and departments the setup does not have are listed once each", () => {
  const p = People.planTeachers(EX, [{ name: "A B", role: "LT", dept: "HU" }, { name: "C D", role: "LT", dept: "MA" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.unknownRoles, ["LT"]); assert.deepStrictEqual(p.unknownDepts, ["HU"]);
});
t("a header in the school's own words is read, not taken as a teacher", () => {
  const r = People.readTeachers("Staff Name\tDept\nArjun Nair\tSC");
  assert.deepStrictEqual(r.teachers, [{ name: "Arjun Nair", dept: "SC" }]); assert.deepStrictEqual(r.skipped, []);
  assert.deepStrictEqual(People.readTeachers("Staff\tName of teacher\tRole\nX Y\tZ\tST").teachers, [{ name: "X Y", role: "ST" }]);
  assert.deepStrictEqual(People.readTeachers("Teacher's name\nArjun Nair").teachers, [{ name: "Arjun Nair" }]);
});
t("a header with no name column is refused, not guessed", () => {
  assert.strictEqual(People.readTeachers("Person\tDept\tRole\nArjun Nair\tSC\tST").error, "Could not find the column of names. Head it Name or Teacher.");
});
t("a headerless paste with several columns says how it was read; one column says nothing", () => {
  const r = People.readTeachers("Arjun Nair\tArjun\nPriya Menon\tPriya");
  assert.deepStrictEqual(r.teachers[0], { name: "Arjun Nair", short: "Arjun" });
  assert.deepStrictEqual(r.skipped, ["No header row was found, so the columns were read in this order: Name, Short name, Department, Role, Allowance, Other duties, Note."]);
  assert.deepStrictEqual(People.readTeachers("Arjun Nair\nPriya Menon\n").skipped, []);
});
t("a row with data but no name is said; an empty row is silent", () => {
  const r = People.readTeachers("Name\tRole\nArjun Nair\tST\n\n\tEO\n");
  assert.strictEqual(r.teachers.length, 1); assert.deepStrictEqual(r.skipped, ["A row with no name was left out (row 4)."]);
});
t("names like Constructor and __proto__ are ordinary names", () => {
  const r = People.readTeachers("Constructor\n__proto__\nTan Wei Ming\n");
  assert.deepStrictEqual(r.teachers.map(x => x.name), ["Constructor", "__proto__", "Tan Wei Ming"]);
  const p = People.planTeachers([{ name: "Constructor", role: "EO" }, { name: "__proto__" }], [{ name: "constructor", role: "ST" }, { name: "__proto__" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.add, []); assert.deepStrictEqual(p.update, [{ i: 0, changes: { role: "ST" } }]); assert.deepStrictEqual(p.missing, []);
});
t("the default short name drops trailing punctuation", () => {
  assert.strictEqual(People.planTeachers([], [{ name: "Nair, Arjun" }], ROLES, DEPTS).add[0].short, "Nair");
});
t("names that look like one person are alike; the same key, an empty name and other people are not", () => {
  for (const [a, b] of [["Tan Wei-Ming", "Tan Wei Ming"], ["O'Brien Lee", "OBrien Lee"], ["Wei Ming Tan", "Tan Wei Ming"],
    ["Tan Wei Ming", "Tan Wei Ming Alex"], ["Tan Wei Meng", "Tan Wei Ming"], ["Arjun Nair", "Arjun Naiir"]])
    { assert.ok(People.alike(a, b), `${a} / ${b}`); assert.ok(People.alike(b, a), `${b} / ${a}`); }
  for (const [a, b] of [["Tan Wei Ming", "TAN wei  ming"], ["", "Tan Wei Ming"], ["Tan Wei Ming", "   "], ["Tan Wei Ming", "Lim Wei Ming"],
    ["Tan", "Tan Wei Ming"], ["Lim Al", "Lim Ali"], ["Arjun Nair", "Priya Menon"], ["--", ".."]])
    assert.ok(!People.alike(a, b), `${a} / ${b}`);
});
t("the plan counts what the updates change, field by field", () => {
  const p = People.planTeachers(EX, [{ name: "Tan Wei Ming", allowance: 80, role: "EO" }, { name: "Lim Hui Min", allowance: 60, short: "LHM" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.fields, { allowance: 2, short: 1 });
  assert.deepStrictEqual(People.planTeachers(EX, [{ name: "Tan Wei Ming" }], ROLES, DEPTS).fields, {});
});
t("a new name that looks like a teacher not in the list is paired with them, once, first in table order", () => {
  const p = People.planTeachers(EX, [{ name: "Tan Wei-Ming" }, { name: "Lim Hui Min" }, { name: "Arjun Nair" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.add.map(x => x.name), ["Tan Wei-Ming", "Arjun Nair"]); assert.deepStrictEqual(p.missing, [0]);
  assert.deepStrictEqual(p.alike, [{ add: "Tan Wei-Ming", missing: "Tan Wei Ming" }]);
  const two = People.planTeachers([{ name: "Tan Wei Meng" }, { name: "Tan Wei Ming" }], [{ name: "Tan Wei-Ming" }], ROLES, DEPTS);
  assert.deepStrictEqual(two.alike, [{ add: "Tan Wei-Ming", missing: "Tan Wei Meng" }]);
  assert.deepStrictEqual(People.planTeachers(EX, [{ name: "Tan Wei Ming" }, { name: "Lim Hui Min" }], ROLES, DEPTS).alike, []);
});
console.log(`${n} cases passed`);

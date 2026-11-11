// Plain-assert tests for static/parents.js: run with `node tests/parents.test.js`
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const Parents = require("../static/parents.js");

const copy = (x) => JSON.parse(JSON.stringify(x));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "parents_cases.json"), "utf8"));
let passed = 0;
for (const c of cases) {
  const spec = copy(c.spec);
  if ("adopt" in c) Parents.adopt(spec, c.adopt);
  Parents.derive(spec);
  assert.deepStrictEqual(spec, c.after, c.name);
  assert.strictEqual(Parents.derive(spec), false, c.name + " second derive");
  assert.deepStrictEqual(spec, c.after, c.name + " second derive leaves it");
  passed++;
}

const spec = {
  school: { parents_subjects: ["CE 1", "Art", "CP Time"], parents_max: 2, parents_name: "  " },
  subjects: [{ _id: "s1", subject: "CP Time" }, { _id: "s2", subject: "CE 1" }],
  classes: [{ _id: "c1", class: "1A", level: "Sec 1", parents: ["Tan", null, "Lim"] }],
};
const whole = { subject: "CE 1", classes: ["1A"], teachers: ["Lim", ""] };
assert.deepStrictEqual(Parents.names(whole), ["Lim"]);
assert.deepStrictEqual(Parents.names(spec.classes[0]), ["Tan", "Lim"]);
assert.deepStrictEqual(Parents.names({}), []);
assert.deepStrictEqual(Parents.subjects(spec), ["CE 1", "CP Time"]);
assert.deepStrictEqual(Parents.subjects({ school: {} }), []);
assert.strictEqual(Parents.staffed(spec, whole), true);
assert.strictEqual(Parents.staffed(spec, { subject: "CE 1", block: "Band" }), false);
assert.strictEqual(Parents.staffed(spec, { subject: "CE 1", code_override: "X" }), false);
assert.strictEqual(Parents.staffed(spec, { subject: "Art" }), false);
assert.strictEqual(Parents.follows(spec, whole), true);
assert.strictEqual(Parents.follows(spec, Object.assign({ by_hand: true }, whole)), false);
assert.deepStrictEqual(Parents.want(spec, whole), ["Tan", "Lim"]);
assert.deepStrictEqual(Parents.want(spec, { subject: "CE 1", classes: ["1B"] }), []);
assert.strictEqual(Parents.same(["Tan", "Lim"], ["Lim", "Tan"]), true);
assert.strictEqual(Parents.same(["Tan"], ["Tan", "Lim"]), false);
assert.strictEqual(Parents.same([], [null]), true);
[[2, 3], [4, 4], ["4", 4], [6, 6], [7, 3], [0, 3], [2.5, 3], ["x", 3], ["0x10", 3], [[4], 3], [null, 3], [Infinity, 3], [" 4 ", 4], [" ", 3]].forEach(function (p) {
  assert.strictEqual(Parents.cap({ school: { parents_max: p[0] } }), p[1], "cap " + String(p[0]));
});
[[" 4 ", 4], ["5", 5], [3, 3], [0, null], [7, null], ["x", null], [2.5, null], [true, null], [" ", null], [null, null]].forEach(function (p) {
  assert.strictEqual(Parents.maximum(p[0]), p[1], "maximum " + String(p[0]));
});
assert.strictEqual(Parents.cap({ school: {} }), 3);
assert.strictEqual(Parents.cap({}), 3);
assert.strictEqual(Parents.label(spec), "Form teachers");
assert.strictEqual(Parents.label({ school: { parents_name: " Class Parents " } }), "Class Parents");
assert.strictEqual(Parents.label({}), "Form teachers");
passed++;

// adopt on a spec with nothing to do adds no keys
{
  const s = { school: {}, lessons: [], classes: [] };
  assert.strictEqual(Parents.adopt(s, null), 0);
  assert.strictEqual(Parents.derive(s), false);
  assert.deepStrictEqual(s, { school: {}, lessons: [], classes: [] });
  assert.strictEqual(Parents.derive({}), false);
}
passed++;

// ---- what the page does on an edit
const clone = copy, row = (s, id) => s.lessons.find((r) => r._id === id);
const base = () => ({
  school: { parents_subjects: ["CE 1", "CE 2"], parents_max: 2, parents_name: "Class Parents" },
  subjects: [{ _id: "s1", subject: "CE 1", periods: { "Sec 1": 1 } }, { _id: "s2", subject: "CE 2", periods: { "Sec 1": 1 } }],
  teachers: ["Tan", "Lim", "Goh", "Ong", "Koh"].map((n, i) => ({ _id: "t" + i, name: n })),
  classes: [{ _id: "c1", class: "1A", level: "Sec 1", parents: ["Tan", "Lim"] }, { _id: "c2", class: "1B", level: "Sec 1", parents: ["Goh", "Ong"] }],
  lessons: [["ce1-1A", "CE 1", "1A", ["Tan", "Lim"]], ["ce2-1A", "CE 2", "1A", ["Tan", "Lim"]], ["ce1-1B", "CE 1", "1B", ["Goh", "Ong"]], ["ce2-1B", "CE 2", "1B", ["Goh", "Ong"]]]
    .map((a) => ({ _id: a[0], level: "Sec 1", subject: a[1], block: null, classes: [a[2]], teachers: a[3], students: null })),
});
const old = () => ({ school: {}, subjects: [{ _id: "s1", subject: "CE 1", periods: { "Sec 1": 1 } }], teachers: [{ _id: "t0", name: "Tan" }],
  classes: [{ _id: "c1", class: "1A", level: "Sec 1" }], lessons: [{ _id: "r1", level: "Sec 1", subject: "CE 1", block: null, classes: ["1A"], teachers: ["Goh"], students: null }] });
const noParents = (s, ci) => { delete s.classes[ci].parents; };
const t = (name, fn) => {
  try { fn(); } catch (e) { console.error("FAILED: " + name); throw e; }
  passed++;
};

t("a hand change of a following lesson is marked, and stays", () => {
  const prev = base(); const now = clone(prev); row(now, "ce1-1A").teachers = ["Goh"];
  assert.strictEqual(Parents.settle(now, prev, true), true);
  assert.deepStrictEqual([row(now, "ce1-1A").by_hand, row(now, "ce1-1A").teachers], [true, ["Goh"]]);
  assert.strictEqual(Parents.settle(now, now, true), false);
  assert.deepStrictEqual([row(now, "ce1-1A").by_hand, row(now, "ce1-1A").teachers], [true, ["Goh"]]);
});
t("the same change arriving from elsewhere (hand false) is put back, not marked", () => {
  const prev = base(); const now = clone(prev); row(now, "ce1-1A").teachers = ["Goh"];
  assert.strictEqual(Parents.settle(now, prev, false), true);
  assert.deepStrictEqual(now, prev);
  const n2 = clone(prev); row(n2, "ce1-1A").teachers = ["Goh"];
  Parents.settle(n2, null, true);
  assert.deepStrictEqual(n2, prev);
});
t("changing the box moves the lessons and marks nothing (Review Focus 2)", () => {
  const prev = base(); const now = clone(prev);
  Parents.setParents(now, 0, ["Tan", "Goh"]);
  assert.strictEqual(Parents.settle(now, prev, true), true);
  assert.deepStrictEqual([row(now, "ce1-1A").teachers, row(now, "ce2-1A").teachers], [["Tan", "Goh"], ["Tan", "Goh"]]);
  assert.ok(now.lessons.every((r) => !("by_hand" in r)));
});
t("undoing a box change marks nothing", () => {
  const prev = base(); prev.classes[0].parents = ["Tan", "Goh"]; prev.lessons.slice(0, 2).forEach((r) => { r.teachers = ["Tan", "Goh"]; });
  const now = base();
  assert.strictEqual(Parents.settle(now, prev, false), false);
  assert.deepStrictEqual(now, base());
  assert.strictEqual(Parents.settle(now, prev, true), false);
  assert.deepStrictEqual(now, base());
});
t("a row split off by hand with other teachers is marked", () => {
  const prev = base(); const now = clone(prev);
  now.lessons.push({ _id: "new1", level: "Sec 1", subject: "CE 1", block: null, classes: ["1B"], teachers: ["Koh"], students: null });
  now.lessons.push({ _id: "new2", level: "Sec 1", subject: "CE 2", block: null, classes: ["1B"], teachers: ["Ong", "Goh"], students: null });
  now.lessons.push({ _id: "new3", level: "Sec 1", subject: "CE 2", block: null, classes: ["1B"], teachers: [], students: null });
  now.lessons.push({ level: "Sec 1", subject: "CE 2", block: null, classes: ["1B"], teachers: ["Koh"], students: null });
  Parents.settle(now, prev, true);
  assert.deepStrictEqual([row(now, "new1").by_hand, row(now, "new2").by_hand, row(now, "new3").by_hand, now.lessons[7].by_hand], [true, undefined, undefined, true]);
  assert.deepStrictEqual(row(now, "new3").teachers, ["Goh", "Ong"]);
});
t("first Class Parents for a class keep what was typed (Review Focus 4)", () => {
  const s = base(); noParents(s, 1); row(s, "ce1-1B").teachers = ["Goh"]; row(s, "ce2-1B").teachers = ["Koh"];
  Parents.setParents(s, 1, ["Goh", null, "Ong", "Goh"]); Parents.derive(s);
  assert.deepStrictEqual(s.classes[1].parents, ["Goh", "Ong"]);
  assert.deepStrictEqual([row(s, "ce1-1B").by_hand, row(s, "ce1-1B").teachers], [true, ["Goh"]]);
  assert.deepStrictEqual([row(s, "ce2-1B").by_hand, row(s, "ce2-1B").teachers], [true, ["Koh"]]);
  const q = base(); noParents(q, 1); row(q, "ce1-1B").teachers = ["Goh"]; row(q, "ce2-1B").teachers = ["Ong", "Goh"];
  Parents.setParents(q, 1, ["Goh", "Ong"]); Parents.derive(q);
  assert.deepStrictEqual([row(q, "ce2-1B").by_hand, row(q, "ce2-1B").teachers], [undefined, ["Goh", "Ong"]]);
});
t("taking every Class Parent off clears the following lessons, not the hand-changed ones", () => {
  const s = base(); row(s, "ce2-1A").by_hand = true; row(s, "ce2-1A").teachers = ["Koh"];
  Parents.setParents(s, 0, []); Parents.derive(s);
  assert.ok(!("parents" in s.classes[0]));
  assert.deepStrictEqual([row(s, "ce1-1A").teachers, row(s, "ce2-1A").teachers, row(s, "ce1-1B").teachers], [[], ["Koh"], ["Goh", "Ong"]]);
  const u = base(); Parents.setParents(u, 0, ["Tan", "Lim"]); assert.deepStrictEqual(u, base());
  Parents.setParents(u, 0, [null, ""]); assert.ok(!("parents" in u.classes[0]));
});
t("naming a subject keeps typed teachers and makes the missing lessons", () => {
  const s = base(); s.school.parents_subjects = ["CE 1"]; row(s, "ce2-1A").teachers = ["Koh"];
  s.subjects.push({ _id: "s3", subject: "CP Time", periods: { "Sec 1": 1 } }); row(s, "ce1-1A").teachers = ["Koh"];
  Parents.setSubjects(s, ["CE 1", "CE 2", "", "CP Time", "CE 2"]); Parents.derive(s);
  assert.deepStrictEqual(s.school.parents_subjects, ["CE 1", "CE 2", "CP Time"]);
  assert.deepStrictEqual([row(s, "ce2-1A").by_hand, row(s, "ce2-1A").teachers], [true, ["Koh"]]);
  assert.strictEqual(row(s, "ce1-1A").by_hand, undefined);   // CE 1 was already named: not adopted here
  assert.deepStrictEqual(row(s, "cp-c1-s3").teachers, ["Tan", "Lim"]);
  Parents.setSubjects(s, []); assert.ok(!("parents_subjects" in s.school));
  const o = old(); Parents.setSubjects(o, []); assert.deepStrictEqual(o, old());
});
t("setMax refuses below what a class has, with the classes named", () => {
  const s = base();
  assert.strictEqual(Parents.setMax(s, 1), "1A, 1B already have more than 1.");
  noParents(s, 1); assert.strictEqual(Parents.setMax(s, 1), "1A already has more than 1.");
  assert.strictEqual(Parents.setMax(s, 0), "Pick a number from 1 to 6.");
  assert.strictEqual(Parents.setMax(s, "x"), "Pick a number from 1 to 6.");
  assert.strictEqual(Parents.setMax(s, 7), "Pick a number from 1 to 6.");
  assert.strictEqual(s.school.parents_max, 2);
  assert.strictEqual(Parents.setMax(s, "3"), null); assert.strictEqual(s.school.parents_max, 3);
});
t("fill takes them from the lessons, in order, up to the maximum, and never touches a class that has some", () => {
  const s = base(); noParents(s, 1); s.classes.push({ _id: "c3", class: "1C", level: "Sec 1" });
  s.lessons = s.lessons.filter((r) => r._id !== "ce2-1B");
  s.lessons.push({ _id: "x", level: "Sec 1", subject: "CE 2", block: null, classes: ["1B"], teachers: ["Koh", "Goh", "Lim"], students: null });
  s.lessons.push({ _id: "y", level: "Sec 1", subject: "CE 1", block: "B", classes: ["1C"], teachers: ["Koh"], students: null });
  assert.strictEqual(Parents.fillCount(s), 1);
  assert.strictEqual(Parents.fill(s), 1);
  assert.deepStrictEqual([s.classes[1].parents, s.classes[0].parents, s.classes[2].parents], [["Goh", "Ong"], ["Tan", "Lim"], undefined]);
  assert.strictEqual(row(s, "x").by_hand, true);
  assert.strictEqual(Parents.fillCount(s), 0);
  const n = base(); n.school.parents_subjects = []; noParents(n, 1);
  assert.strictEqual(Parents.fillCount(n), 0); assert.strictEqual(Parents.fill(n), 0); assert.ok(!("parents" in n.classes[1]));
});
t("back and backAll put the Class Parents on again", () => {
  const s = base(); row(s, "ce1-1A").by_hand = true; row(s, "ce1-1A").teachers = ["Koh"]; row(s, "ce2-1B").by_hand = true;
  s.lessons.push({ _id: "o", level: "Sec 1", subject: "Art", block: null, classes: ["1A"], teachers: ["Koh"], students: null, by_hand: true });
  assert.deepStrictEqual(Parents.handRows(s), [0, 3]);
  Parents.back(s, 0); Parents.back(s, 4); assert.strictEqual(row(s, "o").by_hand, true);
  Parents.derive(s); assert.deepStrictEqual(row(s, "ce1-1A").teachers, ["Tan", "Lim"]);
  assert.strictEqual(Parents.backAll(s), 1); assert.deepStrictEqual(Parents.handRows(s), []);
});
t("exempt is true only for a Class Parent of the row's own class on a staffed row", () => {
  const s = base(); const r = row(s, "ce1-1A");
  assert.strictEqual(Parents.exempt(s, r, "Tan"), true);
  assert.strictEqual(Parents.exempt(s, r, "Goh"), false);
  assert.strictEqual(Parents.exempt(s, { subject: "Art", classes: ["1A"] }, "Tan"), false);
  assert.strictEqual(Parents.exempt(s, { subject: "CE 1", block: "B", classes: ["1A"] }, "Tan"), false);
  assert.deepStrictEqual(Parents.of(s, "Tan"), ["1A"]); assert.deepStrictEqual(Parents.of(s, "Koh"), []);
});
t("issues: the five sentences, in order", () => {
  const s = base();
  s.school.parents_subjects = ["CE 1", "Gone", "CE 2"];
  s.classes.push({ _id: "c3", class: "1C", level: "Sec 1" }, { _id: "c4", class: "1D", level: "Sec 1", parents: ["Tan", "Pat"] }, { _id: "c5", class: "1E", level: "Sec 1", parents: ["Tan"] });
  s.lessons.push({ _id: "a", level: "Sec 1", subject: "CE 1", block: null, classes: ["1C"], teachers: ["Koh"], students: null });
  s.lessons.push({ _id: "b", level: "Sec 1", subject: "CE 2", block: "Band", classes: ["1D"], teachers: ["Koh"], students: null });
  assert.deepStrictEqual(Parents.issues(s), [
    { kind: "classes", i: 2, text: "1C has no Class Parents yet." },
    { kind: "classes", i: 3, text: "1D: Pat is not on the teacher list." },
    { kind: "teachers", i: 0, text: "Tan is one of the Class Parents of 1A, 1D and 1E: their lessons together cannot be at the same time." },
    { kind: "config", i: 0, text: "Class Parents take Gone, which is not on step 3." },
    { kind: "classes", i: 3, text: "CE 2 for 1D cannot be staffed by its Class Parents: it is taught in groups." },
  ]);
  const r = base(); r.classes[1].parents = ["Tan"];
  assert.strictEqual(Parents.issues(r)[0].text, "Tan is one of the Class Parents of 1A and 1B: their lessons together cannot be at the same time.");
  const h = base(); noParents(h, 1); h.lessons.forEach((x) => { if (x.classes[0] === "1B") x.by_hand = true; });
  assert.deepStrictEqual(Parents.issues(h), []);
});
t("issues on a setup from before this change is empty", () => { assert.deepStrictEqual(Parents.issues(old()), []); });

const shared = () => { const s = base(); s.lessons = [{ _id: "R", level: "Sec 1", subject: "CE 1", block: null, classes: ["1A", "1B"], teachers: ["Tan", "Lim", "Goh", "Ong"], students: null }]; return s; };
t("first Class Parents for a class do not mark a shared lesson that followed the other class's box", () => {
  const s = shared(); const prev = clone(s);
  Parents.setParents(s, 0, []); Parents.settle(s, prev, true);
  assert.deepStrictEqual(row(s, "R").teachers, ["Goh", "Ong"]);
  const mid = clone(s);
  Parents.setParents(s, 0, ["Tan", "Lim"]); Parents.settle(s, mid, true);
  assert.deepStrictEqual([row(s, "R").teachers, row(s, "R").by_hand], [["Tan", "Lim", "Goh", "Ong"], undefined]);
  const u = shared(); noParents(u, 0); Parents.derive(u); assert.deepStrictEqual(row(u, "R").teachers, ["Goh", "Ong"]);
  const mid2 = clone(u); Parents.setParents(u, 0, ["Tan", "Lim"]); Parents.settle(u, mid2, true);
  assert.deepStrictEqual([row(u, "R").teachers, row(u, "R").by_hand], [["Tan", "Lim", "Goh", "Ong"], undefined]);
  const w = shared(); noParents(w, 0); row(w, "R").teachers = ["Goh", "Ong", "Koh"];
  Parents.setParents(w, 0, ["Tan"]); assert.strictEqual(row(w, "R").by_hand, true);
});
t("typing a teacher on a lesson of a class with no Class Parents marks nothing, and the issue stays", () => {
  const prev = base(); noParents(prev, 1); prev.lessons.forEach((r) => { if (r.classes[0] === "1B") r.teachers = []; });
  const now = clone(prev); row(now, "ce1-1B").teachers = ["Koh"];
  now.lessons.push({ _id: "n", level: "Sec 1", subject: "CE 2", block: null, classes: ["1B"], teachers: ["Koh"], students: null });
  assert.strictEqual(Parents.settle(now, prev, true), false);
  assert.ok(now.lessons.every((r) => !("by_hand" in r)));
  assert.deepStrictEqual(row(now, "ce1-1B").teachers, ["Koh"]);
  assert.ok(Parents.issues(now).some((x) => x.text === "1B has no Class Parents yet."));
  const a = clone(now); Parents.setParents(a, 1, ["Goh"]); assert.strictEqual(row(a, "ce1-1B").by_hand, true);
  const b = clone(now); Parents.setParents(b, 1, ["Koh"]); assert.strictEqual(row(b, "ce1-1B").by_hand, undefined);
});
t("a lesson that becomes staffed by an edit keeps its typed teachers", () => {
  const prev = base(); prev.lessons.push({ _id: "m", level: "Sec 1", subject: "Art", block: null, classes: ["1A"], teachers: ["Koh"], students: null },
    { _id: "e", level: "Sec 1", subject: "Art", block: null, classes: ["1B"], teachers: [], students: null },
    { _id: "g", level: "Sec 1", subject: "CE 2", block: "Band", classes: ["1B"], teachers: ["Koh"], students: null });
  const now = clone(prev); row(now, "m").subject = "CE 1"; row(now, "e").subject = "CE 1"; row(now, "g").block = null;
  Parents.settle(now, prev, true);
  assert.deepStrictEqual([row(now, "m").by_hand, row(now, "m").teachers], [true, ["Koh"]]);
  assert.deepStrictEqual([row(now, "e").by_hand, row(now, "e").teachers], [undefined, ["Goh", "Ong"]]);
  assert.deepStrictEqual([row(now, "g").by_hand, row(now, "g").teachers], [true, ["Koh"]]);
});
t("fill leaves out a name that is a Class Parent of another class on the same shared lesson", () => {
  const s = shared(); noParents(s, 0); row(s, "R").teachers = ["Goh", "Ong"];
  assert.strictEqual(Parents.fillCount(s), 0); assert.strictEqual(Parents.fill(s), 0); assert.ok(!("parents" in s.classes[0]));
  row(s, "R").teachers = ["Goh", "Koh", "Ong"];
  assert.strictEqual(Parents.fill(s), 1); assert.deepStrictEqual(s.classes[0].parents, ["Koh"]);
});
t("taking Class Parents off leaves another class's typed lesson alone", () => {
  const s = base(); noParents(s, 1); s.lessons.forEach((r) => { if (r.classes[0] === "1B") r.teachers = ["Koh"]; });
  Parents.setParents(s, 0, []);
  assert.deepStrictEqual([row(s, "ce1-1B").teachers, row(s, "ce1-1A").teachers], [["Koh"], []]);
});
t("issues: a subject named twice gives one sentence, a teacher named twice one sentence", () => {
  const s = base(); s.school.parents_subjects = ["Gone", "CE 1", "Gone"]; s.classes[1].parents = ["Tan"];
  s.teachers.push({ _id: "dup", name: "Tan" });
  const got = Parents.issues(s);
  assert.strictEqual(got.filter((x) => x.kind === "config").length, 1);
  const tt = got.filter((x) => x.kind === "teachers"); assert.strictEqual(tt.length, 1); assert.strictEqual(tt[0].i, 0);
});

console.log(passed + " cases passed");

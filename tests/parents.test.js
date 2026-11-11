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
assert.strictEqual(Parents.cap({ school: { parents_max: 2 } }), 3);
assert.strictEqual(Parents.cap({ school: { parents_max: 4 } }), 4);
assert.strictEqual(Parents.cap({ school: { parents_max: "x" } }), 3);
assert.strictEqual(Parents.cap({ school: {} }), 3);
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

console.log(passed + " cases passed");

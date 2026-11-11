// Plain-assert tests for static/sync.js: run with `node tests/sync.test.js`
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const Sync = require("../static/sync.js");

function canon(x) {
  if (Array.isArray(x)) return "[" + x.map(canon).join(",") + "]";
  if (x && typeof x === "object")
    return "{" + Object.keys(x).sort().map((k) => JSON.stringify(k) + ":" + canon(x[k])).join(",") + "}";
  return JSON.stringify(x === undefined ? null : x);
}
// Compare form: no nulls, no `_` keys (except `_id`), rows ordered by _id.
function norm(x, top = true) {
  if (Array.isArray(x)) return x.map((v) => norm(v, false));
  if (x && typeof x === "object") {
    const out = {};
    for (const [k, v0] of Object.entries(x)) {
      let v = v0;
      if (v === null || v === undefined || (k.startsWith("_") && k !== "_id")) continue;
      if (top && Sync.LISTS.includes(k) && Array.isArray(v))
        v = v.slice().sort((a, b) => (a._id < b._id ? -1 : a._id > b._id ? 1 : 0));
      out[k] = norm(v, false);
    }
    return out;
  }
  return x;
}
const same = (a, b) => canon(norm(a)) === canon(norm(b));
const copy = (x) => JSON.parse(JSON.stringify(x));

const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "sync_cases.json"), "utf8"));
let passed = 0;
for (const c of cases) {
  if (c.ops) {
    assert.strictEqual(canon(Sync.diff(c.base, c.cur)), canon(c.ops), c.name + " diff");
    const spec = copy(c.base);
    assert.strictEqual(Sync.apply(spec, c.ops), 0, c.name + " skipped");
    assert(same(spec, c.cur), c.name + " apply");
  } else {
    const spec = copy(c.base);
    Sync.apply(spec, c.theirs);
    Sync.apply(spec, c.mine);
    assert(same(spec, c.merged), c.name + " merge");
  }
  passed++;
}

// constants and ids
assert.deepStrictEqual(Sync.MERGE, { teachers: ["can_teach"], students: ["groups"] });
assert.deepStrictEqual(Sync.LISTS, ["venues", "classes", "subjects", "teachers", "blocks", "lessons",
  "rules", "students", "combinations", "roles", "choices"]);
assert(/^[a-z0-9]{10}$/.test(Sync.newId()));
assert.notStrictEqual(Sync.newId(), Sync.newId());

// ensureIds
{
  const spec = { school: { name: "A" }, classes: [{ class: "1A" }, { _id: "keep", class: "1B" }], teachers: [{ name: "Tan" }] };
  assert.strictEqual(Sync.ensureIds(spec), true);
  assert.strictEqual(spec.classes[1]._id, "keep");
  assert(/^[a-z0-9]{10}$/.test(spec.classes[0]._id) && spec.classes[0]._id !== spec.teachers[0]._id);
  const before = copy(spec);
  assert.strictEqual(Sync.ensureIds(spec), false);
  assert.deepStrictEqual(spec, before);
  assert.strictEqual(Sync.ensureIds({ school: {} }), false);
}
passed++;

// ensureIds links a choice to its rule by the rule's id
{
  const spec = { rules: [{ rule: "In words" }], choices: [{ kind: "rule", rule: 0 }, { kind: "rule", rule: 7 }] };
  assert.strictEqual(Sync.ensureIds(spec), true);
  const [a, b] = spec.choices;
  assert(a._id && b._id && a.rule_id === spec.rules[0]._id && b.rule_id === null);
  assert(!("rule" in a) && !("rule" in b));
  assert.strictEqual(Sync.ensureIds(spec), false);
}
passed++;

// skips and edge behaviour
{
  const spec = { classes: [{ _id: "c1", size: 1 }] };
  assert.strictEqual(Sync.apply(spec, [["set", "classes", "zz", "size", 2], ["del", "classes", "zz"],
    ["add", "classes", { _id: "c1" }, ""], ["merge", "classes", "zz", "x", [], []],
    ["bogus"], ["top", "classes", []]]), 6);
  assert.deepStrictEqual(spec, { classes: [{ _id: "c1", size: 1 }] });
  assert.strictEqual(Sync.apply(spec, [["add", "classes", { _id: "c0" }, ""],
    ["add", "classes", { _id: "c9" }, "nope"], ["set", "classes", "c1", "size", null],
    ["top", "extra_sheets", { a: 1 }]]), 0);
  assert.deepStrictEqual(spec.classes.map((r) => r._id), ["c0", "c1", "c9"]);
  assert.deepStrictEqual(spec.classes[1], { _id: "c1" });
  assert.deepStrictEqual(spec.extra_sheets, { a: 1 });
}
passed++;

// rebase
{
  const base = copy(cases.find((c) => c.name === "set-one-field").base);
  const sent = copy(base); sent.classes[0].size = 40;
  const now = copy(sent); now.classes.push({ _id: "c9", class: "1Z", size: 20 });
  const theirs = [["set", "classes", "c1", "size", 36]];
  const ours = [["set", "classes", "c1", "size", 40]];
  const r = Sync.rebase(base, sent, now, theirs, ours);
  assert.strictEqual(r.base.classes[0].size, 40);
  assert.strictEqual(r.spec.classes[0].size, 40);
  assert(r.spec.classes.some((x) => x._id === "c9"));
  assert(!r.base.classes.some((x) => x._id === "c9"));
  assert.strictEqual(base.classes[0].size, 38, "inputs are not mutated");
}
passed++;

// rebase with `after`: what the server did after our operations goes on last (a stale tab's change put right)
{
  const base = { lessons: [{ _id: "r1", teachers: ["Tan"] }] };
  const sent = copy(base); sent.lessons[0].teachers = ["Koh"];
  const now = copy(sent); now.lessons[0].note = "typed meanwhile";
  const ours = [["set", "lessons", "r1", "teachers", ["Koh"]]], after = [["set", "lessons", "r1", "teachers", ["Tan"]]];
  const r = Sync.rebase(base, sent, now, [], ours, after);
  assert.deepStrictEqual(r.base.lessons[0].teachers, ["Tan"]);
  assert.deepStrictEqual(r.spec.lessons[0], { _id: "r1", teachers: ["Tan"], note: "typed meanwhile" });
  assert.deepStrictEqual(Sync.rebase(base, sent, now, [], ours).base.lessons[0].teachers, ["Koh"], "without after as before");
}
passed++;

// malformed merge lists are skipped, never half-applied or thrown on
[ "x", { a: 1 }, null, 5 ].forEach((bad) => [4, 5].forEach((pos) => {
  const op = ["merge", "teachers", "t1", "can_teach", [], []];
  op[pos] = bad;
  const spec = { teachers: [{ _id: "t1", can_teach: [1] }] };
  assert.strictEqual(Sync.apply(spec, [op]), 1, "merge " + JSON.stringify(bad));
  assert.deepStrictEqual(spec, { teachers: [{ _id: "t1", can_teach: [1] }] });
}));
passed++;

// non-object school / day_structure / level are replaced, not thrown on
{
  let spec = { school: null, day_structure: null };
  assert.strictEqual(Sync.apply(spec, [["school", "name", "B"], ["day", "Sec 1", "Mon", "FL"]]), 0);
  assert.deepStrictEqual(spec, { school: { name: "B" }, day_structure: { "Sec 1": { Mon: "FL" } } });
  spec = { day_structure: { "Sec 1": null, "Sec 2": "x" } };
  assert.strictEqual(Sync.apply(spec, [["day", "Sec 1", "Mon", "FL"], ["day", "Sec 2", "Mon", null]]), 0);
  assert.deepStrictEqual(spec.day_structure["Sec 1"], { Mon: "FL" });
  spec = { school: "oops" };
  assert.strictEqual(Sync.apply(spec, [["school", "name", null]]), 0);
  assert.deepStrictEqual(spec.school, {});
}
passed++;

// a list section that is null or not a list: add starts it as a list, del / set / merge skip (same as sync.py)
[null, "x", { a: 1 }].forEach((bad) => {
  let spec = { roles: bad };
  assert.strictEqual(Sync.apply(spec, [["add", "roles", { _id: "r1", role: "EO" }, ""]]), 0);
  assert.deepStrictEqual(spec, { roles: [{ _id: "r1", role: "EO" }] });
  spec = { roles: bad };
  assert.strictEqual(Sync.apply(spec, [["del", "roles", "r1"], ["set", "roles", "r1", "role", "X"],
    ["merge", "roles", "r1", "x", [1], []]]), 3);
  assert.deepStrictEqual(spec, { roles: bad });
});
passed++;

console.log(passed + " cases passed");

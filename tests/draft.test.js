// Plain-assert tests for static/draft.js (the warning list on step 8): run with `node tests/draft.test.js`
const assert = require("assert");
const Draft = require("../static/draft.js");
let n = 0; const t = (name, f) => { f(); n++; };
const W = (key, kind, group, decision, strength) => ({ key, kind, text: key, strength: strength || "Must", group, where: null, sides: null, ops: null, decision });
const ws = () => [W("c1", "clash", "Ms X"), W("d1", "deployment", "1A"), W("d2", "deployment", "1A", { answer: "step5" }), W("d3", "deployment", "1B", { answer: "left" }), W("r1", "rule", "School", null, "Prefer")];
t("grouping by kind then group, open only", () => {
  const g = Draft.group(ws(), "open");
  assert.deepEqual(g.map(x => x.kind), ["clash", "deployment", "rule"]);
  assert.deepEqual(g[1].groups.map(x => [x.name, x.items.length]), [["1A", 1], ["1B", 1]]);
  assert.equal(g[1].title, "Differences from the deployment");
  assert.deepEqual(Draft.group(ws(), "left").map(x => x.kind), ["deployment"]);
  assert.deepEqual(Draft.group(ws(), "left")[0].groups[0].items.map(w => w.key), ["d3"]);
  assert.equal(Draft.group(ws(), "all")[1].groups[0].items.length, 2);
  assert.deepEqual(Draft.group([], "all"), []);
});
t("groups keep first-seen order", () => {
  const g = Draft.group([W("a", "clash", "Z"), W("b", "clash", "A"), W("c", "clash", "Z")], "all");
  assert.deepEqual(g[0].groups.map(x => [x.name, x.items.length]), [["Z", 2], ["A", 1]]);
});
t("counts", () => {
  assert.deepEqual(Draft.counts(ws()), { open: 4 - 0, left: 1, step5: 1, met: 0, must: 3, prefer: 1 });
  assert.deepEqual(Draft.counts(ws().concat([W("t1:again", "typed", "School", { answer: "met" })])), { open: 4, left: 1, step5: 1, met: 1, must: 3, prefer: 1 });
});
t("isOpen", () => {
  assert.equal(Draft.isOpen(W("a", "clash", "g")), true);
  assert.equal(Draft.isOpen(W("a", "clash", "g", { answer: "left" })), true);
  assert.equal(Draft.isOpen(W("a", "clash", "g", { answer: "step5" })), false);
  assert.equal(Draft.isOpen(W("a", "clash", "g", { answer: "fixed" })), false);
  assert.equal(Draft.isOpen(W("a", "typed", "g", { answer: "met" })), false);
});
t("texts", () => {
  assert.equal(Draft.sideText({ sides: { timetable: "Mr Tan", step5: "Mdm Lee" } }), "Timetable: Mr Tan · Step 5: Mdm Lee");
  assert.equal(Draft.sideText({ sides: null }), "");
  assert.equal(Draft.answerText({ decision: { answer: "left" } }), "Left for now");
  assert.equal(Draft.answerText({ decision: { answer: "step5" } }), "Step 5 updated");
  assert.equal(Draft.answerText({ decision: { answer: "fixed" } }), "Fixed");
  assert.equal(Draft.answerText({ decision: { answer: "met" } }), "Checked: still met");
  assert.equal(Draft.answerText({ decision: null }), "");
});
t("kinds", () => { assert.deepEqual(Draft.KINDS, ["clash", "deployment", "rule", "typed", "choice"]); assert.equal(Draft.KIND_TEXT.typed, "Rules in words"); });
t("whereText: only the parts a warning's where has", () => {
  assert.deepStrictEqual(Draft.whereText({ where: { cls: "1A", day: "Mon", period: 0, id: 3, row: "Entire Class" } }), ["1A", "Mon", "period 0"]);
  assert.deepStrictEqual(Draft.whereText({ where: { teacher: "Ms Ong" } }), ["Ms Ong"]);
  assert.deepStrictEqual(Draft.whereText({ where: { cls: "2B" } }), ["2B"]);
  assert.deepStrictEqual(Draft.whereText({ where: { cls: "", day: "Tue", period: 4 } }), ["Tue", "period 4"]);
  assert.deepStrictEqual(Draft.whereText({ where: null }), []);
});

t("fixTarget: the week a warning's Fix the timetable button opens", () => {
  assert.deepStrictEqual(Draft.fixTarget({ where: { cls: "1A", day: "Mon", period: 0, id: 3, row: "Entire Class" } }), { view: "class", name: "1A", day: "Mon", sel: { id: 3, group: "Entire Class" } });
  assert.deepStrictEqual(Draft.fixTarget({ where: { cls: "1A", day: "Mon", period: 2 } }), { view: "class", name: "1A", day: "Mon", sel: null });
  assert.deepStrictEqual(Draft.fixTarget({ where: { teacher: "Ms Ong" } }), { view: "teacher", name: "Ms Ong", day: "", sel: null });
  assert.deepStrictEqual(Draft.fixTarget({ where: { cls: "2B" } }), { view: "class", name: "2B", day: "", sel: null });
  assert.strictEqual(Draft.fixTarget({ where: { cls: "", day: "Mon", period: 1 } }), null);
  assert.strictEqual(Draft.fixTarget({ where: null }), null);
});

console.log(n + " checks passed");

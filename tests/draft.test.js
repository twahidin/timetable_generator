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

t("batches: neighbours with the same batch are one entry, newest last", () => {
  const f = (text, batch) => ({ text: text, at: "t", kind: "move", batch: batch });
  const out = Draft.batches([f("a", null), f("b", "x1"), f("c", "x1"), f("d", null)]);
  assert.deepStrictEqual(out.map(e => e.batch), [null, "x1", null]);
  assert.deepStrictEqual(out.map(e => e.items.map(i => i.text)), [["a"], ["b", "c"], ["d"]]);
  assert.deepStrictEqual(Draft.batches([f("a", "x"), f("b", "x"), f("c", "x")]).map(e => e.items.length), [3]);   // a batch of three
  assert.deepStrictEqual(Draft.batches([f("a", "x"), f("b", "y"), f("c", "x")]).map(e => e.items.length), [1, 1, 1]);   // not neighbours
  assert.deepStrictEqual(Draft.batches([{ text: "m" }, { text: "n", batch: null }]).map(e => e.items.length), [1, 1]);   // a missing batch
  assert.deepStrictEqual(Draft.batches([]), []);
  assert.deepStrictEqual(Draft.batches(undefined), []);
});
t("undoText: by the size of the last entry", () => {
  const f = (batch) => ({ text: "t", at: "t", kind: "move", batch: batch });
  assert.strictEqual(Draft.undoText([]), "");
  assert.strictEqual(Draft.undoText([f("x"), f(null)]), "Undo the last fix");
  assert.strictEqual(Draft.undoText([f(null), f("x"), f("x")]), "Undo the last two fixes");
  assert.strictEqual(Draft.undoText([f("x"), f("x"), f("x")]), "Undo the last 3 fixes");
  assert.strictEqual(Draft.undoText([f("x"), f("x"), f("x"), f("x")]), "Undo the last 4 fixes");
});
t("stateWord", () => {
  assert.strictEqual(Draft.stateWord("ok"), "Clean");
  assert.strictEqual(Draft.stateWord("prefer"), "Bends a Prefer");
  assert.strictEqual(Draft.stateWord("no"), "");
  assert.strictEqual(Draft.stateWord(undefined), "");
});
const K = (key, kind, where) => ({ key, kind, where: where === undefined ? null : where, text: key });
t("follow: the exact key stays", () => {
  const was = { key: "clash:A", kind: "clash", where: { teacher: "Ms X" } };
  assert.deepEqual(Draft.follow(was, [K("clash:B", "clash", { teacher: "Ms X" }), K("clash:A", "clash", { teacher: "Ms X" })]), { key: "clash:A", how: "same" });
});
t("follow: a card opened on k#2 is followed to k when only k remains", () => {
  assert.deepEqual(Draft.follow({ key: "clash:A#2", kind: "clash", where: null }, [K("clash:A", "clash")]), { key: "clash:A", how: "same" });
  assert.deepEqual(Draft.follow({ key: "clash:A", kind: "clash", where: null }, [K("clash:A#3", "clash"), K("clash:A#2", "clash")]), { key: "clash:A#3", how: "same" });
});
t("follow: a narrowed clash for the same teacher is followed as changed, another teacher is not", () => {
  const was = { key: "clash:Teacher double-booked: Ms X on Mon period 2.", kind: "clash", where: { teacher: "Ms X" } };
  assert.deepEqual(Draft.follow(was, [K("clash:other", "clash", { teacher: "Ms Y" }), K("clash:Teacher double-booked: Ms X on Mon period 3.", "clash", { teacher: "Ms X" })]), { key: "clash:Teacher double-booked: Ms X on Mon period 3.", how: "changed" });
  assert.strictEqual(Draft.follow(was, [K("clash:other", "clash", { teacher: "Ms Y" }), K("clash:cls", "clash", { cls: "1A" })]), null);
  const c = { key: "clash:Class clash: 1A", kind: "clash", where: { cls: "1A" } };
  assert.deepEqual(Draft.follow(c, [K("clash:Class clash: 1A on Tue", "clash", { cls: "1A" })]), { key: "clash:Class clash: 1A on Tue", how: "changed" });
});
t("follow: a rule warning for the same rule and lesson in a new slot is followed, another lesson is not", () => {
  const was = { key: "rule:3:1A|Maths|0|2", kind: "rule", where: { id: 7, row: "Entire Class" } };
  assert.deepEqual(Draft.follow(was, [K("rule:3:1A|Maths|1|4", "rule", { id: 7, row: "Entire Class" })]), { key: "rule:3:1A|Maths|1|4", how: "changed" });
  assert.strictEqual(Draft.follow(was, [K("rule:3:1A|Maths|1|4", "rule", { id: 8, row: "Entire Class" })]), null);
  assert.strictEqual(Draft.follow(was, [K("rule:4:1A|Maths|1|4", "rule", { id: 7, row: "Entire Class" })]), null);
  assert.strictEqual(Draft.follow(was, [K("rule:3:1A|Maths|1|4", "rule", { id: 7, row: "Group 2" })]), null);
});
t("follow: nothing to follow gives null and a was without where never throws", () => {
  assert.strictEqual(Draft.follow({ key: "dep:1", kind: "deployment", where: null }, [K("dep:2", "deployment")]), null);
  assert.strictEqual(Draft.follow({ key: "t:1", kind: "typed", where: { teacher: "Ms X" } }, [K("t:2", "typed", { teacher: "Ms X" })]), null);
  assert.strictEqual(Draft.follow({ key: "clash:A", kind: "clash" }, [K("clash:B", "clash", { teacher: "Ms X" })]), null);
  assert.strictEqual(Draft.follow({ key: "rule:1:a|b|0|0", kind: "rule" }, [K("rule:1:a|b|0|1", "rule")]), null);
  assert.strictEqual(Draft.follow({ key: "clash:A", kind: "clash", where: null }, []), null);
  assert.strictEqual(Draft.follow({ key: "clash:A", kind: "clash", where: null }, undefined), null);
});

t("askSummary: the reply, the count of more lessons, what was asked beyond the ask, an error", () => {
  const ok = o => Object.assign({ ok: true, understood: true, reply: "Moving PE for 2A off Friday.", more: 0, keep: [] }, o);
  assert.equal(Draft.askSummary(ok()), "Moving PE for 2A off Friday.");
  assert.equal(Draft.askSummary(ok({ more: 3 })), "Moving PE for 2A off Friday. 3 more lessons match.");
  assert.equal(Draft.askSummary(ok({ keep: ["keep the doubles together", "not before recess"] })), "Moving PE for 2A off Friday. You also asked: keep the doubles together; not before recess. The app did not check this: look at the preview before you apply.");
  assert.equal(Draft.askSummary(ok({ more: 2, keep: ["keep the doubles together"] })), "Moving PE for 2A off Friday. 2 more lessons match. You also asked: keep the doubles together. The app did not check this: look at the preview before you apply.");
  assert.equal(Draft.askSummary({ ok: false, error: "Keep the request under 300 characters." }), "Keep the request under 300 characters.");
  assert.equal(Draft.askSummary(ok({ understood: false, reply: "I did not follow that.", keep: [] })), "I did not follow that.");
  assert.equal(Draft.askSummary(ok({ reply: "", more: 1 })), "1 more lessons match.");
  assert.equal(Draft.askSummary(null), "");
  assert.equal(Draft.askSummary(ok({ reply: undefined, keep: undefined, more: undefined })), "");
});
t("choiceWord: the question's word for the field", () => {
  assert.deepEqual(["classes", "subject", "teacher", "new_teacher", "new_room"].map(Draft.choiceWord), ["class", "subject", "teacher", "teacher", "room"]);
  assert.equal(Draft.choiceWord("whatever"), "name");
});

console.log(n + " checks passed");

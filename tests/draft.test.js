// Plain-assert tests for static/draft.js (the warning list on step 8): run with `node tests/draft.test.js`
const assert = require("assert");
const Draft = require("../static/draft.js");
let n = 0; const t = (name, f) => { f(); n++; };
const W = (key, kind, group, decision, strength, crit) => ({ key, kind, text: key, strength: strength || "Must", group, where: null, sides: null, ops: null, decision, crit: crit || "" });
const ws = () => [W("c1", "clash", "Ms X", null, null, "teacher"), W("d1", "deployment", "1A"), W("d2", "deployment", "1A", { answer: "step5" }), W("d3", "deployment", "1B", { answer: "left" }), W("r1", "rule", "School", null, "Prefer"), W("c2", "clash", "1A", { answer: "step5" }, null, "class")];
t("grouping by kind then group, open only", () => {
  const g = Draft.group(ws(), "open");
  assert.deepEqual(g.map(x => x.kind), ["clash", "deployment", "rule"]);
  assert.deepEqual(g[1].groups.map(x => [x.name, x.items.length]), [["1A", 1], ["1B", 1]]);
  assert.equal(g[1].title, "Differences from the deployment");
  assert.deepEqual(Draft.group(ws(), "open").map(g => g.groups.length), [1, 2, 1]);   // an old "left" decision is open
  assert.equal(Draft.group(ws(), "all")[1].groups[0].items.length, 2);
  assert.deepEqual(Draft.group([], "all"), []);
});
t("groups keep first-seen order", () => {
  const g = Draft.group([W("a", "clash", "Z"), W("b", "clash", "A"), W("c", "clash", "Z")], "all");
  assert.deepEqual(g[0].groups.map(x => [x.name, x.items.length]), [["Z", 2], ["A", 1]]);
});
t("counts", () => {
  assert.deepEqual(Draft.counts(ws()), { open: 4, critical: 2, step5: 2, met: 0, must: 3, prefer: 1 });
  assert.deepEqual(Draft.counts(ws().concat([W("t1:again", "typed", "School", { answer: "met" })])), { open: 4, critical: 2, step5: 2, met: 1, must: 3, prefer: 1 });
  assert.deepEqual(Draft.counts([]), { open: 0, critical: 0, step5: 0, met: 0, must: 0, prefer: 0 });
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
  assert.equal(Draft.answerText({ decision: { answer: "left" } }), "");
  assert.equal(Draft.answerText({ decision: { answer: "step5" } }), "Step 5 updated");
  assert.equal(Draft.answerText({ decision: { answer: "fixed" } }), "Fixed");
  assert.equal(Draft.answerText({ decision: { answer: "met" } }), "Checked: still met");
  assert.equal(Draft.answerText({ decision: null }), "");
});
t("critical: the warnings with crit, in order", () => {
  assert.deepEqual(Draft.critical(ws()).map(w => w.key), ["c1", "c2"]);
  assert.deepEqual(Draft.critical([]), []);
  assert.deepEqual(Draft.critical(undefined), []);
});
t("gateText", () => {
  assert.strictEqual(Draft.gateText(0), "");
  assert.strictEqual(Draft.gateText(1), "1 critical mistake to settle on step 8 first.");
  assert.strictEqual(Draft.gateText(3), "3 critical mistakes to settle on step 8 first.");
});
t("critWord", () => {
  assert.deepEqual(["teacher", "class", "room", "break", "noteacher"].map(Draft.critWord), ["Teacher in two places", "Class clash", "Room used twice", "In a break or outside the day", "No teacher"]);
  assert.strictEqual(Draft.critWord(""), "");
  assert.strictEqual(Draft.critWord("other"), "");
  assert.strictEqual(Draft.critWord(undefined), "");
});
t("kinds", () => { assert.deepEqual(Draft.KINDS, ["clash", "room", "deployment", "rule", "typed", "choice"]); assert.equal(Draft.KIND_TEXT.room, "No room"); assert.equal(Draft.KIND_TEXT.typed, "Rules in words"); });
t("whereText: only the parts a warning's where has", () => {
  assert.deepStrictEqual(Draft.whereText({ where: { cls: "1A", day: "Mon", period: 0, id: 3, row: "Entire Class" } }), ["1A", "Mon", "period 0"]);
  assert.deepStrictEqual(Draft.whereText({ where: { teacher: "Ms Ong" } }), ["Ms Ong"]);
  assert.deepStrictEqual(Draft.whereText({ where: { cls: "2B" } }), ["2B"]);
  assert.deepStrictEqual(Draft.whereText({ where: { cls: "", day: "Tue", period: 4 } }), ["Tue", "period 4"]);
  assert.deepStrictEqual(Draft.whereText({ where: null }), []);
});

t("fixTarget: the class or teacher a warning is about", () => {
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
  assert.equal(Draft.askSummary(ok({ reply: "", more: 1 })), "1 more lesson matches.");
  assert.equal(Draft.askSummary(null), "");
  assert.equal(Draft.askSummary(ok({ reply: undefined, keep: undefined, more: undefined })), "");
});
t("choiceWord: the question's word for the field", () => {
  assert.deepEqual(["classes", "subject", "teacher", "new_teacher", "new_room"].map(Draft.choiceWord), ["class", "subject", "teacher", "teacher", "room"]);
  assert.equal(Draft.choiceWord("whatever"), "name");
});
t("critWord: notplaced; an unknown word still gives nothing", () => {
  assert.strictEqual(Draft.critWord("notplaced"), "Not placed");
  assert.strictEqual(Draft.critWord("nope"), "");
});
t("a room warning is grouped under No room, after clashes and before the deployment", () => {
  const g = Draft.group([W("d1", "deployment", "1A"), W("m1", "room", "Maths 1A"), W("m2", "room", "Art 1B"), W("c1", "clash", "Ms X", null, null, "teacher")], "open");
  assert.deepEqual(g.map(x => x.kind), ["clash", "room", "deployment"]);
  assert.equal(g[1].title, "No room");
  assert.deepEqual(g[1].groups.map(x => x.name), ["Maths 1A", "Art 1B"]);
});

t("others: the open warnings that are not critical, counted directly", () => {
  assert.strictEqual(Draft.others(ws()), 3);   // d1, d3 (an old "left" is open) and r1; c1 is critical, d2 and c2 are settled
  assert.strictEqual(Draft.others(ws().concat([W("c3", "clash", "1A", { answer: "met" }, null, "teacher")])), 3);   // a settled critical one never takes one off
  assert.strictEqual(Draft.others([]), 0); assert.strictEqual(Draft.others(undefined), 0);
});
t("follow: a settled clash is not followed onto a lesson waiting in Not placed", () => {
  const was = { key: "clash:Class clash: 1A", kind: "clash", where: { cls: "1A" } };
  assert.strictEqual(Draft.follow(was, [Object.assign(K("clash:notplaced:7", "clash", { cls: "1A", id: 7 }), { crit: "notplaced" })]), null);
  assert.deepEqual(Draft.follow(was, [Object.assign(K("clash:notplaced:7", "clash", { cls: "1A", id: 7 }), { crit: "notplaced" }), Object.assign(K("clash:Class clash: 1A on Tue", "clash", { cls: "1A" }), { crit: "class" })]), { key: "clash:Class clash: 1A on Tue", how: "changed" });
});
t("refitTotals: the totals line, with singulars and the typed rules", () => {
  const T = (o) => Object.assign({ changes: 3, moved: 3, another_day: 1, critical: [2, 0], warnings: [4, 3], typed: [] }, o);
  assert.strictEqual(Draft.refitTotals(T({ typed: [5, 2] })), "3 lessons move, 1 to another day · Critical 2 → 0 · Warnings 4 → 3 · 2 typed rules to check again (T2, T5)");
  assert.strictEqual(Draft.refitTotals(T({ moved: 1, another_day: 0 })), "1 lesson moves, 0 to another day · Critical 2 → 0 · Warnings 4 → 3");   // no typed part when there are none
  assert.strictEqual(Draft.refitTotals(T({ typed: [2] })).split(" · ")[3], "1 typed rule to check again (T2)");
  assert.strictEqual(Draft.refitTotals(T({ typed: [1, 2, 3, 4, 5, 6, 7, 8] })).split(" · ")[3], "8 typed rules to check again (T1, T2, T3, T4, T5, T6, T7, T8)");   // up to eight are named
  assert.strictEqual(Draft.refitTotals(T({ typed: [1, 2, 3, 4, 5, 6, 7, 8, 9] })).split(" · ")[3], "9 typed rules to check again");
  assert.strictEqual(Draft.refitTotals(T({ typed: [10, 9, 2] })).split(" · ")[3], "3 typed rules to check again (T2, T9, T10)");   // numerically, not as text
  assert.strictEqual(Draft.refitTotals(T({ moved: 0, another_day: 0, critical: [0, 0], warnings: [1, 0] })), "0 lessons move, 0 to another day · Critical 0 → 0 · Warnings 1 → 0");
  assert.strictEqual(Draft.refitTotals(null), ""); assert.strictEqual(Draft.refitTotals({}), "");
});
t("refitRise: a number that goes up", () => {
  assert.strictEqual(Draft.refitRise({ critical: [1, 0], warnings: [3, 3] }), false);
  assert.strictEqual(Draft.refitRise({ critical: [1, 2], warnings: [3, 3] }), true);
  assert.strictEqual(Draft.refitRise({ critical: [1, 0], warnings: [3, 4] }), true);
  assert.strictEqual(Draft.refitRise(null), false);
});
t("refitApplyWord, refitKeeps and refitDone: the words of the button, the footer and the toast", () => {
  assert.strictEqual(Draft.refitApplyWord(4), "Apply all 4 changes"); assert.strictEqual(Draft.refitApplyWord(1), "Apply 1 change");
  assert.strictEqual(Draft.refitKeeps(4), "The app keeps a version “Before re-fit …” first and applies all 4 changes as one; Undo takes the whole re-fit back.");
  assert.strictEqual(Draft.refitKeeps(1), "The app keeps a version “Before re-fit …” first and applies the change; Undo takes the whole re-fit back.");
  assert.strictEqual(Draft.refitDone(4, "Before re-fit, 22 Nov 1.12 pm"), "Re-fit applied: 4 changes. The draft before is kept as version “Before re-fit, 22 Nov 1.12 pm”.");
  assert.strictEqual(Draft.refitDone(1, null), "Re-fit applied: 1 change.");
});
t("refitRunning: what the window says while the job runs", () => {
  assert.strictEqual(Draft.refitRunning(0, null), "Starting…"); assert.strictEqual(Draft.refitRunning(0, 0), "Starting…"); assert.strictEqual(Draft.refitRunning(undefined, undefined), "Starting…");
  assert.strictEqual(Draft.refitRunning(0, 6), "Looking at 0 of 6…"); assert.strictEqual(Draft.refitRunning(3, 6), "Looking at 3 of 6…");
  assert.strictEqual(Draft.refitRunning(6, 6), "Checking the list…");
});
t("refitTags: the typed rules of a step are one chip", () => {
  assert.deepEqual(Draft.refitTags([]), []); assert.deepEqual(Draft.refitTags(null), []);
  assert.deepEqual(Draft.refitTags(["another day", "no room"]), [{ text: "another day", title: "", kind: "day" }, { text: "no room", title: "", kind: "plain" }]);
  assert.deepEqual(Draft.refitTags(["check T2 again"]), [{ text: "check T2 again", title: "", kind: "typed" }]);
  assert.deepEqual(Draft.refitTags(["another day", "check T5 again", "no room", "check T2 again"]), [{ text: "another day", title: "", kind: "day" }, { text: "check T2, T5 again", title: "", kind: "typed" }, { text: "no room", title: "", kind: "plain" }]);
  const four = Draft.refitTags([4, 3, 2, 1].map(n => `check T${n} again`)); assert.deepEqual(four, [{ text: "check T1, T2, T3, T4 again", title: "", kind: "typed" }]);
  const many = Array.from({ length: 17 }, (_, i) => `check T${i + 1} again`), g = Draft.refitTags(many.concat(["another day"]));
  assert.strictEqual(g.length, 2); assert.strictEqual(g[0].text, "check 17 typed rules again"); assert.strictEqual(g[0].kind, "typed"); assert.strictEqual(g[0].title, "T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, T14, T15, T16, T17"); assert.strictEqual(g[1].text, "another day");
  assert.strictEqual(Draft.refitTags(["check T2 again", "check T2 again"])[0].text, "check T2 again");   // a number twice is one
  assert.strictEqual(Draft.refitTags(["check T1 again", "check T2 again", "check T3 again", "check T4 again", "check T5 again"])[0].text, "check 5 typed rules again");
});
t("refitSplit: the long list of what does not fit is cut after twelve", () => {
  const L = n => Array.from({ length: n }, (_, i) => "t" + i);
  assert.deepEqual(Draft.refitSplit(L(12)), { head: L(12), rest: [] });
  const s = Draft.refitSplit(L(17)); assert.strictEqual(s.head.length, 12); assert.deepEqual(s.rest, ["t12", "t13", "t14", "t15", "t16"]);
  assert.deepEqual(Draft.refitSplit(null), { head: [], rest: [] });
});
console.log(n + " checks passed");

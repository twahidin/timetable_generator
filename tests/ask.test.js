// Plain-assert tests for static/ask.js (the Ask tab's plain functions): run with `node tests/ask.test.js`
const assert = require("assert");
const Board = require("../static/board.js");
const Ask = require("../static/ask.js");
let n = 0; const t = (name, f) => { try { f(); } catch (e) { console.error("FAILED: " + name); throw e; } n++; };

const row = (group, subject, teachers, room) => ({ group: group, subject: subject, teachers: teachers, tshorts: teachers, room: room, key: group + subject });
const card = (id, d, p, k, classes, rows, extra) => Object.assign({ id: id, d: d, p: p, n: k, classes: classes, band: "", what: "", rows: rows, marks: [] }, extra || {});
const board = (cards) => ({ days: ["Mon", "Tue"], NP: 6, levels: [{ level: "Sec 1", classes: ["1A", "1B"] }], codes: {}, subjects: {}, cards: cards });
const band = card(7, 0, 1, 1, ["1A", "1B"], [row("Group 1", "Maths", ["Mr Tan"], "R1"), row("Group 2", "Art", ["Ms Lee"], "R2")], { band: "MA" });

t("ofCard: a plain click, a teacher's row and a room's row", () => {
  assert.deepStrictEqual(Ask.ofCard(band, null), { kind: "lesson", id: 7, group: null, teacher: null });
  assert.deepStrictEqual(Ask.ofCard(band, { by: "teacher", name: "Ms Lee" }), { kind: "lesson", id: 7, group: "Group 2", teacher: "Ms Lee" });
  assert.deepStrictEqual(Ask.ofCard(band, { by: "teacher", name: "Mr Tan" }), { kind: "lesson", id: 7, group: "Group 1", teacher: "Mr Tan" });
  assert.deepStrictEqual(Ask.ofCard(band, { by: "room", name: "R2" }), { kind: "lesson", id: 7, group: "Group 2", teacher: null });
  assert.deepStrictEqual(Ask.ofCard(band, { by: "class", name: "1A" }), { kind: "lesson", id: 7, group: null, teacher: null });
});

t("ofPlace: a class row's name is cls", () => {
  assert.deepStrictEqual(Ask.ofPlace({ cls: "1A", by: "class", name: "", d: 1, p: 2 }), { kind: "place", by: "class", name: "1A", d: 1, p: 2 });
  assert.deepStrictEqual(Ask.ofPlace({ cls: "", by: "teacher", name: "Mr Tan", d: 0, p: 3 }), { kind: "place", by: "teacher", name: "Mr Tan", d: 0, p: 3 });
});

t("pointable: every row's place but the No teacher and No room rows", () => {
  assert.strictEqual(Ask.pointable({ cls: "1A", by: "class", name: "", d: 0, p: 1 }), true);
  assert.strictEqual(Ask.pointable({ cls: "", by: "teacher", name: "Mr Tan", d: 0, p: 1 }), true);
  assert.strictEqual(Ask.pointable({ cls: "", by: "room", name: "R1", d: 0, p: 1 }), true);
  assert.strictEqual(Ask.pointable({ cls: "", by: "teacher", name: "", d: 0, p: 1 }), false);
  assert.strictEqual(Ask.pointable({ cls: "", by: "room", name: "", d: 0, p: 1 }), false);
});

t("empty: nothing covers the period; a two-period card covers its second period", () => {
  const two = card(1, 0, 2, 2, ["1A"], [row("Entire Class", "Maths", ["Mr Tan"], "R1")]), b = board([two]);
  assert.strictEqual(Ask.empty(b, { cls: "1A", by: "class", name: "", d: 0, p: 2 }), false);
  assert.strictEqual(Ask.empty(b, { cls: "1A", by: "class", name: "", d: 0, p: 3 }), false);
  assert.strictEqual(Ask.empty(b, { cls: "1A", by: "class", name: "", d: 0, p: 4 }), true);
  assert.strictEqual(Ask.empty(b, { cls: "1A", by: "class", name: "", d: 0, p: 1 }), true);
  assert.strictEqual(Ask.empty(b, { cls: "1B", by: "class", name: "", d: 0, p: 2 }), true);
  assert.strictEqual(Ask.empty(b, { cls: "1A", by: "class", name: "", d: 1, p: 2 }), true);
  assert.strictEqual(Ask.empty(b, { cls: "", by: "teacher", name: "Mr Tan", d: 0, p: 3 }), false);
  assert.strictEqual(Ask.empty(b, { cls: "", by: "teacher", name: "Ms Lee", d: 0, p: 3 }), true);
  assert.strictEqual(Ask.empty(b, { cls: "", by: "room", name: "R1", d: 0, p: 2 }), false);
  assert.strictEqual(Ask.empty(b, { cls: "", by: "room", name: "R9", d: 0, p: 2 }), true);
});

t("empty: a card waiting in Not placed covers nothing", () => {
  const tray = card(2, null, null, 1, ["1A"], [row("Entire Class", "Maths", ["Mr Tan"], "R1")]);
  assert.strictEqual(Ask.empty(board([tray]), { cls: "1A", by: "class", name: "", d: 0, p: 0 }), true);
});

t("groups: a choice only for a card with more than one row", () => {
  assert.deepStrictEqual(Ask.groups(band), [{ group: "Group 1", label: "Group 1 · Maths" }, { group: "Group 2", label: "Group 2 · Art" }]);
  assert.deepStrictEqual(Ask.groups(card(1, 0, 0, 1, ["1A"], [row("Entire Class", "Maths", [], "")])), []);
});

t("starters: a lesson on the timetable, in the tray, and a place", () => {
  const sub = { kind: "lesson", id: 7, group: null, teacher: null };
  assert.deepStrictEqual(Ask.starters(sub, band), [
    { q: "swaps", label: "What can this swap with?" }, { q: "moves", label: "Where else can it go?" }, { q: "teachers", label: "Who else could teach it?" },
    { q: "trades", label: "Who could I trade this class with?" }, { q: "rooms", label: "Which rooms could it use?" }]);
  const tray = card(8, null, null, 1, ["1A"], [row("Entire Class", "Maths", [], "")]);
  const s = Ask.starters(sub, tray);
  assert.deepStrictEqual(s, [{ q: "moves", label: "Where can it go?" }, { q: "teachers", label: "Who else could teach it?" }, { q: "rooms", label: "Which rooms could it use?" }]);
  assert.ok(!s.some(x => x.q === "swaps" || x.q === "trades"));
  assert.deepStrictEqual(Ask.starters({ kind: "place", by: "class", name: "1A", d: 0, p: 1 }, null),
    [{ q: "fill", label: "What can go here?" }, { q: "free", label: "Who is free then?" }]);
});

t("query: a lesson, with and without a group and teacher; a place; values escaped", () => {
  assert.strictEqual(Ask.query({ kind: "lesson", id: 7, group: null, teacher: null }, "moves"), "q=moves&kind=lesson&id=7");
  assert.strictEqual(Ask.query({ kind: "lesson", id: 7, group: "Group 2", teacher: "Ms Lee" }, "rooms"), "q=rooms&kind=lesson&id=7&group=Group%202&teacher=Ms%20Lee");
  assert.strictEqual(Ask.query({ kind: "place", by: "class", name: "1 A&B", d: 1, p: 2 }, "fill"), "q=fill&kind=place&by=class&name=1%20A%26B&d=1&p=2");
});

t("verdict: the three states", () => {
  assert.deepStrictEqual(Ask.verdict({ state: "ok" }), { text: "Clean", cls: "ok" });
  assert.deepStrictEqual(Ask.verdict({ state: "prefer" }), { text: "Bends a rule", cls: "prefer" });
  assert.deepStrictEqual(Ask.verdict({ state: "no" }), { text: "Lands with a problem", cls: "no" });
});

t("send: one fix, two fixes, anyway and none", () => {
  const fix = { kind: "move", id: 7, d: 1, p: 2 }, o = { fixes: [fix], text: "x", disturbs: [], state: "ok", why: "", apply: "yes" };
  assert.deepStrictEqual(Ask.send(o, "s1"), { url: "/api/draft/fix", body: { kind: "move", id: 7, d: 1, p: 2, stamp: "s1" } });
  assert.deepStrictEqual(fix, { kind: "move", id: 7, d: 1, p: 2 });   // the option's own fix is not changed
  const f2 = { kind: "swap", a: 1, b: 2 };
  assert.deepStrictEqual(Ask.send({ fixes: [fix, f2], apply: "yes", why: "" }, "s2"), { url: "/api/draft/fixes", body: { fixes: [fix, f2], stamp: "s2" } });
  assert.deepStrictEqual(Ask.send({ fixes: [fix], apply: "anyway", why: "Clash" }, "s3"),
    { url: "/api/draft/fix", body: { kind: "move", id: 7, d: 1, p: 2, stamp: "s3", force: true, why: "Clash" } });
  assert.strictEqual(Ask.send({ fixes: [fix], apply: "none", why: "" }, "s4"), null);
});

t("stale: the board has moved on since the answer", () => {
  assert.strictEqual(Ask.stale({ stamp: "a" }, "a"), false);
  assert.strictEqual(Ask.stale({ stamp: "a" }, "b"), true);
});

t("target: the lesson Show on the board goes to", () => {
  const o = (f) => ({ fixes: [f] });
  assert.strictEqual(Ask.target(o({ kind: "move", id: 3, d: 0, p: 0 })), 3);
  assert.strictEqual(Ask.target(o({ kind: "place", id: 4, d: 0, p: 0 })), 4);
  assert.strictEqual(Ask.target(o({ kind: "room", id: 5, group: "g", room: "R" })), 5);
  assert.strictEqual(Ask.target(o({ kind: "swap", a: 6, b: 9 })), 6);
  assert.strictEqual(Ask.target(o({ kind: "teacher", key: "k", teachers: [] })), null);
  assert.strictEqual(Ask.target(o({ kind: "add", key: "k", d: 0, p: 0, n: 1, room: "" })), null);
  assert.strictEqual(Ask.target(o({ kind: "trade", a: 1, b: 2, x: 3, y: 4 })), null);
  assert.strictEqual(Ask.target({ fixes: [] }), null);
});

t("tabLabel: a lesson's page and an empty period's", () => {
  assert.strictEqual(Ask.tabLabel({ kind: "lesson", id: 3 }), "Lesson");
  assert.strictEqual(Ask.tabLabel({ kind: "place", by: "class", name: "1A", d: 0, p: 2 }), "Empty period");
});
t("parts: what the page holds", () => {
  const rows = [{ group: "G1", subject: "Science" }, { group: "G2", subject: "Science" }];
  const on = { id: 3, d: 0, p: 2, n: 1, rows }, tray = { id: 4, d: null, p: null, n: 1, rows };
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: 3, group: null }, on), { lift: true, del: true, lists: true, group: "G1" });
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: 3, group: "G2" }, on), { lift: true, del: true, lists: true, group: "G2" });
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: 4, group: null }, tray), { lift: false, del: true, lists: true, group: "G1" });
  const none = { lift: false, del: false, lists: false, group: null };
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: 9, group: null }, null), none);   // deleted meanwhile
  assert.deepStrictEqual(Ask.parts({ kind: "place", by: "class", name: "1A", d: 0, p: 2 }, null), none);
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: "a:k" }, { id: "a:k", d: null, p: null, rows: [], entry: {} }), none);
});
t("where: the line under a lesson's name", () => {
  assert.strictEqual(Ask.where({ d: 0, p: 20, band: "" }, "Mon", "2.20", ""), "Mon period 20 (2.20)");
  assert.strictEqual(Ask.where({ d: 0, p: 20, band: "B", rows: [1, 2, 3, 4, 5] }, "Mon", "", ""), "Mon period 20 · 5 groups");
  assert.strictEqual(Ask.where({ d: 0, p: 3, band: "B", rows: [1] }, "Mon", "", ""), "Mon period 3 · 1 group");
  assert.strictEqual(Ask.where({ d: null, p: null, band: "" }, "", "", "was Tue period 4"), "Not placed (was Tue period 4)");
  assert.strictEqual(Ask.where({ d: null, p: null, band: "" }, "", "", ""), "Not placed");
});

console.log(`${n} cases passed`);

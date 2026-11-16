// Plain-assert tests for static/board.js (the board's rows, lanes and drag answers): run with `node tests/board.test.js`
const assert = require("assert");
const Board = require("../static/board.js");
let n = 0; const t = (name, f) => { try { f(); } catch (e) { console.error("FAILED: " + name); throw e; } n++; };

const card = (id, d, p, k, classes, extra) => Object.assign({ id: id, d: d, p: p, n: k, classes: classes, band: "", what: "",
  rows: [{ group: "Entire Class", subject: "Maths", teachers: ["Mr Tan"], tshorts: ["TAN"], room: "R1" }] }, extra || {});
const board = (cards) => ({
  days: ["Mon", "Tue"], NP: 6, times: [],
  levels: [{ level: "Sec 1", classes: ["1A", "1B"] }, { level: "Sec 2", classes: ["2A"] }],
  codes: { "1A": ["LLLRLL", "LLLRLL"], "1B": ["LLLRLL", "LLLRLL"], "2A": ["LLLRLL", "LLLRLL"] },
  subjects: { Maths: ["MA", 3, "Maths Dept"], Science: ["SC", 5, "Science Dept"], Art: ["ART", 7, ""] },
  palette: [], cards: cards });

t("lanes: two lessons at the same time are stacked, neither is lost", () => {
  const a = card(1, 0, 1, 2, ["1A"]), b = card(2, 0, 2, 1, ["1A"]), c = card(3, 0, 3, 1, ["1A"]);
  assert.deepStrictEqual(Board.lanes([c, b, a]), [{ card: a, lane: 0 }, { card: b, lane: 1 }, { card: c, lane: 0 }]);
});

t("lanes: same start, the longer first, then the lower id", () => {
  const a = card(4, 0, 1, 1, ["1A"]), b = card(2, 0, 1, 2, ["1A"]), c = card(3, 0, 1, 1, ["1A"]);
  assert.deepStrictEqual(Board.lanes([a, c, b]), [{ card: b, lane: 0 }, { card: c, lane: 1 }, { card: a, lane: 2 }]);
  assert.deepStrictEqual(Board.lanes([]), []);
});

t("groups, day: a row per class under its level, a band piece in each of its classes' rows", () => {
  const band = card(5, 0, 0, 2, ["1A", "2A"], { band: "MT" }), g = Board.groups(board([band, card(6, 1, 0, 1, ["1B"])]), { kind: "day", d: 0 });
  assert.deepStrictEqual(g.map(x => [x.name, x.rows.map(r => r.key)]), [["Sec 1", ["1A", "1B"]], ["Sec 2", ["2A"]]]);
  assert.strictEqual(g[0].rows[0].cards[0].card, band); assert.strictEqual(g[1].rows[0].cards[0].card, band);
  assert.deepStrictEqual(g[0].rows[1].cards, []); assert.strictEqual(g[0].rows[1].lanes, 1); assert.strictEqual(g[0].rows[0].codes, "LLLRLL");
  assert.strictEqual(g[0].rows[0].label, "1A"); assert.strictEqual(g[0].rows[0].cls, "1A"); assert.strictEqual(g[0].rows[0].d, 0);
});

t("groups, day: a lesson with no class has a row of its own", () => {
  const lone = card(7, 0, 2, 1, []), g = Board.groups(board([lone, card(8, 0, 0, 1, ["1A"])]), { kind: "day", d: 0 });
  assert.strictEqual(g.length, 3);
  assert.strictEqual(g[2].name, "No class"); assert.strictEqual(g[2].rows.length, 1);
  assert.deepStrictEqual(Object.assign({}, g[2].rows[0], { cards: undefined }),
    { key: "", label: "No class", d: 0, cls: "", codes: "LLLLLL", lanes: 1, cards: undefined });
  assert.deepStrictEqual(g[2].rows[0].cards, [{ card: lone, lane: 0 }]);
  assert.strictEqual(g[0].rows[0].cards.length, 1);
  const none = Board.groups(board([card(8, 0, 0, 1, ["1A"])]), { kind: "day", d: 0 });
  assert.deepStrictEqual(none.map(x => x.name), ["Sec 1", "Sec 2"]);
});

t("groups, day: a lesson in recess is in its row", () => {
  const rec = card(9, 0, 3, 1, ["1A"]), g = Board.groups(board([rec]), { kind: "day", d: 0 });
  assert.strictEqual(g[0].rows[0].codes[3], "R");
  assert.deepStrictEqual(g[0].rows[0].cards, [{ card: rec, lane: 0 }]);
});

t("groups, day: stacked cards raise the row's lanes; a class with no codes gets dots; a card is never twice in a row", () => {
  const a = card(1, 0, 1, 2, ["1A", "1A"]), b = card(2, 0, 2, 1, ["1A"]);
  const bd = board([a, b]); delete bd.codes["1B"];
  const g = Board.groups(bd, { kind: "day", d: 0 });
  assert.strictEqual(g[0].rows[0].lanes, 2); assert.strictEqual(g[0].rows[0].cards.length, 2);
  assert.strictEqual(g[0].rows[1].codes, "......");
  assert.deepStrictEqual(g[0].rows[0].cards.map(x => x.card.id), [1, 2]);
});

t("groups, cycle: a row per day for one class, grouped by week", () => {
  const a = card(1, 0, 1, 1, ["1A"]), b = card(2, 1, 2, 1, ["1A"]), c = card(3, 1, 0, 1, ["1B"]), e = card(4, 0, 0, 1, ["1B"]);
  const weeks = [{ name: "Odd", days: [{ i: 0, label: "Mon" }] }, { name: "Even", days: [{ i: 1, label: "Mon" }] }];
  const g = Board.groups(board([a, b, c, e]), { kind: "cycle", cls: "1A" }, weeks);
  assert.deepStrictEqual(g.map(x => [x.name, x.rows.map(r => [r.key, r.label, r.d, r.cls, r.codes])]),
    [["Odd", [["0", "Mon", 0, "1A", "LLLRLL"]]], ["Even", [["1", "Mon", 1, "1A", "LLLRLL"]]]]);
  assert.deepStrictEqual(g[0].rows[0].cards, [{ card: a, lane: 0 }]);
  assert.deepStrictEqual(g[1].rows[0].cards, [{ card: b, lane: 0 }]);
  const none = Board.groups(board([a]), { kind: "cycle", cls: "9Z" }, [{ name: "", days: [{ i: 0, label: "Mon" }] }]);
  assert.strictEqual(none[0].rows[0].codes, "......"); assert.deepStrictEqual(none[0].rows[0].cards, []);
});

t("open: only L and A are open", () => {
  assert.deepStrictEqual(["L", "A", "R", ".", ""].map(Board.open), [true, true, false, false, false]);
});

t("box: a lesson that runs past the day is kept on the board", () => { assert.deepStrictEqual(Board.box(card(1, 0, 5, 3, ["1A"]), 6), { from: 5, to: 5 }); assert.deepStrictEqual(Board.box(card(1, 0, 9, 1, ["1A"]), 6), { from: 5, to: 5 }); assert.deepStrictEqual(Board.box(card(1, 0, 1, 0, ["1A"]), 6), { from: 1, to: 1 }); assert.deepStrictEqual(Board.box(card(1, 0, 1, 3, ["1A"]), 6), { from: 1, to: 3 }); });

t("lines: a plain lesson, one with no teacher and no room, a band of one and of three groups", () => {
  const bd = board([]);
  assert.deepStrictEqual(Board.lines(card(1, 0, 0, 1, ["1A"], { rows: [{ group: "G", subject: "Maths", teachers: ["Mr Tan", "Ms Lim"], tshorts: ["TAN", "LIM"], room: "R1" }] }), bd),
    { title: "MA", lines: ["TAN, LIM", "R1"], color: 3 });
  assert.deepStrictEqual(Board.lines(card(1, 0, 0, 1, ["1A"], { rows: [{ group: "G", subject: "Drama", teachers: [], tshorts: [], room: "" }] }), bd),
    { title: "Drama", lines: ["No teacher", "No room"], color: 0 });
  const r = (s) => ({ group: "G", subject: s, teachers: [], tshorts: [], room: "" });
  assert.deepStrictEqual(Board.lines(card(1, 0, 0, 1, ["1A"], { band: "MT", rows: [r("Science")] }), bd), { title: "MT", lines: ["1 group"], color: 5 });
  assert.deepStrictEqual(Board.lines(card(1, 0, 0, 1, ["1A"], { band: "MT", rows: [r("Maths"), r("Science"), r("Art")] }), bd), { title: "MT", lines: ["3 groups"], color: 3 });
});

t("finds and matches: departments first, then subjects, only those on a card", () => {
  const r = (s) => ({ group: "G", subject: s, teachers: [], tshorts: [], room: "" });
  const cards = [card(1, 0, 0, 1, ["1A"], { rows: [r("Science")] }), card(2, 0, 1, 1, ["1A"], { rows: [r("Maths")] }),
    card(3, 0, 2, 1, ["1A"], { rows: [r("Art"), r("Drama")] })];
  const bd = board(cards);
  assert.deepStrictEqual(Board.finds(bd), [{ value: "", label: "All subjects" },
    { value: "d:Maths Dept", label: "Maths Dept (department)" }, { value: "d:Science Dept", label: "Science Dept (department)" },
    { value: "s:Art", label: "Art" }, { value: "s:Drama", label: "Drama" }, { value: "s:Maths", label: "Maths" }, { value: "s:Science", label: "Science" }]);
  assert.deepStrictEqual(Board.finds(board([])), [{ value: "", label: "All subjects" }]);
  assert.strictEqual(Board.matches(cards[0], "", bd), true);
  assert.strictEqual(Board.matches(cards[0], "s:Science", bd), true);
  assert.strictEqual(Board.matches(cards[0], "s:Maths", bd), false);
  assert.strictEqual(Board.matches(cards[0], "d:Science Dept", bd), true);
  assert.strictEqual(Board.matches(cards[0], "d:Maths Dept", bd), false);
  assert.strictEqual(Board.matches(cards[2], "s:Drama", bd), true);
  assert.strictEqual(Board.matches(cards[2], "d:", bd), false);
  assert.strictEqual(Board.matches(cards[2], "s:Nothing", bd), false);
});

t("grab and start: a two-period card held by its second period starts one earlier", () => { assert.strictEqual(Board.grab(card(1, 0, 2, 2, ["1A"]), 3), 1); assert.strictEqual(Board.start(4, 1), 3); assert.strictEqual(Board.start(0, 1), 0); assert.strictEqual(Board.grab(card(1, 0, 2, 2, ["1A"]), 9), 1); assert.strictEqual(Board.grab(card(1, 0, 2, 2, ["1A"]), 0), 0); assert.strictEqual(Board.grab(card(1, 0, 2, 2, ["1A"]), 2), 0); });

t("slot, states, can: the card's own place, a clean place, a clash, a place with no answer", () => {
  const c = card(1, 0, 2, 1, ["1A"]);
  const slots = [{ d: 0, p: 1, state: "ok", why: "", swap: null, also: [] }, { d: 0, p: 3, state: "no", why: "Mr Tan is teaching.", swap: null, also: [] },
    { d: 0, p: 4, state: "na", why: "", swap: null, also: [] }, { d: 0, p: 5, state: "prefer", why: "", swap: null, also: [] },
    { d: 1, p: 2, state: "ok", why: "", swap: null, also: [] }];
  assert.deepStrictEqual(Board.states(c, slots, 0, 6), ["", "ok", "own", "no", "na", "prefer"]);
  assert.deepStrictEqual(Board.states(c, slots, 1, 6), ["", "", "ok", "", "", ""]);
  assert.deepStrictEqual(Board.slot(c, slots, 0, 2), { d: 0, p: 2, state: "own", why: "", swap: null, also: [] });
  assert.strictEqual(Board.slot(c, slots, 0, 1), slots[0]);
  assert.strictEqual(Board.slot(c, slots, 0, 0), null);
  assert.strictEqual(Board.slot(c, null, 0, 1), null);
  assert.deepStrictEqual(Board.slot(c, undefined, 0, 2), { d: 0, p: 2, state: "own", why: "", swap: null, also: [] });
  assert.deepStrictEqual([slots[0], slots[1], slots[2], slots[3], null, Board.slot(c, slots, 0, 2)].map(Board.can), [true, false, false, true, false, false]);
});

t("fix: a move, and a swap when the slot names the other lesson", () => { assert.deepStrictEqual(Board.fix(card(1, 0, 2, 1, ["1A"]), { d: 1, p: 4, swap: null }), { kind: "move", id: 1, d: 1, p: 4 }); assert.deepStrictEqual(Board.fix(card(1, 0, 2, 1, ["1A"]), { d: 1, p: 4, swap: 7 }), { kind: "swap", a: 1, b: 7 }); });

t("onRow: its own class's row, any row of a band's classes, never another class's", () => {
  const one = card(1, 0, 0, 1, ["1A"]), band = card(2, 0, 0, 1, ["1A", "2A"], { band: "MT" }), lone = card(3, 0, 0, 1, []);
  const row = (cls) => ({ cls: cls });
  assert.deepStrictEqual([one, band, lone].map(c => Board.onRow(c, row("1A"))), [true, true, false]);
  assert.deepStrictEqual([one, band, lone].map(c => Board.onRow(c, row("2A"))), [false, true, false]);
  assert.deepStrictEqual([one, band, lone].map(c => Board.onRow(c, row("1B"))), [false, false, false]);
  assert.deepStrictEqual([one, band, lone].map(c => Board.onRow(c, row(""))), [false, false, true]);
});

t("tell: the sentence for a move, a swap, a clash with its reason, and the card's own place", () => {
  const days = ["Mon", "Tue"];
  assert.strictEqual(Board.tell({ d: 1, p: 4, state: "ok", why: "", swap: null }, days), "Move to Tue period 4.");
  assert.strictEqual(Board.tell({ d: 0, p: 2, state: "prefer", why: "", swap: 7 }, days), "Swap with the lesson on Mon period 2.");
  assert.strictEqual(Board.tell({ d: 1, p: 4, state: "no", why: "Mr Tan is teaching.", swap: null }, days), "Move to Tue period 4. Mr Tan is teaching.");
  assert.strictEqual(Board.tell({ d: 1, p: 4, state: "no", why: "Both are away.", swap: 7 }, days), "Swap with the lesson on Tue period 4. Both are away.");
  assert.strictEqual(Board.tell({ d: 1, p: 4, state: "na", why: "", swap: null }, days), "Move to Tue period 4.");
  assert.strictEqual(Board.tell({ d: 0, p: 2, state: "own", why: "", swap: null }, days), "This is where the lesson is now.");
});

console.log(`${n} cases passed`);

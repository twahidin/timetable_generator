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

t("groups, day: a card with only an unknown class is in the No class row and nowhere else; one known class keeps it in that class's row", () => {
  const odd = card(1, 0, 1, 1, ["9Z"]), mixed = card(2, 0, 2, 1, ["9Z", "1A"]), g = Board.groups(board([odd, mixed]), { kind: "day", d: 0 });
  assert.deepStrictEqual(g.map(x => x.name), ["Sec 1", "Sec 2", "No class"]);
  assert.deepStrictEqual(g[0].rows[0].cards, [{ card: mixed, lane: 0 }]);
  assert.deepStrictEqual(g[0].rows[1].cards, []); assert.deepStrictEqual(g[1].rows[0].cards, []);
  assert.deepStrictEqual(g[2].rows[0].cards, [{ card: odd, lane: 0 }]);
  const only = Board.groups(board([mixed]), { kind: "day", d: 0 });
  assert.deepStrictEqual(only.map(x => x.name), ["Sec 1", "Sec 2"]);
});

t("onRow with the board: the No class row takes a card with no class in a level", () => {
  const bd = board([]), odd = card(1, 0, 1, 1, ["9Z"]), mixed = card(2, 0, 2, 1, ["9Z", "1A"]), lone = card(3, 0, 1, 1, []), one = card(4, 0, 1, 1, ["1A"]);
  const none = { cls: "" };
  assert.deepStrictEqual([odd, mixed, lone, one].map(c => Board.onRow(c, none, bd)), [true, false, true, false]);
  assert.deepStrictEqual([odd, mixed, lone, one].map(c => Board.onRow(c, none)), [false, false, true, false]);
  assert.deepStrictEqual([odd, mixed, lone, one].map(c => Board.onRow(c, { cls: "1A" }, bd)), [false, true, false, true]);
  assert.strictEqual(Board.onRow(odd, { cls: "9Z" }), true);
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
  assert.deepStrictEqual(Board.states(c, [{ d: 0, p: 0 }], 0, 6)[0], "");
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
  assert.strictEqual(Board.tell({ d: 1, p: 4, state: "no", why: "Mr Tan is teaching.", swap: null }, days), "Move to Tue period 4. It will clash: Mr Tan is teaching.");
  assert.strictEqual(Board.tell({ d: 1, p: 4, state: "no", why: "Both are away.", swap: 7 }, days), "Swap with the lesson on Tue period 4. Both are away.");
  assert.strictEqual(Board.tell({ d: 1, p: 4, state: "na", why: "", swap: null }, days), "Move to Tue period 4.");
  assert.strictEqual(Board.tell({ d: 0, p: 2, state: "own", why: "", swap: null }, days), "This is where the lesson is now.");
});

t("target: the slot that swaps with a lesson, only when the app allows it", () => {
  const slots = [{ d: 0, p: 1, state: "ok", why: "", swap: 7 }, { d: 0, p: 2, state: "prefer", why: "", swap: 8 }, { d: 0, p: 3, state: "no", why: "x", swap: 9 }, { d: 0, p: 4, state: "ok", why: "", swap: null }];
  assert.strictEqual(Board.target(slots, 7), slots[0]);
  assert.strictEqual(Board.target(slots, 8), slots[1]);
  assert.strictEqual(Board.target(slots, 9), null);
  assert.strictEqual(Board.target(slots, 5), null);
  assert.strictEqual(Board.target(null, 7), null);
});

t("aim: a pointer over a lesson it can swap with aims at that swap; anywhere else the start the pointer gives", () => {
  const pe = card(3, 0, 9, 2, ["1A"]);
  const slots = [{ d: 4, p: 4, state: "ok", why: "", swap: 7 }, { d: 0, p: 23, state: "prefer", why: "Bends a rule.", swap: null },
    { d: 0, p: 12, state: "no", why: "Clash.", swap: 8 }, { d: 0, p: 5, state: "ok", why: "", swap: 9 }];
  assert.strictEqual(Board.aim(pe, slots, 4, 5, 7), slots[0]);      // over the swap target, its start not under the card's start
  assert.strictEqual(Board.aim(pe, slots, 0, 23, null), slots[1]);  // over nothing: the pointer's start
  assert.strictEqual(Board.aim(pe, slots, 0, 23, 8), slots[1]);     // over a lesson it may not swap with: the pointer's start
  assert.strictEqual(Board.aim(pe, slots, 0, 9, 3).state, "own");   // over itself: the pointer's start
  assert.strictEqual(Board.aim(pe, slots, 0, 6, 11), null);         // a place with no slot
  assert.strictEqual(Board.aim(pe, null, 0, 23, 7), null);
});

/* stage 3: the tray, the counters, the marks, forcing and the push question */
const lifted = (id, cls, extra) => card(id, null, null, 1, cls, Object.assign({ was: { d: 0, p: 1 }, marks: ["notplaced"] }, extra || {}));
const marked = (board0) => Object.assign({ unplaced: [], short: [] }, board0);
const ev = (d, p) => ({ d: d, p: p, state: "ok", why: "", swap: null, also: [], push: null });

t("MARK and critical: every mark but noroom is critical", () => {
  assert.deepStrictEqual(Board.MARK, { notplaced: "Not placed", noteacher: "No teacher", "break": "In a break", teacher: "In two places",
    "class": "In two places", room: "In two places", noroom: "No room" });
  assert.strictEqual(Board.critical(card(1, 0, 0, 1, ["1A"], { marks: ["noroom"] })), false);
  assert.strictEqual(Board.critical(card(1, 0, 0, 1, ["1A"], { marks: ["noroom", "teacher"] })), true);
  assert.strictEqual(Board.critical(card(1, 0, 0, 1, ["1A"])), false);
});

t("badge: the first mark's words and whether it is critical; null with no mark", () => {
  assert.deepStrictEqual(Board.badge(card(1, 0, 0, 1, ["1A"], { marks: ["class", "noroom"] })), { text: "In two places", crit: true });
  assert.deepStrictEqual(Board.badge(card(1, 0, 0, 1, ["1A"], { marks: ["noroom"] })), { text: "No room", crit: false });
  assert.strictEqual(Board.badge(card(1, 0, 0, 1, ["1A"], { marks: [] })), null);
  assert.strictEqual(Board.badge(card(1, 0, 0, 1, ["1A"])), null);
});

t("tray: grouped by first class in level order, other classes by name, no class last, empty groups left out", () => {
  const b = marked(board([]));
  b.unplaced = [lifted(1, ["2A"]), lifted(2, []), lifted(3, ["ZZ", "1A"]), lifted(4, ["1A"]), lifted(5, ["AA"]), lifted(6, ["1B"])];
  const tray = Board.tray(b);
  assert.deepStrictEqual(tray.map(g => [g.cls, g.cards.map(c => c.id)]),
    [["1A", [4]], ["1B", [6]], ["2A", [1]], ["AA", [5]], ["ZZ", [3]], ["", [2]]]);
  assert.deepStrictEqual(Board.tray(board([])), []);
});

t("counts: lessons, a card once for two places; a missing list is empty", () => {
  const b = marked(board([
    card(1, 0, 0, 1, ["1A"], { marks: ["teacher", "class", "room"] }), card(2, 0, 1, 1, ["1A"], { marks: ["noteacher", "noroom"] }),
    card(3, 1, 0, 1, ["1B"], { marks: ["break"] }), card(4, 1, 1, 1, ["1B"], { marks: ["noroom"] }), card(5, 1, 2, 1, ["1B"])]));
  b.unplaced = [lifted(9, ["1A"]), lifted(10, [])];
  assert.deepStrictEqual(Board.counts(b), { notplaced: 2, noteacher: 1, twoplaces: 1, inbreak: 1, noroom: 2 });
  assert.deepStrictEqual(Board.counts(board([card(1, 0, 0, 1, ["1A"])])), { notplaced: 0, noteacher: 0, twoplaces: 0, inbreak: 0, noroom: 0 });
  assert.deepStrictEqual(Board.COUNTERS, [["notplaced", "Not placed"], ["noteacher", "No teacher"], ["twoplaces", "In two places"],
    ["inbreak", "In a break"], ["noroom", "No room"]]);
});

t("hits: the cards a counter counts, by day, period, first class, id; the tray's order for notplaced", () => {
  const a = card(7, 1, 0, 1, ["1A"], { marks: ["room"] }), b = card(3, 0, 2, 1, ["1B"], { marks: ["class"] }), c = card(5, 0, 2, 1, ["1A"], { marks: ["teacher"] });
  const d = card(4, 0, 2, 1, [], { marks: ["teacher"] }), e = card(2, 0, 2, 1, ["1A"], { marks: ["teacher"] }), f = card(9, 0, 0, 1, ["1A"], { marks: ["break"] });
  const b0 = marked(board([a, b, c, d, e, f]));
  b0.unplaced = [lifted(21, ["2A"]), lifted(22, ["1A"])];
  assert.deepStrictEqual(Board.hits(b0, "twoplaces").map(x => x.id), [2, 5, 3, 4, 7]);
  assert.deepStrictEqual(Board.hits(b0, "inbreak").map(x => x.id), [9]);
  assert.deepStrictEqual(Board.hits(b0, "notplaced").map(x => x.id), [22, 21]);
  assert.deepStrictEqual(Board.hits(b0, "noteacher"), []);
});

t("step: the next card, the first after the last or an unknown id, null when empty", () => {
  const h = [{ id: 4 }, { id: 8 }, { id: 2 }];
  assert.strictEqual(Board.step(h, 4), h[1]); assert.strictEqual(Board.step(h, 2), h[0]);
  assert.strictEqual(Board.step(h, 99), h[0]); assert.strictEqual(Board.step(h, null), h[0]);
  assert.strictEqual(Board.step([], 4), null);
});

t("lands and forced: a place with no lesson to push, judged ok, prefer or no", () => {
  const push = { state: "ok", why: "", out: [{ id: 5, what: "Maths" }] };
  assert.strictEqual(Board.lands(ev(0, 1)), true);
  assert.strictEqual(Board.lands(Object.assign(ev(0, 1), { state: "prefer" })), true);
  assert.strictEqual(Board.lands(Object.assign(ev(0, 1), { state: "no" })), true);
  assert.strictEqual(Board.lands(Object.assign(ev(0, 1), { state: "na" })), false);
  assert.strictEqual(Board.lands({ d: 0, p: 1, state: "own", why: "", swap: null, also: [] }), false);
  assert.strictEqual(Board.lands(Object.assign(ev(0, 1), { push: push })), false);
  assert.strictEqual(Board.lands({ d: 0, p: 1, state: "ok", why: "", swap: null }), true);   // no push key: from before this stage
  assert.strictEqual(Board.lands(null), false);
  assert.strictEqual(Board.forced(Object.assign(ev(0, 1), { state: "no" })), true);
  assert.strictEqual(Board.forced(ev(0, 1)), false);
});

t("asks: null with no other lesson; swap when allowed and ok or prefer; push when its state is not na", () => {
  const out = [{ id: 5, what: "Maths" }];
  const s = (o) => Object.assign(ev(0, 1), o);
  assert.strictEqual(Board.asks(ev(0, 1)), null);
  assert.strictEqual(Board.asks({ d: 0, p: 1, state: "ok", swap: null }), null);
  assert.deepStrictEqual(Board.asks(s({ swap: 5, push: { state: "ok", why: "", out: out } })), { swap: true, push: true });
  assert.deepStrictEqual(Board.asks(s({ swap: 5, state: "prefer", push: { state: "no", why: "x", out: out } })), { swap: true, push: true });
  assert.deepStrictEqual(Board.asks(s({ swap: 5, state: "no", push: { state: "ok", why: "", out: out } })), { swap: false, push: true });
  assert.deepStrictEqual(Board.asks(s({ swap: null, state: "ok", push: { state: "ok", why: "", out: out } })), { swap: false, push: true });
  assert.deepStrictEqual(Board.asks(s({ swap: 5, state: "ok", push: { state: "na", why: "", out: out } })), { swap: true, push: false });
  assert.deepStrictEqual(Board.asks(s({ swap: null, state: "na", push: { state: "na", why: "", out: out } })), { swap: false, push: false });
});

t("fix: a move, a forced move, a swap, a push; the two-argument call as before", () => {
  const c = card(3, 0, 1, 1, ["1A"]), out = [{ id: 5, what: "Maths" }];
  assert.deepStrictEqual(Board.fix(c, ev(1, 2)), { kind: "move", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, ev(1, 2), "move"), { kind: "move", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { state: "no" }), "move"), { kind: "move", id: 3, d: 1, p: 2, force: true });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { swap: 5 })), { kind: "swap", a: 3, b: 5 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { swap: 5 }), "swap"), { kind: "swap", a: 3, b: 5 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { swap: 5 }), "move"), { kind: "move", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { push: { state: "ok", why: "", out: out } }), "push"), { kind: "move", id: 3, d: 1, p: 2, push: true });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { push: { state: "no", why: "x", out: out } }), "push"), { kind: "move", id: 3, d: 1, p: 2, push: true, force: true });
});

t("fix from the tray: place, never a swap", () => {
  const c = lifted(3, ["1A"]), out = [{ id: 5, what: "Maths" }];
  assert.deepStrictEqual(Board.fix(c, ev(1, 2), "move"), { kind: "place", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, ev(1, 2)), { kind: "place", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { state: "no" }), "move"), { kind: "place", id: 3, d: 1, p: 2, force: true });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { swap: 5 }), "swap"), { kind: "place", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { push: { state: "no", why: "x", out: out } }), "push"), { kind: "place", id: 3, d: 1, p: 2, push: true, force: true });
});

t("addFix and liftFix", () => {
  const out = [{ id: 5, what: "Maths" }];
  const short = { key: "k1", name: "Maths 1A", have: 1, want: 2, n: 1, classes: ["1A"] };
  assert.deepStrictEqual(Board.addFix(short, ev(1, 2), "move"), { kind: "add", key: "k1", d: 1, p: 2, n: 1 });
  assert.deepStrictEqual(Board.addFix(short, Object.assign(ev(1, 2), { state: "no" })), { kind: "add", key: "k1", d: 1, p: 2, n: 1, force: true });
  assert.deepStrictEqual(Board.addFix(short, Object.assign(ev(1, 2), { push: { state: "ok", why: "", out: out } }), "push"), { kind: "add", key: "k1", d: 1, p: 2, n: 1, push: true });
  assert.deepStrictEqual(Board.addFix(short, Object.assign(ev(1, 2), { push: { state: "no", why: "x", out: out } }), "push"), { kind: "add", key: "k1", d: 1, p: 2, n: 1, push: true, force: true });
  assert.deepStrictEqual(Board.liftFix(card(8, 0, 0, 1, ["1A"])), { kind: "lift", id: 8 });
});

t("question: the text, the swap and push buttons, the also sentences", () => {
  const c = card(3, 0, 1, 1, ["1A"], { what: "Science" }), days = ["Mon", "Tue"], b = marked(board([c]));
  const o1 = [{ id: 5, what: "Maths" }], o2 = [{ id: 5, what: "Maths" }, { id: 6, what: "Art" }], o3 = o2.concat([{ id: 7, what: "PE" }]);
  const s1 = Object.assign(ev(1, 2), { swap: 5, also: ["Art also moves."], push: { state: "ok", why: "", out: o1 } });
  assert.deepStrictEqual(Board.question(c, s1, b), { text: "Science on Tue period 2: another lesson is there.",
    also: ["Art also moves."], swap: "Swap with Maths", push: "Push out Maths" });
  const s2 = Object.assign(ev(1, 2), { push: { state: "no", why: "Mr Lee is busy.", out: o2 } });
  assert.deepStrictEqual(Board.question(c, s2, b), { text: "Science on Tue period 2: another lesson is there.",
    also: ["It will still clash: Mr Lee is busy."], swap: null, push: "Push out Maths and Art" });
  const s3 = Object.assign(ev(0, 4), { push: { state: "ok", why: "", out: o3 } });
  assert.strictEqual(Board.question(c, s3, b).push, "Push out 3 lessons");
  const s4 = Object.assign(ev(0, 4), { swap: 9, push: { state: "ok", why: "", out: o1 } });
  assert.strictEqual(Board.question(c, s4, b).swap, "Swap");
  const s5 = Object.assign(ev(0, 4), { swap: 5, push: { state: "na", why: "", out: o1 } });
  assert.deepStrictEqual(Board.question(c, s5, b), { text: "Science on Mon period 4: another lesson is there.", also: [], swap: "Swap with Maths", push: null });
});

t("tell: the new sentences; a swap keeps today's words", () => {
  const days = ["Mon", "Tue"], out = [{ id: 5, what: "Maths" }];
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { push: { state: "ok", why: "", out: out } }), days), "Another lesson is there. Drop to swap or push out.");
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { swap: 5, push: { state: "ok", why: "", out: out } }), days), "Swap with the lesson on Tue period 2.");
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { swap: 5, why: "Bends a rule.", push: null }), days), "Swap with the lesson on Tue period 2. Bends a rule.");
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { state: "no", why: "Mr Lee is busy." }), days), "Move to Tue period 2. It will clash: Mr Lee is busy.");
  assert.strictEqual(Board.tell(ev(1, 2), days), "Move to Tue period 2.");
  assert.strictEqual(Board.tell({ d: 1, p: 2, state: "prefer", why: "Bends a rule.", swap: null }, days), "Move to Tue period 2. Bends a rule.");
});

console.log(`${n} cases passed`);

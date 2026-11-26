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
    { key: "", label: "No class", d: 0, cls: "", codes: "LLLLLL", lanes: 1, cards: undefined, by: "class", name: "" });
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
  assert.strictEqual(Board.tell({ d: 1, p: 4, state: "no", why: "Mr Tan is teaching.", swap: null }, days), "Move to Tue period 4. It lands with a problem: Mr Tan is teaching.");
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
  assert.deepStrictEqual(Board.MARK, { notplaced: "Not placed", noteacher: "No teacher", "break": "In a break", teacher: "Teacher in two places",
    "class": "Class in two places", room: "Room in two places", noroom: "No room" });
  assert.strictEqual(Board.critical(card(1, 0, 0, 1, ["1A"], { marks: ["noroom"] })), false);
  assert.strictEqual(Board.critical(card(1, 0, 0, 1, ["1A"], { marks: ["noroom", "teacher"] })), true);
  assert.strictEqual(Board.critical(card(1, 0, 0, 1, ["1A"])), false);
});

t("badge: the first mark's words and whether it is critical; null with no mark", () => {
  assert.deepStrictEqual(Board.badge(card(1, 0, 0, 1, ["1A"], { marks: ["class", "noroom"] })), { text: "Class in two places", crit: true });
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
    ["inbreak", "Not lesson time"], ["noroom", "No room"]]);
  assert.strictEqual(Board.badge({ marks: ["break"] }).text, "In a break");
  assert.strictEqual(Board.badge({ marks: ["break"], out: true }).text, "Outside the day");   // no school then, or past the day's end
  assert.strictEqual(Board.badge({ marks: ["teacher"], out: true }).text, "Teacher in two places");
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

t("asks: null with no other lesson; swap when allowed and ok or prefer; anyway when the plain move collides", () => {
  const out = [{ id: 5, what: "Maths" }];
  const s = (o) => Object.assign(ev(0, 1), o);
  assert.strictEqual(Board.asks(ev(0, 1)), null);
  assert.strictEqual(Board.asks({ d: 0, p: 1, state: "ok", swap: null }), null);
  assert.deepStrictEqual(Board.asks(s({ swap: 5, push: { state: "ok", why: "", out: out } })), { swap: true, beside: false, anyway: false });
  assert.deepStrictEqual(Board.asks(s({ swap: 5, state: "prefer", push: { state: "no", why: "x", out: out } })), { swap: true, beside: false, anyway: false });
  assert.deepStrictEqual(Board.asks(s({ swap: 5, state: "no", push: { state: "ok", why: "", out: out }, beside: { state: "no", why: "y" } })), { swap: false, beside: false, anyway: true });
  assert.deepStrictEqual(Board.asks(s({ swap: null, state: "ok", push: { state: "ok", why: "", out: out } })), { swap: false, beside: false, anyway: false });
  assert.deepStrictEqual(Board.asks(s({ swap: 5, state: "ok", push: { state: "na", why: "", out: out } })), { swap: true, beside: false, anyway: false });
  assert.deepStrictEqual(Board.asks(s({ swap: null, state: "na", push: { state: "na", why: "", out: out }, beside: { state: "na", why: "z" } })), { swap: false, beside: false, anyway: false });
});

t("fix: a move, a forced move, a swap, a push; the two-argument call as before", () => {
  const c = card(3, 0, 1, 1, ["1A"]), out = [{ id: 5, what: "Maths" }];
  assert.deepStrictEqual(Board.fix(c, ev(1, 2)), { kind: "move", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, ev(1, 2), "move"), { kind: "move", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { state: "no" }), "move"), { kind: "move", id: 3, d: 1, p: 2, force: true, why: "" });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { swap: 5 })), { kind: "swap", a: 3, b: 5 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { swap: 5 }), "swap"), { kind: "swap", a: 3, b: 5 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { swap: 5 }), "move"), { kind: "move", id: 3, d: 1, p: 2 });
});

t("fix from the tray: place, never a swap", () => {
  const c = lifted(3, ["1A"]), out = [{ id: 5, what: "Maths" }];
  assert.deepStrictEqual(Board.fix(c, ev(1, 2), "move"), { kind: "place", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, ev(1, 2)), { kind: "place", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { state: "no" }), "move"), { kind: "place", id: 3, d: 1, p: 2, force: true, why: "" });
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { swap: 5 }), "swap"), { kind: "place", id: 3, d: 1, p: 2 });
});

t("addFix and liftFix", () => {
  const out = [{ id: 5, what: "Maths" }];
  const short = { key: "k1", name: "Maths 1A", have: 1, want: 2, n: 1, classes: ["1A"] };
  assert.deepStrictEqual(Board.addFix(short, ev(1, 2), "move"), { kind: "add", key: "k1", d: 1, p: 2, n: 1 });
  assert.deepStrictEqual(Board.addFix(short, Object.assign(ev(1, 2), { state: "no" })), { kind: "add", key: "k1", d: 1, p: 2, n: 1, force: true, why: "" });
  assert.deepStrictEqual(Board.liftFix(card(8, 0, 0, 1, ["1A"])), { kind: "lift", id: 8 });
});

t("question: the swap button and its also sentences", () => {
  const c = card(3, 0, 1, 1, ["1A"], { what: "Science" }), b = marked(board([c])), o1 = [{ id: 5, what: "Maths" }];
  const s1 = Object.assign(ev(1, 2), { swap: 5, also: ["Art also moves."], push: { state: "ok", why: "", out: o1 }, beside: { state: "no", why: "1A has Maths then." }, clashes: [{ kind: "class", text: "1A has Maths then." }] });
  const q1 = Board.question(c, s1, b);
  assert.strictEqual(q1.swap, "Swap with Maths"); assert.deepStrictEqual(q1.also, ["Art also moves."]); assert.strictEqual(q1.anyway, "Put it here anyway");
  const s4 = Object.assign(ev(0, 4), { swap: 9, push: { state: "ok", why: "", out: o1 } });
  assert.strictEqual(Board.question(c, s4, b).swap, "Swap");
  assert.strictEqual(Board.question(c, Object.assign(ev(0, 4), { swap: 5, state: "no", also: ["x"], push: { state: "ok", why: "", out: o1 } }), b).swap, null);
});

t("tell: one sentence over another lesson; a swap from an older server keeps today's words", () => {
  const days = ["Mon", "Tue"], out = [{ id: 5, what: "Maths" }];
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { push: { state: "ok", why: "", out: out } }), days), "Another lesson is there. Drop or click to see what can be done.");
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { swap: 5, push: { state: "ok", why: "", out: out } }), days), "Another lesson is there. Drop or click to see what can be done.");
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { swap: 5, why: "Bends a rule.", push: null }), days), "Swap with the lesson on Tue period 2. Bends a rule.");
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { state: "no", why: "Mr Lee is busy." }), days), "Move to Tue period 2. It lands with a problem: Mr Lee is busy.");
  assert.strictEqual(Board.tell(ev(1, 2), days), "Move to Tue period 2.");
  assert.strictEqual(Board.tell({ d: 1, p: 2, state: "prefer", why: "Bends a rule.", swap: null }, days), "Move to Tue period 2. Bends a rule.");
});

/* fix round 1: a lesson put beside another of its classes (two groups of one class at once) */
t("asks: beside when the plain move or place is ok or prefer; a slot with no beside key (an older server) offers none", () => {
  const out = [{ id: 5, what: "Maths" }], s = (o) => Object.assign(ev(0, 1), { state: "na", push: { state: "ok", why: "", out: out } }, o);
  assert.deepStrictEqual(Board.asks(s({ beside: { state: "ok", why: "" } })), { swap: false, beside: true, anyway: false });
  assert.deepStrictEqual(Board.asks(s({ beside: { state: "prefer", why: "Bends a rule." } })), { swap: false, beside: true, anyway: false });
  assert.deepStrictEqual(Board.asks(s({ beside: { state: "no", why: "1A has Maths then." } })), { swap: false, beside: false, anyway: true });
  assert.deepStrictEqual(Board.asks(s({ beside: { state: "na", why: "" } })), { swap: false, beside: false, anyway: false });
  assert.deepStrictEqual(Board.asks(s({ beside: null })), { swap: false, beside: false, anyway: false });
  assert.deepStrictEqual(Board.asks(s({})), { swap: false, beside: false, anyway: false });
  assert.strictEqual(Board.asks(Object.assign(ev(0, 1), { beside: null })), null);
});

t("question: Put it beside, named for one lesson, 'them' for several", () => {
  const c = card(3, 0, 1, 1, ["1A"], { what: "Science" }), b = marked(board([c]));
  const o1 = [{ id: 5, what: "Maths G1" }], o2 = o1.concat([{ id: 6, what: "Art G2" }]);
  const s1 = Object.assign(ev(1, 2), { state: "na", push: { state: "ok", why: "", out: o1 }, beside: { state: "ok", why: "" }, clashes: [] });
  assert.deepStrictEqual(Board.question(c, s1, b), { text: "Science on Tue period 2: another lesson is there.", lines: [], more: 0, why: "Nothing collides.",
    also: [], swap: null, beside: "Put it beside Maths G1", anyway: null });
  const s2 = Object.assign(ev(1, 2), { state: "na", push: { state: "na", why: "x", out: o2 }, beside: { state: "prefer", why: "Bends a rule." }, clashes: [] });
  const q2 = Board.question(c, s2, b); assert.strictEqual(q2.beside, "Put it beside them"); assert.strictEqual(q2.anyway, null);
  const s3 = Object.assign(ev(1, 2), { state: "na", push: { state: "ok", why: "", out: o1 }, beside: { state: "no", why: "1A has Maths then." } });
  assert.strictEqual(Board.question(c, s3, b).beside, null);
  assert.strictEqual(Board.question(c, Object.assign(ev(1, 2), { state: "na", push: { state: "ok", why: "", out: o1 } }), b).beside, null);
});

t("fix beside: the plain move or place, with no push and no force", () => {
  const out = [{ id: 5, what: "Maths" }], sl = Object.assign(ev(1, 2), { state: "na", swap: 5, push: { state: "no", why: "x", out: out }, beside: { state: "ok", why: "" } });
  assert.deepStrictEqual(Board.fix(card(3, 0, 1, 1, ["1A"]), sl, "beside"), { kind: "move", id: 3, d: 1, p: 2 });
  assert.deepStrictEqual(Board.fix(lifted(3, ["1A"]), Object.assign({}, sl, { state: "no" }), "beside"), { kind: "place", id: 3, d: 1, p: 2 });
});

t("tell with the card: a tray card is placed; over another lesson the one sentence", () => {
  const days = ["Mon", "Tue"], out = [{ id: 5, what: "Maths" }], tray = lifted(3, ["1A"]), on = card(3, 0, 1, 1, ["1A"]);
  const there = Object.assign(ev(1, 2), { state: "na", push: { state: "ok", why: "", out: out }, beside: { state: "ok", why: "" } });
  assert.strictEqual(Board.tell(there, days, tray), "Another lesson is there. Drop or click to see what can be done.");
  assert.strictEqual(Board.tell(there, days, on), "Another lesson is there. Drop or click to see what can be done.");
  assert.strictEqual(Board.tell(there, days), "Another lesson is there. Drop or click to see what can be done.");
  assert.strictEqual(Board.tell(ev(1, 2), days, tray), "Place on Tue period 2.");
  assert.strictEqual(Board.tell(Object.assign(ev(1, 2), { state: "no", why: "Mr Lee is busy." }), days, tray), "Place on Tue period 2. It lands with a problem: Mr Lee is busy.");
  assert.strictEqual(Board.tell({ d: 1, p: 2, state: "prefer", why: "Bends a rule.", swap: null }, days, tray), "Place on Tue period 2. Bends a rule.");
  assert.strictEqual(Board.tell(ev(1, 2), days, on), "Move to Tue period 2.");
});

/* the drop box: every collision at the place, and "Put it here anyway" in place of push out */
t("question: the collisions, cut at 8, and what can be done", () => {
  const c = card(9, 0, 1, 1, ["1A"], { what: "Science" }), b = board([c]);
  const out = [{ id: 5, what: "Maths", classes: ["1A"], groups: 1 }];
  const cl = [{ kind: "teacher", text: "Mr Tan is teaching 1B Art then." }, { kind: "class", text: "1A has Maths then." }];
  const s = { d: 1, p: 2, state: "na", why: "Another lesson is there.", swap: null, also: [], push: { state: "ok", why: "", out },
    beside: { state: "no", why: "Mr Tan is teaching 1B Art then." }, clashes: cl };
  assert.deepStrictEqual(Board.question(c, s, b), { text: "Science on Tue period 2 collides with:",
    lines: [{ kind: "Teacher", text: "Mr Tan is teaching 1B Art then." }, { kind: "Class", text: "1A has Maths then." }], more: 0, why: "",
    also: [], swap: null, beside: null, anyway: "Put it here anyway" });
  const many = Array.from({ length: 11 }, (_, i) => ({ kind: "room", text: "R" + i + " is in use then." }));
  const q = Board.question(c, Object.assign({}, s, { clashes: many }), b); assert.strictEqual(q.lines.length, 8); assert.strictEqual(q.more, 3);
});
t("question: nothing collides, a rule in the way, not lesson time, an older answer", () => {
  const c = card(9, 0, 1, 1, ["1A"], { what: "Science" }), b = board([c]), out = [{ id: 5, what: "Maths G1", classes: ["1A"], groups: 1 }];
  const base = { d: 1, p: 2, state: "na", why: "Another lesson is there.", swap: null, also: [], push: { state: "ok", why: "", out } };
  const free = Board.question(c, Object.assign({}, base, { beside: { state: "ok", why: "" }, clashes: [] }), b);
  assert.strictEqual(free.text, "Science on Tue period 2: another lesson is there."); assert.strictEqual(free.why, "Nothing collides.");
  assert.strictEqual(free.beside, "Put it beside Maths G1"); assert.strictEqual(free.anyway, null);
  const rule = Board.question(c, Object.assign({}, base, { beside: { state: "no", why: "Rule School: no Science after lunch." }, clashes: [] }), b);
  assert.strictEqual(rule.why, "Rule School: no Science after lunch."); assert.strictEqual(rule.anyway, "Put it here anyway"); assert.strictEqual(rule.beside, null);
  const na = Board.question(c, Object.assign({}, base, { beside: { state: "na", why: "That is not lesson time for 1A." }, clashes: [] }), b);
  assert.strictEqual(na.why, "That is not lesson time for 1A."); assert.strictEqual(na.anyway, null); assert.strictEqual(na.beside, null);
  const old = Board.question(c, Object.assign({}, base, { beside: { state: "no", why: "1A has Maths G1 then." } }), b);   // no clashes key
  assert.deepStrictEqual(old.lines, []); assert.strictEqual(old.why, "1A has Maths G1 then."); assert.strictEqual(old.anyway, "Put it here anyway");
});
t("question: collisions at a place that is not lesson time say that sentence too, and offer nothing but Cancel", () => {
  const c = card(9, 0, 1, 1, ["1A"], { what: "Science" }), b = board([c]), out = [{ id: 5, what: "Maths G1", classes: ["1A"], groups: 1 }];
  const s = { d: 1, p: 2, state: "na", why: "Another lesson is there.", swap: null, also: [], push: { state: "ok", why: "", out },
    clashes: [{ kind: "class", text: "1A has Maths G1 then." }], beside: { state: "na", why: "That is not lesson time for 1A." } };
  const q = Board.question(c, s, b);
  assert.ok(q.text.endsWith("collides with:")); assert.strictEqual(q.lines.length, 1);
  assert.strictEqual(q.why, "That is not lesson time for 1A."); assert.strictEqual(q.anyway, null); assert.strictEqual(q.beside, null);
});
t("fix: put it here anyway is the plain move forced with the reason shown; no push", () => {
  const c = card(9, 0, 1, 1, ["1A"]), s = { d: 1, p: 2, state: "na", swap: null, push: { state: "ok", why: "", out: [] }, beside: { state: "no", why: "1A has Maths then." } };
  assert.deepStrictEqual(Board.fix(c, s, "anyway"), { kind: "move", id: 9, d: 1, p: 2, force: true, why: "1A has Maths then." });
  assert.deepStrictEqual(Board.fix(card(9, null, null, 1, ["1A"]), s, "anyway"), { kind: "place", id: 9, d: 1, p: 2, force: true, why: "1A has Maths then." });
  assert.deepStrictEqual(Board.asks(s), { swap: false, beside: false, anyway: true });
  assert.strictEqual(Board.states(c, [s], 1, 6)[2], "ask");
  assert.strictEqual(Board.tell(s, ["Mon", "Tue"]), "Another lesson is there. Drop or click to see what can be done.");
});

const wn = (key, where, extra) => Object.assign({ key: key, kind: "rule", text: "Text " + key, strength: "Must", group: "1A", where: where, crit: "" }, extra || {});
t("warned: the open warnings that name a lesson, by lesson id, critical ones first", () => {
  const a = wn("a", { cls: "1A", id: 3 }), b = wn("b", { cls: "1A", id: 3 }, { crit: "teacher" }), c = wn("c", { cls: "1B", id: 4 });
  const settled = wn("d", { cls: "1A", id: 3 }, { decision: { answer: "step5" } }), nowhere = wn("e", undefined), noid = wn("f", { cls: "1A", day: "Mon" });
  assert.deepStrictEqual(Board.warned([a, settled, b, nowhere, noid, c]), { 3: [b, a], 4: [c] });
  assert.deepStrictEqual(Board.warned([]), {}); assert.deepStrictEqual(Board.warned(undefined), {});
});

t("flag: a mark keeps its badge; else the lesson's warnings are counted; else nothing", () => {
  const marked = card(3, 0, 1, 1, ["1A"], { marks: ["teacher"] }), plain = card(4, 0, 2, 1, ["1A"]), other = card(5, 0, 3, 1, ["1A"]);
  const w = Board.warned([wn("a", { id: 3 }), wn("b", { id: 4 }), wn("c", { id: 4 }), wn("d", { id: 5 })]);
  assert.deepStrictEqual(Board.flag(marked, w), { text: "Teacher in two places", crit: true });
  assert.deepStrictEqual(Board.flag(plain, w), { text: "2 warnings", crit: false });
  assert.deepStrictEqual(Board.flag(other, w), { text: "1 warning", crit: false });
  assert.strictEqual(Board.flag(card(6, 0, 4, 1, ["1A"]), w), null);
  assert.strictEqual(Board.flag(card(6, 0, 4, 1, ["1A"]), {}), null);
});

t("at: the lesson on the board or in the tray, else the class (on the warning's day), else nothing", () => {
  const b = Object.assign(board([card(3, 1, 2, 1, ["1B", "1A"])]), { unplaced: [lifted(7, ["2A"])] });
  assert.deepStrictEqual(Board.at(wn("a", { cls: "1A", day: "Mon", id: 3 }), b), { id: 3, d: 1, cls: "1B" });
  assert.deepStrictEqual(Board.at(wn("b", { cls: "2A", id: 7 }), b), { id: 7, d: null, cls: "2A" });
  assert.deepStrictEqual(Board.at(wn("c", { cls: "1A", day: "Tue", id: 99 }), b), { id: null, d: 1, cls: "1A" });
  assert.deepStrictEqual(Board.at(wn("d", { cls: "2A" }), b), { id: null, d: null, cls: "2A" });
  assert.deepStrictEqual(Board.at(wn("e", { cls: "1A", day: "Someday" }), b), { id: null, d: null, cls: "1A" });
  assert.strictEqual(Board.at(wn("f", { cls: "9Z", day: "Mon" }), b), null);
  assert.strictEqual(Board.at(wn("g", { teacher: "Mr Tan" }), b), null);
  assert.strictEqual(Board.at(wn("h", undefined), b), null);
});

/* the fix wave after the whole-branch review */
t("states: a place with another lesson is ask when a drop there offers something, na when it offers nothing", () => {
  const c = card(1, 0, 2, 1, ["1A"]), out = [{ id: 5, what: "Maths", classes: ["1A"], groups: 1 }];
  const at = (p, o) => Object.assign({ d: 0, p: p, state: "na", why: "Another lesson is there.", swap: null, also: [] }, o);
  const slots = [at(0, { push: { state: "ok", why: "", out: out }, beside: { state: "no", why: "1A has Maths then." } }), at(1, { push: { state: "na", why: "That is not lesson time for 1A.", out: out }, beside: { state: "na", why: "That is not lesson time for 1A." } }),
    at(3, { state: "ok", why: "", swap: 5, push: { state: "na", why: "x", out: out } }), at(4, { push: { state: "na", why: "x", out: out }, beside: { state: "prefer", why: "Bends a rule." } }),
    at(5, { state: "ok", why: "", push: null })];
  assert.deepStrictEqual(Board.states(c, slots, 0, 6), ["ask", "na", "own", "ask", "ask", "ok"]);
  const tray = lifted(1, ["1A"]), tslots = slots.concat([at(2, { state: "no", why: "1A has Art then.", push: { state: "ok", why: "", out: out }, beside: { state: "no", why: "1A has Art then." } })]);
  assert.deepStrictEqual(Board.states(tray, tslots, 0, 6), ["ask", "na", "ask", "na", "ask", "ok"]);   // from the tray a swap is not offered
  assert.deepStrictEqual(Board.states(c, [at(3, { state: "ok", why: "", swap: 5 })], 0, 6), ["", "", "own", "ok", "", ""]);   // an older server's swap, with no push key
});



t("a forced fix carries the sentence the page showed for the place", () => {
  const c = card(3, 0, 1, 1, ["1A"]), out = [{ id: 5, what: "Maths" }];
  assert.deepStrictEqual(Board.fix(c, Object.assign(ev(1, 2), { state: "no", why: "Mr Tan is teaching." }), "move"), { kind: "move", id: 3, d: 1, p: 2, force: true, why: "Mr Tan is teaching." });
  assert.deepStrictEqual(Board.fix(lifted(3, ["1A"]), Object.assign(ev(1, 2), { state: "no", why: "1A has Art then." })), { kind: "place", id: 3, d: 1, p: 2, force: true, why: "1A has Art then." });
  const short = { key: "k1", n: 1 };
  assert.deepStrictEqual(Board.addFix(short, Object.assign(ev(1, 2), { state: "no", why: "Over the plan." })), { kind: "add", key: "k1", d: 1, p: 2, n: 1, force: true, why: "Over the plan." });
  assert.deepStrictEqual(Board.deleteFix(c, { state: "no", why: "That would leave Maths for 1A with 4 periods; step 3 plans 5." }), { kind: "delete", id: 3, force: true, why: "That would leave Maths for 1A with 4 periods; step 3 plans 5." });
  assert.deepStrictEqual(Board.deleteFix(c, { state: "ok", why: "" }), { kind: "delete", id: 3 });
});

// ---- stage 4: rows by teacher and room, handing a lesson over, a lesson's choices ----
const crow = (extra) => Object.assign({ group: "Entire Class", subject: "Maths", teachers: ["Mr Tan"], tshorts: ["TAN"], room: "R1", key: "C:1A:Maths" }, extra || {});
const board4 = (cards) => Object.assign(board(cards), {
  day: ["LLLLLL", "LLLLLL"],
  teachers: [{ dept: "Maths Dept", teachers: [{ name: "Mr Tan", short: "TAN" }, { name: "Ms Lim", short: "LIM" }] },
             { dept: "Science Dept", teachers: [{ name: "Mr Ong", short: "ONG" }] }, { dept: "", teachers: [{ name: "Ms Free", short: "FRE" }] }],
  rooms: [{ kind: "Classroom", rooms: ["R1", "R2"] }, { kind: "Lab", rooms: ["LAB1"] }] });
const tcard = (id, d, p, classes, rows, extra) => card(id, d, p, 1, classes, Object.assign({ what: "Maths for 1A", rows: rows }, extra || {}));

t("groups, by teacher: a row per teacher of the setup under its department, the No teacher row first only when needed", () => {
  const a = tcard(1, 0, 1, ["1A"], [crow()]), b = tcard(2, 0, 2, ["1B"], [crow({ teachers: [], tshorts: [], key: "C:1B:Maths" })]);
  const g = Board.groups(board4([a]), { kind: "day", d: 0, by: "teacher" });
  assert.deepStrictEqual(g.map(x => [x.name, x.rows.map(r => r.name)]), [["Maths Dept", ["Mr Tan", "Ms Lim"]], ["Science Dept", ["Mr Ong"]], ["No department", ["Ms Free"]]]);
  assert.deepStrictEqual(g[0].rows[0].cards, [{ card: a, lane: 0 }]); assert.deepStrictEqual(g[0].rows[1].cards, []);
  const r = g[0].rows[0];
  assert.deepStrictEqual([r.key, r.label, r.by, r.name, r.cls, r.d, r.codes, r.lanes], ["Mr Tan", "Mr Tan", "teacher", "Mr Tan", "", 0, "LLLLLL", 1]);
  const g2 = Board.groups(board4([a, b]), { kind: "day", d: 0, by: "teacher" });
  assert.deepStrictEqual(g2[0].name, ""); assert.deepStrictEqual(g2[0].rows.length, 1);
  const no = g2[0].rows[0];
  assert.deepStrictEqual([no.key, no.label, no.by, no.name, no.cls], ["", "No teacher", "teacher", "", ""]);
  assert.deepStrictEqual(no.cards, [{ card: b, lane: 0 }]);
});

t("groups, by teacher: a teacher not in the setup gets a last group; a card is in a row once; day codes fall back to L", () => {
  const a = tcard(1, 0, 1, ["1A"], [crow({ teachers: ["Mr Tan", "Mr Tan"] }), crow({ group: "G2", key: "G:1MAA1", teachers: ["Mr Tan", "Mr Gone"] })]);
  const bd = board4([a]); delete bd.day;
  const g = Board.groups(bd, { kind: "day", d: 0, by: "teacher" });
  assert.deepStrictEqual(g.map(x => x.name), ["Maths Dept", "Science Dept", "No department", "Not in the setup"]);
  assert.deepStrictEqual(g[3].rows.map(r => r.name), ["Mr Gone"]);
  assert.strictEqual(g[0].rows[0].cards.length, 1); assert.strictEqual(g[0].rows[0].codes, "LLLLLL");
  const listed = board4([a]); listed.teachers.push({ dept: "Not in the setup", teachers: [{ name: "Mr Gone", short: "GON" }] });
  const g2 = Board.groups(listed, { kind: "day", d: 0, by: "teacher" });
  assert.deepStrictEqual(g2.map(x => x.name), ["Maths Dept", "Science Dept", "No department", "Not in the setup"]);
  assert.strictEqual(g2[3].rows.length, 1);
  const g3 = Board.groups(board([a]), { kind: "day", d: 0, by: "teacher" });
  assert.deepStrictEqual(g3.map(x => x.name), ["Not in the setup"]);
});

t("groups, by room: a row per room under its kind, No room for '' and TBC, a card in a room's row when a row has it", () => {
  const a = tcard(1, 0, 1, ["1A"], [crow(), crow({ group: "G2", key: "G:1MAA1", room: "LAB1" })]);
  const b = tcard(2, 0, 2, ["1B"], [crow({ room: "TBC" })]), c = tcard(3, 0, 3, ["1B"], [crow({ room: "" })]);
  const g = Board.groups(board4([a, b, c]), { kind: "day", d: 0, by: "room" });
  assert.deepStrictEqual(g.map(x => [x.name, x.rows.map(r => r.name)]), [["", [""]], ["Classroom", ["R1", "R2"]], ["Lab", ["LAB1"]]]);
  assert.deepStrictEqual([g[0].rows[0].key, g[0].rows[0].label, g[0].rows[0].by], ["", "No room", "room"]);
  assert.deepStrictEqual(g[0].rows[0].cards.map(x => x.card.id), [2, 3]);
  assert.deepStrictEqual(g[1].rows[0].cards.map(x => x.card.id), [1]); assert.deepStrictEqual(g[2].rows[0].cards.map(x => x.card.id), [1]);
  const none = Board.groups(board4([a]), { kind: "day", d: 0, by: "room" });
  assert.deepStrictEqual(none.map(x => x.name), ["Classroom", "Lab"]);
  const odd = Board.groups(board4([tcard(4, 0, 1, ["1A"], [crow({ room: "Hall" })])]), { kind: "day", d: 0, by: "room" });
  assert.deepStrictEqual(odd.map(x => x.name), ["Classroom", "Lab", "Not in the setup"]); assert.deepStrictEqual(odd[2].rows.map(r => r.name), ["Hall"]);
});

t("groups, cycle by teacher and by room; class rows gain by and name", () => {
  const a = tcard(1, 0, 1, ["1A"], [crow()]), b = tcard(2, 1, 2, ["1B"], [crow({ room: "R2", teachers: ["Ms Lim"] })]);
  const weeks = [{ name: "Odd", days: [{ i: 0, label: "Mon" }] }, { name: "Even", days: [{ i: 1, label: "Tue" }] }];
  const g = Board.groups(board4([a, b]), { kind: "cycle", by: "teacher", name: "Mr Tan" }, weeks);
  assert.deepStrictEqual(g.map(x => [x.name, x.rows.map(r => [r.key, r.label, r.d, r.cls, r.by, r.name, r.codes, r.cards.length])]),
    [["Odd", [["0", "Mon", 0, "", "teacher", "Mr Tan", "LLLLLL", 1]]], ["Even", [["1", "Tue", 1, "", "teacher", "Mr Tan", "LLLLLL", 0]]]]);
  const h = Board.groups(board4([a, b]), { kind: "cycle", by: "room", name: "R2" }, weeks);
  assert.deepStrictEqual(h[1].rows[0].cards.map(x => x.card.id), [2]); assert.strictEqual(h[1].rows[0].by, "room");
  const c = Board.groups(board4([a]), { kind: "day", d: 0 });
  assert.deepStrictEqual([c[0].rows[0].by, c[0].rows[0].name], ["class", "1A"]);
});

t("of: a class row gives all the rows, a teacher row its teacher's, a room row its room's, the No rows the empty ones", () => {
  const r1 = crow(), r2 = crow({ group: "G2", key: "G:1MAA1", teachers: ["Ms Lim"], tshorts: ["LIM"], room: "R2" }), r3 = crow({ teachers: [], tshorts: [], room: "TBC", key: "C:1A:Art" });
  const a = tcard(1, 0, 1, ["1A"], [r1, r2, r3]);
  assert.deepStrictEqual(Board.of(a, { by: "class", cls: "1A" }), [r1, r2, r3]);
  assert.deepStrictEqual(Board.of(a, { cls: "1A" }), [r1, r2, r3]);
  assert.deepStrictEqual(Board.of(a, { by: "teacher", name: "Ms Lim" }), [r2]);
  assert.deepStrictEqual(Board.of(a, { by: "teacher", name: "" }), [r3]);
  assert.deepStrictEqual(Board.of(a, { by: "room", name: "R1" }), [r1]);
  assert.deepStrictEqual(Board.of(a, { by: "room", name: "" }), [r3]);
});

t("lines: for a teacher row the classes (three, then +N) and the matching row's room; for a room row the teachers", () => {
  const a = tcard(1, 0, 1, ["1A", "1B", "1C", "1D", "1E"], [crow({ teachers: ["Ms Lim", "Mr Tan"], tshorts: ["LIM", "TAN"] }), crow({ group: "G2", key: "G:1MAA1", room: "LAB1" })]);
  const b = board4([a]);
  assert.deepStrictEqual(Board.lines(a, b, { by: "teacher", name: "Ms Lim" }), { title: "MA", lines: ["1A, 1B, 1C +2", "R1"], color: 3 });
  assert.deepStrictEqual(Board.lines(a, b, { by: "room", name: "LAB1" }), { title: "MA", lines: ["1A, 1B, 1C +2", "TAN"], color: 3 });
  assert.deepStrictEqual(Board.lines(a, b, { by: "room", name: "R1" }).lines, ["1A, 1B, 1C +2", "LIM, TAN"]);
  const x = tcard(2, 0, 1, ["1A", "1B"], [crow({ teachers: [], tshorts: [], room: "" })]);
  assert.deepStrictEqual(Board.lines(x, b, { by: "teacher", name: "" }).lines, ["1A, 1B", "No room"]);
  assert.deepStrictEqual(Board.lines(x, b, { by: "room", name: "" }).lines, ["1A, 1B", "No teacher"]);
  const band = tcard(3, 0, 1, ["1A"], [crow()], { band: "MT" });
  assert.strictEqual(Board.lines(band, b, { by: "teacher", name: "Mr Tan" }).title, "MT");
  assert.deepStrictEqual(Board.lines(a, b), Board.lines(a, b, { by: "class", cls: "1A" }));
});

t("onRow: always true on a teacher or room row", () => {
  const a = tcard(1, 0, 1, ["1A"], [crow()]);
  assert.strictEqual(Board.onRow(a, { by: "teacher", name: "Ms Lim", cls: "" }, board4([a])), true);
  assert.strictEqual(Board.onRow(a, { by: "room", name: "R2", cls: "" }, board4([a])), true);
  assert.strictEqual(Board.onRow(a, { by: "class", cls: "1B" }, board4([a])), false);
});

const T = (name) => ({ by: "teacher", name: name, cls: "" }), R = (name) => ({ by: "room", name: name, cls: "" });

t("hand, teacher: replaces on the first row, adds from No teacher, takes away onto it, null for the same, a duplicate or a class row", () => {
  const plain = tcard(1, 0, 1, ["1A"], [crow()]);
  assert.deepStrictEqual(Board.hand(plain, T("Mr Tan"), T("Ms Lim"), board4([plain])), { kind: "teacher", key: "C:1A:Maths", teachers: ["Ms Lim"] });
  const two = tcard(2, 0, 1, ["1A"], [crow({ teachers: ["Mr Tan", "Ms Lim"] })]);
  assert.deepStrictEqual(Board.hand(two, T("Ms Lim"), T("Mr Ong")), { kind: "teacher", key: "C:1A:Maths", teachers: ["Mr Tan", "Mr Ong"] });
  assert.strictEqual(Board.hand(two, T("Ms Lim"), T("Mr Tan")), null);
  const band = tcard(3, 0, 1, ["1A"], [crow({ key: "G:1MAA1", group: "G1" }), crow({ key: "G:1MAA2", group: "G2", teachers: ["Ms Lim"] })], { band: "MT" });
  assert.deepStrictEqual(Board.hand(band, T("Ms Lim"), T("Mr Ong")), { kind: "teacher", key: "G:1MAA2", teachers: ["Mr Ong"] });
  const none = tcard(4, 0, 1, ["1A"], [crow({ teachers: [], tshorts: [] })]);
  assert.deepStrictEqual(Board.hand(none, T(""), T("Mr Ong")), { kind: "teacher", key: "C:1A:Maths", teachers: ["Mr Ong"] });
  assert.deepStrictEqual(Board.hand(two, T("Ms Lim"), T("")), { kind: "teacher", key: "C:1A:Maths", teachers: ["Mr Tan"] });
  assert.deepStrictEqual(Board.hand(plain, T("Mr Tan"), T("")), { kind: "teacher", key: "C:1A:Maths", teachers: [] });
  assert.strictEqual(Board.hand(plain, T("Mr Tan"), T("Mr Tan")), null);
  assert.strictEqual(Board.hand(plain, T("Mr Tan"), R("R2")), null);
  assert.strictEqual(Board.hand(plain, { by: "class", cls: "1A" }, { by: "class", cls: "1B" }), null);
});

t("hand, room: moves the matching row's room, '' onto No room, null onto its own room", () => {
  const a = tcard(1, 0, 1, ["1A"], [crow(), crow({ group: "G2", key: "G:1MAA1", room: "LAB1" })]);
  assert.deepStrictEqual(Board.hand(a, R("LAB1"), R("R2")), { kind: "room", id: 1, group: "G2", room: "R2" });
  assert.deepStrictEqual(Board.hand(a, R("R1"), R("")), { kind: "room", id: 1, group: "Entire Class", room: "" });
  assert.strictEqual(Board.hand(a, R("R1"), R("R1")), null);
  const none = tcard(2, 0, 1, ["1A"], [crow({ room: "TBC" })]);
  assert.deepStrictEqual(Board.hand(none, R(""), R("R2")), { kind: "room", id: 2, group: "Entire Class", room: "R2" });
  assert.strictEqual(Board.hand(a, R("R2"), R("LAB1")), null);
});

t("handText: each sentence, one lesson and many", () => {
  const a = tcard(1, 0, 1, ["1A"], [crow()]), b = tcard(2, 0, 1, ["1A"], [crow({ key: "G:1MAA1", teachers: [] })], { what: "Maths group 1MAA1" });
  assert.strictEqual(Board.handText(a, T("Mr Tan"), T("Ms Lim"), 3), "Give Maths for 1A to Ms Lim in place of Mr Tan? It changes 3 lessons of Maths for 1A.");
  assert.strictEqual(Board.handText(a, T("Mr Tan"), T("Ms Lim"), 1), "Give Maths for 1A to Ms Lim in place of Mr Tan? It changes 1 lesson of Maths for 1A.");
  assert.strictEqual(Board.handText(b, T(""), T("Ms Lim"), 2), "Give Maths group 1MAA1 to Ms Lim? It changes 2 lessons of group 1MAA1.");
  assert.strictEqual(Board.handText(a, T("Mr Tan"), T(""), 4), "Take Mr Tan off Maths for 1A? It changes 4 lessons of Maths for 1A.");
  assert.strictEqual(Board.handText(a, R("R1"), R("R2"), 1), "Move Maths for 1A to R2?");
  assert.strictEqual(Board.handText(a, R("R1"), R(""), 1), "Leave Maths for 1A with no room?");
});

t("states: a slot with there as a list is ask; null there is judged as before; a push slot still works", () => {
  const c = tcard(1, 0, 1, ["1A"], [crow()]);
  const there = [{ id: 9, what: "Art", classes: ["1B"], groups: [] }];
  const slots = [{ d: 0, p: 2, state: "ok", why: "", swap: null, also: [], there: there }, { d: 0, p: 3, state: "no", why: "x", swap: null, also: [], there: null },
    { d: 0, p: 4, state: "ok", why: "", swap: null, also: [], there: [] }, { d: 0, p: 5, state: "ok", why: "", swap: 9, also: [], push: { state: "ok", why: "", out: [] }, beside: { state: "ok" } }];
  assert.deepStrictEqual(Board.states(c, slots, 0, 6), ["", "own", "ask", "no", "ok", "ask"]);
});

t("people and venues: split in the server's order", () => {
  const lesson = { id: 1, teachers: [{ name: "A", free: true }, { name: "B", free: false }, { name: "C", free: true }],
    rooms: [{ room: "R1", right: true, free: true }, { room: "R2", right: false, free: true }, { room: "R3", right: true, free: false }, { room: "R4", right: true, free: true }] };
  assert.deepStrictEqual(Board.people(lesson).free.map(x => x.name), ["A", "C"]); assert.deepStrictEqual(Board.people(lesson).busy.map(x => x.name), ["B"]);
  const v = Board.venues(lesson);
  assert.deepStrictEqual([v.right.map(x => x.room), v.other.map(x => x.room), v.busy.map(x => x.room)], [["R1", "R4"], ["R2"], ["R3"]]);
  assert.deepStrictEqual(Board.people({}), { free: [], busy: [] });
});

t("teacherFix and roomFix", () => {
  const lesson = { id: 7 }, row = crow({ teachers: ["Mr Tan", "Ms Lim"] });
  assert.deepStrictEqual(Board.teacherFix(lesson, row, 1, "Mr Ong"), { kind: "teacher", key: "C:1A:Maths", teachers: ["Mr Tan", "Mr Ong"] });
  assert.deepStrictEqual(Board.teacherFix(lesson, row, 0, ""), { kind: "teacher", key: "C:1A:Maths", teachers: ["Ms Lim"] });
  assert.deepStrictEqual(Board.teacherFix(lesson, row, 2, "Mr Ong"), { kind: "teacher", key: "C:1A:Maths", teachers: ["Mr Tan", "Ms Lim", "Mr Ong"] });
  assert.deepStrictEqual(Board.teacherFix(lesson, row, 1, "Mr Tan"), { kind: "teacher", key: "C:1A:Maths", teachers: ["Mr Tan"] });
  assert.deepStrictEqual(Board.teacherFix(lesson, crow({ teachers: ["Mr Tan"] }), 0, ""), { kind: "teacher", key: "C:1A:Maths", teachers: [] });
  assert.deepStrictEqual(Board.roomFix(lesson, row, "R2", false), { kind: "room", id: 7, group: "Entire Class", room: "R2" });
  assert.deepStrictEqual(Board.roomFix(lesson, row, "", true), { kind: "room", id: 7, group: "Entire Class", room: "", all: true });
});

t("rowless cards: a card with rows [] or no rows is in the No teacher and No room rows, of is empty, lines does not throw, hand is null", () => {
  const e = tcard(1, 0, 1, ["1A"], [], { what: "Free period" }), m = tcard(2, 0, 2, ["1B"], [], { band: "MT" }); delete m.rows;
  const b = board4([e, m]);
  [["teacher", "No teacher"], ["room", "No room"]].forEach(([by, label]) => {
    const g = Board.groups(b, { kind: "day", d: 0, by: by }), r = g[0].rows[0];
    assert.deepStrictEqual([g[0].name, r.label, r.name], ["", label, ""]);
    assert.deepStrictEqual(r.cards.map(x => x.card.id), [1, 2]);
    assert.deepStrictEqual(Board.of(e, r), []); assert.deepStrictEqual(Board.of(m, r), []);
    assert.strictEqual(Board.lines(e, b, r).title, "Free period");
    assert.strictEqual(Board.lines(m, b, r).title, "MT");
    assert.ok(Array.isArray(Board.lines(e, b, r).lines));
    assert.strictEqual(Board.hand(e, r, by === "teacher" ? T("Mr Ong") : R("R2")), null);
  });
});

t("handText: a subject with a colon; states: there and push together is ask; teacherFix adds to a row with no teachers", () => {
  const a = tcard(1, 0, 1, ["1A"], [crow({ key: "C:1A:Art: Design", subject: "Art" })]);
  assert.strictEqual(Board.handText(a, T("Mr Tan"), T("Ms Lim"), 2), "Give Maths for 1A to Ms Lim in place of Mr Tan? It changes 2 lessons of Art: Design for 1A.");
  const slots = [{ d: 0, p: 2, state: "no", why: "x", swap: null, also: [], there: [{ id: 9, what: "Art", classes: [], groups: [] }], push: { state: "ok", why: "", out: [] } }];
  assert.strictEqual(Board.states(a, slots, 0, 6)[2], "ask");
  assert.deepStrictEqual(Board.teacherFix({ id: 1 }, crow({ teachers: [] }), 3, "Mr Ong"), { kind: "teacher", key: "C:1A:Maths", teachers: ["Mr Ong"] });
});

t("keyName: a class's subject with a colon, and a group", () => {
  assert.strictEqual(Board.keyName(null, "C:1A:Art: Design"), "Art: Design for 1A");
  assert.strictEqual(Board.keyName(null, "G:1MAA1"), "group 1MAA1");
});

t("popAt: beside the point, on its right when it fits, else its left, never past the card's edges", () => {
  assert.deepStrictEqual(Board.popAt({ x: 100, y: 200 }, 320, 150, 1200, 900), { left: 114, top: 176, side: "right" });
  assert.deepStrictEqual(Board.popAt({ x: 1000, y: 200 }, 320, 150, 1200, 900), { left: 666, top: 176, side: "left" });   // no room on the right
  assert.deepStrictEqual(Board.popAt({ x: 100, y: 10 }, 320, 150, 1200, 900).top, 8);                                // not above the card
  assert.deepStrictEqual(Board.popAt({ x: 100, y: 880 }, 320, 150, 1200, 900).top, 742);                             // not below it
  assert.deepStrictEqual(Board.popAt({ x: 20, y: 200 }, 320, 150, 300, 900), { left: 8, top: 176, side: "left" });  // a card narrower than the pop-out: from its left edge
  assert.deepStrictEqual(Board.popAt(null, 320, 150, 1200, 900), { left: 614, top: 8, side: "right" });              // no point yet: the middle of the top
  assert.deepStrictEqual(Board.popAt({ x: NaN, y: 5 }, 320, 150, 1200, 900).top, 8);
});
t("popAt: with rows to keep clear, just under them (else over them), so the lesson's own row stays free to click", () => {
  assert.deepStrictEqual(Board.popAt({ x: 300, y: 200, top: 180, bottom: 340 }, 320, 150, 1200, 900), { left: 276, top: 346, side: "below" });
  assert.deepStrictEqual(Board.popAt({ x: 300, y: 700, top: 650, bottom: 800 }, 320, 150, 1200, 900), { left: 276, top: 494, side: "above" });   // no room under
  assert.deepStrictEqual(Board.popAt({ x: 1150, y: 200, top: 180, bottom: 340 }, 320, 150, 1200, 900).left, 872);                                 // not past the right edge
  assert.deepStrictEqual(Board.popAt({ x: 300, y: 100, top: 20, bottom: 820 }, 320, 150, 1200, 900).side, "right");                               // fits neither: beside the point
});
t("sideWidth: at least 220, at most 60% of the board and panel together", () => {
  assert.strictEqual(Board.sideWidth(400, 1200), 400);
  assert.strictEqual(Board.sideWidth(100, 1200), 220);
  assert.strictEqual(Board.sideWidth(900, 1200), 720);
  assert.strictEqual(Board.sideWidth(300.6, 1200), 301);
  assert.strictEqual(Board.sideWidth(500, 300), 220);   // a narrow window: never under 220
  assert.strictEqual(Board.sideWidth("350", 1200), 350);
  assert.strictEqual(Board.sideWidth("wide", 1200), null);
  assert.strictEqual(Board.sideWidth(null, 1200), null);
  assert.strictEqual(Board.sideWidth("", 1200), null);
});
t("ruleRefusal: the server's sentence for a rule that would be broken, and nothing else", () => {
  assert.strictEqual(Board.ruleRefusal("Rule School · Whole school · Max periods in a row: Jasper Goh teaches 12 periods in a row on Even Fri, more than 9."), true);
  assert.strictEqual(Board.ruleRefusal("Rule Room · Hall · Not available: Hall is not available."), true);
  assert.strictEqual(Board.ruleRefusal("Jasper Goh is teaching group 2ELP1 then."), false);
  assert.strictEqual(Board.ruleRefusal("A1-01 is in use then."), false);
  assert.strictEqual(Board.ruleRefusal("That changes nothing."), false);
  assert.strictEqual(Board.ruleRefusal("Rule"), false);
  assert.strictEqual(Board.ruleRefusal(""), false);
  assert.strictEqual(Board.ruleRefusal(null), false);
});
t("busyRefusal: only the server's two busy sentences, for that teacher or room", () => {
  assert.strictEqual(Board.busyRefusal("Jasper Goh is teaching Character and Citizenship Education for 3D then.", "Jasper Goh", "teacher"), true);
  assert.strictEqual(Board.busyRefusal("Jasper Goh is teaching group 2ELP1 then.", "Jasper Lim", "teacher"), false);
  assert.strictEqual(Board.busyRefusal("A1-01 is in use then.", "A1-01", "room"), true);
  assert.strictEqual(Board.busyRefusal("A1-01 is not on the setup's list of rooms.", "A1-01", "room"), false);
  assert.strictEqual(Board.busyRefusal("A1-01 is in use then.", "A1-01", "teacher"), false);
  assert.strictEqual(Board.busyRefusal("Jasper Goh is teaching X then.", "Jasper Goh", "room"), false);
  assert.strictEqual(Board.busyRefusal("Rule Room · Hall · Not available: Hall is not available.", "Hall", "room"), false);
  assert.strictEqual(Board.busyRefusal("", "", "room"), false);
  assert.strictEqual(Board.busyRefusal(null, "A1-01", "room"), false);
});

t("clashPlace: the day and first period a teacher clash's sentence names", () => {
  const days = ["Odd Mon", "Odd Tue", "Even Mon", "Even Tue"];
  assert.deepStrictEqual(Board.clashPlace("Teacher double-booked: Adeline Tan on Odd Mon period 1 (7.50).", days), { d: 0, p: 1 });
  assert.deepStrictEqual(Board.clashPlace("Teacher double-booked: Farhan Low on Even Mon 11.30-12.30 (periods 12-14).", days), { d: 2, p: 12 });
  assert.deepStrictEqual(Board.clashPlace("Teacher double-booked: Simon on Lee on Odd Tue period 3 (9.10).", days), { d: 1, p: 3 });   // a name that holds " on "
  assert.deepStrictEqual(Board.clashPlace("Teacher double-booked: Ann Ho on Mon B period 4 (9.30).", ["Mon", "Mon B"]), { d: 1, p: 4 });   // the longer day's name first
  assert.deepStrictEqual(Board.clashPlace("Teacher double-booked: Ann Ho on Mon period 4 (9.30).", ["Mon", "Mon B"]), { d: 0, p: 4 });
  assert.strictEqual(Board.clashPlace("Teacher double-booked: Ann Ho on Sun period 4 (9.30).", days), null);
  assert.strictEqual(Board.clashPlace("Teacher double-booked: Ann Ho.", days), null);
  assert.strictEqual(Board.clashPlace(null, days), null);
  assert.strictEqual(Board.clashPlace("Teacher double-booked: Ann Ho on Odd Mon period 1 (7.50).", null), null);
});

t("roomsMeet: a venue meets its own rooms and itself, not its neighbour's", () => {
  const parts = { "Lab 1&2": ["Lab 1", "Lab 2"] };
  assert.strictEqual(Board.roomsMeet(parts, "Lab 1&2", "Lab 1"), true);
  assert.strictEqual(Board.roomsMeet(parts, "Lab 2", "Lab 1&2"), true);
  assert.strictEqual(Board.roomsMeet(parts, "Lab 1&2", "Lab 1&2"), true);
  assert.strictEqual(Board.roomsMeet(parts, "Lab 1", "Lab 2"), false);
  assert.strictEqual(Board.roomsMeet(undefined, "A", "A"), true);
  assert.strictEqual(Board.roomsMeet(undefined, "A", "B"), false);
  assert.strictEqual(Board.roomsMeet(parts, "", "Lab 1"), false);
  assert.strictEqual(Board.roomsMeet(parts, "constructor", "Lab 1"), false);   // a room named as an Object property is a room
  assert.strictEqual(Board.roomsMeet(parts, "toString", "toString"), true);
  assert.strictEqual(Board.roomsMeet({ constructor: ["A", "B"] }, "constructor", "A"), true);
});

t("panels: three entries, a class once, unknown classes emptied, none left is null", () => {
  const all = ["1A", "1B", "2A"];
  assert.deepStrictEqual(Board.panels(["1A", "1B", "2A"], all), ["1A", "1B", "2A"]);
  assert.deepStrictEqual(Board.panels(["1A", "9Z", "1A", "2A"], all), ["1A", "", ""]);
  assert.deepStrictEqual(Board.panels(["", "2A"], all), ["", "2A", ""]);
  [null, undefined, "1A", {}, [], ["", "", ""], ["9Z"], [1, null, {}]].forEach(x => assert.strictEqual(Board.panels(x, all), null));
});
t("panelsFor: what Four panels opens", () => {
  const lv = board([]).levels;   // Sec 1: 1A, 1B; Sec 2: 2A
  assert.deepStrictEqual(Board.panelsFor(["2A", "", "1B"], lv, "", ""), ["2A", "", "1B"]);
  assert.deepStrictEqual(Board.panelsFor(null, lv, "", "Sec 2"), ["2A", "", ""]);
  assert.deepStrictEqual(Board.panelsFor(["9Z"], lv, "", "No such level"), ["1A", "1B", ""]);
  assert.deepStrictEqual(Board.panelsFor(["2A", "", "1B"], lv, "1B", ""), ["2A", "", "1B"]);
  assert.deepStrictEqual(Board.panelsFor(["2A", "", ""], lv, "1B", ""), ["1B", "", ""]);
  assert.deepStrictEqual(Board.panelsFor(null, [{ level: "S", classes: [] }, { level: "T", classes: ["a", "b", "c", "d"] }], "", ""), ["a", "b", "c"]);
  assert.strictEqual(Board.panelsFor(null, [], "", ""), null); assert.strictEqual(Board.panelsFor(["1A"], [{ level: "S", classes: [] }], "", ""), null);
});
t("panelSet: a panel's class changed or emptied", () => {
  assert.deepStrictEqual(Board.panelSet(["1A", "", ""], 1, "1B"), ["1A", "1B", ""]);
  assert.deepStrictEqual(Board.panelSet(["1A", "1B", ""], 0, ""), ["", "1B", ""]);
  assert.deepStrictEqual(Board.panelSet(["1A", "", ""], 0, ""), ["1A", "", ""]);         // the last class stays
  assert.deepStrictEqual(Board.panelSet(["1A", "1B", ""], 2, "1A"), ["1A", "1B", ""]);   // a class is never shown twice
  assert.deepStrictEqual(Board.panelSet(["1A", "1B", ""], 7, "2A"), ["1A", "1B", ""]);
});
t("panelPut and panelShow: a class into the first empty panel", () => {
  assert.deepStrictEqual(Board.panelPut(["1A", "", "2A"], "1B"), ["1A", "1B", "2A"]);
  assert.deepStrictEqual(Board.panelPut(["1A", "", "2A"], "2A"), ["1A", "", "2A"]);
  assert.strictEqual(Board.panelPut(["1A", "1B", "2A"], "3C"), null);
  assert.deepStrictEqual(Board.panelShow(["1A", "", ""], ["2A", "1A"]), { panels: ["1A", "", ""], cls: "1A" });
  assert.deepStrictEqual(Board.panelShow(["1A", "", ""], ["2A", "1B"]), { panels: ["1A", "2A", ""], cls: "2A" });
  assert.strictEqual(Board.panelShow(["1A", "1B", "2A"], ["3C"]), null); assert.strictEqual(Board.panelShow(["1A", "", ""], []), null);
});
t("panes: a panel a class, row keys that never collide, a lesson of two shown classes in both", () => {
  const weeks = [{ name: "", days: [{ i: 0, label: "Mon" }, { i: 1, label: "Tue" }] }];
  const band = card(5, 0, 0, 2, ["1A", "2A"], { band: "MT" }), b = board([band, card(6, 1, 0, 1, ["1B"])]);
  const ps = Board.panes(b, ["1A", "", "2A"], weeks), keys = [].concat(...ps.map(p => [].concat(...p.groups.map(g => g.rows.map(r => r.key)))));
  assert.deepStrictEqual(ps.map(p => p.cls), ["1A", "", "2A"]); assert.deepStrictEqual(ps[1].groups, []);
  assert.deepStrictEqual(keys, ["1A|0", "1A|1", "2A|0", "2A|1"]);
  assert.strictEqual(ps[0].groups[0].rows[0].cards[0].card, band); assert.strictEqual(ps[2].groups[0].rows[0].cards[0].card, band);
  const one = Board.groups(b, { kind: "cycle", cls: "1A" }, weeks)[0].rows[0];
  assert.deepStrictEqual(Object.assign({}, ps[0].groups[0].rows[0], { key: one.key }), one);   // but for its key, the row of the one-class cycle
});
t("lane: the rows share the panel's height, between 16 and 60", () => {
  assert.strictEqual(Board.lane(331, 71, 10), 26); assert.strictEqual(Board.lane(331, 71, 12), 21);
  assert.strictEqual(Board.lane(200, 71, 10), 16); assert.strictEqual(Board.lane(2000, 71, 10), 60);
  assert.strictEqual(Board.lane(0, 0, 0), 16); assert.strictEqual(Board.lane(NaN, 71, 10), 16); assert.strictEqual(Board.lane(331, 71, -3), 60);
});
t("ownRows: whose rows a lesson can go on", () => {
  assert.strictEqual(Board.ownRows(card(1, 0, 0, 1, ["1A"])), "This lesson is 1A's. It can only go on 1A's rows.");
  assert.strictEqual(Board.ownRows(card(1, 0, 0, 1, ["1A", "1B"])), "This lesson is 1A and 1B's. It can only go on their rows.");
  assert.strictEqual(Board.ownRows(card(1, 0, 0, 1, ["1A", "1B", "1C"])), "This lesson is 1A, 1B and 1C's. It can only go on their rows.");
  assert.strictEqual(Board.ownRows(card(1, 0, 0, 1, [])), "");
});

t("tied: the same teacher, else a room that meets, else nothing", () => {
  const mk = (id, teachers, room, more) => card(id, 0, 0, 1, ["1A"], { rows: [{ group: "G", subject: "Maths", teachers: teachers, room: room }].concat(more || []) });
  const a = mk(1, ["Mr Tan", "Ms Lee"], "Lab 1&2"), parts = { "Lab 1&2": ["Lab 1", "Lab 2"] };
  assert.strictEqual(Board.tied(a, mk(2, ["Ms Lee"], "R9"), parts), "teacher");
  assert.strictEqual(Board.tied(a, mk(3, ["Mr Ong"], "R9", [{ group: "H", subject: "Art", teachers: ["Mr Tan"], room: "" }]), parts), "teacher");   // any row
  assert.strictEqual(Board.tied(a, mk(4, ["Mr Ong"], "Lab 2"), parts), "room");      // a combined venue meets its rooms
  assert.strictEqual(Board.tied(a, mk(5, ["Ms Lee"], "Lab 1"), parts), "teacher");   // the teacher comes first
  assert.strictEqual(Board.tied(a, mk(6, ["Mr Ong"], "R9"), parts), "");
  assert.strictEqual(Board.tied(a, a, parts), ""); assert.strictEqual(Board.tied(a, mk(1, ["Mr Tan"], "Lab 1"), parts), "");   // itself, by id
  assert.strictEqual(Board.tied(mk(7, [], ""), mk(9, [], ""), parts), ""); assert.strictEqual(Board.tied(mk(8, [], "TBC"), mk(10, [], "TBC"), undefined), "");
  assert.strictEqual(Board.tied({ id: 11 }, { id: 12 }, parts), "");   // cards with no rows
});
t("blockers: the ids a judged place names, each once, in order", () => {
  assert.deepStrictEqual(Board.blockers({ clashes: [{ kind: "teacher", text: "x", ids: [7] }, { kind: "room", text: "y", ids: [3, 7, 9] }, { kind: "room", text: "z", ids: [] }] }), [3, 7, 9]);
  [null, undefined, {}, { clashes: null }, { clashes: "x" }, { clashes: [{ kind: "class", text: "from an older server" }] }].forEach(s => assert.deepStrictEqual(Board.blockers(s), []));
});

t("tally: where a lesson can go, counted as the board colours its places", () => {
  const c = card(1, 0, 0, 1, ["1A"]), s = (d, p, state, more) => Object.assign({ d: d, p: p, state: state, why: "", swap: null, also: [], there: null }, more || {});
  const slots = [s(0, 1, "ok"), s(0, 2, "ok"), s(0, 3, "prefer"), s(0, 4, "no"), s(0, 5, "na"),
    s(1, 0, "ok", { swap: 5, there: [{ id: 5 }] }), s(1, 1, "na", { there: [{ id: 6 }, { id: 7 }] })];
  assert.deepStrictEqual(Board.tally(c, slots), { ok: 2, prefer: 1, ask: 2 });
  assert.deepStrictEqual(Board.tally(c, null), { ok: 0, prefer: 0, ask: 0 });
});
t("ties: each teacher's other classes with their lessons; a band of several classes says so", () => {
  const mk = (id, cls, teachers) => card(id, 0, 0, 1, cls, { rows: [{ group: "G", subject: "Maths", teachers: teachers, room: "" }] });
  const me = mk(1, ["1A"], ["Mr Tan", "Ms Lee"]);
  const b = board([me, mk(2, ["1A"], ["Mr Tan"]), mk(3, ["2A"], ["Mr Tan"]), mk(4, ["1B"], ["Mr Tan"]), mk(5, ["2A"], ["Mr Tan"]), mk(6, ["1B", "2A"], ["Mr Ong"])]);
  assert.deepStrictEqual(Board.ties(me, b), { band: null, teachers: [{ name: "Mr Tan", classes: [{ cls: "1B", n: 1 }, { cls: "2A", n: 2 }] }, { name: "Ms Lee", classes: [] }] });
  assert.deepStrictEqual(Board.ties(card(7, 0, 0, 1, ["1A", "1B"], { band: "MT" }), b).band, ["1A", "1B"]);
  assert.strictEqual(Board.ties(card(8, 0, 0, 1, ["1A"], { band: "MT" }), b).band, null);
  assert.deepStrictEqual(Board.ties({ id: 9, classes: ["1A"] }, b), { band: null, teachers: [] });
});

console.log(`${n} cases passed`);

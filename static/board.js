/* The board: where each card sits in its row, and the answers the page needs during a drag. Plain functions over the
   board payload (days, NP, levels, codes, subjects, cards) and the options slots, no page access, so they run under
   Node (tests/board.test.js). */
var Board = (function () {
  "use strict";

  function span(card) { var k = Number(card.n); return k > 0 ? k : 1; }

  function byStart(a, b) { return a.p - b.p || span(b) - span(a) || a.id - b.id; }

  /* the cards of one row, each on the lowest lane free in all its periods: [{card, lane}] in start order */
  function lanes(cards) {
    var ends = [], out = [];
    cards.slice().sort(byStart).forEach(function (card) {
      var lane = 0;
      while (lane < ends.length && ends[lane] > card.p) lane++;
      ends[lane] = card.p + span(card);
      out.push({ card: card, lane: lane });
    });
    return out;
  }

  function holds(card, cls) {
    var list = card.classes || [];
    return cls === "" ? list.length === 0 : list.indexOf(cls) >= 0;
  }

  /* the set of classes that have a row in the day mode */
  function known(board) {
    var set = {};
    (board.levels || []).forEach(function (lv) { lv.classes.forEach(function (c) { set[c] = true; }); });
    return set;
  }

  /* a card with no class in any level belongs in the "No class" row */
  function classless(card, set) { return !(card.classes || []).some(function (c) { return set[c]; }); }

  function dots(NP) { return new Array(NP + 1).join("."); }

  function codesFor(board, cls, d) {
    var c = (board.codes || {})[cls];
    return c && c[d] != null ? c[d] : dots(board.NP);
  }

  function row(board, key, label, d, cls, codes, set) {
    var placed = lanes(board.cards.filter(function (c) {
      return c.d === d && (set && cls === "" ? classless(c, set) : holds(c, cls));
    }));
    var used = 1;
    placed.forEach(function (x) { if (x.lane + 1 > used) used = x.lane + 1; });
    return { key: key, label: label, d: d, cls: cls, codes: codes, lanes: used, cards: placed };
  }

  /* day mode: a group per level, a row per class, then "No class" when a card has none; cycle mode: a group per week,
     a row per day for one class */
  function groups(board, mode, weeks) {
    if (mode.kind === "cycle") {
      return (weeks || []).map(function (w) {
        return {
          name: w.name,
          rows: w.days.map(function (day) {
            return row(board, String(day.i), day.label, day.i, mode.cls, codesFor(board, mode.cls, day.i));
          })
        };
      });
    }
    var d = mode.d, set = known(board);
    var out = (board.levels || []).map(function (lv) {
      return { name: lv.level, rows: lv.classes.map(function (c) { return row(board, c, c, d, c, codesFor(board, c, d)); }) };
    });
    if (board.cards.some(function (c) { return classless(c, set); })) {
      out.push({ name: "No class", rows: [row(board, "", "No class", d, "", dots(board.NP).replace(/\./g, "L"), set)] });
    }
    return out;
  }

  function open(code) { return code === "L" || code === "A"; }

  function box(card, NP) {
    var last = NP - 1, from = Math.max(0, Math.min(card.p, last));
    return { from: from, to: Math.max(from, Math.min(card.p + span(card) - 1, last)) };
  }

  function subjectOf(board, name) { return (board.subjects || {})[name] || null; }

  function lines(card, board) {
    var rows = card.rows || [], first = rows[0], info = first ? subjectOf(board, first.subject) : null;
    var color = info && info[1] ? info[1] : 0;
    if (card.band) return { title: card.band, lines: [rows.length === 1 ? "1 group" : rows.length + " groups"], color: color };
    if (!first) return { title: "", lines: ["No teacher", "No room"], color: 0 };
    var teachers = first.tshorts && first.tshorts.length ? first.tshorts.join(", ") : "No teacher";
    return { title: info && info[0] ? info[0] : first.subject, lines: [teachers, first.room || "No room"], color: color };
  }

  function finds(board) {
    var subs = {}, depts = {};
    board.cards.forEach(function (c) {
      (c.rows || []).forEach(function (r) {
        subs[r.subject] = true;
        var info = subjectOf(board, r.subject);
        if (info && info[2]) depts[info[2]] = true;
      });
    });
    var out = [{ value: "", label: "All subjects" }];
    Object.keys(depts).sort().forEach(function (d) { out.push({ value: "d:" + d, label: d + " (department)" }); });
    Object.keys(subs).sort().forEach(function (s) { out.push({ value: "s:" + s, label: s }); });
    return out;
  }

  function matches(card, find, board) {
    if (!find) return true;
    var kind = find.slice(0, 2), name = find.slice(2);
    return (card.rows || []).some(function (r) {
      if (kind === "s:") return r.subject === name;
      if (kind === "d:") { var info = subjectOf(board, r.subject); return !!info && name !== "" && info[2] === name; }
      return false;
    });
  }

  function grab(card, p) { return Math.max(0, Math.min(p - card.p, span(card) - 1)); }

  function start(p, g) { return Math.max(0, p - g); }

  function slot(card, slots, d, p) {
    if (d === card.d && p === card.p) return { d: d, p: p, state: "own", why: "", swap: null, also: [] };
    var found = null;
    (slots || []).forEach(function (s) { if (!found && s.d === d && s.p === p) found = s; });
    return found;
  }

  function states(card, slots, d, NP) {
    var out = [], p, s;
    for (p = 0; p < NP; p++) { s = slot(card, slots, d, p); out.push(s && s.state ? s.state : ""); }
    return out;
  }

  function can(s) { return !!s && (s.state === "ok" || s.state === "prefer"); }

  /* the slot that swaps the selected lesson with lesson id, when the app allows it, else null */
  function target(slots, id) {
    var found = null;
    (slots || []).forEach(function (s) { if (!found && s.swap === id && can(s)) found = s; });
    return found;
  }

  function fix(card, s) {
    if (s.swap !== null && s.swap !== undefined) return { kind: "swap", a: card.id, b: s.swap };
    return { kind: "move", id: card.id, d: s.d, p: s.p };
  }

  /* with the board, the "No class" row (cls "") also takes a card none of whose classes is in a level */
  function onRow(card, r, board) {
    if (board && r.cls === "") return classless(card, known(board));
    return holds(card, r.cls);
  }

  function tell(s, days) {
    if (s.state === "own") return "This is where the lesson is now.";
    var day = days[s.d], p = s.p;
    var text = s.swap !== null && s.swap !== undefined
      ? "Swap with the lesson on " + day + " period " + p + "."
      : "Move to " + day + " period " + p + ".";
    return s.why ? text + " " + s.why : text;
  }

  return { lanes: lanes, groups: groups, open: open, box: box, lines: lines, finds: finds, matches: matches, grab: grab,
           start: start, slot: slot, states: states, can: can, target: target, fix: fix, onRow: onRow, tell: tell };
})();
if (typeof module !== "undefined") module.exports = Board;

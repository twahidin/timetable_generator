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

  function build(board, key, label, d, codes, test, extra) {
    var placed = lanes(board.cards.filter(function (c) { return c.d === d && test(c); }));
    var used = 1;
    placed.forEach(function (x) { if (x.lane + 1 > used) used = x.lane + 1; });
    var out = { key: key, label: label, d: d, cls: "", codes: codes, lanes: used, cards: placed };
    Object.keys(extra || {}).forEach(function (k) { out[k] = extra[k]; });
    return out;
  }

  function row(board, key, label, d, cls, codes, set) {
    var out = build(board, key, label, d, codes, function (c) { return set && cls === "" ? classless(c, set) : holds(c, cls); }, {});
    out.cls = cls;
    out.by = "class"; out.name = cls;
    return out;
  }

  /* the rows of a card that put it in a teacher's or room's board row; name "" is the "No teacher" / "No room" row */
  function matching(card, by, name) {
    return (card.rows || []).filter(function (r) {
      if (by === "teacher") {
        var t = r.teachers || [];
        return name === "" ? t.length === 0 : t.indexOf(name) >= 0;
      }
      return name === "" ? (r.room || "") === "" || r.room === "TBC" : r.room === name;
    });
  }

  /* whether the card is in the board row: a card with no rows has no teacher and no room, so it is in the "No" rows */
  function inRow(card, by, name) {
    return matching(card, by, name).length > 0 || (name === "" && !(card.rows || []).length);
  }

  function dayCodes(board, d) {
    var c = board.day && board.day[d] != null ? board.day[d] : null;
    return c !== null ? c : dots(board.NP).replace(/\./g, "L");
  }

  function personRow(board, by, name, d) {
    return build(board, name, name === "" ? (by === "teacher" ? "No teacher" : "No room") : name, d, dayCodes(board, d),
      function (c) { return inRow(c, by, name); }, { by: by, name: name });
  }

  /* names of teachers (or rooms) the day's cards use, sorted */
  function used(board, by, d) {
    var seen = {};
    board.cards.forEach(function (c) {
      if (c.d !== d) return;
      (c.rows || []).forEach(function (r) {
        if (by === "teacher") (r.teachers || []).forEach(function (t) { if (t !== "") seen[t] = true; });
        else if (r.room && r.room !== "TBC") seen[r.room] = true;
      });
    });
    return Object.keys(seen).sort();
  }

  /* day mode by teacher or room: the "No ..." row first when a card needs it, a group per department or kind, then the
     names the cards use that the setup lacks */
  function peopleGroups(board, by, d) {
    var out = [], listed = {}, src = by === "teacher" ? board.teachers || [] : board.rooms || [];
    if (board.cards.some(function (c) { return c.d === d && inRow(c, by, ""); })) out.push({ name: "", rows: [personRow(board, by, "", d)] });
    src.forEach(function (g) {
      var names = by === "teacher" ? (g.teachers || []).map(function (t) { return t.name; }) : g.rooms || [];
      var title = by === "teacher" ? (g.dept === "" ? "No department" : g.dept) : g.kind;
      names.forEach(function (n) { listed[n] = true; });
      out.push({ name: title, rows: names.map(function (n) { return personRow(board, by, n, d); }) });
    });
    var extra = used(board, by, d).filter(function (n) { return !listed[n]; });
    if (extra.length) out.push({ name: "Not in the setup", rows: extra.map(function (n) { return personRow(board, by, n, d); }) });
    return out;
  }

  /* day mode: a group per level, a row per class, then "No class" when a card has none; cycle mode: a group per week,
     a row per day for one class, teacher or room; mode.by "teacher" or "room" makes the day rows per person */
  function groups(board, mode, weeks) {
    var by = mode.by || "class";
    if (mode.kind === "cycle") {
      return (weeks || []).map(function (w) {
        return {
          name: w.name,
          rows: w.days.map(function (day) {
            if (by === "class") return row(board, String(day.i), day.label, day.i, mode.cls, codesFor(board, mode.cls, day.i));
            var r = personRow(board, by, mode.name, day.i);
            r.key = String(day.i); r.label = day.label;
            return r;
          })
        };
      });
    }
    var d = mode.d, set = known(board);
    if (by !== "class") return peopleGroups(board, by, d);
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

  /* the rows of the card that put it in this board row: all of them for a class row */
  function of(card, r) {
    var by = r && r.by ? r.by : "class";
    return by === "class" ? (card.rows || []).slice() : matching(card, by, r.name || "");
  }

  function classText(card) {
    var cs = card.classes || [];
    return cs.slice(0, 3).join(", ") + (cs.length > 3 ? " +" + (cs.length - 3) : "");
  }

  function lines(card, board, r) {
    var by = r && r.by ? r.by : "class", rows = card.rows || [];
    var first = by === "class" ? rows[0] : of(card, r)[0] || rows[0], info = first ? subjectOf(board, first.subject) : null;
    var color = info && info[1] ? info[1] : 0;
    if (by !== "class" && first) {
      var title = card.band ? card.band : info && info[0] ? info[0] : first.subject;
      var second = by === "teacher" ? first.room || "No room" : first.tshorts && first.tshorts.length ? first.tshorts.join(", ") : "No teacher";
      return { title: title, lines: [classText(card), second], color: color };
    }
    if (card.band) return { title: card.band, lines: [rows.length === 1 ? "1 group" : rows.length + " groups"], color: color };
    if (!first) return { title: card.band || card.what || "", lines: ["No teacher", "No room"], color: 0 };
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

  function inTray(card) { return !!card && (card.d === null || card.d === undefined); }

  /* what a drop on a place with another lesson offers this card (a lesson from the tray is never swapped), or null */
  function offers(card, s) {
    var a = asks(s); if (!a) return null;
    return { swap: a.swap && !inTray(card), push: a.push, beside: a.beside };
  }

  /* the colour of each period of day d for the card: its slot's state, but "ask" where another lesson is and a drop there
     offers a swap, a place beside or a push, and "na" where another lesson is and nothing can be done */
  function states(card, slots, d, NP) {
    var out = [], p, s, o;
    for (p = 0; p < NP; p++) {
      s = slot(card, slots, d, p); o = s && s.state !== "own" ? offers(card, s) : null;
      if (s && s.state !== "own" && Array.isArray(s.there) && s.there.length) { out.push("ask"); continue; }
      out.push(o ? (o.swap || o.push || o.beside ? "ask" : "na") : s && s.state ? s.state : "");
    }
    return out;
  }

  function can(s) { return !!s && (s.state === "ok" || s.state === "prefer"); }

  /* the slot that swaps the selected lesson with lesson id, when the app allows it, else null */
  function target(slots, id) {
    var found = null;
    (slots || []).forEach(function (s) { if (!found && s.swap === id && can(s)) found = s; });
    return found;
  }

  /* the slot a dragged lesson is aimed at: the swap with the lesson under the pointer (over, its id, or null) when the app
     allows that swap, else the slot at the start p that the pointer gives on day d */
  function aim(card, slots, d, p, over) {
    var t = over !== null && over !== undefined && over !== card.id ? target(slots, over) : null;
    return t || slot(card, slots, d, p);
  }

  /* a place a lesson can be put down on with nothing in the way to push out, even one that will clash (judged "no") */
  function lands(s) {
    return !!s && !s.push && (s.state === "ok" || s.state === "prefer" || s.state === "no");
  }

  /* a place that will clash: dropping there is forced */
  function forced(s) { return !!s && s.state === "no"; }

  function fits(j) { return !!j && (j.state === "ok" || j.state === "prefer"); }

  /* what a drop on a place with another lesson asks: swap (the one lesson, allowed and clean or bending), push out, and
     put it beside (the plain move or place, the other lessons left there, clean or bending; a slot from an older server
     has no beside) */
  function asks(s) {
    if (!s || !s.push) return null;
    return { swap: s.swap !== null && s.swap !== undefined && fits(s), push: s.push.state !== "na", beside: fits(s.beside) };
  }

  /* a forced change carries the sentence the page showed for the place, so the server keeps it only for that same reason */
  function force(out, why) { out.force = true; out.why = why || ""; return out; }

  /* the fix a drop sends. how is "move" (default), "swap", "push" or "beside" (the plain move or place, never forced);
     with no how, a slot with a swap gives the swap, as before this stage. A lesson from the tray is placed, never swapped. */
  function fix(card, s, how) {
    var tray = card.d === null || card.d === undefined;
    if (how === undefined && !tray && s.swap !== null && s.swap !== undefined) how = "swap";
    if (how === "swap" && !tray) return { kind: "swap", a: card.id, b: s.swap };
    var out = { kind: tray ? "place" : "move", id: card.id, d: s.d, p: s.p };
    if (how === "beside") return out;
    if (how === "push") {
      out.push = true;
      if (s.push && s.push.state === "no") force(out, s.push.why);
    } else if (forced(s)) force(out, s.why);
    return out;
  }

  /* the fix that puts a lesson the plan wants more of onto the board */
  function addFix(short, s, how) {
    var out = { kind: "add", key: short.key, d: s.d, p: s.p, n: short.n };
    if (how === "push") {
      out.push = true;
      if (s.push && s.push.state === "no") force(out, s.push.why);
    } else if (forced(s)) force(out, s.why);
    return out;
  }

  /* the delete of a lesson as the page posts it: forced, with the judgement's sentence, when the judgement is "no" */
  function deleteFix(card, j) {
    var out = { kind: "delete", id: card.id };
    return j && j.state === "no" ? force(out, j.why) : out;
  }

  function liftFix(card) { return { kind: "lift", id: card.id }; }

  function pushWords(out) {
    var names = out.map(function (o) { return o.what; });
    return names.length >= 3 ? "Push out " + names.length + " lessons" : "Push out " + names.join(" and ");
  }

  /* names in a sentence: "a", "a and b", "a, b and c" */
  function list(xs) { return xs.length < 2 ? xs.join("") : xs.slice(0, -1).join(", ") + " and " + xs[xs.length - 1]; }

  /* what the page asks when a lesson is dropped where another lesson is */
  function question(card, s, board) {
    var a = asks(s) || { swap: false, push: false }, out = s.push ? s.push.out || [] : [], mine = card.classes || [];
    var text = card.what + " on " + board.days[s.d] + " period " + s.p + ": another lesson is there.";
    var swap = null, push = null, beside = null, also = [];
    if (a.swap) {
      var other = null;
      out.forEach(function (o) { if (other === null && o.id === s.swap) other = o; });
      swap = other ? "Swap with " + other.what : "Swap";
      also = (s.also || []).slice();
    }
    if (a.push && out.length) {
      push = pushWords(out);
      out.forEach(function (o) {   // a band pushed out leaves other classes too: say which
        var more = (o.classes || []).filter(function (c) { return mine.indexOf(c) < 0; });
        if (more.length) also.push("This also takes it off " + list(more) + ".");
      });
      if (s.push.state === "no") also.push("It will still land with a problem: " + s.push.why);
    }
    if (a.beside && out.length) beside = out.length > 1 ? "Put it beside them" : "Put it beside " + out[0].what;
    return { text: text, also: also, swap: swap, push: push, beside: beside };
  }

  /* with the board, the "No class" row (cls "") also takes a card none of whose classes is in a level */
  function onRow(card, r, board) {
    if (r.by === "teacher" || r.by === "room") return true;
    if (board && r.cls === "") return classless(card, known(board));
    return holds(card, r.cls);
  }

  /* what the line says over a place; card (optional) tells a lesson from the tray, which is placed and never swapped */
  function tell(s, days, card) {
    if (s.state === "own") return "This is where the lesson is now.";
    var tray = !!card && (card.d === null || card.d === undefined), go = tray ? "Place on " : "Move to ";
    var day = days[s.d], p = s.p, has = !tray && s.swap !== null && s.swap !== undefined;
    if (s.push) {   // another lesson is there: what a drop offers, in this order
      var o = offers(card, s), can = [o.swap ? "swap" : "", o.beside ? "put it beside" : "", o.push ? "push it out" : ""].filter(Boolean);
      if (!can.length) return ("Another lesson is there and it cannot be moved out: " + (s.push.why || s.why || "")).trim();
      return "Another lesson is there. Drop to " + (can.length < 2 ? can[0] : can.slice(0, -1).join(", ") + " or " + can[can.length - 1]) + ".";
    }
    var text = has ? "Swap with the lesson on " + day + " period " + p + "."
      : s.state === "no" && s.why ? go + day + " period " + p + ". It lands with a problem: " + s.why
      : go + day + " period " + p + ".";
    return s.why && !(s.state === "no" && !has) ? text + " " + s.why : text;
  }

  /* the marks of a card, a missing list being empty */
  function marksOf(card) { return card.marks || []; }

  var MARK = { notplaced: "Not placed", noteacher: "No teacher", "break": "In a break", teacher: "In two places",
    "class": "In two places", room: "In two places", noroom: "No room" };
  var COUNTERS = [["notplaced", "Not placed"], ["noteacher", "No teacher"], ["twoplaces", "In two places"],
    ["inbreak", "Not lesson time"], ["noroom", "No room"]];

  /* a mark that stops the publish: every one but "no room" */
  function critical(card) { return marksOf(card).some(function (m) { return m !== "noroom"; }); }

  /* the words on a card's corner: its first mark (the server lists them by weight), and whether it is critical */
  function badge(card) {
    var m = marksOf(card);
    return m.length ? { text: m[0] === "break" && card.out ? "Outside the day" : MARK[m[0]] || "", crit: critical(card) } : null;   // out: no school then for the class, or past the day's end
  }

  function firstClass(card) { return (card.classes || [])[0] || ""; }

  /* the lessons not placed, in a group per first class: the levels' classes in order, other classes by name, "" last */
  function tray(board) {
    var order = [], seen = {}, groups = {}, extra = [];
    (board.levels || []).forEach(function (lv) { lv.classes.forEach(function (c) { if (!seen[c]) { seen[c] = true; order.push(c); } }); });
    (board.unplaced || []).forEach(function (c) {
      var k = firstClass(c);
      if (!Object.prototype.hasOwnProperty.call(groups, k)) { groups[k] = []; if (!seen[k] && k !== "") extra.push(k); }
      groups[k].push(c);
    });
    extra.sort();
    return order.concat(extra, [""]).filter(function (k) { return Object.prototype.hasOwnProperty.call(groups, k); })
      .map(function (k) { return { cls: k, cards: groups[k] }; });
  }

  function has(card, kinds) { return marksOf(card).some(function (m) { return kinds.indexOf(m) >= 0; }); }

  var TWO = ["teacher", "class", "room"];

  function counts(board) {
    var c = { notplaced: (board.unplaced || []).length, noteacher: 0, twoplaces: 0, inbreak: 0, noroom: 0 };
    (board.cards || []).forEach(function (x) {
      if (has(x, ["noteacher"])) c.noteacher++;
      if (has(x, TWO)) c.twoplaces++;
      if (has(x, ["break"])) c.inbreak++;
      if (has(x, ["noroom"])) c.noroom++;
    });
    return c;
  }

  function byPlace(a, b) {
    var x = firstClass(a), y = firstClass(b);
    if (a.d !== b.d) return a.d - b.d;
    if (a.p !== b.p) return a.p - b.p;
    if (x !== y) return x === "" ? 1 : y === "" ? -1 : x < y ? -1 : 1;
    return a.id - b.id;
  }

  /* the cards a counter counts: the tray's cards in the tray's order, the others by day, period, first class, id */
  function hits(board, counter) {
    if (counter === "notplaced") {
      var out = [];
      tray(board).forEach(function (g) { out = out.concat(g.cards); });
      return out;
    }
    var kinds = { noteacher: ["noteacher"], twoplaces: TWO, inbreak: ["break"], noroom: ["noroom"] }[counter] || [];
    return (board.cards || []).filter(function (c) { return has(c, kinds); }).sort(byPlace);
  }

  /* the card after the one with id in hits: the first when id is not there or is the last; null when there are none */
  function step(list, id) {
    if (!list.length) return null;
    var at = -1;
    list.forEach(function (c, i) { if (at < 0 && c.id === id) at = i; });
    return list[at < 0 || at === list.length - 1 ? 0 : at + 1];
  }

  /* the open warnings (no decision) that name a lesson (where.id a number), by lesson id, the critical ones first */
  function warned(warnings) {
    var out = {};
    (warnings || []).forEach(function (w) {
      var id = w && !w.decision && w.where ? w.where.id : null;
      if (typeof id !== "number") return;
      (out[id] = out[id] || []).push(w);
    });
    Object.keys(out).forEach(function (k) { out[k] = out[k].filter(function (w) { return !!w.crit; }).concat(out[k].filter(function (w) { return !w.crit; })); });
    return out;
  }

  /* what a card's corner says: its mark's badge, else how many open warnings name it, else null */
  function flag(card, warned) {
    var b = badge(card); if (b) return b;
    var n = ((warned || {})[card.id] || []).length;
    return n ? { text: n === 1 ? "1 warning" : n + " warnings", crit: false } : null;
  }

  /* where a warning's "Show me" goes: its lesson on the board (d its day) or in the tray (d null); else its class, on the
     warning's day when the board has that day; else null */
  function at(w, board) {
    var h = w && w.where; if (!h) return null;
    if (typeof h.id === "number") {
      var c = (board.cards || []).filter(function (x) { return x.id === h.id; })[0] || (board.unplaced || []).filter(function (x) { return x.id === h.id; })[0];
      if (c) return { id: c.id, d: c.d === null || c.d === undefined ? null : c.d, cls: firstClass(c) };
    }
    var all = [].concat.apply([], (board.levels || []).map(function (lv) { return lv.classes; }));
    if (!h.cls || all.indexOf(h.cls) < 0) return null;
    var d = h.day ? (board.days || []).indexOf(h.day) : -1;
    return { id: null, d: d < 0 ? null : d, cls: h.cls };
  }

  /* the place a teacher clash's sentence names ("...: {teacher} on {day} period {p} (7.50)." or "... on {day} 11.30-12.30 (periods 12-14).")
     -> {d, p}: the day's index in days and the first period; null when it names no day of days. A name may hold " on ", so each " on "
     is tried; the longest day's name is tried first ("Mon B" before "Mon") */
  function clashPlace(text, days) {
    var s = String(text || ""), list = (days || []).map(function (n, i) { return { n: String(n), i: i }; })
      .sort(function (a, b) { return b.n.length - a.n.length; });
    for (var at = s.indexOf(" on "); at >= 0; at = s.indexOf(" on ", at + 1)) {
      var rest = s.slice(at + 4);
      for (var k = 0; k < list.length; k++) {
        if (rest.indexOf(list[k].n + " ") !== 0) continue;
        var tail = rest.slice(list[k].n.length), m = /^ period (\d+)/.exec(tail) || /^ [\d.:]+-[\d.:]+ \(periods? (\d+)/.exec(tail);
        if (m) return { d: list[k].i, p: Number(m[1]) };
      }
    }
    return null;
  }

  function keyName(card, key) {
    var parts = String(key || "").split(":");
    if (parts[0] === "G") return "group " + parts.slice(1).join(":");
    return parts.slice(2).join(":") + " for " + parts[1];
  }

  function same(from, to) {
    var a = from && from.by, b = to && to.by;
    return !!a && a === b && a !== "class";
  }

  /* the fix that hands the lesson from one teacher's (or room's) row to another's, or null when nothing would change */
  function hand(card, from, to, board) {
    if (!same(from, to) || from.name === to.name) return null;
    var r = of(card, from)[0];
    if (!r) return null;
    if (from.by === "room") return to.name === (r.room || "") ? null : { kind: "room", id: card.id, group: r.group, room: to.name };
    var t = (r.teachers || []).slice(), at = t.indexOf(from.name);
    if (to.name !== "" && t.indexOf(to.name) >= 0) return null;
    if (to.name === "") { if (at >= 0) t.splice(at, 1); }
    else if (from.name === "" || at < 0) t.push(to.name);
    else t[at] = to.name;
    return { kind: "teacher", key: r.key, teachers: t };
  }

  /* what the page asks before a hand-over; n is the number of lessons the change touches */
  function handText(card, from, to, n) {
    var what = card.what;
    if (from.by === "room") return to.name === "" ? "Leave " + what + " with no room?" : "Move " + what + " to " + to.name + "?";
    var r = of(card, from)[0], name = keyName(card, r ? r.key : ""), count = n + (n === 1 ? " lesson" : " lessons");
    var tail = " It changes " + count + " of " + name + ".";
    if (to.name === "") return "Take " + from.name + " off " + what + "?" + tail;
    if (from.name === "") return "Give " + what + " to " + to.name + "?" + tail;
    return "Give " + what + " to " + to.name + " in place of " + from.name + "?" + tail;
  }

  /* whether the server refused a teacher or room fix because that teacher (kind "teacher") or room (kind "room") is busy then: its
     sentence is "{name} is teaching ... then." or "{room} is in use then." (fixes.Busy); only then may the fix be forced with it */
  function busyRefusal(sentence, who, kind) {
    var s = typeof sentence === "string" ? sentence : "";
    if (!who) return false;
    if (kind === "teacher") return s.indexOf(who + " is teaching ") === 0 && / then\.$/.test(s);
    if (kind === "room") return s === who + " is in use then.";
    return false;
  }

  /* a lesson's teachers split into those free then and those busy, each in the server's order */
  function people(lesson) {
    var all = (lesson && lesson.teachers) || [];
    return { free: all.filter(function (x) { return x.free; }), busy: all.filter(function (x) { return !x.free; }) };
  }

  /* a lesson's rooms: free and right for it, free and not right, busy */
  function venues(lesson) {
    var all = (lesson && lesson.rooms) || [];
    return { right: all.filter(function (x) { return x.free && x.right; }), other: all.filter(function (x) { return x.free && !x.right; }),
             busy: all.filter(function (x) { return !x.free; }) };
  }

  /* the fix that puts name in place of the row's ith teacher ("" takes it away; i past the end adds), with no duplicates */
  function teacherFix(lesson, r, i, name) {
    var t = (r.teachers || []).slice();
    if (name === "") t.splice(i, 1); else t[Math.min(i, t.length)] = name;
    return { kind: "teacher", key: r.key, teachers: t.filter(function (x, k) { return t.indexOf(x) === k; }) };
  }

  function roomFix(lesson, r, room, all) {
    var out = { kind: "room", id: lesson.id, group: r.group, room: room };
    if (all) out.all = true;
    return out;
  }

  return { lanes: lanes, groups: groups, open: open, box: box, lines: lines, finds: finds, matches: matches, grab: grab,
           start: start, slot: slot, states: states, can: can, target: target, aim: aim, fix: fix, onRow: onRow, tell: tell,
           MARK: MARK, COUNTERS: COUNTERS, critical: critical, badge: badge, tray: tray, counts: counts, hits: hits, step: step,
           lands: lands, forced: forced, asks: asks, offers: offers, addFix: addFix, liftFix: liftFix, deleteFix: deleteFix, question: question,
           warned: warned, flag: flag, at: at, clashPlace: clashPlace, of: of, hand: hand, handText: handText, people: people, venues: venues,
           teacherFix: teacherFix, roomFix: roomFix, keyName: keyName, busyRefusal: busyRefusal };
})();
if (typeof module !== "undefined") module.exports = Board;

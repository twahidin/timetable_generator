/* The Ask tab: what a click on a lesson or an empty place asks the server, and what to show and send for each answer. Plain
   functions, no page access, so they run under Node (tests/ask.test.js). Board is a page global, or board.js under Node. */
var Ask = (function () {
  "use strict";

  var B = typeof Board !== "undefined" ? Board : require("./board.js");

  function span(card) { var k = Number(card.n); return k > 0 ? k : 1; }

  function onTimetable(card) { return card.d !== null && card.d !== undefined; }

  /* the question a click on a lesson asks; from is the row it was clicked on ({by, name}) or null */
  function ofCard(card, from) {
    var rows = card.rows || [], out = { kind: "lesson", id: card.id, group: null, teacher: null };
    if (from && from.by === "teacher") {
      out.teacher = from.name;
      rows.some(function (r) { if ((r.teachers || []).indexOf(from.name) >= 0) { out.group = r.group; return true; } return false; });
    } else if (from && from.by === "room") {
      rows.some(function (r) { if (r.room === from.name) { out.group = r.group; return true; } return false; });
    }
    return out;
  }

  /* the question a click on a place of the board asks (a class row's name is its cls) */
  function ofPlace(at) { return { kind: "place", by: at.by, name: at.by === "class" ? at.cls : at.name, d: at.d, p: at.p }; }

  /* whether no card of that row covers period p on day d */
  function empty(board, at) {
    var row = { by: at.by, name: at.name, cls: at.cls };
    return !board.cards.some(function (c) {
      if (c.d !== at.d || at.p < c.p || at.p >= c.p + span(c)) return false;
      return at.by === "class" ? B.onRow(c, row, board) : B.of(c, row).length > 0;
    });
  }

  /* the groups a card with more than one row lets the person choose between: [{group, label}] */
  function groups(card) {
    var rows = card.rows || [];
    return rows.length > 1 ? rows.map(function (r) { return { group: r.group, label: r.group + " · " + r.subject }; }) : [];
  }

  /* the starter questions for a lesson (card, on the timetable or in the tray) or a place */
  function starters(sub, card) {
    if (sub.kind === "place") return [{ q: "fill", label: "What can go here?" }, { q: "free", label: "Who is free then?" }];
    var teachers = { q: "teachers", label: "Who else could teach it?" }, rooms = { q: "rooms", label: "Which rooms could it use?" };
    if (card && !onTimetable(card)) return [{ q: "moves", label: "Where can it go?" }, teachers, rooms];
    return [{ q: "swaps", label: "What can this swap with?" }, { q: "moves", label: "Where else can it go?" }, teachers,
            { q: "trades", label: "Who could I trade this class with?" }, rooms];
  }

  /* the query string (no "?") of GET /api/draft/about for this question */
  function query(sub, q) {
    var parts = [["q", q], ["kind", sub.kind]];
    if (sub.kind === "place") parts.push(["by", sub.by], ["name", sub.name], ["d", sub.d], ["p", sub.p]);
    else {
      parts.push(["id", sub.id]);
      if (sub.group !== null && sub.group !== undefined) parts.push(["group", sub.group]);
      if (sub.teacher !== null && sub.teacher !== undefined) parts.push(["teacher", sub.teacher]);
    }
    return parts.map(function (x) { return x[0] + "=" + encodeURIComponent(String(x[1])); }).join("&");
  }

  /* the words and the style class for an option's state */
  function verdict(option) {
    if (option.state === "ok") return { text: "Clean", cls: "ok" };
    if (option.state === "prefer") return { text: "Bends a rule", cls: "prefer" };
    return { text: "Lands with a problem", cls: "no" };
  }

  /* where and what to post to apply an option, or null when it cannot be applied */
  function send(option, stamp) {
    if (option.apply === "none") return null;
    var fixes = option.fixes || [];
    if (fixes.length === 1) {
      var body = {};
      Object.keys(fixes[0]).forEach(function (k) { body[k] = fixes[0][k]; });
      body.stamp = stamp;
      if (option.apply === "anyway") { body.force = true; body.why = option.why; }
      return { url: "/api/draft/fix", body: body };
    }
    return { url: "/api/draft/fixes", body: { fixes: fixes, stamp: stamp } };
  }

  /* whether the board has changed since this log entry's answer */
  function stale(entry, stamp) { return entry.stamp !== stamp; }

  /* the lesson "Show on the board" goes to, or null when the option names no single lesson */
  function target(option) {
    var f = (option.fixes || [])[0];
    if (!f) return null;
    if (f.kind === "move" || f.kind === "place" || f.kind === "room") return f.id;
    return f.kind === "swap" ? f.a : null;
  }

  return { ofCard: ofCard, ofPlace: ofPlace, empty: empty, groups: groups, starters: starters, query: query, verdict: verdict,
           send: send, stale: stale, target: target };
})();
if (typeof module !== "undefined") module.exports = Ask;

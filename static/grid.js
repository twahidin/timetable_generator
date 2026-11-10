/* The week as a table: which lessons start in which cell, which cells lie under a longer lesson, and the words for a slot
   the options list offers. Plain functions over the grid payload (days, NP, codes, lessons) and the options slots, no page
   access, so they run under Node (tests/grid.test.js). */
var Grid = (function () {
  "use strict";

  var ORDER = { ok: 0, prefer: 1, no: 2 };

  /* [{name, days: [{i, label}]}]: "Odd Mon" ... make weeks "Odd" and "Even"; any other school is one week named "" */
  function weeks(days) {
    var two = days.length > 0 && days.every(function (d) { return /^(Odd|Even) /.test(d); });
    var out = [], by = {};
    days.forEach(function (d, i) {
      var name = "", label = d, m = /^(Odd|Even) (.*)$/.exec(d);
      if (two && m) { name = m[1]; label = m[2]; }
      if (!by[name]) { by[name] = { name: name, days: [] }; out.push(by[name]); }
      by[name].days.push({ i: i, label: label });
    });
    return out.length ? out : [{ name: "", days: [] }];
  }

  /* one row per period, one cell per day of the week: {d, p, code, lessons, rowspan, covered} */
  function table(payload, week) {
    var rows = [], p, np = payload.NP, lessons = payload.lessons || [];
    var under = {};   // "d:p" of the cells lying under an earlier cell's span
    var cells = week.days.map(function (day) {
      var col = [];
      for (p = 0; p < np; p++) {
        var here = lessons.filter(function (r) { return r.d === day.i && r.p === p; });
        var span = here.reduce(function (m, r) { return Math.max(m, r.n); }, 1);
        col.push({ d: day.i, p: p, code: (payload.codes[day.i] || "")[p] || ".", lessons: here, rowspan: span, covered: false });
      }
      col.forEach(function (c) {
        if (c.covered) return;   // a lesson that starts under another's span does not cover cells of its own
        for (var q = c.p + 1; q < c.p + c.rowspan && q < np; q++) col[q].covered = true;
      });
      return col;
    });
    for (p = 0; p < np; p++) rows.push(cells.map(function (col) { return col[p]; }));
    return rows;
  }

  function lesson(payload, id, group) {
    return (payload.lessons || []).find(function (r) { return r.id === id && r.group === group; }) || null;
  }
  function same(a, b) { return !!a && !!b && a.id === b.id && a.group === b.group; }

  function slotAt(slots, d, p) {
    return (slots || []).find(function (s) { return s.d === d && s.p === p; }) || null;
  }
  function stateClass(state) { return state === "ok" || state === "prefer" || state === "no" || state === "na" ? state : ""; }

  function slotText(slot, days) {
    var where = days[slot.d] + " period " + slot.p;
    var text = (slot.swap === null || slot.swap === undefined ? "Move to " : "Swap with the lesson on ") + where;
    return slot.why ? text + " — " + slot.why : text;
  }

  /* a new list: ok, then prefer, then no; na left out; within a state by day, then period */
  function sorted(slots) {
    return (slots || []).filter(function (s) { return s.state in ORDER; }).sort(function (a, b) {
      return ORDER[a.state] - ORDER[b.state] || a.d - b.d || a.p - b.p;
    });
  }

  return { weeks: weeks, table: table, lesson: lesson, same: same, slotAt: slotAt, stateClass: stateClass, slotText: slotText, sorted: sorted };
})();
if (typeof module !== "undefined") module.exports = Grid;

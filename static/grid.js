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

  function span(r) { var k = Number(r.n); return k > 0 ? k : 1; }

  /* one row per period, one cell per day of the week: {d, p, code, lessons, rowspan, covered}. A lesson that starts under
     another's span joins that top cell (the span grows to the end of the last of them), so none is left unseen. */
  function table(payload, week) {
    var np = payload.NP, all = payload.lessons || [], codes = payload.codes || [], rows = [], p;
    var cells = week.days.map(function (day) {
      var col = [], mine = all.filter(function (r) { return r.d === day.i; });
      var byP = mine.map(function (r, i) { return { r: r, i: i }; }).sort(function (a, b) { return a.r.p - b.r.p || a.i - b.i; })
        .map(function (x) { return x.r; });
      for (p = 0; p < np; p++) col.push({ d: day.i, p: p, code: (codes[day.i] || "")[p] || ".", lessons: [], rowspan: 1, covered: false });
      var q = 0, top, end, here, k;
      while (q < byP.length) {
        top = byP[q].p; end = top; here = [];
        while (q < byP.length && byP[q].p < Math.max(end, top + 1)) { here.push(byP[q]); end = Math.max(end, byP[q].p + span(byP[q])); q++; }
        if (top < 0 || top >= np) continue;
        end = Math.min(end, np);
        col[top].lessons = here; col[top].rowspan = end - top;
        for (k = top + 1; k < end; k++) col[k].covered = true;
      }
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

  /* one line for a lesson row in a cell: the subject's short form, the group unless it is the whole class, the teachers' short names
     (the row's short and tshorts when the server gave them, else the full subject and names) */
  function label(r, short) {
    var ts = (r.tshorts && r.tshorts.length === (r.teachers || []).length ? r.tshorts : (r.teachers || []).map(function (t) { return (short && short[t]) || t; }));
    var group = r.group && r.group !== "Entire Class" ? r.group : "";
    return [r.short || r.subject, group].concat(ts.length ? [ts.join(", ")] : []).filter(Boolean).join(" · ");
  }
  /* the full words for the button's title */
  function fullLabel(r) { return [r.subject, r.group, (r.teachers || []).join(", "), r.room].filter(Boolean).join(" · "); }
  /* is an answer fetched for `asked` still the one wanted now? same view and name (a grid), or the same selected lesson / add key (options) */
  function wanted(asked, now) {
    if (!asked || !now) return false;
    return asked.view === now.view && asked.name === now.name && asked.key === now.key && asked.id === now.id && asked.group === now.group;
  }

  return { label: label, fullLabel: fullLabel, wanted: wanted, weeks: weeks, table: table, lesson: lesson, same: same, slotAt: slotAt, stateClass: stateClass, slotText: slotText, sorted: sorted };
})();
if (typeof module !== "undefined") module.exports = Grid;

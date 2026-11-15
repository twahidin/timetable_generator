/* The Cards view of step 2 (Classes): each class as a card with its Class Parents, its subjects and its student counts.
   Plain functions over the setup, no page access, so they run under Node (tests/classview.test.js).
   Groups.codes(spec) is called once per model; the lessons and the students are each read once. */
var ClassView = (function () {
  "use strict";
  var G = typeof Groups !== "undefined" ? Groups : require("./groups.js");
  var P = typeof Parents !== "undefined" ? Parents : require("./parents.js");

  function rows(spec, k) { return spec && Array.isArray(spec[k]) ? spec[k] : []; }
  function levelOf(c) { return c.level ? String(c.level) : ""; }

  /* the levels that have at least one class: the school's order, then others as first seen, then "" for no level */
  function levels(spec) {
    var have = {}, out = [], extra = [];
    rows(spec, "classes").forEach(function (c) { if (c && c["class"]) have[levelOf(c)] = true; });
    (((spec && spec.school) || {}).levels || []).forEach(function (l) { if (have[l] && out.indexOf(l) < 0) out.push(l); });
    rows(spec, "classes").forEach(function (c) {
      if (!c || !c["class"]) return;
      var l = levelOf(c); if (l && out.indexOf(l) < 0 && extra.indexOf(l) < 0) extra.push(l);
    });
    out = out.concat(extra);
    if (have[""]) out.push("");
    return out;
  }

  function cards(spec) {
    var classes = rows(spec, "classes"), lessons = rows(spec, "lessons"), students = rows(spec, "students");
    var codes = G.codes(spec || {}), order = {}, parts = {}, held = {}, real = {};
    rows(spec, "subjects").forEach(function (s, i) { if (s && s.subject && !(s.subject in order)) order[s.subject] = i; });

    // per class: its subjects (in first-seen order) with the codes of its rows of each
    lessons.forEach(function (x, i) {
      if (!x || !x.subject || !Array.isArray(x.classes)) return;
      x.classes.forEach(function (cn) {
        var m = parts[cn] || (parts[cn] = { list: [], by: {} }), s = m.by[x.subject];
        if (!s) { s = m.by[x.subject] = { subject: x.subject, whole: false, codes: {}, seen: m.list.length }; m.list.push(s); }
        if (codes[i] === "Entire Class") s.whole = true; else if (codes[i]) s.codes[codes[i]] = true;
      });
    });
    // per class: its students' codes, and the number of students
    students.forEach(function (st) {
      if (!st || !st["class"]) return;
      real[st["class"]] = (real[st["class"]] || 0) + 1;
      (held[st["class"]] || (held[st["class"]] = [])).push(Array.isArray(st.groups) ? st.groups : []);
    });

    function rank(s) { return s.subject in order ? order[s.subject] : Infinity; }
    function byStep3(a, b) { return rank(a) - rank(b) || a.seen - b.seen; }

    var byLevel = {};
    classes.forEach(function (c, ci) {
      if (!c || !c["class"]) return;
      var name = c["class"], n = real[name] == null ? null : real[name];
      var size = c.size === "" || c.size == null ? NaN : Number(c.size);
      var m = parts[name] || { list: [] }, mates = held[name] || [];
      var subs = m.list.slice().sort(function (a, b) { return (b.whole - a.whole) || byStep3(a, b); }).map(function (s) {
        var count = null;
        if (!s.whole && n !== null) count = mates.filter(function (g) { return g.some(function (k) { return s.codes[k]; }); }).length;
        return { subject: s.subject, whole: s.whole, count: count };
      });
      (byLevel[levelOf(c)] || (byLevel[levelOf(c)] = [])).push({
        ci: ci, "class": name, planned: isNaN(size) ? null : size, real: n,
        home_room: c.home_room || "", parents: P.names(c), subjects: subs });
    });

    return levels(spec).map(function (l) {
      var cs = byLevel[l], planned = 0, real = null;
      cs.forEach(function (c) { planned += c.planned || 0; if (c.real !== null) real = (real || 0) + c.real; });
      return { level: l, planned: planned, real: real, cards: cs };
    });
  }

  /* The band picture of one level: a column per class, a row per label. Subjects taken whole or as a kept group are
     cells; a band is a bar across the columns of its classes, on the row of its subject (or its own name). */
  function bands(spec, level) {
    level = level == null ? "" : String(level);
    var cols = [], at = Object.create(null);   // typed names key these tables
    rows(spec, "classes").forEach(function (c) {
      if (c && c["class"] && levelOf(c) === level && !(c["class"] in at)) { at[c["class"]] = cols.length; cols.push(c["class"]); }
    });
    if (!cols.length) return { level: level, classes: [], rows: [] };

    var codes = G.codes(spec || {}), lanes = G.lanes(spec || {}, level);
    var byLabel = Object.create(null), labels = [];
    function put(label) {
      if (!byLabel[label]) { byLabel[label] = []; labels.push(label); }
      return byLabel[label];
    }
    function rowOf(list, i) { return list[i] || (list[i] = { cells: cols.map(function () { return null; }), bars: [], used: cols.map(function () { return false; }) }); }

    // subjects with no band: one cell per class on the first row of the subject's label
    rows(spec, "lessons").forEach(function (x, i) {
      if (!x || x.block || !x.subject || !Array.isArray(x.classes)) return;
      var code = codes[i], list = null;
      x.classes.forEach(function (cn) {
        if (!(cn in at)) return;
        var row = rowOf(list || (list = put(G.untag(x.subject))), 0), k = at[cn], was = row.cells[k];
        if (code === "Entire Class") row.cells[k] = { kind: "whole" };
        else if (!was) row.cells[k] = { kind: "part", code: code };
        row.used[k] = true;
      });
    });

    // bands: a bar on the first row of its label where none of its classes is taken
    lanes.forEach(function (l) {
      if ((l.level || "") !== level) return;
      var want = Object.create(null), ks = [];
      (l.classes.length ? l.classes : [].concat.apply([], l.groups.map(function (g) { return g.classes; }))).forEach(function (cn) {
        if (cn in at && !want[cn]) { want[cn] = true; ks.push(at[cn]); }
      });
      if (!ks.length) return;
      ks.sort(function (a, b) { return a - b; });
      var spans = [];
      ks.forEach(function (k) {
        var last = spans[spans.length - 1];
        if (last && last[0] + last[1] === k) last[1]++; else spans.push([k, 1]);
      });
      var subs = [];
      l.groups.forEach(function (g) { var f = G.untag(g.subject); if (f && subs.indexOf(f) < 0) subs.push(f); });
      var list = put(subs.length === 1 ? subs[0] : l.block), i = 0;
      while (list[i] && ks.some(function (k) { return list[i].used[k]; })) i++;
      var row = rowOf(list, i);
      ks.forEach(function (k) { row.used[k] = true; });
      row.bars.push({ block: l.block, bi: l.bi, classes: ks.map(function (k) { return cols[k]; }), spans: spans,
        groups: l.groups.map(function (g) { return { code: g.code, subject: g.subject, students: g.students }; }) });
    });

    // labels in the order of step 3's subjects, then the rest as they turned up
    var order = Object.create(null);
    rows(spec, "subjects").forEach(function (s, i) { var f = s && s.subject ? G.untag(s.subject) : ""; if (f && !(f in order)) order[f] = i; });
    var known = labels.filter(function (l) { return l in order; }).sort(function (a, b) { return order[a] - order[b]; });
    var out = [];
    known.concat(labels.filter(function (l) { return !(l in order); })).forEach(function (label) {
      byLabel[label].forEach(function (r) { if (r) out.push({ label: label, cells: r.cells, bars: r.bars }); });
    });
    return { level: level, classes: cols, rows: out };
  }

  return { cards: cards, levels: levels, bands: bands };
})();
if (typeof module !== "undefined") module.exports = ClassView;

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

  return { cards: cards, levels: levels };
})();
if (typeof module !== "undefined") module.exports = ClassView;

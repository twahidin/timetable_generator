/* Parents: the Class Parents rule (a class's form teachers and the lessons they take). Pure: functions over a spec,
   no document, no window, no randomness, so Node can test them. ttgen/parents.py is its twin; both run the cases in
   tests/parents_cases.json, so change them together. */
var Parents = (function () {
  "use strict";

  var blank = function (n) { return n == null || String(n).trim() === ""; };
  var school = function (spec) { return (spec && spec.school) || {}; };
  var list = function (spec, k) { return (spec && Array.isArray(spec[k])) ? spec[k] : []; };

  // A row's teachers (or a class's parents) with blanks dropped.
  function names(row) {
    var v = row && (row.teachers != null ? row.teachers : row.parents);
    return Array.isArray(v) ? v.filter(function (n) { return !blank(n); }) : [];
  }

  // The named subjects that are on step 3, in the order the school named them.
  function subjects(spec) {
    var named = school(spec).parents_subjects;
    if (!Array.isArray(named)) return [];
    var have = {};
    list(spec, "subjects").forEach(function (s) { have[s.subject] = true; });
    return named.filter(function (n, i) { return have[n] === true && named.indexOf(n) === i; });
  }

  function cap(spec) { return Math.max(3, Number(school(spec).parents_max) || 2); }

  function label(spec) { return String(school(spec).parents_name || "").trim() || "Form teachers"; }

  function staffed(spec, row) {
    return !!row && !row.block && !row.code_override && subjects(spec).indexOf(row.subject) >= 0;
  }

  function follows(spec, row) { return staffed(spec, row) && row.by_hand !== true; }

  // The Class Parents of each of the row's classes, class order then box order, each name once.
  function want(spec, row) {
    var out = [];
    (row.classes || []).forEach(function (cn) {
      var c = list(spec, "classes").filter(function (k) { return k["class"] === cn; })[0];
      names(c).forEach(function (n) { if (out.indexOf(n) < 0) out.push(n); });
    });
    return out;
  }

  // The same people, order ignored.
  function same(a, b) {
    a = names({ teachers: a }); b = names({ teachers: b });
    return a.every(function (n) { return b.indexOf(n) >= 0; }) && b.every(function (n) { return a.indexOf(n) >= 0; });
  }

  // Protect typed teachers: mark by_hand on every following row with other people than the boxes give.
  function adopt(spec, only) {
    var n = 0;
    list(spec, "lessons").forEach(function (r) {
      if (!follows(spec, r) || !names(r).length) return;
      if (only && only.subjects && only.subjects.indexOf(r.subject) < 0) return;
      if (only && only.classes && !(r.classes || []).some(function (c) { return only.classes.indexOf(c) >= 0; })) return;
      var w = want(spec, r);
      if (!w.length || same(names(r), w)) return;
      r.by_hand = true; n++;
    });
    return n;
  }

  // Put the setup right. Returns whether anything changed.
  function derive(spec) {
    var changed = false, subs = subjects(spec), lessons = list(spec, "lessons");
    lessons.forEach(function (r) {
      if ("by_hand" in r && !staffed(spec, r)) { delete r.by_hand; changed = true; }
    });
    if (!subs.length) return changed;
    list(spec, "classes").forEach(function (c) {
      if (!c._id || !c.level) return;
      subs.forEach(function (sn) {
        var s = list(spec, "subjects").filter(function (k) { return k.subject === sn; })[0];
        if (!s || !s._id || !(Number((s.periods || {})[c.level]) > 0)) return;
        var has = lessons.some(function (r) { return r.subject === sn && (r.classes || []).indexOf(c["class"]) >= 0; });
        if (has) return;
        lessons.push({ _id: "cp-" + c._id + "-" + s._id, level: c.level, subject: sn, block: null,
          classes: [c["class"]], teachers: names(c), students: null });
        changed = true;
      });
    });
    lessons.forEach(function (r) {
      if (!follows(spec, r)) return;
      var w = want(spec, r);
      if (!w.length || (Array.isArray(r.teachers) && JSON.stringify(r.teachers) === JSON.stringify(w))) return;
      r.teachers = w; changed = true;
    });
    return changed;
  }

  return { names: names, subjects: subjects, cap: cap, label: label, staffed: staffed, follows: follows,
    want: want, same: same, adopt: adopt, derive: derive };
})();
if (typeof module !== "undefined") module.exports = Parents;

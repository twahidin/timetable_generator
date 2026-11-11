/* Parents: the Class Parents rule (a class's form teachers and the lessons they take). Pure: functions over a spec,
   no document, no window, no randomness, so Node can test them. ttgen/parents.py is its twin; both run the cases in
   tests/parents_cases.json, so change them together. */
var Parents = (function () {
  "use strict";

  var blank = function (n) { return n == null || String(n).trim() === ""; };
  var school = function (spec) { return (spec && spec.school) || {}; };
  var isObj = function (v) { return !!v && typeof v === "object" && !Array.isArray(v); };
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

  // A whole number 1 to 6, given as a number or as digits; anything else counts as 2.
  function cap(spec) {
    var v = school(spec).parents_max;
    if (typeof v === "string" && /^[0-9]+$/.test(v)) v = Number(v);
    return Math.max(3, typeof v === "number" && Number.isInteger(v) && v >= 1 && v <= 6 ? v : 2);
  }

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
      if ("by_hand" in r && (r.by_hand !== true || !staffed(spec, r))) { delete r.by_hand; changed = true; }
    });
    if (!subs.length) return changed;
    list(spec, "classes").forEach(function (c) {
      if (!c._id || !c.level) return;
      subs.forEach(function (sn) {
        var s = list(spec, "subjects").filter(function (k) { return k.subject === sn; })[0];
        if (!s || !s._id || !(Number(isObj(s.periods) ? s.periods[c.level] : 0) > 0)) return;
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

  // ---- what the page does on an edit (page only: the server never marks hand changes)

  // The maximum as the school set it: a whole number 1 to 6 (number or digits), else 2.
  function pmax(spec) {
    var v = school(spec).parents_max;
    if (typeof v === "string" && /^[0-9]+$/.test(v)) v = Number(v);
    return typeof v === "number" && Number.isInteger(v) && v >= 1 && v <= 6 ? v : 2;
  }
  function clean(l) {
    var out = [];
    (Array.isArray(l) ? l : []).forEach(function (n) { if (!blank(n) && out.indexOf(n) < 0) out.push(n); });
    return out;
  }
  function classOf(spec, cn) { return list(spec, "classes").filter(function (k) { return k["class"] === cn; })[0]; }

  // Called from save(). With hand true, mark the edits a person made to following rows, then put the rest right.
  function settle(spec, prev, hand) {
    var marked = false;
    if (hand && prev) {
      var was = {};
      list(prev, "lessons").forEach(function (r) { if (r && r._id != null) was[r._id] = r; });
      list(spec, "lessons").forEach(function (r) {
        if (!follows(spec, r)) return;
        var p = r._id != null ? was[r._id] : null, have = names(r), w = want(spec, r);
        if (p) {
          if (same(have, names(p)) || JSON.stringify(want(prev, p)) !== JSON.stringify(w)) return;
        } else if (!have.length || !w.length || same(have, w)) return;
        r.by_hand = true; marked = true;
      });
    }
    return derive(spec) || marked;
  }

  function setParents(spec, ci, l) {
    var c = list(spec, "classes")[ci];
    if (!c) return;
    var before = names(c), after = clean(l);
    if (after.length) { if (JSON.stringify(c.parents) !== JSON.stringify(after)) c.parents = after; }
    else if ("parents" in c) delete c.parents;
    if (!before.length && after.length) adopt(spec, { classes: [c["class"]] });
    if (before.length && !after.length) {
      list(spec, "lessons").forEach(function (r) {
        if (!follows(spec, r) || (r.classes || []).indexOf(c["class"]) < 0 || want(spec, r).length || !names(r).length) return;
        r.teachers = [];
      });
    }
  }

  function setSubjects(spec, l) {
    var now = clean(l), had = Array.isArray(school(spec).parents_subjects) ? school(spec).parents_subjects : [];
    if (JSON.stringify(had) !== JSON.stringify(now)) {
      if (now.length) { spec.school = spec.school || {}; spec.school.parents_subjects = now; }
      else delete spec.school.parents_subjects;
    }
    now.forEach(function (sn) { if (had.indexOf(sn) < 0) adopt(spec, { subjects: [sn] }); });
  }

  function setMax(spec, n) {
    if (typeof n === "string" && /^[0-9]+$/.test(n)) n = Number(n);
    if (typeof n !== "number" || !Number.isInteger(n) || n < 1 || n > 6) return "Pick a number from 1 to 6.";
    var over = list(spec, "classes").filter(function (c) { return names(c).length > n; }).map(function (c) { return c["class"]; });
    if (over.length) return over.join(", ") + (over.length > 1 ? " already have" : " already has") + " more than " + n + ".";
    if (school(spec).parents_max !== n) { spec.school = spec.school || {}; spec.school.parents_max = n; }
    return null;
  }

  // The classes with no Class Parents that the staffed rows could give some: [index, names] pairs.
  function fillable(spec) {
    var out = [];
    if (!subjects(spec).length) return out;
    var m = pmax(spec);
    list(spec, "classes").forEach(function (c, i) {
      if (names(c).length) return;
      var got = [];
      list(spec, "lessons").forEach(function (r) {
        if (!staffed(spec, r) || (r.classes || []).indexOf(c["class"]) < 0) return;
        names(r).forEach(function (n) { if (got.indexOf(n) < 0) got.push(n); });
      });
      if (got.length) out.push([i, got.slice(0, m)]);
    });
    return out;
  }
  function fillCount(spec) { return fillable(spec).length; }
  function fill(spec) {
    var todo = fillable(spec);
    todo.forEach(function (p) { setParents(spec, p[0], p[1]); });
    return todo.length;
  }

  function handRows(spec) {
    var out = [];
    list(spec, "lessons").forEach(function (r, i) { if (staffed(spec, r) && r.by_hand === true) out.push(i); });
    return out;
  }
  function back(spec, i) {
    var r = list(spec, "lessons")[i];
    if (r && staffed(spec, r) && "by_hand" in r) delete r.by_hand;
  }
  function backAll(spec) {
    var rows = handRows(spec);
    rows.forEach(function (i) { back(spec, i); });
    return rows.length;
  }

  function exempt(spec, row, name) {
    return staffed(spec, row) && (row.classes || []).some(function (cn) { return names(classOf(spec, cn)).indexOf(name) >= 0; });
  }
  function of(spec, name) {
    return list(spec, "classes").filter(function (c) { return names(c).indexOf(name) >= 0; }).map(function (c) { return c["class"]; });
  }

  // The Things to fix sentences, in the order of their kinds.
  function issues(spec) {
    var out = [], nm = label(spec), subs = subjects(spec), classes = list(spec, "classes"), lessons = list(spec, "lessons");
    var add = function (kind, i, text) { out.push({ kind: kind, i: i, text: text }); };
    classes.forEach(function (c, i) {
      if (subs.length && !names(c).length && lessons.some(function (r) { return follows(spec, r) && (r.classes || []).indexOf(c["class"]) >= 0; }))
        add("classes", i, c["class"] + " has no " + nm + " yet.");
    });
    var known = {};
    list(spec, "teachers").forEach(function (t) { if (t && !blank(t.name)) known[t.name] = true; });
    classes.forEach(function (c, i) {
      names(c).forEach(function (n) { if (known[n] !== true) add("classes", i, c["class"] + ": " + n + " is not on the teacher list."); });
    });
    list(spec, "teachers").forEach(function (t, i) {
      var cs = of(spec, t && t.name);
      if (cs.length < 2) return;
      add("teachers", i, t.name + " is one of the " + nm + " of " + cs.slice(0, -1).join(", ") + " and " + cs[cs.length - 1] +
        ": their lessons together cannot be at the same time.");
    });
    var named = Array.isArray(school(spec).parents_subjects) ? school(spec).parents_subjects : [];
    named.forEach(function (sn, i) {
      if (named.indexOf(sn) === i && subs.indexOf(sn) < 0) add("config", 0, nm + " take " + sn + ", which is not on step 3.");
    });
    classes.forEach(function (c, i) {
      subs.forEach(function (sn) {
        var mine = lessons.filter(function (r) { return r.subject === sn && (r.classes || []).indexOf(c["class"]) >= 0; });
        if (mine.length && !mine.some(function (r) { return !r.block && !r.code_override; }))
          add("classes", i, sn + " for " + c["class"] + " cannot be staffed by its " + nm + ": it is taught in groups.");
      });
    });
    return out;
  }

  return { names: names, subjects: subjects, cap: cap, label: label, staffed: staffed, follows: follows,
    want: want, same: same, adopt: adopt, derive: derive, settle: settle, setParents: setParents, setSubjects: setSubjects,
    setMax: setMax, fillCount: fillCount, fill: fill, handRows: handRows, back: back, backAll: backAll,
    exempt: exempt, of: of, issues: issues };
})();
if (typeof module !== "undefined") module.exports = Parents;

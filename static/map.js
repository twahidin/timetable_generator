/* The department map (step 5): what it shows and what it writes, as plain functions over the setup.
   No page access, nothing random, so it runs under Node (tests/map.test.js). Teachers are addressed by
   their row's `_id` or index; lessons name teachers by name, as the setup does. Loaded after people.js. */
var DeptMap = (function () {
  "use strict";
  var P = typeof People !== "undefined" ? People : require("./people.js");

  function rows(spec, k) { return Array.isArray(spec[k]) ? spec[k] : []; }
  function names(row) { return (row.teachers || []).filter(Boolean); }
  function subjectOf(spec, name) { return rows(spec, "subjects").find(function (s) { return s.subject === name; }) || null; }
  function hasSubject(t, subject) { return (t.can_teach || []).some(function (c) { return c && c.subject === subject; }); }
  function anySubject(t) { return (t.can_teach || []).some(function (c) { return c && c.subject; }); }

  /* each teacher's load: periods deployed (info[i].tp per row naming them) plus other duties, against the allowance */
  function loads(spec, info) {
    var out = {};
    rows(spec, "teachers").forEach(function (t) {
      var allow = Number(t.allowance) || null, duties = Number(t.other_duties) || 0;
      out[t.name] = { lessons: 0, duties: duties, allowance: allow, total: duties, over: false };
    });
    rows(spec, "lessons").forEach(function (x, i) {
      names(x).forEach(function (nm) { if (out[nm]) out[nm].lessons += Number((info[i] || {}).tp) || 0; });
    });
    Object.keys(out).forEach(function (nm) {
      var o = out[nm]; o.total = o.lessons + o.duties; o.over = o.allowance !== null && o.total > o.allowance;
    });
    return out;
  }

  function deptSubjects(spec, dept) {
    return rows(spec, "subjects").filter(function (s) { return s.subject && s.dept === dept; }).map(function (s) { return s.subject; });
  }

  /* the department's teachers in setup order, then the visitors (by _id) not already there */
  function roster(spec, dept, extraIds) {
    var T = rows(spec, "teachers"), out = [];
    T.forEach(function (t, i) { if (t && t.dept === dept) out.push(i); });
    var want = {}; (extraIds || []).forEach(function (id) { want[id] = true; });
    T.forEach(function (t, i) { if (t && want[t._id] && out.indexOf(i) < 0) out.push(i); });
    return out;
  }

  function unplaced(spec, idxs) {
    var T = rows(spec, "teachers");
    return (idxs || []).filter(function (i) { return T[i] && !anySubject(T[i]); });
  }

  /* teachers of other departments whose name or short name contains q (at most 8) */
  function search(spec, q, dept) {
    var k = P.key(q || ""); if (!k) return [];
    var out = [];
    rows(spec, "teachers").forEach(function (t, i) {
      if (!t || t.dept === dept || out.length >= 8) return;
      if (P.key(t.name || "").indexOf(k) >= 0 || P.key(t.short || "").indexOf(k) >= 0) out.push(i);
    });
    return out;
  }

  /* one basket per subject of the department: every teacher (any department) who can teach it */
  function baskets(spec, dept) {
    var T = rows(spec, "teachers");
    return deptSubjects(spec, dept).map(function (s) {
      var who = []; T.forEach(function (t, i) { if (t && hasSubject(t, s)) who.push(i); });
      return { subject: s, teachers: who };
    });
  }

  /* the cards of the right-hand column: one class of a whole-class row, a group, or a band with its groups */
  function cards(spec, info, dept, tab, level) {
    var subs = deptSubjects(spec, dept), L = rows(spec, "lessons"), lv = (spec.school || {}).levels || [];
    var mine = function (x) { return x && x.subject && subs.indexOf(x.subject) >= 0 && (!level || x.level === level); };
    var whole = function (x) { return !x.block && !x.code_override; };
    var inf = function (i) { return info[i] || {}; };
    if (tab === "classes") {
      var out = [];
      L.forEach(function (x, i) {
        if (!mine(x) || !whole(x)) return;
        (x.classes || []).forEach(function (c) {
          out.push({ kind: "class", li: i, cls: c, title: c, subject: x.subject, level: x.level, periods: inf(i).p, teachers: names(x) });
        });
      });
      var rank = function (c) { var k = lv.indexOf(c.level); return k < 0 ? lv.length : k; };
      return out.sort(function (a, b) {
        return rank(a) - rank(b) || String(a.cls).localeCompare(String(b.cls)) || String(a.subject).localeCompare(String(b.subject));
      });
    }
    var groups = [];
    L.forEach(function (x, i) {
      if (!mine(x) || whole(x)) return;
      groups.push({ kind: "group", li: i, title: inf(i).code, subject: x.subject, level: x.level, periods: inf(i).p, teachers: names(x), block: x.block || null });
    });
    if (tab === "groups") return groups;
    var out2 = [];
    rows(spec, "blocks").forEach(function (b, bi) {
      var gs = groups.filter(function (g) { return g.block && g.block === b.block; });
      if (!gs.length) return;
      var seen = {}, twice = [];
      gs.forEach(function (g) { g.teachers.forEach(function (nm) { seen[nm] = (seen[nm] || 0) + 1; if (seen[nm] === 2) twice.push(nm); }); });
      out2.push({ kind: "band", bi: bi, title: b.block, level: b.level, groups: gs, twice: twice });
    });
    return out2;
  }

  function prune(ids, spec) {
    var have = {}; rows(spec, "teachers").forEach(function (t) { if (t && t._id) have[t._id] = true; });
    return (ids || []).filter(function (id) { return have[id]; });
  }

  return {
    loads: loads, deptSubjects: deptSubjects, roster: roster, unplaced: unplaced, search: search,
    baskets: baskets, staffRoom: unplaced, cards: cards, prune: prune, subjectOf: subjectOf
  };
})();
if (typeof module !== "undefined") module.exports = DeptMap;

/* The department map (step 5): what it shows and what it writes, as plain functions over the setup.
   No page access, nothing random, so it runs under Node (tests/map.test.js). Teachers are addressed by
   their row's `_id` or index; lessons name teachers by name, as the setup does. Loaded after people.js. */
var DeptMap = (function () {
  "use strict";
  var P = typeof People !== "undefined" ? People : require("./people.js");

  function rows(spec, k) { return Array.isArray(spec[k]) ? spec[k] : []; }
  function names(row) { return (row.teachers || []).filter(Boolean); }
  function subjectOf(spec, name) { return rows(spec, "subjects").find(function (s) { return s.subject === name; }) || null; }

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
    T.forEach(function (t, i) { if (t && P.inDept(t, dept)) out.push(i); });
    var want = {}; (extraIds || []).forEach(function (id) { want[id] = true; });
    T.forEach(function (t, i) { if (t && want[t._id] && out.indexOf(i) < 0) out.push(i); });
    return out;
  }

  /* those of idxs named on no lesson row */
  function unplaced(spec, idxs) {
    var T = rows(spec, "teachers"), on = {};
    rows(spec, "lessons").forEach(function (x) { if (x) names(x).forEach(function (nm) { on[nm] = true; }); });
    return (idxs || []).filter(function (i) { return T[i] && !on[T[i].name]; });
  }

  /* teachers in neither department of the page whose name or short name contains q (at most 8) */
  function search(spec, q, dept) {
    var k = P.key(q || ""); if (!k) return [];
    var out = [];
    rows(spec, "teachers").forEach(function (t, i) {
      if (!t || P.inDept(t, dept) || out.length >= 8) return;
      if (P.key(t.name || "").indexOf(k) >= 0 || P.key(t.short || "").indexOf(k) >= 0) out.push(i);
    });
    return out;
  }

  /* the cards of one kind (the profile's "Teaches" list uses them): one class of a whole-class row, a group, or a band with its groups */
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

  function count(v) { if (v === null || v === undefined || String(v).trim() === "") return null; var n = Number(v); return isFinite(n) ? n : null; }

  /* the department's page: for each level, its subjects in step 3's order (a subject's class cards in the class list's order,
     then its groups in no band), and each band as a lane at the place of the first of its subjects; every card of cards() once.
     A band gets one lane in each level where this department has groups of it, holding that level's groups; its "twice" is worked
     out over all its groups of this department (every level) and given to each lane. A subject with only band groups has no section of its own. */
  function page(spec, info, dept, level) {
    info = info || [];
    var subs = deptSubjects(spec, dept), L = rows(spec, "lessons"), lv = (spec.school || {}).levels || [];
    var classes = rows(spec, "classes"), bands = rows(spec, "blocks");
    var inf = function (i) { return info[i] || {}; };
    var lvl = function (x) { return x.level === undefined || x.level === null ? "" : x.level; };
    var classIx = function (c) { for (var k = 0; k < classes.length; k++) if (classes[k] && classes[k]["class"] === c) return k; return classes.length; };
    var size = function (c) { var k = classIx(c); return k < classes.length ? count(classes[k].size) : null; };
    var bandIx = function (name) { for (var k = 0; k < bands.length; k++) if (bands[k] && bands[k].block && bands[k].block === name) return k; return -1; };
    var byLevel = {}, seen = [], bandCount = {}, bandTwice = {};
    var slot = function (l) { if (!byLevel[l]) { byLevel[l] = { classes: [], loose: [], lanes: {} }; seen.push(l); } return byLevel[l]; };
    L.forEach(function (x, i) {
      if (!x || !x.subject || subs.indexOf(x.subject) < 0) return;
      var gb = x.block ? bandIx(x.block) : -1;
      if (gb >= 0) names(x).forEach(function (nm) {   // every level, whatever the level box says
        var c = bandCount[gb] = bandCount[gb] || {}; c[nm] = (c[nm] || 0) + 1;
        if (c[nm] === 2) (bandTwice[gb] = bandTwice[gb] || []).push(nm);
      });
      if (level && x.level !== level) return;
      var at = slot(lvl(x));
      if (!x.block && !x.code_override) {
        if (!Array.isArray(x.classes)) return;
        x.classes.forEach(function (c) {
          at.classes.push({ kind: "class", li: i, cls: c, title: c, subject: x.subject, level: lvl(x), periods: inf(i).p, students: size(c), teachers: names(x), block: null });
        });
        return;
      }
      var g = { kind: "group", li: i, title: inf(i).code, subject: x.subject, level: lvl(x), periods: inf(i).p, students: count(x.students), teachers: names(x), block: x.block || null };
      var bi = x.block ? bandIx(x.block) : -1;
      if (bi < 0) { at.loose.push(g); return; }
      (at.lanes[bi] = at.lanes[bi] || []).push(g);
    });
    var rank = function (l) { var k = lv.indexOf(l); return k < 0 ? lv.length : k; };
    var order = seen.map(function (l, k) { return [l, k]; }).sort(function (a, b) { return rank(a[0]) - rank(b[0]) || a[1] - b[1]; });
    return order.map(function (o) {
      var at = byLevel[o[0]], parts = [];
      subs.forEach(function (sub, place) {
        var cs = at.classes.filter(function (c) { return c.subject === sub; })
          .map(function (c, k) { return [c, k]; })
          .sort(function (a, b) { return classIx(a[0].cls) - classIx(b[0].cls) || a[0].li - b[0].li || a[1] - b[1]; })
          .map(function (p) { return p[0]; });
        var cards = cs.concat(at.loose.filter(function (g) { return g.subject === sub; }));
        if (cards.length) parts.push({ place: place, rank: 0, sub: 0, section: { kind: "subject", subject: sub, cards: cards } });
      });
      Object.keys(at.lanes).forEach(function (k) {
        var gs = at.lanes[k], bi = Number(k), first = subs.length;
        gs.forEach(function (g) { first = Math.min(first, subs.indexOf(g.subject)); });
        parts.push({ place: first, rank: 1, sub: bi, section: { kind: "band", bi: bi, title: bands[bi].block, groups: gs, twice: (bandTwice[bi] || []).slice() } });
      });
      parts.sort(function (a, b) { return a.place - b.place || a.rank - b.rank || a.sub - b.sub; });
      return { level: o[0], sections: parts.map(function (p) { return p.section; }) };
    });
  }

  /* ---- what the map writes (the caller saves afterwards) */
  var MAX = 3;   // teachers on one card (Teacher 1 to 3); a staffed lesson may hold more (opts.max)
  var NUM = ["zero", "one", "two", "three", "four", "five", "six"];

  /* a class card of a row that lists several classes: that class becomes a row of its own (a copy without the _id, which
     the sync gives it on save); returns the row the change goes on */
  function rowFor(spec, card) {
    var L = rows(spec, "lessons"), x = L[card.li];
    if (!x) return null;
    if (card.kind !== "class" || (x.classes || []).length <= 1 || (x.classes || []).indexOf(card.cls) < 0) return { row: x, split: false };
    x.classes = x.classes.filter(function (c) { return c !== card.cls; });
    var copy = JSON.parse(JSON.stringify(x)); delete copy._id; copy.classes = [card.cls];
    L.push(copy);
    return { row: copy, split: true };
  }

  /* opts.max: the most teachers on the card (default MAX). A teacher is refused only when the card would hold too many */
  function deploy(spec, card, idxs, opts) {
    opts = opts || {};
    var max = Number(opts.max) || MAX;
    var T = rows(spec, "teachers"), x = rows(spec, "lessons")[card.li];
    var out = { placed: [], already: [], refused: [], split: false };
    if (!x) return out;
    var title = card.title || (card.kind === "class" ? card.cls : "The group");
    var on = names(x), left = [];
    (idxs || []).forEach(function (i) {
      var t = T[i]; if (!t || !t.name) return;
      if (on.indexOf(t.name) >= 0) { out.already.push(t.name); return; }
      left.push(t);
    });
    if (!left.length) return out;
    if (on.length + left.length > max) {   // a refused drop changes nothing
      var why = title + " would have " + (on.length + left.length) + " teachers; " + (NUM[max] || max) + " is the most.";
      left.forEach(function (t) { out.refused.push({ name: t.name, why: why }); });
      return out;
    }
    var r = rowFor(spec, card); out.split = r.split;
    out.placed = left.map(function (t) { return t.name; });
    r.row.teachers = names(r.row).concat(out.placed);
    return out;
  }

  function undeploy(spec, card, name) {
    var x = rows(spec, "lessons")[card.li];
    if (!x || names(x).indexOf(name) < 0) return false;
    var r = rowFor(spec, card);
    r.row.teachers = names(r.row).filter(function (nm) { return nm !== name; });
    return true;
  }

  function newTeacher(spec, fields, roles, provisional) {
    var f = fields || {}, name = String(f.name || "").trim().replace(/\s+/g, " ");
    if (!name) return { error: "Give the teacher a name." };
    var k = P.key(name), T = rows(spec, "teachers");
    for (var i = 0; i < T.length; i++) if (T[i] && P.key(T[i].name || "") === k) return { error: T[i].name + " is already a teacher." };
    var role = (roles || []).find(function (r) { return r && r.role === f.role; });
    var allow = Number(f.allowance) || (role && Number(role.allowance)) || null;
    if (!Array.isArray(spec.teachers)) spec.teachers = [];
    spec.teachers.push({ name: name, short: String(f.short || "").trim() || name.split(" ")[0], dept: f.dept || "", role: f.role || "",
      allowance: allow, provisional: provisional ? "Yes" : "No" });
    return { i: spec.teachers.length - 1 };
  }

  function prune(ids, spec) {
    var have = {}; rows(spec, "teachers").forEach(function (t) { if (t && t._id) have[t._id] = true; });
    return (ids || []).filter(function (id) { return have[id]; });
  }

  return {
    loads: loads, deptSubjects: deptSubjects, roster: roster, unplaced: unplaced, search: search,
    cards: cards, page: page, prune: prune, subjectOf: subjectOf,
    MAX: MAX, deploy: deploy, undeploy: undeploy, newTeacher: newTeacher
  };
})();
if (typeof module !== "undefined") module.exports = DeptMap;

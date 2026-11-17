/* Groups and bands on step 5: band names, group codes, making a group or a band, moving rows between bands.
   Plain functions over the setup, no page access, nothing random, so they run under Node (tests/groups.test.js).
   Groups are lessons[] rows with a block; bands are blocks[]; codes are numbered as the table numbers them. */
var Groups = (function () {
  "use strict";

  function rows(spec, k) { return Array.isArray(spec[k]) ? spec[k] : []; }
  function names(row) { return (row.teachers || []).filter(Boolean); }
  function norm(s) { return String(s || "").trim().replace(/\s+/g, " ").toLowerCase(); }
  function untag(name) { return String(name || "").trim().replace(/\s+(G[123]|Std|Fdn|Standard|Foundation)$/, ""); }

  /* "Sec 2 Mathematics" for one subject family; "Sec 3 Option A" for several; a taken name gets the next letter or number */
  function bandName(level, subjects, existing) {
    var taken = {}; (existing || []).forEach(function (n) { taken[norm(n)] = true; });
    var fams = []; (subjects || []).forEach(function (s) { var f = untag(s); if (f && fams.indexOf(f) < 0) fams.push(f); });
    var base, i;
    if (!fams.length) base = level + " Band";
    else if (fams.length === 1) base = level + " " + fams[0];
    else {
      for (i = 0; i < 26; i++) { var c = level + " Option " + String.fromCharCode(65 + i); if (!taken[norm(c)]) return c; }
      base = level + " Option";
    }
    if (!taken[norm(base)]) return base;
    for (i = 2; ; i++) if (!taken[norm(base + " " + i)]) return base + " " + i;
  }

  function classSize(spec, c) { var row = rows(spec, "classes").find(function (y) { return y && y.class === c; }); return row ? (Number(row.size) || null) : null; }
  function letters(spec) {
    var out = {}; ((spec.school || {}).tags || []).forEach(function (t) { out[t[0]] = t[1] || ""; }); return out;
  }
  function subjectOf(spec, name) { return rows(spec, "subjects").find(function (s) { return s.subject === name; }) || null; }
  function stem(spec, level, subject) {   // level digit + subject code + tag letter
    var s = subjectOf(spec, subject) || {};
    return String(level).slice(-1) + (s.code || "??") + (letters(spec)[s.tag] || "");
  }

  /* one code per lessons row, exactly as lessonInfo() in app.js gives them */
  function codes(spec) {
    var seq = {};
    return rows(spec, "lessons").map(function (x) {
      if (!x || !x.subject) return "";
      var k = x.level + "|" + x.subject;
      if (x.block) seq[k] = (seq[k] || 0) + 1;   // a banded row takes a number even when it keeps its own code, as lessonInfo counts
      if (x.code_override) return String(x.code_override);
      if (!x.block) return "Entire Class";
      return stem(spec, x.level, x.subject) + seq[k];
    });
  }

  function sizeOf(spec, classes) { return (classes || []).reduce(function (a, c) { return a + (classSize(spec, c) || 0); }, 0); }
  function freeCode(spec, level, subject) {   // the first unused number on the stem, as Keep code picks it
    var used = {}; codes(spec).forEach(function (c) { used[c] = true; });
    var st = stem(spec, level, subject), k = 1; while (used[st + k]) k++;
    return st + k;
  }
  /* the code a row appended now would get: in a band, the next number; with no band, "Entire Class" unless it is a
     pull-out group (fewer students than its classes hold), which gets a code of its own */
  function codeFor(spec, level, subject, block, students, classes) {
    if (!level || !subject) return "";
    if (!block) {
      var n0 = Number(students), size = sizeOf(spec, classes);
      return n0 > 0 && size > 0 && n0 < size ? freeCode(spec, level, subject) : "Entire Class";
    }
    var n = rows(spec, "lessons").filter(function (x) { return x && x.block && x.level === level && x.subject === subject; }).length;
    return stem(spec, level, subject) + (n + 1);
  }
  /* a row with no band for fewer students than its classes hold is a group of its own: it gets a kept code (null: not one) */
  function pullOutCode(spec, li) {
    var x = rows(spec, "lessons")[li];
    if (!x || x.block || x.code_override || !x.subject) return null;
    var n = Number(x.students), size = sizeOf(spec, x.classes);
    if (!(n > 0) || !size || n >= size) return null;
    x.code_override = freeCode(spec, x.level, x.subject);
    return x.code_override;
  }

  /* ---- making and moving (the caller saves afterwards) */
  function bandOf(spec, name) { return rows(spec, "blocks").find(function (b) { return b && b.block === name; }) || null; }

  function newGroup(spec, f) {
    f = f || {};
    if (!f.level || !f.subject) return { error: "Pick a level and a subject." };
    var band = null;
    if (f.block) {
      band = bandOf(spec, f.block);
      if (!band) return { error: "There is no band called " + f.block + "." };
      if (band.level !== f.level) return { error: band.block + " is a " + band.level + " band, not " + f.level + "." };
    }
    var classes = (f.classes || []).slice();
    if (!classes.length) { if (band) classes = (band.classes || []).slice(); else return { error: "Pick the classes." }; }
    if (!Array.isArray(spec.lessons)) spec.lessons = [];
    spec.lessons.push({ level: f.level, subject: f.subject, block: f.block || null, classes: classes, teachers: [], students: Number(f.students) || null });
    return { i: spec.lessons.length - 1 };
  }

  /* one whole-class row per class that has none of this subject yet (a pull-out group with its own code does not count) */
  function addOnePerClass(spec, level, subject, classes) {
    var L = rows(spec, "lessons"), n = 0;
    (classes || []).forEach(function (c) {
      var has = L.some(function (x) { return x && x.subject === subject && !x.block && !x.code_override && (x.classes || []).indexOf(c) >= 0; });
      if (has) return;
      if (!Array.isArray(spec.lessons)) spec.lessons = [];
      spec.lessons.push({ level: level, subject: subject, block: null, classes: [c], teachers: [], students: classSize(spec, c) }); n++;
    });
    return n;
  }

  function newBand(spec, f) {
    f = f || {};
    var name = String(f.block || "").trim().replace(/\s+/g, " ");
    if (!name) return { error: "Give the band a name." };
    var dup = rows(spec, "blocks").find(function (b) { return b && norm(b.block) === norm(name); });
    if (dup) return { error: dup.block + " exists already." };
    if (!f.level) return { error: "Pick a level." };
    if (!(f.classes || []).length) return { error: "Pick the band's classes." };
    if (!Array.isArray(spec.blocks)) spec.blocks = [];
    var band = { block: name, level: f.level, classes: f.classes.slice() };
    if (typeof f.everyone === "boolean") band.everyone = f.everyone;   // left out: the name decides (option, elective)
    spec.blocks.push(band);
    return { i: spec.blocks.length - 1 };
  }

  /* rows of the band's level join it; the band's classes widen to cover theirs */
  function toBand(spec, lis, block) {
    var band = bandOf(spec, block), L = rows(spec, "lessons"), out = { moved: 0, skipped: 0, widened: [] };
    if (!band) return out;
    band.classes = band.classes || [];
    (lis || []).forEach(function (li) {
      var x = L[li]; if (!x) return;
      if (x.level !== band.level) { out.skipped++; return; }
      x.block = block; delete x.code_override; out.moved++;   // the band's own numbering takes over from a kept code
      (x.classes || []).forEach(function (c) { if (band.classes.indexOf(c) < 0) { band.classes.push(c); out.widened.push(c); } });
    });
    return out;
  }

  function fromBand(spec, li) {
    var x = rows(spec, "lessons")[li];
    if (!x || !x.block) return false;
    x.block = null; return true;
  }

  /* a row is deleted, in a band or not -> what it was, or null when there is no such row */
  function dropRow(spec, li) {
    var L = rows(spec, "lessons"), x = L[li];
    if (!x) return null;
    var code = codes(spec)[li]; L.splice(li, 1);
    return { subject: x.subject, classes: (x.classes || []).slice(), block: x.block || null, code: code };
  }
  /* a band is deleted. keep: its groups stay, as rows not in a band (one of fewer students than its classes hold keeps a code of its own: the one it had, when free);
     otherwise they are deleted with it -> {groups: how many it had, kept: how many got a code of their own}, or null when there is no such band */
  function dropBand(spec, block, keep) {
    var band = bandOf(spec, block), L = rows(spec, "lessons"), mine = [], kept = 0;
    if (!band) return null;
    L.forEach(function (x, i) { if (x && x.block === block) mine.push(i); });
    if (keep) {   // all leave the band first, then each group of its own keeps the code it had when that code is still free (so a student list naming it still holds)
      var was = codes(spec);
      mine.forEach(function (li) { fromBand(spec, li); });
      mine.forEach(function (li) {
        var x = L[li], n = Number(x.students), size = sizeOf(spec, x.classes), used = {};
        if (x.code_override || !x.subject || !(n > 0) || !size || n >= size) return;   // as pullOutCode: only a group of fewer students than its classes hold
        codes(spec).forEach(function (c) { used[c] = true; });
        x.code_override = was[li] && was[li] !== "Entire Class" && !used[was[li]] ? was[li] : freeCode(spec, x.level, x.subject); kept++;
      });
    }
    else for (var k = mine.length - 1; k >= 0; k--) L.splice(mine[k], 1);
    spec.blocks.splice(spec.blocks.indexOf(band), 1);
    return { groups: mine.length, kept: kept };
  }
  /* how many rules on step 6 name the band */
  function bandRules(spec, block) { return rows(spec, "rules").filter(function (r) { return r && r.scope === "Block" && r.target === block; }).length; }

  /* what a change would do to the codes: run it on a copy, compare by row id, count the students naming a changed code */
  function shift(spec, fn) {
    var copy = JSON.parse(JSON.stringify(spec)), was = codes(spec);
    var before = {}; rows(spec, "lessons").forEach(function (x, i) { if (x && x._id) before[x._id] = was[i]; });
    fn(copy);
    var after = codes(copy), changes = [], old = {};
    rows(copy, "lessons").forEach(function (x, i) {
      if (!x || !x._id || !(x._id in before) || before[x._id] === after[i]) return;
      changes.push([x._id, before[x._id], after[i]]); old[before[x._id]] = true;
    });
    var left = {}; rows(copy, "lessons").forEach(function (x) { if (x && x._id) left[x._id] = true; });
    Object.keys(before).forEach(function (id) {   // a row the change deleted: its code is gone (a whole-class row has none to lose)
      if (left[id] || before[id] === "Entire Class") return;
      changes.push([id, before[id], null]); old[before[id]] = true;
    });
    var students = rows(spec, "students").filter(function (s) { return s && (s.groups || []).some(function (g) { return old[g]; }); }).length;
    var rulesN = rows(spec, "rules").filter(function (r) { return r && r.scope === "Group" && old[r.target]; }).length;
    return { changes: changes, students: students, rules: rulesN };
  }

  /* ---- the bands page */
  function lanes(spec, level) {
    var L = rows(spec, "lessons"), C = codes(spec), out = [];
    rows(spec, "blocks").forEach(function (b, bi) {
      if (!b || (level && b.level !== level)) return;
      var groups = [], seen = {}, twice = [];
      L.forEach(function (x, li) {
        if (!x || x.block !== b.block) return;
        groups.push({ li: li, code: C[li], subject: x.subject, classes: (x.classes || []).slice(), students: x.students == null ? null : Number(x.students) || null, teachers: names(x) });
        names(x).forEach(function (nm) { seen[nm] = (seen[nm] || 0) + 1; if (seen[nm] === 2) twice.push(nm); });
      });
      out.push({ bi: bi, block: b.block, level: b.level, classes: (b.classes || []).slice(), everyone: b.everyone == null ? !/option|elective/i.test(b.block || "") : !!b.everyone, groups: groups, twice: twice });
    });
    return out;
  }

  function pool(spec, level, subject) {
    var C = codes(spec), out = [];
    rows(spec, "lessons").forEach(function (x, li) {
      if (!x || x.block || !x.subject || (level && x.level !== level) || (subject && x.subject !== subject)) return;
      out.push({ li: li, kind: x.code_override ? "group" : "class", code: C[li], title: (x.classes || []).join(", ") + " · " + x.subject, subject: x.subject, level: x.level, classes: (x.classes || []).slice(), students: x.students == null ? null : Number(x.students) || null, teachers: names(x) });
    });
    return out;
  }

  /* ---- the bands page as its filter shows it */
  var NONE = "::no teacher::";   // the teacher filter's choice "No teacher": not a name anyone has
  function inOrder(found, listed) {   // the listed names that were found, in the list's order, then the others as they were found
    var out = listed.filter(function (n, i) { return found.indexOf(n) >= 0 && listed.indexOf(n) === i; });   // a name listed twice counts once
    found.forEach(function (n) { if (out.indexOf(n) < 0) out.push(n); });
    return out;
  }
  /* f = {level, subject, teacher, band}; "" (or missing) is all, teacher NONE is "taught by nobody". -> {f, filtered, subjects, teachers, bands, none, pool, lanes}:
     subjects and teachers are what the filter can offer at that level (the setup's order first), none whether a row there has no teacher; f is the
     filter as used (a subject or teacher that is not on offer counts as all); pool is the rows not in a band that match; lanes are the bands, each
     whole, every group saying whether it matches, and with a subject or a teacher chosen (filtered) only the bands with a group that matches;
     bands are the names of the level's bands, and with one of them chosen (band) the lanes are that band alone (the pool is not narrowed by it) */
  function view(spec, f) {
    f = f || {};
    var level = f.level || "", P = pool(spec, level, ""), L = lanes(spec, level), all = P.slice(), subj = [], who = [], none = false;
    L.forEach(function (l) { all = all.concat(l.groups); });
    all.forEach(function (x) {
      if (x.subject && subj.indexOf(x.subject) < 0) subj.push(x.subject);
      if (!x.teachers.length) none = true;
      x.teachers.forEach(function (t) { if (who.indexOf(t) < 0) who.push(t); });
    });
    var subjects = inOrder(subj, rows(spec, "subjects").map(function (x) { return x && x.subject; }));
    var teachers = inOrder(who, rows(spec, "teachers").map(function (x) { return x && x.name; }));
    var subject = subjects.indexOf(f.subject) >= 0 ? f.subject : "";
    var teacher = f.teacher === NONE ? (none ? NONE : "") : teachers.indexOf(f.teacher) >= 0 ? f.teacher : "";
    var filtered = !!(subject || teacher), bands = L.map(function (l) { return l.block; }), band = bands.indexOf(f.band) >= 0 ? f.band : "";
    function hit(x) { return (!subject || x.subject === subject) && (!teacher || (teacher === NONE ? !x.teachers.length : x.teachers.indexOf(teacher) >= 0)); }
    var shown = L.map(function (l) {
      var c = {}; Object.keys(l).forEach(function (k) { c[k] = l[k]; });
      c.groups = l.groups.map(function (g) { var d = {}; Object.keys(g).forEach(function (k) { d[k] = g[k]; }); d.match = hit(g); return d; });
      return c;
    }).filter(function (l) { return (!band || l.block === band) && (!filtered || l.groups.some(function (g) { return g.match; })); });
    return { f: { level: level, subject: subject, teacher: teacher, band: band }, filtered: filtered, subjects: subjects, teachers: teachers, bands: bands, none: none, pool: P.filter(hit), lanes: shown };
  }

  return { untag: untag, bandName: bandName, codes: codes, codeFor: codeFor, pullOutCode: pullOutCode, lanes: lanes, pool: pool, view: view, NONE: NONE, dropRow: dropRow, dropBand: dropBand, bandRules: bandRules,
    newGroup: newGroup, addOnePerClass: addOnePerClass, newBand: newBand, toBand: toBand, fromBand: fromBand, shift: shift };
})();
if (typeof module !== "undefined") module.exports = Groups;

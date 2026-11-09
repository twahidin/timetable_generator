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
      if (x.code_override) return String(x.code_override);
      if (!x.block) return "Entire Class";
      var k = x.level + "|" + x.subject; seq[k] = (seq[k] || 0) + 1;
      return stem(spec, x.level, x.subject) + seq[k];
    });
  }

  /* the code a row appended now would get */
  function codeFor(spec, level, subject, block) {
    if (!level || !subject) return "";
    if (!block) return "Entire Class";
    var n = rows(spec, "lessons").filter(function (x) { return x && x.block && x.level === level && x.subject === subject; }).length;
    return stem(spec, level, subject) + (n + 1);
  }

  /* ---- making and moving (the caller saves afterwards) */
  function bandOf(spec, name) { return rows(spec, "blocks").find(function (b) { return b && b.block === name; }) || null; }
  function classSize(spec, c) { var row = rows(spec, "classes").find(function (y) { return y && y.class === c; }); return row ? (Number(row.size) || null) : null; }

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
    spec.blocks.push({ block: name, level: f.level, classes: f.classes.slice(), everyone: !!f.everyone });
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
      x.block = block; out.moved++;
      (x.classes || []).forEach(function (c) { if (band.classes.indexOf(c) < 0) { band.classes.push(c); out.widened.push(c); } });
    });
    return out;
  }

  function fromBand(spec, li) {
    var x = rows(spec, "lessons")[li];
    if (!x || !x.block) return false;
    x.block = null; return true;
  }

  /* what a change would do to the codes: run it on a copy, compare by row id, count the students naming a changed code */
  function shift(spec, fn) {
    var copy = JSON.parse(JSON.stringify(spec));
    var before = {}; rows(spec, "lessons").forEach(function (x, i) { if (x && x._id) before[x._id] = codes(spec)[i]; });
    fn(copy);
    var after = codes(copy), changes = [], old = {};
    rows(copy, "lessons").forEach(function (x, i) {
      if (!x || !x._id || !(x._id in before) || before[x._id] === after[i]) return;
      changes.push([x._id, before[x._id], after[i]]); old[before[x._id]] = true;
    });
    var students = rows(spec, "students").filter(function (s) { return s && (s.groups || []).some(function (g) { return old[g]; }); }).length;
    return { changes: changes, students: students };
  }

  return { untag: untag, bandName: bandName, codes: codes, codeFor: codeFor,
    newGroup: newGroup, addOnePerClass: addOnePerClass, newBand: newBand, toBand: toBand, fromBand: fromBand, shift: shift };
})();
if (typeof module !== "undefined") module.exports = Groups;

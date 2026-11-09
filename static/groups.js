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

  return { untag: untag, bandName: bandName, codes: codes, codeFor: codeFor };
})();
if (typeof module !== "undefined") module.exports = Groups;

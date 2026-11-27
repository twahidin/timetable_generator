/* Teacher-only periods on step 6: the blank row, who a row means, its faults and the lines under it.
   Plain functions over the setup, no page access, so they run under Node (tests/staffperiods.test.js).
   people and faults give the same answers and sentences as ttgen/spec.py staff_people and staff_faults. */
var StaffPeriods = (function () {
  "use strict";

  function slist(v) {
    return Array.isArray(v) ? v.filter(function (x) { return typeof x === "string" && x.trim(); }).map(function (x) { return x.trim(); }) : [];
  }
  function sstr(v) { return typeof v === "string" ? v : ""; }
  function len(v) { return Array.from(sstr(v)).length; }
  function clock(v) {
    var m = typeof v === "string" ? /^(\d{1,2}):(\d{2})$/.exec(v.trim()) : null;
    return m && +m[1] < 24 && +m[2] < 60 ? +m[1] * 60 + +m[2] : null;
  }
  function clock12(min) {
    return ((Math.floor(min / 60) % 12) || 12) + "." + ("0" + (min % 60)).slice(-2) + (min >= 720 ? " pm" : " am");
  }
  function tdepts(t) {
    var out = [];
    ["dept", "dept2"].forEach(function (k) {
      var d = String(t[k] == null ? "" : t[k]).trim();
      if (d && out.indexOf(d) < 0) out.push(d);
    });
    return out;
  }
  function teachers(spec) {
    var v = spec && spec.teachers;
    return Array.isArray(v) ? v.filter(function (t) { return t && typeof t === "object" && !Array.isArray(t); }) : [];
  }

  function blank() {
    return { name: "", all: false, depts: [], teachers: [], week: "Both", days: [], times: ["15:00", "16:00"], place: "" };
  }

  function people(spec, row) {
    row = row || {};
    var depts = slist(row.depts), names = slist(row.teachers), out = [];
    teachers(spec).forEach(function (t) {
      var nm = String(t.name == null ? "" : t.name).trim();
      if (nm && out.indexOf(nm) < 0 && (row.all === true || names.indexOf(nm) >= 0 || tdepts(t).some(function (d) { return depts.indexOf(d) >= 0; }))) out.push(nm);
    });
    return out;
  }

  function faults(spec, row) {
    if (!row || typeof row !== "object") return [];
    var ts = teachers(spec), have = {}, haveD = {}, out = [];
    ts.forEach(function (t) { have[String(t.name == null ? "" : t.name).trim()] = true; tdepts(t).forEach(function (d) { haveD[d] = true; }); });
    slist(row.teachers).forEach(function (x) { if (!have[x]) out.push({ hard: false, text: x + " is not on step 4." }); });
    slist(row.depts).forEach(function (x) { if (!haveD[x]) out.push({ hard: false, text: "Department " + x + " has no teacher." }); });
    if (!sstr(row.name).trim()) out.push({ hard: true, text: "It has no name." });
    if (len(row.name) > 60) out.push({ hard: true, text: "Its name is longer than 60 letters." });
    if (len(row.place) > 60) out.push({ hard: true, text: "Its place is longer than 60 letters." });
    if (!people(spec, row).length) out.push({ hard: true, text: "Nobody is in it." });
    if (!slist(row.days).length) out.push({ hard: true, text: "It has no day." });
    var tm = Array.isArray(row.times) && row.times.length === 2 ? row.times : [null, null];
    var a = clock(tm[0]), b = clock(tm[1]);
    if (a === null || b === null) out.push({ hard: true, text: "Its From and To times are not times." });
    else if (b <= a) out.push({ hard: true, text: "Its To time is not after its From time." });
    return out;
  }

  function whoLine(spec, row) {
    row = row || {};
    if (row.all !== true && !slist(row.depts).length) return "";
    var n = people(spec, row).length;
    return n + (n === 1 ? " teacher now." : " teachers now.") + (row.all === true ? " A new teacher is included." : "");
  }

  function blocksLine(school, row) {
    school = school || {}; row = row || {};
    var tm = Array.isArray(row.times) && row.times.length === 2 ? row.times : [null, null];
    var st = clock(sstr(school.start_time)), pl = parseInt(school.period_minutes, 10), np = parseInt(school.periods_per_day, 10);
    var a = clock(tm[0]), b = clock(tm[1]);
    if (a === null || b === null || b <= a || st === null || !(pl > 0) || !(np > 0)) return "";
    var lo = Math.floor((a - st) / pl), hi = Math.ceil((b - st) / pl) - 1;
    var before = a < st, after = b > st + np * pl;
    var endWord = "after the last period (" + clock12(st + np * pl) + ")", startWord = "before the first period (" + clock12(st) + ")";
    if (lo > np - 1) return endWord + ": it blocks no lesson";
    if (hi < 0) return startWord + ": it blocks no lesson";
    lo = Math.max(0, lo); hi = Math.min(np - 1, hi);
    var s = lo === hi ? "blocks period " + lo : "blocks periods " + lo + " to " + hi;
    if (before) s += " · " + startWord;
    if (after) s += " · " + endWord;
    return s;
  }

  function options(spec, row) {
    row = row || {};
    var depts = [], names = [], haveD = slist(row.depts), haveT = slist(row.teachers);
    teachers(spec).forEach(function (t) {
      tdepts(t).forEach(function (d) { if (depts.indexOf(d) < 0 && haveD.indexOf(d) < 0) depts.push(d); });
      var nm = String(t.name == null ? "" : t.name).trim();
      if (nm && names.indexOf(nm) < 0 && haveT.indexOf(nm) < 0) names.push(nm);
    });
    return row.all === true ? { all: false, depts: [], teachers: [] } : { all: true, depts: depts, teachers: names };
  }

  return { blank: blank, people: people, faults: faults, whoLine: whoLine, blocksLine: blocksLine, options: options };
})();
if (typeof module !== "undefined") module.exports = StaffPeriods;

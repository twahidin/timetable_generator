/* One student's screen on the Students step: the bands and groups of the student's class (from step 5), the head
   counts as they will be after Save, the student's week on the published timetable with the lessons gained and left,
   and every clash named. Plain functions over the setup and the published skeleton, no page access, nothing random,
   nothing changed in place, so they run under Node (tests/studentview.test.js). The page draws what view() returns. */
var StudentView = (function () {
  "use strict";

  var EXEMPT = "exempt", NONE = "";

  function rows(spec, k) { return spec && Array.isArray(spec[k]) ? spec[k] : []; }
  function own(o, k) { return !!o && Object.prototype.hasOwnProperty.call(o, k); }
  function isCode(c) { return !!c && c !== "Entire Class"; }
  function uniq(list) { var out = []; (list || []).forEach(function (c) { if (c && out.indexOf(c) < 0) out.push(c); }); return out; }
  function joined(list) { return (list || []).filter(Boolean).join(", "); }
  function plural(k, one, many) { return k === 1 ? "1 " + one : k + " " + many; }

  /* step 5's Everyone takes one, else the rule of everyone() in static/app.js: option and elective bands are for some */
  function everyoneOf(spec, band) {
    var b = rows(spec, "blocks").find(function (x) { return x && x.block === band; });
    return b && b.everyone != null ? !!b.everyone : !/option|elective/i.test(band || "");
  }

  /* students on the list per group code (a student counts once per group) */
  function counts(spec) {
    var out = {};
    rows(spec, "students").forEach(function (s) { uniq(s && s.groups).forEach(function (c) { out[c] = (out[c] || 0) + 1; }); });
    return out;
  }

  /* the bands and groups of one class on step 5: bands in the order of spec.blocks, then any others in row order */
  function bands(spec, codes, cls) {
    var byBand = {}, met = [], other = [], seen = {};
    if (!cls) return { bands: [], other: [] };
    rows(spec, "lessons").forEach(function (row, i) {
      var code = codes && codes[i];
      if (!row || !isCode(code) || seen[code] || (row.classes || []).indexOf(cls) < 0) return;
      seen[code] = true;
      var g = { code: code, subject: row.subject || "", size: Number(row.students) || null }, b = row.block || "";
      if (!b) { other.push(g); return; }
      if (!byBand[b]) { byBand[b] = []; met.push(b); }
      byBand[b].push(g);
    });
    var names = [];
    rows(spec, "blocks").forEach(function (x) { if (x && own(byBand, x.block) && names.indexOf(x.block) < 0) names.push(x.block); });
    met.forEach(function (b) { if (names.indexOf(b) < 0) names.push(b); });
    return { bands: names.map(function (b) { return { band: b, everyone: everyoneOf(spec, b), groups: byBand[b] }; }), other: other };
  }

  /* the picks when the screen opens: one group per band (or NONE, or EXEMPT for a band the Note exempts the student
     from), the rest of the student's groups under other (a group outside the class, off step 5, or a second one of a band) */
  function open(spec, codes, student, exempt) {
    var st = student || {}, cls = st.class || "", mine = uniq(st.groups), band = {}, exemptWas = {}, used = {};
    bands(spec, codes, cls).bands.forEach(function (x) {
      var hit = mine.filter(function (c) { return !used[c] && x.groups.some(function (y) { return y.code === c; }); })[0];
      if (hit) { band[x.band] = hit; used[hit] = true; }
      else if (exempt && exempt[x.band]) { band[x.band] = EXEMPT; exemptWas[x.band] = true; }
      else band[x.band] = NONE;
    });
    return { cls: cls, band: band, other: mine.filter(function (c) { return !used[c]; }), was: mine.slice(), exemptWas: exemptWas };
  }

  /* the picked groups: the band picks that are codes, then other */
  function groupsOf(picks) {
    var out = [], b = (picks && picks.band) || {};
    Object.keys(b).forEach(function (k) { var c = b[k]; if (c && c !== EXEMPT && out.indexOf(c) < 0) out.push(c); });
    ((picks && picks.other) || []).forEach(function (c) { if (c && c !== EXEMPT && out.indexOf(c) < 0) out.push(c); });
    return out;
  }

  function wholeOf(skel, cls) {
    var k = skel && own(skel.classes, cls) ? skel.classes[cls] : null;
    return ((k && k.whole) || []).map(function (w) { return { d: w[0], p: w[1], n: w[2], short: w[3] || "", room: w[4] || "", code: "" }; });
  }
  function lessonsOf(skel, groups) {
    var out = [];
    uniq(groups).forEach(function (c) {
      var g = skel && own(skel.groups, c) ? skel.groups[c] : null;
      if (g) (g.slots || []).forEach(function (s) { out.push({ d: s[0], p: s[1], n: s[2], short: g.short || "", room: joined(g.rooms), code: c }); });
    });
    return out;
  }

  /* the class's whole-class lessons (code "") and the lessons of each group the skeleton has */
  function week(skel, cls, groups) { return skel ? wholeOf(skel, cls).concat(lessonsOf(skel, groups)) : []; }

  /* a lesson's key: a group by its code, a whole-class lesson by its short name; two lessons of one key never clash */
  function keyOf(x) { return x.code || "=" + x.short; }
  /* every period two lessons share: {d, p, i, j}, i < j their places in the list, lowest day, then period, first */
  function overlaps(list) {
    var at = {}, spots = [], out = [];
    list.forEach(function (x, i) {
      for (var k = 0; k < (Number(x.n) || 1); k++) {
        var key = x.d + "," + (x.p + k);
        if (!own(at, key)) { at[key] = []; spots.push([x.d, x.p + k, key]); }
        at[key].push(i);
      }
    });
    spots.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    spots.forEach(function (s) {
      var here = at[s[2]];
      for (var a = 0; a < here.length; a++) for (var b = a + 1; b < here.length; b++) {
        var i = Math.min(here[a], here[b]), j = Math.max(here[a], here[b]);
        if (keyOf(list[i]) !== keyOf(list[j])) out.push({ d: s[0], p: s[1], i: i, j: j });
      }
    });
    out.sort(function (x, y) { return x.d - y.d || x.p - y.p || x.i - y.i || x.j - y.j; });
    return out;
  }

  /* every period two of those lessons share, a and b the codes ("" for a whole-class lesson) */
  function clashes(skel, cls, groups) {
    var list = week(skel, cls, groups);
    return overlaps(list).map(function (o) { return { d: o.d, p: o.p, a: list[o.i].code, b: list[o.j].code }; });
  }

  function view(spec, codes, skel, student, picks) {
    var st = student || {}, pk = picks || {}, cls = pk.cls || "", was = uniq(pk.was), now = groupsOf(pk), base = counts(spec);
    var mine = bands(spec, codes, cls), sg = (skel && skel.groups) || {}, lessons = rows(spec, "lessons"), exWas = pk.exemptWas || {};
    var pickOf = function (b) { return own(pk.band, b) ? pk.band[b] : NONE; };
    function isOn(c) { return now.indexOf(c) >= 0; }
    function wasIn(c) { return was.indexOf(c) >= 0; }
    function sk(c) { return skel && own(sg, c) ? sg[c] : null; }
    function row(c) { var i = (codes || []).indexOf(c); return i >= 0 && lessons[i] ? lessons[i] : null; }
    function subjectOf(c) { var r = row(c), g = sk(c); return r ? r.subject || "" : g ? g.subject || "" : ""; }
    function named(c) { var s = subjectOf(c); return s ? c + " " + s : c; }
    function lessonName(x) { return x.code ? named(x.code) : x.short; }
    function day(d) { return skel && skel.days && skel.days[d] != null ? skel.days[d] : "day " + (d + 1); }
    function nOf(c) { return (base[c] || 0) - (wasIn(c) && !isOn(c) ? 1 : 0) + (isOn(c) && !wasIn(c) ? 1 : 0); }

    /* the first clash of group c against the lessons the student would still have with it picked */
    function clashOf(c, leaveOut) {
      if (!skel || !sk(c)) return "";
      var list = week(skel, cls, now.filter(function (x) { return x !== c && x !== leaveOut; }).concat([c]));
      var hit = overlaps(list).filter(function (o) { return (list[o.i].code === c) !== (list[o.j].code === c); })[0];
      if (!hit) return "";
      var other = list[hit.i].code === c ? list[hit.j] : list[hit.i];
      return "Clashes: " + day(hit.d) + " period " + (hit.p + 1) + ", with " + lessonName(other);
    }
    function option(c, stepSize, leaveOut) {
      var g = sk(c), r = row(c), on = isOn(c), n = nOf(c);
      var size = stepSize || (r ? Number(r.students) || null : null) || (g ? Number(g.seats) || null : null);
      return { code: c, subject: subjectOf(c), teacher: g ? joined(g.teachers) : r ? joined(r.teachers) : "", room: g ? joined(g.rooms) : "",
        n: n, size: size, full: !on && !!size && n >= size, over: on && !!size && n > size, clash: clashOf(c, leaveOut),
        on: on, was: wasIn(c), off: !!skel && !g };
    }

    /* subjects in the order the published timetable lists them, then step 5's; most room first (the list's count as it
       is, so the order stays put while picks change); unknown size last; then by code */
    var subjects = [];
    Object.keys(sg).forEach(function (c) { var s = sg[c] && sg[c].subject; if (s && subjects.indexOf(s) < 0) subjects.push(s); });
    mine.bands.forEach(function (b) { b.groups.forEach(function (x) { if (subjects.indexOf(x.subject) < 0) subjects.push(x.subject); }); });
    function roomOf(o) { return o.size ? o.size - (base[o.code] || 0) : null; }
    function byRoom(a, b) {
      var s = subjects.indexOf(a.subject) - subjects.indexOf(b.subject); if (s) return s;
      var ra = roomOf(a), rb = roomOf(b);
      if (ra !== rb) { if (ra === null) return 1; if (rb === null) return -1; return rb - ra; }
      return a.code < b.code ? -1 : a.code > b.code ? 1 : 0;
    }
    var outBands = mine.bands.map(function (b) {
      var pick = pickOf(b.band);
      return { band: b.band, everyone: b.everyone, pick: pick,
        options: b.groups.map(function (x) { return option(x.code, x.size, pick); }).sort(byRoom) };
    });

    var ofClass = {};
    mine.bands.forEach(function (b) { b.groups.forEach(function (x) { ofClass[x.code] = true; }); });
    mine.other.forEach(function (x) { ofClass[x.code] = true; });
    function why(c) { return !row(c) ? "not on step 5" : ofClass[c] ? "" : cls ? "not a group of class " + cls : "no class is chosen"; }
    var outOther = mine.other.map(function (x) { return x.code; });
    uniq(pk.other).forEach(function (c) { if (c !== EXEMPT && outOther.indexOf(c) < 0) outOther.push(c); });
    outOther = outOther.map(function (c) {
      var x = mine.other.find(function (y) { return y.code === c; }), o = option(c, x ? x.size : null, null);
      o.why = why(c); return o;
    });

    /* the week: whole-class lessons (new when the class changes), the picked groups' lessons, then the lessons left */
    var oldCls = st.class || "", left = was.filter(function (c) { return !isOn(c); }), joinedNow = now.filter(function (c) { return !wasIn(c); });
    var alive = [], gone = [], pairs = [];
    if (skel) {
      wholeOf(skel, cls).forEach(function (x) { x.change = cls === oldCls ? "" : "new"; alive.push(x); });
      lessonsOf(skel, now).forEach(function (x) { x.change = wasIn(x.code) ? "" : "new"; alive.push(x); });
      if (oldCls && oldCls !== cls) wholeOf(skel, oldCls).forEach(function (x) { x.change = "gone"; gone.push(x); });
      lessonsOf(skel, left).forEach(function (x) { x.change = "gone"; gone.push(x); });
    }
    var hits = overlaps(alive), clashed = {}, seenPair = {};
    hits.forEach(function (o) {
      clashed[o.i] = clashed[o.j] = true;
      var k = keyOf(alive[o.i]) + "|" + keyOf(alive[o.j]);
      if (!seenPair[k]) { seenPair[k] = true; pairs.push(o); }
    });
    var cells = alive.map(function (x, i) {
      return { d: x.d, p: x.p, n: x.n, short: x.short, room: x.room, code: x.code, state: clashed[i] ? "clash" : x.change || "same", change: x.change };
    }).concat(gone.map(function (x) { return { d: x.d, p: x.p, n: x.n, short: x.short, room: x.room, code: x.code, state: "gone", change: "gone" }; }));

    /* changed: the groups as a set, the class, or a band's exempt state */
    var exemptMoved = uniq(Object.keys(pk.band || {}).concat(Object.keys(exWas))).filter(function (b) { return (pickOf(b) === EXEMPT) !== !!exWas[b]; });
    var changed = left.length > 0 || joinedNow.length > 0 || cls !== oldCls || exemptMoved.length > 0;

    var asks = pairs.map(function (o) {
      var later = alive[o.j];
      return (later.code || later.short) + " clashes on " + day(o.d) + " period " + (o.p + 1) + " with " + lessonName(alive[o.i]) + ".";
    });
    outBands.forEach(function (b) { if (b.everyone && b.pick === NONE) asks.push("No " + b.band + " group is chosen."); });
    if (skel) now.forEach(function (c) {
      if (!sk(c)) asks.push(c + " is not on the published timetable, so the published timetable will not change for this student until the next publish.");
    });

    var summary = "Nothing changed.";
    if (changed) {
      var parts = [];
      if (cls !== oldCls) parts.push(!cls ? "Leaves class " + oldCls + "." : oldCls ? "Moves to class " + cls + "." : "Joins class " + cls + ".");
      var bandOf = function (c) { var r = row(c), g = sk(c); return (r && r.block) || (g && g.band) || ""; };
      var tally = function (list, b) { return list.filter(function (c) { return bandOf(c) === b; }).length; };
      var moved = {};
      joinedNow.forEach(function (c) {
        var b = bandOf(c);
        if (!b || tally(joinedNow, b) !== 1 || tally(left, b) !== 1) return;
        var from = left.filter(function (x) { return bandOf(x) === b; })[0];
        moved[c] = moved[from] = true;
        parts.push("Moves from " + named(from) + " to " + named(c) + ".");
      });
      joinedNow.forEach(function (c) { if (!moved[c]) parts.push("Joins " + named(c) + "."); });
      left.forEach(function (c) { if (!moved[c]) parts.push("Leaves " + named(c) + "."); });
      exemptMoved.forEach(function (b) { parts.push(pickOf(b) === EXEMPT ? "Exempt from " + b + "." : "No longer exempt from " + b + "."); });
      if (skel) {
        var k = cells.filter(function (c) { return c.change === "new" || c.change === "gone"; }).length;
        parts.push(k === 0 ? "No lesson changes." : k === 1 ? "1 lesson changes." : k + " lessons change.");
        parts.push(pairs.length ? plural(pairs.length, "clash.", "clashes.") : "No clash.");
      }
      summary = parts.join(" ");
    }
    return { bands: outBands, other: outOther, cells: cells, summary: summary, asks: asks, changed: changed };
  }

  /* the student's new groups: the old ones kept, in their order, then the new ones */
  function apply(student, picks) {
    var old = uniq(student && student.groups), now = groupsOf(picks);
    return { groups: old.filter(function (c) { return now.indexOf(c) >= 0; }).concat(now.filter(function (c) { return old.indexOf(c) < 0; })) };
  }

  return { EXEMPT: EXEMPT, NONE: NONE, counts: counts, bands: bands, open: open, groupsOf: groupsOf, week: week, clashes: clashes, view: view, apply: apply };
})();
if (typeof module !== "undefined") module.exports = StudentView;

/* The Cards view of step 3 (Subjects): a subject and its G-levels drawn as one card, the cards in a column per department.
   Plain functions over the setup, no page access, so they run under Node (tests/subjectview.test.js).
   A card is not stored: it exists because rows of the subject list share a department, a code and a subject name. */
var SubjectView = (function () {
  "use strict";

  function rows(spec, k) { return spec && Array.isArray(spec[k]) ? spec[k] : []; }
  function text(v) { return v == null ? "" : String(v).trim(); }
  function endsWithTag(name, tag) { return name.length > tag.length && name.slice(name.length - tag.length - 1) === " " + tag; }

  /* the school's tags in its order, each once, without "-" and empty ones */
  function tags(spec) {
    var out = [], seen = Object.create(null);
    rows(spec && spec.school, "tags").forEach(function (p) {
      var t = Array.isArray(p) ? text(p[0]) : "";
      if (t === "" || t === "-" || seen[t]) return;
      seen[t] = true; out.push(t);
    });
    return out;
  }

  function isLesson(x) { return x && typeof x === "object"; }

  /* how many lesson rows name exactly this subject */
  function uses(spec, subject) {
    if (subject == null || subject === "") return 0;
    return rows(spec, "lessons").filter(function (x) { return isLesson(x) && x.subject === subject; }).length;
  }

  /* the table's "Teaching groups" figure: a lesson row with a band or a code of its own counts once, any other once per class */
  function groupsOf(x) { return x.block || x.code_override ? 1 : (Array.isArray(x.classes) ? x.classes.length : 0); }

  function lengthOf(v) {
    if (typeof v === "number") return isFinite(v) ? v : null;
    if (typeof v === "string" && v.trim() !== "") { var n = Number(v); return isFinite(n) ? n : null; }
    return null;
  }

  function columns(spec) {
    var school = (spec && spec.school) || {}, T = tags(spec), order = Object.create(null);
    T.forEach(function (t, i) { order[t] = i; });
    var used = Object.create(null), grp = Object.create(null);
    rows(spec, "lessons").forEach(function (x) {
      if (!isLesson(x) || x.subject == null || x.subject === "") return;
      var s = x.subject;
      used[s] = (used[s] || 0) + 1; grp[s] = (grp[s] || 0) + groupsOf(x);
    });

    var cards = [], byKey = new Map();
    rows(spec, "subjects").forEach(function (r, ri) {
      if (!r || typeof r !== "object") return;
      var tag = text(r.tag), name = text(r.subject), dept = text(r.dept), code = text(r.code), base = name, odd = "", i;
      if (tag === "-") tag = "";
      if (tag !== "") {
        if (tag in order && (name === tag || endsWithTag(name, tag))) base = name.slice(0, name.length - tag.length).trim();
        else odd = "tag";
      } else {
        for (i = 0; i < T.length; i++) if (name === T[i] || endsWithTag(name, T[i])) { odd = "tag"; break; }
      }
      var row = { ri: ri, tag: tag, subject: name, room_kind: text(r.room_kind), lesson_length: lengthOf(r.lesson_length),
        lessons: used[name] || 0, groups: grp[name] || 0 };
      var card = null, key = null;
      if (!odd && base !== "") {
        key = JSON.stringify([dept, code, base]); card = byKey.get(key) || null;
        if (card && card.rows.some(function (x) { return x.tag === tag; })) { card = null; odd = "twin"; }
      }
      if (card) { card.rows.push(row); return; }
      card = { ri: ri, dept: dept, code: code, name: odd ? name : base, odd: odd, rows: [row], ticked: [], plain: null, same_kind: true, same_length: true };
      cards.push(card);
      if (!odd && base !== "") byKey.set(key, card);
    });

    cards.forEach(function (c) {
      if (!c.odd) {
        c.rows.sort(function (a, b) { return (a.tag === "" ? -1 : order[a.tag]) - (b.tag === "" ? -1 : order[b.tag]); });
        c.ticked = c.rows.filter(function (x) { return x.tag !== ""; }).map(function (x) { return x.tag; });
        var p = c.rows.filter(function (x) { return x.tag === ""; })[0];
        c.plain = p ? p.ri : null;
      }
      c.same_kind = c.rows.every(function (x) { return x.room_kind === c.rows[0].room_kind; });
      c.same_length = c.rows.every(function (x) { return x.lesson_length === c.rows[0].lesson_length; });
    });

    var cols = [], byDept = Object.create(null);
    function column(d) { if (!(d in byDept)) { byDept[d] = { dept: d, cards: [] }; cols.push(byDept[d]); } return byDept[d]; }
    rows(school, "departments").forEach(function (d) { var t = text(d); if (t !== "") column(t); });
    cards.forEach(function (c) { if (c.dept !== "") column(c.dept); });
    if (cards.some(function (c) { return c.dept === ""; })) column("");
    cards.forEach(function (c) { column(c.dept).cards.push(c); });
    return cols;
  }

  return { tags: tags, columns: columns, uses: uses };
})();
if (typeof module !== "undefined") module.exports = SubjectView;

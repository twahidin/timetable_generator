/* The Cards view of step 4 (Teachers): a teacher drawn as a card in the column of each of their departments.
   Plain functions over the setup, no page access, so they run under Node (tests/teacherview.test.js).
   A card is not stored: it exists because a teacher row has a department (dept, the home one) or a second one (dept2). */
var TeacherView = (function () {
  "use strict";
  var P = typeof People !== "undefined" ? People : require("./people.js");

  function text(v) { return v == null ? "" : String(v).trim(); }
  function isRow(x) { return x && typeof x === "object"; }
  function list(v) { return Array.isArray(v) ? v : []; }

  /* the second department a row really has: none when empty or the home department */
  function secondOf(t) {
    var d2 = text(t.dept2);
    return d2 === text(t.dept) ? "" : d2;
  }

  /* [{ dept, cards: [{ ti, name, short, role, dept, dept2, home, provisional }] }]
     f (optional) = { dept, q }: only that department's column; only teachers whose name or short name holds q */
  function columns(spec, f) {
    var teachers = list(spec && spec.teachers), want = text(f && f.dept), q = P.key(f && f.q);
    var order = [], byDept = Object.create(null), noDept = false;
    function column(d) {
      if (!byDept[d]) { byDept[d] = { dept: d, cards: [] }; order.push(d); }
      return byDept[d];
    }
    list(spec && spec.school && spec.school.departments).forEach(function (d) { if (text(d) !== "") column(text(d)); });
    teachers.forEach(function (t, ti) {
      if (!isRow(t)) return;
      var ds = P.depts(t);
      if (!ds.length) { noDept = true; ds = [""]; }
      ds.forEach(function (d) { column(d); });
    });
    if (noDept) column("");
    var out = [];
    order.forEach(function (d) { if (d !== "" || noDept) out.push(byDept[d]); });
    teachers.forEach(function (t, ti) {
      if (!isRow(t)) return;
      if (q && P.key(t.name).indexOf(q) < 0 && P.key(t.short).indexOf(q) < 0) return;
      var ds = P.depts(t);
      if (!ds.length) ds = [""];
      ds.forEach(function (d, i) {
        byDept[d].cards.push({ ti: ti, name: text(t.name), short: text(t.short), role: text(t.role),
          dept: text(t.dept), dept2: secondOf(t), home: i === 0, provisional: text(t.provisional) === "Yes" });
      });
    });
    return want ? out.filter(function (c) { return c.dept === want; }) : out;
  }

  /* gives, changes or takes off the second department of teacher ti; how it went, and what it was */
  function setSecond(spec, ti, dept) {
    var t = list(spec && spec.teachers)[ti];
    if (!isRow(t)) return null;
    var d = text(dept), was = secondOf(t);
    if (d === "") {
      if (was === "" && !("dept2" in t)) return { how: "none", was: "" };
      delete t.dept2;
      return { how: was === "" ? "none" : "off", was: was };
    }
    if (d === text(t.dept)) return { how: "home", was: was };
    if (d === was) return { how: "same", was: was };
    t.dept2 = d;
    return { how: was === "" ? "set" : "changed", was: was };
  }

  /* takes off a dept2 that is empty or equal to dept; true when the row changed */
  function tidy(t) {
    if (!isRow(t) || !("dept2" in t) || secondOf(t) !== "") return false;
    delete t.dept2;
    return true;
  }

  return { columns: columns, setSecond: setSecond, tidy: tidy };
})();
if (typeof module !== "undefined") module.exports = TeacherView;

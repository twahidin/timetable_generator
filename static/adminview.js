/* AdminView: pure helpers for the admin page's Staff tab. No document, no window:
   functions over the plain objects GET /api/admin/people sends, so Node can test them.
   Every check that matters is the server's; these only decide what the page shows. */
var AdminView = (function () {
  "use strict";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var ON_TIMETABLE = " is on the published timetable, so they cannot be removed: they would come straight back. Switch them off instead.";
  var SELF = "You cannot remove yourself.";

  function day(iso) {
    var m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(iso || "");
    return m ? (+m[3]) + " " + MONTHS[+m[2] - 1] + " " + m[1] : String(iso || "");
  }

  // a date box's value that is a whole date: Chrome fires "change" while a year is still being typed ("0002-12-31")
  function wholeDay(v) {
    var m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(typeof v === "string" ? v : "");
    if (!m || +m[1] < 2000) return false;
    var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return d.getUTCFullYear() === +m[1] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3];
  }

  function extras(p) { return (p && p.extras) || {}; }

  // the chips of the Committees column, in this order; a passed exams day still shows (the page always has)
  function committees(p) {
    var x = extras(p), out = [];
    if (x.timetable) out.push({ key: "timetable", text: "Timetable committee" });
    if (x.relief) out.push({ key: "relief", text: "Relief team" });
    if (x.exams) out.push({ key: "exams", text: "Exams and events · to " + day(x.exams) });
    if (x.admin) out.push({ key: "admin", text: "Admin" });
    return out;
  }

  // committee: "", "timetable", "relief", "exams", "admin", "none" (none of the three committees) or "off"
  function committeeOk(p, c) {
    var x = extras(p);
    if (!c) return true;
    if (c === "off") return !!p.off;
    if (c === "none") return !x.timetable && !x.relief && !x.exams;
    return !!x[c];
  }

  function shown(people, f) {
    f = f || {};
    var q = String(f.q || "").trim().toLowerCase();
    return (people || []).filter(function (p) {
      return (!q || String(p.name).toLowerCase().indexOf(q) !== -1) && (!f.role || p.group === f.role) &&
        (!f.dept || (p.depts || []).indexOf(f.dept) !== -1) && committeeOk(p, f.committee);
    });
  }

  // the timetable's sentence wins over "yourself": the server checks in that order too
  function canRemove(p, me) {
    if (!p.staff_only) return { ok: false, why: p.name + ON_TIMETABLE };
    if (p.name === me) return { ok: false, why: SELF };
    return { ok: true, why: "" };
  }

  function noPassword(p) {
    var strong = (p.gives || []).some(function (g) { return g && g.strong; });
    return strong && !p.strong ? "The lines marked ✱ need a password account. " + p.name + " has none yet." : "";
  }

  return { day: day, wholeDay: wholeDay, committees: committees, shown: shown, canRemove: canRemove, noPassword: noPassword };
})();
if (typeof module !== "undefined") module.exports = AdminView;

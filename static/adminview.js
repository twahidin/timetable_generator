/* AdminView: pure helpers for the admin page's Staff and Ways in tabs. No document, no window:
   functions over the plain objects GET /api/admin/people and /api/admin/ways send, so Node can test them.
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

  /* ---- the Ways in tab */
  var SHARED_NAMES = { committee: "Shared committee code", head: "Shared heads' code", teacher: "Shared teacher code", student: "Shared student code" };
  var USERNAME_SLIPS = { act: "menu", kind: "uslips", text: "Print username slips" };

  function count(n) { return String(+n || 0).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }   /* 1284 -> "1,284" */

  // t in seconds since 1970 -> "Off since 26 Nov 2026", the day where the page is open
  function offSince(t) {
    var d = new Date(t * 1000);
    return "Off since " + d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear();
  }

  function staffOffAsk(waiting) {
    var first = "Staff codes stop working at once, on every device. ";
    if (!waiting) return first + "Every staff member has chosen their own password.";
    return first + count(waiting) + " staff " + (waiting === 1 ? "has" : "have") + " not signed in with a password yet: they will need their slip.";
  }

  /* the table's rows, in order: {name, bold, state, cls ("" plain, "on" green, "stillon", "w" grey), buttons [{act, text, cls, code?, off?}]} */
  function waysRows(w) {
    var on = w.personal_codes ? "On" : "Off", sc = w.staff_codes || {}, staffOff = sc.off != null, students = +w.students || 0;
    var rows = [
      { name: "Student codes", bold: true, state: on + " · " + count(students) + (students === 1 ? " student" : " students"), cls: "",
        buttons: [{ act: "slipsstu", text: "Print slips", cls: "small" }] },
      staffOff
        ? { name: "Staff codes", bold: true, state: offSince(sc.off), cls: "on", buttons: [{ act: "staffcodes", text: "Turn on", cls: "small", off: false }] }
        : { name: "Staff codes", bold: true, state: on + " · " + count(sc.waiting) + " staff without a password yet", cls: "",
            buttons: [{ act: "slipsall", text: "Print code slips", cls: "small" }, { act: "staffask", text: "Turn off", cls: "small danger" }] },
      { name: "Username and password", bold: true, state: (w.secret_key ? "On" : "Off") + " · " + count(w.staff_chosen) + " of " + count(w.staff) + " staff", cls: "",
        buttons: [{ act: "mkslips", text: "Make accounts and print slips", cls: "small" }] },
      { name: "Recovery code", bold: true, state: w.recovery_set ? "Set in Railway variables" : w.recovery_short ? "Too short: recovery is off" : "Not set", cls: "", buttons: [] }];
    (w.shared || []).forEach(function (r) {
      var off = r.off != null;
      rows.push({ name: SHARED_NAMES[r.code] || r.code, bold: false,
        state: !r.set ? "Not set" : off ? offSince(r.off) : "Still on · used " + r.used_week + (r.used_week === 1 ? " time" : " times") + " this week",
        cls: !r.set ? "w" : off ? "on" : "stillon",
        buttons: !r.set ? [] : [off ? { act: "shared", text: "Turn on", cls: "small", code: r.code, off: false } : { act: "shared", text: "Turn off", cls: "small danger", code: r.code, off: true }] });
    });
    return rows;
  }

  // the slip buttons of the dark bar: relief code slips only while staff codes are on (the server refuses them once off)
  function barSlips(staffOff) {
    return staffOff ? [USERNAME_SLIPS] : [{ act: "slips", text: "Print their code slips" }, USERNAME_SLIPS];
  }

  function slipsSaved(n) {
    return "Sign-in slips for " + count(n) + " staff are saved: sign-in slips.pdf to print, and sign-in slips.csv for a mail merge.";
  }

  return { day: day, wholeDay: wholeDay, committees: committees, shown: shown, canRemove: canRemove, noPassword: noPassword,
           SHARED_NAMES: SHARED_NAMES, offSince: offSince, staffOffAsk: staffOffAsk, waysRows: waysRows, barSlips: barSlips, slipsSaved: slipsSaved };
})();
if (typeof module !== "undefined") module.exports = AdminView;

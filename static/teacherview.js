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

  /* ---- renaming a teacher: the new name follows to groups, form teachers and Teacher rules ----
     Names are matched exactly (===); only the "already a teacher" check ignores case and spacing (P.key). */

  /* a name as it is stored: the ends trimmed, runs of spaces made one; "" for nothing */
  function cleanName(v) { return v == null || (typeof v !== "string" && typeof v !== "number") ? "" : String(v).replace(/\s+/g, " ").trim(); }

  var NOTE_LISTS = ["venues", "classes", "subjects", "teachers", "blocks", "lessons", "rules"];

  /* where a teacher's name is used: row numbers (from 0) of groups, classes and Teacher rules, the numbers (from 1)
     of typed rules that say it, how many notes say it, and whether two teacher rows have exactly this name */
  function uses(spec, name) {
    var out = { lessons: [], classes: [], rules: [], staff: [], typed: [], notes: 0, twice: false };
    if (typeof name !== "string" || name.trim() === "" || !isRow(spec)) return out;
    list(spec.lessons).forEach(function (l, i) { if (isRow(l) && list(l.teachers).indexOf(name) >= 0) out.lessons.push(i); });
    list(spec.classes).forEach(function (c, i) { if (isRow(c) && list(c.parents).indexOf(name) >= 0) out.classes.push(i); });
    list(spec.staff_periods).forEach(function (r, i) { if (isRow(r) && list(r.teachers).indexOf(name) >= 0) out.staff.push(i); });
    var typed = 0;
    list(spec.rules).forEach(function (r, i) {
      if (!isRow(r)) return;
      if (r.scope === "Teacher" && r.target === name) out.rules.push(i);
      if (r.rule === "In words") { typed++; if (typeof r.text === "string" && r.text.indexOf(name) >= 0) out.typed.push(typed); }
    });
    NOTE_LISTS.forEach(function (k) {
      list(spec[k]).forEach(function (row) { if (isRow(row) && typeof row.note === "string" && row.note.indexOf(name) >= 0) out.notes++; });
    });
    out.twice = list(spec.teachers).filter(function (t) { return isRow(t) && t.name === name; }).length > 1;
    return out;
  }

  /* puts every row's earlier_names right: only text, no repeats, no name a teacher has now, no name two rows claim
     (it stays on the last of them); the key goes when nothing is left. True when anything changed. */
  function settle(spec) {
    var teachers = list(spec && spec.teachers), current = Object.create(null), seen = Object.create(null), changed = false;
    teachers.forEach(function (t) { if (isRow(t) && typeof t.name === "string") current[t.name] = true; });
    var clean = teachers.map(function (t) {
      if (!isRow(t) || !("earlier_names" in t)) return null;
      var mine = Object.create(null);
      return list(t.earlier_names).filter(function (n) {
        if (typeof n !== "string" || n === "" || current[n] || mine[n]) return false;
        mine[n] = true;
        return true;
      });
    });
    for (var i = teachers.length - 1; i >= 0; i--) {
      if (!clean[i]) continue;
      clean[i] = clean[i].filter(function (n) { if (seen[n]) return false; seen[n] = true; return true; });
    }
    teachers.forEach(function (t, i) {
      if (!clean[i]) return;
      if (clean[i].length === 0) { delete t.earlier_names; changed = true; return; }
      if (JSON.stringify(t.earlier_names) !== JSON.stringify(clean[i])) { t.earlier_names = clean[i]; changed = true; }
    });
    return changed;
  }

  /* gives teacher row ti the name `to` and carries it to their groups, the classes they are form teacher of and their
     Teacher rules (not when two rows have the old name). Changes spec in place.
     null: not a rename; { same: true }: the cleaned name is the stored one (nothing changes); { error }: the name is another
     teacher's; else { was, now, groups, classes, rules, typed, notes, twice, short } (short: a short name that did not follow, else null) */
  function rename(spec, ti, to) {
    var teachers = list(spec && spec.teachers), t = teachers[ti];
    if (!isRow(t) || typeof t.name !== "string" || t.name.trim() === "" || to == null) return null;
    var now = cleanName(to), was = t.name;
    if (now === "") return null;
    if (now === was) return { same: true };
    for (var j = 0; j < teachers.length; j++) {
      if (j !== ti && isRow(teachers[j]) && P.key(teachers[j].name) === P.key(now)) return { error: teachers[j].name + " is already a teacher." };
    }
    var u = uses(spec, was), r = { was: was, now: now, groups: 0, classes: [], rules: 0, staff: 0, typed: u.typed, notes: u.notes, twice: u.twice, short: null };
    if (!u.twice) {
      u.lessons.forEach(function (i) {
        var ts = spec.lessons[i].teachers;
        r.groups++;
        for (var k = 0; k < ts.length; k++) if (ts[k] === was) ts[k] = now;
      });
      u.classes.forEach(function (i) {
        var c = spec.classes[i], ps = c.parents;
        r.classes.push(c.class);
        for (var k = 0; k < ps.length; k++) if (ps[k] === was) ps[k] = now;
      });
      u.rules.forEach(function (i) { spec.rules[i].target = now; r.rules++; });
      u.staff.forEach(function (i) {
        var ts = spec.staff_periods[i].teachers;
        r.staff++;
        for (var k = 0; k < ts.length; k++) if (ts[k] === was) ts[k] = now;
      });
    }
    var earlier = list(t.earlier_names).filter(function (n) { return n !== was; });
    earlier.push(was);
    teachers.forEach(function (o) {
      if (o === t || !isRow(o) || !Array.isArray(o.earlier_names)) return;
      o.earlier_names = o.earlier_names.filter(function (n) { return n !== was; });
    });
    t.earlier_names = earlier;
    if (t.short === was) t.short = now;                       // a short name that was the name follows it
    else if (typeof t.short === "string" && t.short.trim() !== "") r.short = t.short;
    t.name = now;
    settle(spec);
    return r;
  }

  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }
  function andList(a) { return a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; }

  /* the toast for a result of rename that is not null and has no error */
  function renameText(r) {
    var out = r.was + " is now " + r.now, parts = [];
    if (r.groups) parts.push("on " + plural(r.groups, "group", "groups"));
    if (r.classes.length) parts.push("form teacher of " + andList(r.classes));
    if (r.rules) parts.push(plural(r.rules, "rule", "rules"));
    if (r.staff) parts.push(plural(r.staff, "teacher-only period", "teacher-only periods"));
    if (parts.length) out += ": " + parts.join(", ") + ". Undo, at the top, brings it back.";
    else if (r.twice) out += ". Two teachers were called " + r.was + ", so their groups were not changed: pick the right teacher on each.";
    else out += ".";
    if (typeof r.short === "string" && r.short.trim() !== "") out += " The short name is still " + r.short + ": change it too if it should be different.";
    if (r.typed.length) {
      var one = r.typed.length === 1;
      out += " Typed " + (one ? "rule " : "rules ") + andList(r.typed.map(function (n) { return "T" + n; })) +
        (one ? " still says " : " still say ") + r.was + ": check " + (one ? "it" : "them") + ".";
    }
    if (r.notes) out += " " + plural(r.notes, "note", "notes") + (r.notes === 1 ? " still says " : " still say ") + r.was + ": check " + (r.notes === 1 ? "it" : "them") + ".";
    return out;
  }

  /* why a head may not rename this teacher: "" when nothing stands in the way. other(row) and staffed(row) are the page's
     tests of a lesson row (another department's group; a lesson the form teachers take). Changes nothing. */
  function blocked(spec, name, other, staffed) {
    var u = uses(spec, name), parts = [], others = 0, taken = 0;
    if (u.classes.length) parts.push("a form teacher of " + andList(u.classes.map(function (i) { return text(spec.classes[i].class); })));
    if (u.rules.length) parts.push("named in " + plural(u.rules.length, "rule", "rules"));
    u.lessons.forEach(function (i) {
      var row = spec.lessons[i];
      if (other(row)) others++;
      else if (staffed(row)) taken++;
    });
    if (others) parts.push("on " + plural(others, "group", "groups") + " of other departments");
    if (taken) parts.push("on " + plural(taken, "lesson", "lessons") + " the form teachers take");
    return parts.length ? "Only the committee can rename " + name + ": they are " + andList(parts) + "." : "";
  }

  return { cleanName: cleanName, columns: columns, setSecond: setSecond, tidy: tidy, uses: uses, rename: rename, renameText: renameText, settle: settle, blocked: blocked };
})();
if (typeof module !== "undefined") module.exports = TeacherView;

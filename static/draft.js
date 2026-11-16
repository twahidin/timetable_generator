/* The draft on step 8: how its warnings are grouped, counted and worded. Plain functions over the warnings the server
   gives the page (GET /api/draft), no page access, so they run under Node (tests/draft.test.js). */
var Draft = (function () {
  "use strict";

  var KINDS = ["clash", "room", "deployment", "rule", "typed", "choice"];
  var KIND_TEXT = { clash: "Clashes", room: "No room", deployment: "Differences from the deployment", rule: "Rules", typed: "Rules in words", choice: "Choices used" };

  function answer(w) { return w && w.decision ? w.decision.answer : ""; }
  /* a warning is open until it has a decision; an old "left" decision is no decision */
  function isOpen(w) { var a = answer(w); return !a || a === "left"; }

  /* filter is "open" or "all" */
  function keep(w, filter) { return filter === "all" || isOpen(w); }

  /* [{kind, title, groups: [{name, items}]}]: by kind in KINDS order, then by group in first-seen order */
  function group(warnings, filter) {
    var out = [];
    KINDS.forEach(function (kind) {
      var groups = [], by = {};
      (warnings || []).forEach(function (w) {
        if (w.kind !== kind || !keep(w, filter)) return;
        if (!Object.prototype.hasOwnProperty.call(by, w.group)) { by[w.group] = { name: w.group, items: [] }; groups.push(by[w.group]); }
        by[w.group].items.push(w);
      });
      if (groups.length) out.push({ kind: kind, title: KIND_TEXT[kind], groups: groups });
    });
    return out;
  }

  /* the warnings that are critical mistakes (they have a crit), in their order */
  function critical(warnings) { return (warnings || []).filter(function (w) { return !!w.crit; }); }

  /* the line above the Publish button while critical mistakes remain */
  function gateText(n) { return !n ? "" : n === 1 ? "1 critical mistake to settle on step 8 first." : n + " critical mistakes to settle on step 8 first."; }

  /* a critical mistake's kind in words */
  function critWord(crit) {
    return { teacher: "Teacher in two places", "class": "Class clash", room: "Room used twice", "break": "In a break or outside the day", noteacher: "No teacher", notplaced: "Not placed" }[crit] || "";
  }

  /* open (no decision) with how many Must and Prefer among them, how many are critical, settled on step 5, and checked as still met */
  function counts(warnings) {
    var c = { open: 0, critical: 0, step5: 0, met: 0, must: 0, prefer: 0 };
    (warnings || []).forEach(function (w) {
      var a = answer(w);
      if (w.crit) c.critical++;
      if (a === "step5") c.step5++;
      if (a === "met") c.met++;
      if (isOpen(w)) { c.open++; if (w.strength === "Prefer") c.prefer++; else c.must++; }
    });
    return c;
  }

  /* the open warnings that are not critical mistakes, counted on their own */
  function others(warnings) { return (warnings || []).filter(function (w) { return isOpen(w) && !w.crit; }).length; }

  function answerText(w) { return { step5: "Step 5 updated", fixed: "Fixed", met: "Checked: still met" }[answer(w)] || ""; }

  function sideText(w) { var s = w && w.sides; return s ? "Timetable: " + s.timetable + " · Step 5: " + s.step5 : ""; }

  /* the parts of a warning's where that are there, in words: teacher, class, day, "period N" */
  function whereText(w) {
    var h = (w && w.where) || {};
    return [h.teacher, h.cls, h.day, h.period === null || h.period === undefined || h.period === "" ? "" : "period " + h.period].filter(function (x) { return x !== null && x !== undefined && x !== ""; }).map(String);
  }
  /* the week the warning's Fix the timetable button opens -> {view, name, day, sel} or null when there is none: the teacher's
     week, else the class's (on the warning's day, its lesson selected); day "" opens the first week */
  function fixTarget(w) {
    var h = w && w.where;
    if (!h) return null;
    if (h.teacher) return { view: "teacher", name: h.teacher, day: "", sel: null };
    if (!h.cls) return null;
    return { view: "class", name: h.cls, day: h.day || "", sel: h.id !== undefined && h.id !== null ? { id: Number(h.id), group: h.row } : null };
  }

  /* [{batch, items}]: neighbours with the same non-null batch are one entry; any other fix is its own; order kept, newest last */
  function batches(fixes) {
    var out = [];
    (fixes || []).forEach(function (f) {
      var last = out[out.length - 1];
      if (f.batch && last && last.batch === f.batch) last.items.push(f);
      else out.push({ batch: f.batch || null, items: [f] });
    });
    return out;
  }
  /* the Undo button's words: it undoes the newest entry, which may be a batch */
  function undoText(fixes) {
    var all = batches(fixes), k = all.length ? all[all.length - 1].items.length : 0;
    return !k ? "" : k === 1 ? "Undo the last fix" : k === 2 ? "Undo the last two fixes" : "Undo the last " + k + " fixes";
  }
  /* a suggestion's state in words */
  function stateWord(state) { return state === "ok" ? "Clean" : state === "prefer" ? "Bends a Prefer" : ""; }

  /* the warning the card was opened on (was: {key, kind, where}), found again in the list now -> {key, how} or null.
     "same": the key is there, or only renumbered (#2, #3); "changed": a clash for the same teacher or class, or a rule warning
     for the same rule and lesson, under a new key; null when there is nothing to follow */
  function follow(was, warnings) {
    var list = warnings || [], base = function (k) { return String(k).replace(/#\d+$/, ""); };
    if (!was || was.key === undefined || was.key === null) return null;
    var hit = list.filter(function (w) { return w.key === was.key; })[0] || list.filter(function (w) { return base(w.key) === base(was.key); })[0];
    if (hit) return { key: hit.key, how: "same" };
    var wh = was.where || null;
    if (was.kind === "clash" && wh && (wh.teacher || wh.cls)) {
      hit = list.filter(function (w) { var x = w.where || {}; return w.kind === "clash" && w.crit !== "notplaced" && (wh.teacher ? x.teacher === wh.teacher : x.cls === wh.cls); })[0];   // a lesson waiting in Not placed is not the clash it settled
    } else if (was.kind === "rule" && wh && wh.id !== undefined && wh.id !== null) {
      var rid = function (k) { return String(k).split(":")[1]; };
      hit = list.filter(function (w) { var x = w.where || {}; return w.kind === "rule" && rid(w.key) === rid(was.key) && x.id === wh.id && x.row === wh.row; })[0];
    }
    return hit ? { key: hit.key, how: "changed" } : null;
  }

  /* the line above a typed request's results: the model's reply, the count left out, and what was asked beyond the ask (the app did not check that) */
  function askSummary(a) {
    if (!a) return "";
    if (a.ok === false) return a.error || "";
    var out = [];
    if (a.reply) out.push(a.reply);
    if (a.more) out.push(a.more === 1 ? "1 more lesson matches." : a.more + " more lessons match.");
    if (a.keep && a.keep.length) out.push("You also asked: " + a.keep.join("; ") + ". The app did not check this: look at the preview before you apply.");
    return out.join(" ");
  }
  /* the word a choice question uses for the field the name was meant for */
  function choiceWord(field) { return { classes: "class", subject: "subject", teacher: "teacher", new_teacher: "teacher", new_room: "room" }[field] || "name"; }

  return { askSummary: askSummary, choiceWord: choiceWord, follow: follow, batches: batches, undoText: undoText, stateWord: stateWord, whereText: whereText, fixTarget: fixTarget, KINDS: KINDS, KIND_TEXT: KIND_TEXT, isOpen: isOpen, critical: critical, gateText: gateText, critWord: critWord, group: group, counts: counts, others: others, answerText: answerText, sideText: sideText };
})();
if (typeof module !== "undefined") module.exports = Draft;

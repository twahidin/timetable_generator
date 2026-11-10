/* The draft on step 8: how its warnings are grouped, counted and worded. Plain functions over the warnings the server
   gives the page (GET /api/draft), no page access, so they run under Node (tests/draft.test.js). */
var Draft = (function () {
  "use strict";

  var KINDS = ["clash", "deployment", "rule", "typed", "choice"];
  var KIND_TEXT = { clash: "Clashes", deployment: "Differences from the deployment", rule: "Rules", typed: "Rules in words", choice: "Choices used" };

  function answer(w) { return w && w.decision ? w.decision.answer : ""; }
  /* a warning is open until it is settled: no decision yet, or left for now */
  function isOpen(w) { var a = answer(w); return !a || a === "left"; }

  function keep(w, filter) { return filter === "all" || (filter === "left" ? answer(w) === "left" : isOpen(w)); }

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

  /* open (no decision or left) with how many Must and Prefer among them, left, and settled on step 5 */
  function counts(warnings) {
    var c = { open: 0, left: 0, step5: 0, must: 0, prefer: 0 };
    (warnings || []).forEach(function (w) {
      var a = answer(w);
      if (a === "left") c.left++;
      if (a === "step5") c.step5++;
      if (isOpen(w)) { c.open++; if (w.strength === "Prefer") c.prefer++; else c.must++; }
    });
    return c;
  }

  function answerText(w) { return { left: "Left for now", step5: "Step 5 updated", fixed: "Fixed" }[answer(w)] || ""; }

  function sideText(w) { var s = w && w.sides; return s ? "Timetable: " + s.timetable + " · Step 5: " + s.step5 : ""; }

  return { KINDS: KINDS, KIND_TEXT: KIND_TEXT, isOpen: isOpen, group: group, counts: counts, answerText: answerText, sideText: sideText };
})();
if (typeof module !== "undefined") module.exports = Draft;

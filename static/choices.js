/* Second choices on step 6: how a choice reads in words, which items can still be given one, adding and ordering choices,
   and what is wrong with one. Plain functions over the setup (spec) and the settings list the server gives the page
   (SET = S.meta.setting_rules), no page access, so they run under Node (tests/choices.test.js). Mirrors ttgen/choices.py. */
var Choices = (function () {
  "use strict";

  var TYPED = "In words", FALLBACKS = ["Prefer", "Instead", "Drop"];

  function blank(v) { return v === null || v === undefined || v === ""; }
  function list(spec, k) { return Array.isArray(spec[k]) ? spec[k] : []; }
  function school(spec) { return spec.school || {}; }
  function setOf(SET, key) { return (SET || []).find(function (s) { return s.key === key; }) || null; }
  function strength(r) { return String(r.strength || "Must"); }

  /* [{i, c}] by order, then position; a choice without an order is last */
  function ordered(spec) {
    return list(spec, "choices").map(function (c, i) { return { i: i, c: c }; }).sort(function (a, b) {
      var x = typeof a.c.order === "number" ? a.c.order : Infinity, y = typeof b.c.order === "number" ? b.c.order : Infinity;
      return x === y ? a.i - b.i : (x < y ? -1 : 1);
    });
  }

  function ruleLabel(r) {
    return [r.scope, r.target, r.subject, r.rule].filter(function (x) { return !blank(x); }).join(" · ");
  }
  function typedNo(spec, i) {
    var n = 0, found = 1;
    list(spec, "rules").forEach(function (r, j) { if (r && r.rule === TYPED) { n++; if (j === i) found = n; } });
    return found;
  }
  function ruleIndex(spec, c) {
    if (blank(c.rule_id)) return null;
    var j = list(spec, "rules").findIndex(function (r) { return r && r._id === c.rule_id; });
    return j < 0 ? null : j;
  }
  function ruleWords(spec, i) {
    var r = spec.rules[i];
    if (r.rule === TYPED) {
      var parts = ["T" + typedNo(spec, i), strength(r)];
      if (String(r.target || "").trim()) parts.push(String(r.target).trim());
      parts.push(String(r.text || "").trim());
      return "Rule: " + parts.join(" · ");
    }
    return "Rule: " + ruleLabel(r);
  }

  /* clock times */
  function minutes(t) {
    var p = String(t === null || t === undefined ? "" : t).trim().replace(".", ":").split(":");
    return parseInt(p[0], 10) * 60 + (parseInt((p[1] || "0").slice(0, 2), 10) || 0);
  }
  function clockMin(m) { return Math.floor(m / 60) + "." + ("0" + (m % 60)).slice(-2); }
  function clock(t) { return clockMin(minutes(t)); }

  /* a rule row that a Settings row stands for */
  function isSettingRule(r, s) {
    var w = s.rule;
    return !!w && r.rule === w.rule && r.scope === w.scope && (w.scope !== "Department" || r.target === w.target);
  }
  function settingValue(spec, SET, key) {
    var s = setOf(SET, key), sc = school(spec);
    if (key === "after_school") return blank(sc.after_school) || sc.after_school ? "Yes" : "No";
    if (key === "pe_rain_home") return sc.pe_rain_home ? "Yes" : "No";
    if (!s) return "";
    var rows = list(spec, "rules").filter(function (r) { return r && isSettingRule(r, s) && strength(r) === "Must"; });
    if (s.number) return rows.length && !blank(rows[0].number) ? rows[0].number : "";
    return rows.length ? "Yes" : "No";
  }
  function firstValue(spec, SET, key) { var v = settingValue(spec, SET, key); return v === "" ? "no limit" : String(v); }

  /* the level's fixed recess (the first run of R): {from, to, length, text} or null */
  function recessFirst(spec, level) {
    var sc = school(spec), st = minutes(sc.start_time), pm = parseInt(sc.period_minutes, 10);
    var rows = Object.values((spec.day_structure || {})[level] || {});
    for (var k = 0; k < rows.length; k++) {
      var m = /R+/.exec(String(rows[k]));
      if (m) {
        var a = m.index, b = m.index + m[0].length - 1;
        return { from: a, to: b, length: b - a + 1, text: clockMin(st + a * pm) + " to " + clockMin(st + (b + 1) * pm) };
      }
    }
    return null;
  }
  function hasWindow(spec, level) {
    return Object.values((spec.day_structure || {})[level] || {}).some(function (row) { return String(row).indexOf("W") >= 0; });
  }
  function periodsBetween(sc, a, b) {
    var st = minutes(sc.start_time), pl = parseInt(sc.period_minutes, 10), np = parseInt(sc.periods_per_day, 10);
    return [Math.max(0, Math.floor((minutes(a) - st) / pl)), Math.min(np - 1, Math.ceil((minutes(b) - st) / pl) - 1)];
  }
  function timeOk(t) { return typeof t === "string" && /^\d{1,2}[:.]\d{2}$/.test(t.trim()); }

  /* the sentence for what is wrong with a recess window on a level, or "" */
  function recessProblem(spec, lv, w) {
    if (hasWindow(spec, lv)) return lv + " already has a floating recess (W on Day structure).";
    var rf = recessFirst(spec, lv);
    if (!rf) return lv + " has no fixed recess (R on Day structure) to float.";
    if (!Array.isArray(w) || !timeOk(w[0]) || !timeOk(w[1])) return "The window is missing or cannot be read.";
    var a = minutes(w[0]), b = minutes(w[1]), p = periodsBetween(school(spec), w[0], w[1]), lo = p[0], hi = p[1];
    var shown = clock(w[0]) + " to " + clock(w[1]);
    if (b - a < rf.length * parseInt(school(spec).period_minutes, 10) || hi - lo + 1 < rf.length)
      return "The window " + shown + " is shorter than the recess (" + rf.length + " period" + (rf.length !== 1 ? "s" : "") + ").";
    if (hi < rf.from || lo > rf.to) return "The window " + shown + " does not include the recess (" + rf.text + ").";
    return "";
  }

  function itemLabel(spec, c, SET) {
    var s, i;
    if (c.kind === "setting") { s = setOf(SET, c.key); return s ? s.label : "(missing) " + (c.item || c.key || "setting"); }
    if (c.kind === "rule") { i = ruleIndex(spec, c); return i !== null ? ruleWords(spec, i) : "(missing) " + (c.item || "Rule"); }
    if (c.kind === "recess") return "Recess for " + c.level;
    return "(missing) " + (c.item || c.kind || "choice");
  }
  function firstText(spec, c, SET) {
    var i, rf;
    if (c.kind === "setting") return setOf(SET, c.key) ? firstValue(spec, SET, c.key) : "(missing)";
    if (c.kind === "rule") { i = ruleIndex(spec, c); return i !== null ? "As written (" + strength(spec.rules[i]) + ")" : "(missing)"; }
    if (c.kind === "recess") {
      rf = recessFirst(spec, c.level);
      if (!rf) return "(no fixed recess)";
      return "Fixed at " + rf.text + " (" + (rf.from !== rf.to ? "periods " + rf.from + "-" + rf.to : "period " + rf.from) + ")";
    }
    return "";
  }
  function secondText(spec, c) {
    var r, w;
    if (c.kind === "setting") return blank(c.second) ? "" : String(c.second);
    if (c.kind === "rule") {
      if (c.fallback === "Prefer") return "Make it Prefer";
      if (c.fallback === "Drop") return "Drop it";
      if (c.fallback === "Instead") { r = c.instead || {}; return "Instead: " + (r.rule === TYPED ? String(r.text || "").trim() : ruleLabel(r)); }
      return "";
    }
    if (c.kind === "recess") {
      w = c.window;
      return Array.isArray(w) && timeOk(w[0]) && timeOk(w[1]) ? "Floating between " + clock(w[0]) + " and " + clock(w[1]) : "(no window)";
    }
    return "";
  }

  /* {choice index: [sentence]} for the choices with something wrong; the same sentences as ttgen/choices.py problems() */
  function problems(spec, SET) {
    var out = {};
    list(spec, "choices").forEach(function (c, i) {
      function say(t) { out[i] = [t]; }
      var s, sec, j, t;
      if (c.kind === "setting") {
        s = setOf(SET, c.key);
        if (!s) return say("'" + (c.key || c.item || "") + "' is not a setting the timetable knows.");
        sec = blank(c.second) ? "" : String(c.second).trim();
        if (sec === "") return say("The second choice is blank.");
        if (s.number) { if (sec.toLowerCase() !== "no limit" && !/^\d+$/.test(sec)) return say("The second choice must be a whole number or no limit."); }
        else if (sec !== "Yes" && sec !== "No") return say("The second choice must be Yes or No.");
        if (sec.toLowerCase() === firstValue(spec, SET, c.key).trim().toLowerCase()) say("The second choice is the same as the first.");
      } else if (c.kind === "rule") {
        j = ruleIndex(spec, c);
        if (j === null) return say("The rule this choice falls back on is no longer on the setup.");
        if (FALLBACKS.indexOf(c.fallback) < 0) return say("Pick Make it Prefer, Instead or Drop it for the second choice.");
        if (c.fallback === "Instead" && !(c.instead || {}).rule) say("The Instead rule is not filled in.");
      } else if (c.kind === "recess") {
        t = recessProblem(spec, c.level, c.window);
        if (t) say(t);
      } else say("This choice is not a setting, a rule or a recess.");
    });
    return out;
  }

  function hasChoice(spec, test) { return list(spec, "choices").some(test); }
  function candidates(spec, SET) {
    var haveRule = {}, haveSet = {}, haveLevel = {};
    list(spec, "choices").forEach(function (c) {
      if (c.kind === "setting") haveSet[c.key] = true;
      else if (c.kind === "rule") haveRule[ruleIndex(spec, c)] = true;
      else if (c.kind === "recess") haveLevel[c.level] = true;
    });
    return {
      settings: (SET || []).filter(function (s) { return !haveSet[s.key]; }).map(function (s) { return s.key; }),
      rules: list(spec, "rules").map(function (r, i) { return i; }).filter(function (i) {
        var r = spec.rules[i];
        return r && !haveRule[i] && !((SET || []).some(function (s) { return strength(r) === "Must" && isSettingRule(r, s); }));
      }),
      levels: (school(spec).levels || []).filter(function (lv) { return !haveLevel[lv] && recessFirst(spec, lv) && !hasWindow(spec, lv); })
    };
  }

  function nextOrder(spec) {
    return list(spec, "choices").reduce(function (m, c) { return typeof c.order === "number" && c.order > m ? c.order : m; }, 0) + 1;
  }
  function add(spec, row) {
    if (!Array.isArray(spec.choices)) spec.choices = [];
    row.order = nextOrder(spec); spec.choices.push(row);
    return { i: spec.choices.length - 1 };
  }

  function newSetting(spec, SET, key, second) {
    var s = setOf(SET, key), v = blank(second) ? "" : String(second).trim();
    if (!s) return { error: "Pick the setting." };
    if (v === "") return { error: "Give the second value." };
    if (hasChoice(spec, function (c) { return c.kind === "setting" && c.key === key; })) return { error: s.label + " already has a second choice." };
    if (v.toLowerCase() === firstValue(spec, SET, key).trim().toLowerCase()) return { error: "The second choice is the same as the first." };
    return add(spec, { kind: "setting", key: key, second: v });
  }
  function newRule(spec, ruleId, fallback, instead) {
    var i = blank(ruleId) ? null : ruleIndex(spec, { rule_id: ruleId }), row;
    if (i === null) return { error: "Pick the rule." };
    if (FALLBACKS.indexOf(fallback) < 0) return { error: "Pick Make it Prefer, Instead or Drop it for the second choice." };
    if (hasChoice(spec, function (c) { return c.kind === "rule" && ruleIndex(spec, c) === i; })) return { error: ruleWords(spec, i) + " already has a second choice." };
    row = { kind: "rule", rule_id: ruleId, fallback: fallback };
    if (fallback === "Instead") row.instead = copyRule(instead || spec.rules[i]);
    return add(spec, row);
  }
  function copyRule(r) { var x = JSON.parse(JSON.stringify(r)); delete x._id; return x; }
  /* the Second choice of a rule changed on the list: Instead starts from a copy of the rule when it has no rule of its own yet */
  function setFallback(spec, i, fallback) {
    var c = list(spec, "choices")[i], j;
    if (!c || c.kind !== "rule") return false;
    c.fallback = fallback;
    j = ruleIndex(spec, c);
    if (fallback === "Instead" && !(c.instead || {}).rule && j !== null) c.instead = copyRule(spec.rules[j]);
    return true;
  }
  function newRecess(spec, level, from, to) {
    if (!timeOk(from) || !timeOk(to)) return { error: "Give the window as two times." };
    if (hasChoice(spec, function (c) { return c.kind === "recess" && c.level === level; })) return { error: "Recess for " + level + " already has a second choice." };
    var bad = recessProblem(spec, level, [from, to]);
    if (bad) return { error: bad };
    return add(spec, { kind: "recess", level: level, window: [from, to] });
  }

  function renumber(spec, idx) { idx.forEach(function (i, n) { spec.choices[i].order = n + 1; }); }
  function move(spec, i, dir) {
    var idx = ordered(spec).map(function (x) { return x.i; }), p = idx.indexOf(i), q = p + dir;
    if (p < 0 || q < 0 || q >= idx.length) return false;
    idx[p] = idx[q]; idx[q] = i; renumber(spec, idx);
    return true;
  }
  function moveTo(spec, i, before) {
    var was = ordered(spec).map(function (x) { return x.i; }), idx = was.filter(function (j) { return j !== i; });
    if (was.indexOf(i) < 0 || before === i) return false;
    var p = before === null || before === undefined ? -1 : idx.indexOf(before);
    if (p < 0) idx.push(i); else idx.splice(p, 0, i);
    if (idx.every(function (j, n) { return j === was[n]; })) return false;
    renumber(spec, idx);
    return true;
  }
  function prune(spec) {
    var all = list(spec, "choices"), keep = all.filter(function (c) { return c.kind !== "rule" || ruleIndex(spec, c) !== null; });
    if (Array.isArray(spec.choices)) spec.choices = keep;
    return all.length - keep.length;
  }

  return { ordered: ordered, ruleLabel: ruleLabel, typedNo: typedNo, itemLabel: itemLabel, firstText: firstText, secondText: secondText,
    ruleIndex: ruleIndex, settingValue: settingValue, recessFirst: recessFirst, problems: problems, candidates: candidates,
    newSetting: newSetting, newRule: newRule, newRecess: newRecess, move: move, moveTo: moveTo, prune: prune, setFallback: setFallback };
})();
if (typeof module !== "undefined") module.exports = Choices;

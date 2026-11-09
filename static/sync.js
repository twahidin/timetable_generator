/* The change format: a setup is edited by small operations, so several people
   can work on it at once. Same logic as sync.py; keep the two in step.
   Operations (applied in order):
     ["set", section, id, field, value]            value null removes the field
     ["merge", section, id, field, adds, removes]  list fields merged item by item
     ["add", section, row, after]                  after "" = first, unknown = append
     ["del", section, id]
     ["school", key, value]                        null removes the key
     ["day", level, day, codes]                    null removes the day (and an empty level)
     ["top", key, value]                           any other top-level key */
var Sync = (function () {
  "use strict";
  var LISTS = ["venues", "classes", "subjects", "teachers", "blocks", "lessons",
    "rules", "students", "combinations", "roles"];
  var MERGE = { teachers: ["can_teach"], students: ["groups"] };
  var ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789";
  var RESERVED_TOP = LISTS.concat(["school", "day_structure"]);
  var ARITY = { set: 5, merge: 6, add: 4, del: 3, school: 3, day: 4, top: 3 };
  var STR_ARGS = { set: [1, 2, 3], merge: [1, 2, 3], add: [1], del: [1, 2],
    school: [1], day: [1, 2], top: [1] };

  function clone(x) { return x === undefined ? undefined : JSON.parse(JSON.stringify(x)); }

  function newId() {
    var out = "", i, bytes = null;
    var c = typeof globalThis !== "undefined" ? globalThis.crypto : null;
    if (c && c.getRandomValues) bytes = c.getRandomValues(new Uint8Array(10));
    for (i = 0; i < 10; i++) {
      var n = bytes ? bytes[i] : Math.floor(Math.random() * 256);
      out += ALPHABET.charAt(n % 36);
    }
    return out;
  }

  function canon(x) {
    if (Array.isArray(x)) return "[" + x.map(canon).join(",") + "]";
    if (x && typeof x === "object") {
      return "{" + Object.keys(x).sort().map(function (k) {
        return JSON.stringify(k) + ":" + canon(x[k]);
      }).join(",") + "}";
    }
    return JSON.stringify(x === undefined ? null : x);
  }

  function isObj(x) { return x !== null && typeof x === "object" && !Array.isArray(x); }
  function rowsOf(spec, section) { return Array.isArray(spec[section]) ? spec[section] : []; }
  function get(o, k) { return o[k] === undefined ? null : o[k]; }
  function items(row, key) { return Array.isArray(row[key]) ? row[key] : []; }
  function union(a, b) {
    var seen = {};
    Object.keys(a).concat(Object.keys(b)).forEach(function (k) { seen[k] = true; });
    return Object.keys(seen).sort();
  }
  function find(spec, section, id) {
    var rows = rowsOf(spec, section);
    for (var i = 0; i < rows.length; i++) if (isObj(rows[i]) && rows[i]._id === id) return rows[i];
    return null;
  }

  function ensureIds(spec) {
    var added = false;
    LISTS.forEach(function (section) {
      var rows = rowsOf(spec, section), used = {};
      rows.forEach(function (r) { if (isObj(r) && r._id) used[r._id] = true; });
      rows.forEach(function (r) {
        if (isObj(r) && !r._id) {
          var id = newId();
          while (used[id]) id = newId();
          used[id] = true;
          r._id = id;
          added = true;
        }
      });
    });
    return added;
  }

  function cleanRow(row) {
    var out = {};
    Object.keys(row).forEach(function (k) {
      if (row[k] !== null && row[k] !== undefined && (k === "_id" || k.charAt(0) !== "_")) out[k] = row[k];
    });
    return out;
  }

  function withId(rows) { return rows.filter(function (r) { return isObj(r) && r._id; }); }

  function diff(base, cur) {
    var ops = [];
    LISTS.forEach(function (section) {
      var brows = withId(rowsOf(base, section)), crows = withId(rowsOf(cur, section));
      var bmap = {}, cmap = {};
      brows.forEach(function (r) { bmap[r._id] = r; });
      crows.forEach(function (r) { cmap[r._id] = r; });
      brows.forEach(function (r) { if (!cmap[r._id]) ops.push(["del", section, r._id]); });
      var prev = "";
      crows.forEach(function (r) {
        if (!bmap[r._id]) ops.push(["add", section, cleanRow(r), prev]);
        prev = r._id;
      });
      var merged = MERGE[section] || [];
      crows.forEach(function (r) {
        var b = bmap[r._id];
        if (!b) return;
        var fields = union(r, b).filter(function (k) { return k.charAt(0) !== "_"; });
        fields.forEach(function (f) {
          if (merged.indexOf(f) >= 0) {
            var bi = items(b, f), ci = items(r, f), bk = {}, ck = {};
            bi.forEach(function (i) { bk[canon(i)] = true; });
            ci.forEach(function (i) { ck[canon(i)] = true; });
            var adds = ci.filter(function (i) { return !bk[canon(i)]; });
            var removes = bi.filter(function (i) { return !ck[canon(i)]; });
            if (adds.length || removes.length) ops.push(["merge", section, r._id, f, adds, removes]);
          } else if (canon(get(b, f)) !== canon(get(r, f))) {
            ops.push(["set", section, r._id, f, get(r, f)]);
          }
        });
      });
    });
    var bs = base.school || {}, cs = cur.school || {};
    union(bs, cs).forEach(function (k) {
      if (canon(get(bs, k)) !== canon(get(cs, k))) ops.push(["school", k, get(cs, k)]);
    });
    var bd = base.day_structure || {}, cd = cur.day_structure || {};
    union(bd, cd).forEach(function (level) {
      var bl = bd[level] || {}, cl = cd[level] || {};
      union(bl, cl).forEach(function (day) {
        if (canon(get(bl, day)) !== canon(get(cl, day))) ops.push(["day", level, day, get(cl, day)]);
      });
    });
    union(base, cur).forEach(function (k) {
      if (RESERVED_TOP.indexOf(k) >= 0 || k.charAt(0) === "_") return;
      if (canon(get(base, k)) !== canon(get(cur, k))) ops.push(["top", k, get(cur, k)]);
    });
    return ops;
  }

  function applyOne(spec, op) {
    var name = op[0], i;
    if (["set", "merge", "add", "del"].indexOf(name) >= 0 && LISTS.indexOf(op[1]) < 0) return false;
    if (name === "set") {
      var row = find(spec, op[1], op[2]);
      if (!row || op[3].charAt(0) === "_") return false;
      if (op[4] === null || op[4] === undefined) delete row[op[3]];
      else row[op[3]] = clone(op[4]);
    } else if (name === "merge") {
      var mrow = find(spec, op[1], op[2]);
      if (!mrow || op[3].charAt(0) === "_") return false;
      var gone = {}, have = {};
      op[5].forEach(function (x) { gone[canon(x)] = true; });
      var list = items(mrow, op[3]).filter(function (x) { return !gone[canon(x)]; });
      list.forEach(function (x) { have[canon(x)] = true; });
      op[4].forEach(function (x) {
        if (!have[canon(x)]) { have[canon(x)] = true; list.push(clone(x)); }
      });
      mrow[op[3]] = list;
    } else if (name === "add") {
      var nrow = op[2];
      if (!isObj(nrow) || !nrow._id || find(spec, op[1], nrow._id)) return false;
      if (!Array.isArray(spec[op[1]])) spec[op[1]] = [];
      var rows = spec[op[1]], pos = rows.length;
      if (op[3] === "") pos = 0;
      else for (i = 0; i < rows.length; i++) {
        if (isObj(rows[i]) && rows[i]._id === op[3]) { pos = i + 1; break; }
      }
      rows.splice(pos, 0, clone(nrow));
    } else if (name === "del") {
      var drow = find(spec, op[1], op[2]);
      if (!drow) return false;
      spec[op[1]] = spec[op[1]].filter(function (r) { return r !== drow; });
    } else if (name === "school") {
      if (!isObj(spec.school)) spec.school = {};
      if (op[2] === null || op[2] === undefined) delete spec.school[op[1]];
      else spec.school[op[1]] = clone(op[2]);
    } else if (name === "day") {
      if (!isObj(spec.day_structure)) spec.day_structure = {};
      var days = spec.day_structure;
      if (op[3] === null || op[3] === undefined) {
        if (isObj(days[op[1]])) {
          delete days[op[1]][op[2]];
          if (!Object.keys(days[op[1]]).length) delete days[op[1]];
        }
      } else {
        if (!isObj(days[op[1]])) days[op[1]] = {};
        days[op[1]][op[2]] = op[3];
      }
    } else { // top
      if (RESERVED_TOP.indexOf(op[1]) >= 0 || op[1].charAt(0) === "_") return false;
      if (op[2] === null || op[2] === undefined) delete spec[op[1]];
      else spec[op[1]] = clone(op[2]);
    }
    return true;
  }

  // Applies ops to spec in place; returns how many were skipped.
  function apply(spec, ops) {
    var skipped = 0;
    ops.forEach(function (op) {
      var ok = Array.isArray(op) && ARITY[op[0]] === op.length &&
        STR_ARGS[op[0]].every(function (i) { return typeof op[i] === "string"; }) &&
        (op[0] !== "merge" || (Array.isArray(op[4]) && Array.isArray(op[5])));
      if (!ok || !applyOne(spec, op)) skipped++;
    });
    return skipped;
  }

  // base: last confirmed copy; sent: copy the diff was taken from; now: working copy when the
  // answer came back; theirs: others' operations applied first; ours: the operations just accepted.
  function rebase(base, sent, now, theirs, ours) {
    var nb = clone(base);
    apply(nb, theirs);
    apply(nb, ours);
    var spec = clone(nb);
    apply(spec, diff(sent, now));
    return { base: nb, spec: spec };
  }

  return { LISTS: LISTS, MERGE: MERGE, newId: newId, ensureIds: ensureIds, diff: diff,
    apply: apply, clone: clone, rebase: rebase };
})();
if (typeof module !== "undefined") module.exports = Sync;

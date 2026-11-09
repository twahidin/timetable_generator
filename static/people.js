/* People: pure helpers for the teacher list. No document, no window, no
   randomness: functions over strings and plain objects, so Node can test them.
   Avatars: a small flat cartoon face drawn from a name alone. Every part comes
   from the name's hash (and an optional "look" number), never from a guess about
   the person. */
var People = (function () {
  "use strict";

  function key(name) {
    return String(name == null ? "" : name).trim().toLowerCase().replace(/\s+/g, " ");
  }

  // 32-bit FNV-1a, unsigned.
  function hash(text) {
    var h = 2166136261;
    var s = String(text);
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h >>> 0;
  }

  // Final mix so neighbouring names do not land on neighbouring parts.
  function mix(h) {
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b) >>> 0;
    h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35) >>> 0;
    h ^= h >>> 16;
    return h >>> 0;
  }

  var FRINGE = "M9 15 C9 8 13 5.5 18 5.5 C23 5.5 27 8 27 15 C24 12 21 10.5 18 10.5 C15 10.5 12 12 9 15 Z";
  var HAIR = [
    { back: "", front: "" },
    { back: "", front: FRINGE },
    { back: "", front: "M9 15 C8.5 7 14 4.5 19 5.5 C24 6 27.5 9 27 15 C25 11 21 10 15 11.5 C12 12.3 10 13.5 9 15 Z" },
    { back: "M7 31 C5 18 7 5 18 5 C29 5 31 18 29 31 Z", front: FRINGE },
    { back: '<circle cx="18" cy="4.5" r="3.5"/>', front: FRINGE },
    { back: '<circle cx="10" cy="11" r="4"/><circle cx="14" cy="7.5" r="4"/><circle cx="18" cy="6.5" r="4"/>' +
      '<circle cx="22" cy="7.5" r="4"/><circle cx="26" cy="11" r="4"/>', front: "" },
    { back: "", front: "M9 14 L9 7 L13 10 L15 4.5 L18 9 L21 4.5 L23 10 L27 7 L27 14 C24 11.5 21 10.5 18 10.5 C15 10.5 12 11.5 9 14 Z" },
    { back: "M7 22 C6 8 11 5 18 5 C25 5 30 8 29 22 Z", front: FRINGE },
    { back: "M25 8 C32 8 33 18 30 24 C29 18 27 14 25 12 Z", front: FRINGE },
    { back: "", front: "M9.5 13.5 C10 8.5 13 6.5 18 6.5 C23 6.5 26 8.5 26.5 13.5 C24 10.5 21 9.5 18 9.5 C15 9.5 12 10.5 9.5 13.5 Z" }
  ];

  var AVATAR = {
    bg: ["#f4b6a6", "#f6d28b", "#bfdc9f", "#9fd8c9", "#9cc9ee", "#b9b6f0", "#e3b0e0", "#f2a9c0",
      "#f0c27a", "#a8d8a0", "#8fd0e0", "#c9c0e8"],
    skin: ["#f9dcc4", "#f1c9a0", "#e0ac7e", "#c68b5b", "#a06a42", "#7a4a2d"],
    hair: HAIR,
    hairColor: ["#2b2118", "#5a3825", "#8a5a2b", "#c99a4b", "#a33b2a", "#8d8d96"],
    glasses: ["none", "round", "square"],
    mouth: ["smile", "grin", "small"],
    top: ["#3b6fb6", "#d1495b", "#2f9e77", "#edae49", "#7b5ea7", "#4a4e69"]
  };
  var ORDER = ["bg", "skin", "hair", "hairColor", "glasses", "mouth", "top"];
  var AVATAR_COMBOS = ORDER.reduce(function (n, k) { return n * AVATAR[k].length; }, 1);

  function avatarParts(name, seed) {
    var text = key(name) + "|" + (seed || 0);
    var a = mix(hash(text)), b = mix(hash(text + "#"));
    var parts = {};
    // Decode each hash as mixed-radix digits: a feeds the first four parts, b the rest.
    [[a, ORDER.slice(0, 4)], [b, ORDER.slice(4)]].forEach(function (g) {
      var v = g[0];
      g[1].forEach(function (k) {
        var len = AVATAR[k].length;
        parts[k] = v % len;
        v = Math.floor(v / len);
      });
    });
    return parts;
  }

  function avatar(name, seed, size) {
    var px = Number(size);
    if (!(px > 0)) px = 32;
    var head = '<svg width="' + px + '" height="' + px + '" viewBox="0 0 36 36" aria-hidden="true">';
    if (!key(name)) return head + '<circle cx="18" cy="18" r="18" fill="#d5d8de"/></svg>';
    var p = avatarParts(name, seed);
    var skin = AVATAR.skin[p.skin], ink = "#2b2b2b", hc = AVATAR.hairColor[p.hairColor];
    var hair = HAIR[p.hair];
    var s = head + '<circle cx="18" cy="18" r="18" fill="' + AVATAR.bg[p.bg] + '"/><g>';
    s += '<path d="M4.6 30 C8 27 13 26 18 26 C23 26 28 27 31.4 30 A18 18 0 0 1 4.6 30 Z" fill="' + AVATAR.top[p.top] + '"/>';
    s += '<rect x="15.5" y="22" width="5" height="5" fill="' + skin + '"/>';
    s += '<g fill="' + hc + '">' + (hair.back ? (hair.back.charAt(0) === "<" ? hair.back : '<path d="' + hair.back + '"/>') : "") + "</g>";
    s += '<circle cx="18" cy="16" r="9" fill="' + skin + '"/>';
    if (hair.front) s += '<path d="' + hair.front + '" fill="' + hc + '"/>';
    s += '<circle cx="14.5" cy="16.5" r="1.1" fill="' + ink + '"/><circle cx="21.5" cy="16.5" r="1.1" fill="' + ink + '"/>';
    if (p.mouth === 0) s += '<path d="M14.5 20.5 Q18 23.5 21.5 20.5" fill="none" stroke="' + ink + '" stroke-width="1.2" stroke-linecap="round"/>';
    else if (p.mouth === 1) s += '<path d="M14.5 20 Q18 25 21.5 20 Z" fill="' + ink + '"/>';
    else s += '<path d="M16 21 Q18 22.3 20 21" fill="none" stroke="' + ink + '" stroke-width="1.2" stroke-linecap="round"/>';
    if (p.glasses === 1)
      s += '<g fill="none" stroke="' + ink + '" stroke-width="0.9"><circle cx="14.5" cy="16.5" r="2.9"/><circle cx="21.5" cy="16.5" r="2.9"/><path d="M17.4 16.5 H18.6"/></g>';
    else if (p.glasses === 2)
      s += '<g fill="none" stroke="' + ink + '" stroke-width="0.9"><rect x="11.6" y="13.9" width="5.8" height="5.2" rx="1"/><rect x="18.6" y="13.9" width="5.8" height="5.2" rx="1"/><path d="M17.4 16.5 H18.6"/></g>';
    return s + "</g></svg>";
  }

  // ---- Reading a teacher list ----

  var FIELDS = ["name", "short", "dept", "role", "allowance", "other_duties", "note"];
  var HEADERS = {
    name: ["name", "teacher", "teacher name", "full name", "staff name", "name of teacher",
      "teacher s name", "teachers name", "staff"],
    short: ["short", "short name", "initials", "abbreviation"],
    dept: ["department", "dept"],
    role: ["role", "appointment"],
    allowance: ["allowance", "allowance periods", "periods"],
    other_duties: ["other duties", "duties"],
    note: ["note", "notes", "remarks"]
  };
  var NUMERIC = { allowance: true, other_duties: true };

  function headerField(cell) {
    var w = String(cell).toLowerCase().replace(/\([^)]*\)|\[[^\]]*\]/g, " ")
      .replace(/[^a-z0-9]+/g, " ").trim();
    for (var i = 0; i < FIELDS.length; i++)
      if (HEADERS[FIELDS[i]].indexOf(w) >= 0) return FIELDS[i];
    return null;
  }

  function splitCsv(line) {
    var cells = [], cur = "", q = false;
    for (var i = 0; i < line.length; i++) {
      var c = line.charAt(i);
      if (q) {
        if (c === '"') { if (line.charAt(i + 1) === '"') { cur += '"'; i++; } else q = false; }
        else cur += c;
      } else if (c === '"' && cur.trim() === "") { q = true; cur = ""; }
      else if (c === ",") { cells.push(cur); cur = ""; }
      else cur += c;
    }
    cells.push(cur);
    return cells;
  }

  function readTeachers(text) {
    var rows = [];   // non-empty rows, each remembering its line number in the paste
    String(text == null ? "" : text).split(/\r?\n/).forEach(function (line, li) {
      var cells = (line.indexOf("\t") >= 0 ? line.split("\t") : splitCsv(line)).map(function (c) { return c.trim(); });
      if (cells.some(function (c) { return c !== ""; })) { cells.line = li + 1; rows.push(cells); }
    });
    if (!rows.length) return { error: "No teachers found in that list. It needs a column of names." };

    var map = null, start = 0, skipped = [], otherHeader = false;   // map: field -> column index
    for (var r = 0; r < Math.min(10, rows.length) && !map; r++) {
      var found = {}, hasName = false;
      rows[r].forEach(function (cell, ci) {
        var f = headerField(cell);
        if (f && !(f in found)) { found[f] = ci; if (f === "name") hasName = true; }
      });
      if (hasName) { map = found; start = r + 1; }
      else if (Object.keys(found).length) otherHeader = true;
    }
    if (!map && otherHeader) return { error: "Could not find the column of names. Head it Name or Teacher." };
    if (!map) {
      var width = rows[0].length;
      while (width > 1 && rows[0][width - 1] === "") width--;
      map = {};
      FIELDS.slice(0, width).forEach(function (f, i) { map[f] = i; });
      if (width > 1) skipped.push("No header row was found, so the columns were read in this order: " +
        "Name, Short name, Department, Role, Allowance, Other duties, Note.");
    }
    var columns = FIELDS.filter(function (f) { return f in map; });
    var teachers = [], seen = Object.create(null);
    rows.slice(start).forEach(function (cells) {
      var name = (cells[map.name] || "").trim();
      if (!name) { skipped.push("A row with no name was left out (row " + cells.line + ")."); return; }
      var k = key(name);
      if (seen[k]) { skipped.push(name + " is in the list twice: the second row was left out."); return; }
      seen[k] = true;
      var t = {};
      columns.forEach(function (f) {
        var v = (cells[map[f]] || "").trim();
        if (v === "") return;
        if (NUMERIC[f]) {
          if (/^-?\d+(\.\d+)?$/.test(v)) t[f] = Number(v);
          else skipped.push(name + ": \"" + v + "\" is not a number, so " + f.replace("_", " ") + " was left out.");
        } else t[f] = v;
      });
      teachers.push(t);
    });
    if (!teachers.length) return { error: "No teachers found in that list. It needs a column of names." };
    return { teachers: teachers, columns: columns, skipped: skipped };
  }

  // ---- Matching a list to the teachers already in the setup ----

  function planTeachers(existing, incoming, roles, departments) {
    var byKey = Object.create(null);
    existing.forEach(function (t, i) { var k = key(t.name); if (!(k in byKey)) byKey[k] = i; });
    var plan = { add: [], update: [], missing: [], unknownRoles: [], unknownDepts: [] };
    var inFile = Object.create(null), roleNames = (roles || []).map(function (r) { return r.role; });
    function note(list, v) { if (v && list.indexOf(v) < 0) list.push(v); }

    incoming.forEach(function (row) {
      var k = key(row.name);
      if (!k || inFile[k]) return;
      inFile[k] = true;
      if (row.role && roleNames.indexOf(row.role) < 0) note(plan.unknownRoles, row.role);
      if (row.dept && (departments || []).indexOf(row.dept) < 0) note(plan.unknownDepts, row.dept);
      if (k in byKey) {
        var cur = existing[byKey[k]], changes = {}, any = false;
        FIELDS.forEach(function (f) {
          if (f === "name" || !(f in row) || row[f] === cur[f]) return;
          changes[f] = row[f]; any = true;
        });
        if (any) plan.update.push({ i: byKey[k], changes: changes });
        return;
      }
      var t = {};
      FIELDS.forEach(function (f) { if (f in row) t[f] = row[f]; });
      if (!t.short) t.short = String(t.name).trim().split(/\s+/)[0].replace(/[,;:.]+$/, "");
      if (t.allowance === undefined) {
        var guide = (roles || []).filter(function (r) { return r.role === t.role; })[0];
        if (guide && typeof guide.allowance === "number") t.allowance = guide.allowance;
      }
      t.can_teach = [];
      t.provisional = "No";
      plan.add.push(t);
    });
    existing.forEach(function (t, i) { if (!inFile[key(t.name)]) plan.missing.push(i); });
    return plan;
  }

  return { key: key, hash: hash, AVATAR: AVATAR, AVATAR_COMBOS: AVATAR_COMBOS,
    avatarParts: avatarParts, avatar: avatar, FIELDS: FIELDS,
    readTeachers: readTeachers, planTeachers: planTeachers };
})();
if (typeof module !== "undefined") module.exports = People;

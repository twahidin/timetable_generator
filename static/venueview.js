/* The Blocks view of step 1 (Venues): the rooms drawn by block and floor.
   Plain functions over the setup, no page access, so they run under Node (tests/venueview.test.js).
   A block or a floor is not stored: it exists because a room names it. */
var VenueView = (function () {
  "use strict";

  function rows(spec, k) { return spec && Array.isArray(spec[k]) ? spec[k] : []; }
  function text(v) { return v == null ? "" : String(v).trim(); }
  function strings(v) { return Array.isArray(v) ? v.map(function (x) { return String(x); }) : []; }
  function isNumber(s) { return /^-?\d+(\.\d+)?$/.test(s); }

  /* natural order: numbers inside a name count as numbers, letter case ignored; a plain comparison breaks a tie
     so the order is the same on every machine */
  function cmp(a, b) {
    var c = a.localeCompare(b, "en", { numeric: true, sensitivity: "base" });
    if (c) return c;
    return a < b ? -1 : a > b ? 1 : 0;
  }

  function capacityOf(v) {
    if (typeof v === "number") return isFinite(v) ? v : null;
    if (typeof v === "string" && v.trim() !== "") { var n = Number(v); return isFinite(n) ? n : null; }
    return null;
  }

  function blocks(spec) {
    var homes = Object.create(null), byBlock = Object.create(null), list = [];
    rows(spec, "classes").forEach(function (c) {
      if (!c || !c["class"] || !c.home_room) return;
      (homes[c.home_room] || (homes[c.home_room] = [])).push(c["class"]);
    });
    var P = parts(spec);
    rows(spec, "venues").forEach(function (v, vi) {
      if (!v || typeof v !== "object") return;
      var combo = isCombined(v, P), name = text(v.building), floor = text(v.floor), b = byBlock[name], f;
      if (!b) { b = byBlock[name] = { block: name, rooms: 0, seats: 0, floors: [], by: Object.create(null) }; list.push(b); }
      f = b.by[floor];
      if (!f) { f = b.by[floor] = { floor: floor, rooms: [] }; b.floors.push(f); }
      var room = v.room == null ? "" : String(v.room), cap = capacityOf(v.capacity);
      f.rooms.push({ vi: vi, room: room, kind: v.kind ? String(v.kind) : "", capacity: cap, home: room ? (homes[room] || []).slice() : [],
        only_for: strings(v.only_for), equipment: strings(v.equipment), configuration: v.configuration == null ? "" : String(v.configuration),
        note: v.note == null ? "" : String(v.note), made_of: combo ? P[cleanName(v.room)].slice() : [] });
      if (combo) return;   // a combined venue adds no room and no seats: its rooms are counted already
      b.rooms++; if (cap != null) b.seats += cap;
    });
    list.sort(function (a, b) { return a.block === "" ? (b.block === "" ? 0 : 1) : b.block === "" ? -1 : cmp(a.block, b.block); });
    list.forEach(function (b) {
      b.floors.sort(function (x, y) {
        if (x.floor === "" || y.floor === "") return x.floor === y.floor ? 0 : x.floor === "" ? 1 : -1;
        var nx = isNumber(x.floor), ny = isNumber(y.floor);
        if (nx && ny) return Number(y.floor) - Number(x.floor) || cmp(x.floor, y.floor);
        if (nx !== ny) return nx ? -1 : 1;
        return cmp(x.floor, y.floor);
      });
      b.floors.forEach(function (f) {
        f.rooms.sort(function (x, y) { return (x.made_of.length ? 1 : 0) - (y.made_of.length ? 1 : 0) || cmp(x.room, y.room) || x.vi - y.vi; });   // combined venues last
      });
      delete b.by;
    });
    return list;
  }

  function kinds(spec) {
    var out = [], seen = Object.create(null);
    function add(k) { if (k == null || String(k) === "" || seen[k]) return; seen[k] = true; out.push(String(k)); }
    var own = spec && spec.school && spec.school.room_kinds;
    (Array.isArray(own) ? own : []).forEach(add);
    rows(spec, "venues").forEach(function (v) { if (v && typeof v === "object") add(v.kind); });
    return out;
  }

  /* one more, done on the digits as text so a long number never loses its last places; 09 gives 10, 99 gives 100 */
  function plusOne(d) {
    var a = d.split(""), i = a.length - 1;
    while (i >= 0 && a[i] === "9") { a[i] = "0"; i--; }
    if (i < 0) return "1" + a.join("");
    a[i] = String(Number(a[i]) + 1);
    return a.join("");
  }

  /* the room about to be added on a floor: the floor's last room's kind and capacity, and its name one higher */
  function nextRoom(spec, block, floor) {
    var b = text(block), f = text(floor), found = null, last = null;
    blocks(spec).forEach(function (x) { if (x.block === b) found = x; });
    if (found) found.floors.forEach(function (x) { if (x.floor === f && x.rooms.length) last = x.rooms[x.rooms.length - 1]; });
    if (!last) return { room: "", kind: kinds(spec)[0] || "classroom", capacity: null };
    var used = Object.create(null), room = "", m = /^(.*?)(\d+)$/.exec(last.room.trim()), tries = 0;
    rows(spec, "venues").forEach(function (v) { if (v && v.room) used[String(v.room).trim().toLowerCase()] = true; });
    if (m) {
      var digits = m[2];
      do {
        if (tries++ >= 1000) { room = ""; break; }
        digits = plusOne(digits); room = m[1] + digits;
      } while (used[room.trim().toLowerCase()]);
    }
    return { room: room, kind: last.kind, capacity: last.capacity };
  }

  /* the floor a new one goes above: the block's highest number floor plus one */
  function nextFloor(spec, block) {
    var b = text(block), top = null;
    blocks(spec).forEach(function (x) {
      if (x.block !== b) return;
      x.floors.forEach(function (f) { if (isNumber(f.floor) && (top === null || Number(f.floor) > top)) top = Number(f.floor); });
    });
    return top === null ? "1" : String(Math.floor(top) + 1);
  }

  /* the named blocks and each one's named floors, in the view's order: what a room can be moved to -> [{block, floors}] */
  function places(spec) {
    return blocks(spec).filter(function (b) { return b.block !== ""; }).map(function (b) {
      return { block: b.block, floors: b.floors.map(function (f) { return f.floor; }).filter(function (f) { return f !== ""; }) };
    });
  }
  /* the rooms at these indexes go to the block and the floor (either may be empty: no block yet, no floor yet); nothing else
     of a room changes -> how many rooms changed place */
  function move(spec, vis, block, floor) {
    var V = rows(spec, "venues"), b = text(block), f = text(floor), n = 0;
    (Array.isArray(vis) ? vis : []).forEach(function (vi) {
      var v = V[vi];
      if (!v || typeof v !== "object") return;
      if (text(v.building) === b && text(v.floor) === f) return;
      if (b === "") delete v.building; else v.building = b;
      if (f === "") delete v.floor; else v.floor = f;
      n++;
    });
    return n;
  }

  /* the names the Add rooms bar makes: the prefix and each number from a to b, two digits at least ("B1-01"), without the
     names a room has already (in any letters) -> {names, skipped}, or {error: sentence} */
  function newRooms(spec, prefix, a, b) {
    var pre = String(prefix == null ? "" : prefix).replace(/^\s+/, ""), sa = text(a), sb = text(b);
    if (!/^\d+$/.test(sa) || !/^\d+$/.test(sb)) return { error: "Give From and To as whole numbers." };
    var from = Number(sa), to = Number(sb), have = Object.create(null), names = [], skipped = 0;
    if (from > to) return { error: "From is after To." };
    if (to - from + 1 > 200) return { error: "That is " + (to - from + 1) + " rooms at once. Add at most 200 at a time." };
    rows(spec, "venues").forEach(function (v) { if (v && v.room != null) have[text(v.room).toLowerCase()] = true; });
    for (var i = from; i <= to; i++) {
      var name = pre + (i < 10 ? "0" + i : String(i)), key = name.trim().toLowerCase();
      if (have[key]) { skipped++; continue; }
      have[key] = true; names.push(name);
    }
    return { names: names, skipped: skipped };
  }

  /* ---- combined venues: one venue made of two or more rooms (a row's made_of). The same rules as ttgen/spec.py:
     clean_name, venue_parts and venue_problems, so the page and the server say the same thing */

  /* a name as typed, with runs of spaces made one and the ends trimmed */
  function cleanName(s) { return String(s == null ? "" : s).split(/\s+/).filter(function (x) { return x !== ""; }).join(" "); }
  function isObj(v) { return !!v && typeof v === "object" && !Array.isArray(v); }
  /* the distinct cleaned room names a row is made of, in the order listed */
  function madeOf(v) {
    var out = [];
    (isObj(v) && Array.isArray(v.made_of) ? v.made_of : []).forEach(function (x) { x = cleanName(x); if (x && out.indexOf(x) < 0) out.push(x); });
    return out;
  }
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  /* {combined venue: its rooms} for each sound one: at least two distinct rooms, each another row's room, none a combined
     venue itself; any other row is an ordinary room. A name on two rows: the last row's made_of counts (as venue_parts) */
  function parts(spec) {
    var made = Object.create(null), out = {};
    rows(spec, "venues").forEach(function (v) { if (!isObj(v)) return; var n = cleanName(v.room); if (n) made[n] = madeOf(v); });
    Object.keys(made).forEach(function (name) {
      var rs = made[name];
      if (rs.length >= 2 && rs.every(function (r) { return r !== name && has(made, r) && !made[r].length; })) out[name] = rs;
    });
    return out;
  }
  function isCombined(v, P) { var n = cleanName(v.room); return has(P, n) && madeOf(v).length >= 2; }
  /* a number as Python's int() reads it: 20, " 20 ", "+20" and 20.9 are 20; "20.0", text and blank are none (null) */
  function pyInt(x) {
    if (typeof x === "boolean") return x ? 1 : 0;
    if (typeof x === "number") return isFinite(x) ? Math.trunc(x) : null;
    if (typeof x !== "string") return null;
    var s = x.trim(); if (!/^[+-]?\d+(_\d+)*$/.test(s)) return null;
    return Number(s.replace(/_/g, ""));
  }
  function kindOf(v) { return v && v.kind ? String(v.kind) : "classroom"; }
  /* the "At most N at once" Must rules on this room that let it take more than one group -> [N, ...] */
  function manyAtOnce(spec, name) {
    var out = [];
    rows(spec, "rules").forEach(function (ru) {
      if (!isObj(ru) || ru.scope !== "Room" || cleanName(ru.target) !== name || ru.rule !== "At most N at once" || String(ru.strength || "Must") !== "Must") return;
      var k = pyInt(ru.number); if (k != null && k > 1) out.push(k);
    });
    return out;
  }
  /* what is wrong with the combined venues on step 1 -> [{vi, text, hard}], in venue_problems' order and words */
  function problems(spec) {
    var V = rows(spec, "venues"), row = Object.create(null), made = Object.create(null), claimed = Object.create(null), out = [];
    V.forEach(function (v) { if (!isObj(v)) return; var n = cleanName(v.room); if (!has(row, n)) row[n] = v; });
    Object.keys(row).forEach(function (n) { made[n] = madeOf(row[n]); });
    function seats(x) { return pyInt(x.capacity); }
    V.forEach(function (v, i) {
      if (!isObj(v)) return;
      var name = cleanName(v.room), rs = madeOf(v), say = function (t, hard) { out.push({ vi: i, text: t, hard: hard }); };
      if (!rs.length) return;
      if (rs.length < 2) say(name + ": a combined venue needs at least two rooms.", true);
      rs.forEach(function (r) {
        if (!has(row, r)) say(name + ": made of " + r + ", which is not on step 1 (Venues).", true);
        else if (made[r].length) say(name + ": made of " + r + ", which is a combined venue itself.", true);
      });
      rs.forEach(function (r) {
        if (has(claimed, r) && claimed[r].indexOf(name) < 0)
          say(r + " is in more than one combined venue (" + claimed[r].concat([name]).join(", ") + "): a room can be in one only.", true);
        if (!has(claimed, r)) claimed[r] = [];
        if (claimed[r].indexOf(name) < 0) claimed[r].push(name);
      });
      var found = rs.filter(function (r) { return has(row, r); }), ks = [kindOf(v)];
      found.forEach(function (r) { var k = kindOf(row[r]); if (ks.indexOf(k) < 0) ks.push(k); });
      ks = ks.filter(function (k, j) { return ks.indexOf(k) === j; }).sort(function (a, b) { return a < b ? -1 : a > b ? 1 : 0; });
      if (ks.length > 1) say(name + ": it and its rooms are of different kinds (" + ks.join(", ") + "); they must all be one kind.", true);
      rs.concat([name]).forEach(function (r) {
        manyAtOnce(spec, r).forEach(function (k) { say(name + ": " + r + " takes " + k + ' groups at once (an "At most N at once" rule); a combined venue and its rooms take one group at a time.', true); });
      });
      var mine = seats(v);
      if (!mine) say(name + ": give its seats (seats decide which groups get it).", false);
      else if (found.length === rs.length && found.every(function (r) { return !!seats(row[r]); })) {
        var total = found.reduce(function (a, r) { return a + seats(row[r]); }, 0);
        if (mine > total * 1.1) say(name + ": " + mine + " seats, but its rooms seat " + total + " together.", false);
      }
    });
    return out;
  }
  function ticked(spec, vis) {   // the rows at these indexes, each once, in the order given
    var V = rows(spec, "venues"), seen = Object.create(null), out = [];
    (Array.isArray(vis) ? vis : []).forEach(function (vi) { if (isObj(V[vi]) && !seen[vi]) { seen[vi] = true; out.push(V[vi]); } });
    return out;
  }
  /* can the rooms at these indexes be combined into one venue? -> {ok, why}: why is a sentence for the bar */
  function canCombine(spec, vis) {
    var T = ticked(spec, vis), V = rows(spec, "venues"), no = function (why) { return { ok: false, why: why }; }, i, j;
    if (T.length < 2) return no("Tick two or more rooms to combine them.");
    for (i = 0; i < T.length; i++) if (!cleanName(T[i].room)) return no("Give each ticked room a name first.");
    var names = T.map(function (v) { return cleanName(v.room); }).filter(function (n, k, a) { return a.indexOf(n) === k; });
    if (names.length < 2) return no("Tick two or more rooms to combine them.");
    for (i = 0; i < T.length; i++) {
      var n = cleanName(T[i].room);
      if (madeOf(T[i]).length) return no(n + " is a combined venue already.");
      for (j = 0; j < V.length; j++) if (isObj(V[j]) && madeOf(V[j]).indexOf(n) >= 0) return no(n + " is already in " + cleanName(V[j].room) + ".");
    }
    if (T.some(function (v) { return kindOf(v) !== kindOf(T[0]); })) return no("Rooms of different kinds cannot be combined.");
    for (i = 0; i < names.length; i++) { var k = manyAtOnce(spec, names[i]); if (k.length) return no(names[i] + " takes " + k[0] + " groups at once, so it cannot be combined."); }
    return { ok: true, why: "" };
  }
  /* a name for the combined venue: "Lab 1&2" when the names differ only in an ending of digits or of one letter, else "A + B" */
  function suggestName(names) {
    var N = (Array.isArray(names) ? names : []).map(cleanName);
    if (!N.length) return "";
    function shared(re) {
      var pre = null, ends = [];
      for (var i = 0; i < N.length; i++) {
        var m = re.exec(N[i]); if (!m || (pre !== null && m[1] !== pre)) return null;
        pre = m[1]; ends.push(m[2]);
      }
      return N.length > 1 ? pre + ends.join("&") : null;
    }
    return shared(/^(.*?)(\d+)$/) || shared(/^(.*?)([A-Za-z])$/) || N.join(" + ");
  }
  function newId(V) {   // a row id as Sync makes them (Sync.ensureIds would give one at the next save; given now so the page can hold the row open)
    var S = typeof Sync !== "undefined" ? Sync : typeof require === "function" ? require("./sync.js") : null;
    if (!S || !S.newId) return null;
    var used = Object.create(null), id; V.forEach(function (v) { if (isObj(v) && v._id) used[v._id] = true; });
    do { id = S.newId(); } while (used[id]);
    return id;
  }
  /* the rooms at these indexes made into one new venue row: the first room's kind, block and floor, the seats added up
     (none when a room has none), a suggested name not used yet -> the new row's index */
  function combine(spec, vis) {
    var T = ticked(spec, vis), V = spec.venues, first = T[0] || {}, cap = 0;
    var names = T.map(function (v) { return cleanName(v.room); }).filter(function (n, k, a) { return n && a.indexOf(n) === k; });
    T.forEach(function (v) { var c = capacityOf(v.capacity); cap = cap === null || c === null ? null : cap + c; });
    var taken = Object.create(null); V.forEach(function (v) { if (isObj(v)) taken[cleanName(v.room).toLowerCase()] = true; });
    var base = suggestName(names), room = base, k = 2;
    while (taken[room.toLowerCase()]) room = base + " (" + k++ + ")";
    var row = {}, id = newId(V);
    if (id) row._id = id;
    row.room = room; row.kind = first.kind || "classroom"; row.capacity = cap;
    if (text(first.building) !== "") row.building = text(first.building);
    if (text(first.floor) !== "") row.floor = first.floor;
    row.made_of = names;
    V.push(row);
    return V.length - 1;
  }
  /* each sound combined venue takes its rooms' kind when they all share one (no kind is "classroom", as venue_problems
     compares them); rooms of different kinds leave it alone, for Things to fix -> how many venues changed */
  function syncKinds(spec) {
    var P = parts(spec), row = Object.create(null), c = 0;
    rows(spec, "venues").forEach(function (v) { if (!isObj(v)) return; var n = cleanName(v.room); if (!has(row, n)) row[n] = v; });
    rows(spec, "venues").forEach(function (v) {
      if (!isObj(v) || !isCombined(v, P)) return;
      var ks = P[cleanName(v.room)].map(function (r) { return kindOf(row[r]); });
      if (ks.some(function (k) { return k !== ks[0]; }) || kindOf(v) === ks[0]) return;
      v.kind = ks[0]; c++;
    });
    return c;
  }
  /* the kind a combined venue's rooms share, or null when they differ (for the card and the table) */
  function roomsKind(spec, vi) {
    var V = rows(spec, "venues"), v = V[vi], P = parts(spec), row = Object.create(null);
    if (!isObj(v) || !isCombined(v, P)) return null;
    V.forEach(function (x) { if (!isObj(x)) return; var n = cleanName(x.room); if (!has(row, n)) row[n] = x; });
    var ks = P[cleanName(v.room)].map(function (r) { return kindOf(row[r]); });
    return ks.every(function (k) { return k === ks[0]; }) ? ks[0] : null;
  }
  /* a room renamed: every venue made of it names it the new way -> how many venues changed */
  function renameRoom(spec, was, now) {
    var w = cleanName(was), n = cleanName(now), c = 0;
    if (!w || !n || w === n) return 0;
    rows(spec, "venues").forEach(function (v) {
      if (!isObj(v) || !Array.isArray(v.made_of) || !v.made_of.some(function (x) { return cleanName(x) === w; })) return;
      v.made_of = v.made_of.map(function (x) { return cleanName(x) === w ? n : x; }); c++;
    });
    return c;
  }
  /* a room deleted: it leaves every venue made of it -> how many venues changed */
  function dropRoom(spec, name) {
    var w = cleanName(name), c = 0;
    if (!w) return 0;
    rows(spec, "venues").forEach(function (v) {
      if (!isObj(v) || !Array.isArray(v.made_of) || !v.made_of.some(function (x) { return cleanName(x) === w; })) return;
      v.made_of = v.made_of.filter(function (x) { return cleanName(x) !== w; }); c++;
    });
    return c;
  }

  return { blocks: blocks, nextRoom: nextRoom, nextFloor: nextFloor, kinds: kinds, places: places, move: move, newRooms: newRooms,
    cleanName: cleanName, parts: parts, problems: problems, canCombine: canCombine, suggestName: suggestName, combine: combine, renameRoom: renameRoom, dropRoom: dropRoom, syncKinds: syncKinds, roomsKind: roomsKind };
})();
if (typeof module !== "undefined") module.exports = VenueView;

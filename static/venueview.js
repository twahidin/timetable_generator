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
    rows(spec, "venues").forEach(function (v, vi) {
      if (!v || typeof v !== "object") return;
      var name = text(v.building), floor = text(v.floor), b = byBlock[name], f;
      if (!b) { b = byBlock[name] = { block: name, rooms: 0, seats: 0, floors: [], by: Object.create(null) }; list.push(b); }
      f = b.by[floor];
      if (!f) { f = b.by[floor] = { floor: floor, rooms: [] }; b.floors.push(f); }
      var room = v.room == null ? "" : String(v.room), cap = capacityOf(v.capacity);
      f.rooms.push({ vi: vi, room: room, kind: v.kind ? String(v.kind) : "", capacity: cap, home: room ? (homes[room] || []).slice() : [],
        only_for: strings(v.only_for), equipment: strings(v.equipment), configuration: v.configuration == null ? "" : String(v.configuration),
        note: v.note == null ? "" : String(v.note) });
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
        f.rooms.sort(function (x, y) { return cmp(x.room, y.room) || x.vi - y.vi; });
      });
      delete b.by;
    });
    return list;
  }

  function kinds(spec) {
    var out = [], seen = Object.create(null);
    function add(k) { if (k == null || String(k) === "" || seen[k]) return; seen[k] = true; out.push(String(k)); }
    ((spec && spec.school && spec.school.room_kinds) || []).forEach(add);
    rows(spec, "venues").forEach(function (v) { if (v && typeof v === "object") add(v.kind); });
    return out;
  }

  /* the room about to be added on a floor: the floor's last room's kind and capacity, and its name one higher */
  function nextRoom(spec, block, floor) {
    var b = text(block), f = text(floor), found = null, last = null;
    blocks(spec).forEach(function (x) { if (x.block === b) found = x; });
    if (found) found.floors.forEach(function (x) { if (x.floor === f && x.rooms.length) last = x.rooms[x.rooms.length - 1]; });
    if (!last) return { room: "", kind: kinds(spec)[0] || "classroom", capacity: null };
    var used = Object.create(null), room = "", m = /^(.*?)(\d+)$/.exec(last.room);
    rows(spec, "venues").forEach(function (v) { if (v && v.room) used[String(v.room).trim().toLowerCase()] = true; });
    if (m) {
      var num = Number(m[2]) + 1;
      do { room = m[1] + String(num).padStart(m[2].length, "0"); num++; } while (used[room.trim().toLowerCase()]);
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

  return { blocks: blocks, nextRoom: nextRoom, nextFloor: nextFloor, kinds: kinds };
})();
if (typeof module !== "undefined") module.exports = VenueView;

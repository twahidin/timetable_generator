// Plain-assert tests for static/venueview.js (step 1's Blocks view): run with `node tests/venueview.test.js`
const assert = require("assert");
const VenueView = require("../static/venueview.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { room_kinds: ["classroom", "lab", "computer lab", "music room"] },
  venues: [{ _id: "v1", room: "B1-1", kind: "classroom", capacity: 44, building: "Block B", floor: 1 },
           { _id: "v2", room: "B1-2", kind: "classroom", capacity: 44, building: " Block B ", floor: "1" },
           { _id: "v3", room: "B2-1", kind: "classroom", capacity: 40, building: "Block B", floor: 2, only_for: ["Sec 3"] },
           { _id: "v4", room: "B2-10", kind: "lab", capacity: 30, building: "Block B", floor: 2 },
           { _id: "v5", room: "B2-9", kind: "classroom", capacity: "40", building: "Block B", floor: 2 },
           { _id: "v6", room: "Music Room", kind: "music room", capacity: 30, building: "Block A", floor: 3, equipment: ["30 keyboards", "2 amps"], configuration: "cluster seating", note: "by the hall" },
           { _id: "v7", room: "Field", kind: "pe venue", capacity: "" },
           { _id: "v8", room: "A-G1", kind: "classroom", capacity: 20, building: "Block A", floor: "G" }],
  classes: [{ class: "4P1", home_room: "B1-1" }, { class: "2R1", home_room: "B2-1" }, { class: "2R9", home_room: "B2-1" }]
});
const names = b => b.floors.map(f => [f.floor, f.rooms.map(r => r.room)]);

t("blocks_in_natural_order_with_their_counts_and_no_block_last", () => {
  const B = VenueView.blocks(fixture());
  assert.deepStrictEqual(B.map(b => [b.block, b.rooms, b.seats]), [["Block A", 2, 50], ["Block B", 5, 198], ["", 1, 0]]);
});
t("floors_highest_first_then_the_named_ones_and_rooms_in_natural_order", () => {
  const B = VenueView.blocks(fixture());
  assert.deepStrictEqual(names(B[0]), [["3", ["Music Room"]], ["G", ["A-G1"]]]);
  assert.deepStrictEqual(names(B[1]), [["2", ["B2-1", "B2-9", "B2-10"]], ["1", ["B1-1", "B1-2"]]]);
  assert.deepStrictEqual(names(B[2]), [["", ["Field"]]]);
});
t("a_room_carries_what_the_tile_and_the_editor_show", () => {
  const B = VenueView.blocks(fixture());
  assert.deepStrictEqual(B[1].floors[0].rooms[0], { vi: 2, room: "B2-1", kind: "classroom", capacity: 40, home: ["2R1", "2R9"], only_for: ["Sec 3"], equipment: [], configuration: "", note: "" });
  assert.deepStrictEqual(B[0].floors[0].rooms[0], { vi: 5, room: "Music Room", kind: "music room", capacity: 30, home: [], only_for: [], equipment: ["30 keyboards", "2 amps"], configuration: "cluster seating", note: "by the hall" });
  assert.deepStrictEqual([B[1].floors[0].rooms[1].capacity, B[2].floors[0].rooms[0].capacity], [40, null]);   // "40" is 40; "" is none
});
t("every_room_shows_once_whatever_it_lacks", () => {
  const s = fixture();
  s.venues.push(null, {}, { room: "", building: "Block B", floor: 2 }, { room: "B1-1", kind: "classroom", building: "Block B", floor: 1 }, { room: "Loft", building: "Block B", floor: "Mezz" }, { room: "Hall", building: "block a" }, { room: "X", floor: 0, building: "Block B" });
  const B = VenueView.blocks(s), all = B.reduce((a, b) => a.concat(b.floors.reduce((x, f) => x.concat(f.rooms), [])), []);
  assert.strictEqual(all.length, 14); assert.deepStrictEqual(all.map(r => r.vi).sort((a, b) => a - b), [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14]);   // every row but the null one, once
  assert.deepStrictEqual(B.map(b => b.block), ["Block A", "block a", "Block B", ""]);                       // case is ignored for the order, not for which block a room is in
  assert.deepStrictEqual(B[2].floors.map(f => f.floor), ["2", "1", "0", "Mezz"]);
  assert.deepStrictEqual(B[2].floors[0].rooms.map(r => r.room), ["", "B2-1", "B2-9", "B2-10"]);            // a room with no name yet is first on its floor
  assert.deepStrictEqual(VenueView.blocks({}), []); assert.deepStrictEqual(VenueView.blocks({ venues: [null] }), []);
});
t("the_next_room_follows_the_floors_pattern", () => {
  const s = fixture();
  assert.deepStrictEqual(VenueView.nextRoom(s, "Block B", "1"), { room: "B1-3", kind: "classroom", capacity: 44 });
  assert.deepStrictEqual(VenueView.nextRoom(s, "Block B", 2), { room: "B2-11", kind: "lab", capacity: 30 });              // after the floor's last room, B2-10
  assert.deepStrictEqual(VenueView.nextRoom(s, "Block A", "3"), { room: "", kind: "music room", capacity: 30 });          // "Music Room" ends in no number
  assert.deepStrictEqual(VenueView.nextRoom(s, "Block C", "1"), { room: "", kind: "classroom", capacity: null });         // a new block: the school's first kind
  assert.deepStrictEqual(VenueView.nextRoom({ venues: [] }, "", ""), { room: "", kind: "classroom", capacity: null });
  s.venues.push({ room: "B1-3", building: "Block Z", floor: 9 }, { room: "b1-4", building: "Block Z", floor: 9 });
  assert.strictEqual(VenueView.nextRoom(s, "Block B", "1").room, "B1-5");                                               // names used anywhere are stepped over, whatever their case
  const p = { venues: [{ room: "L1-08", building: "L", floor: 1 }, { room: "L1-09", building: "L", floor: 1 }] };
  assert.strictEqual(VenueView.nextRoom(p, "L", "1").room, "L1-10");
});
t("the_next_floor_is_one_above_the_highest", () => {
  const s = fixture();
  assert.deepStrictEqual([VenueView.nextFloor(s, "Block B"), VenueView.nextFloor(s, "Block A"), VenueView.nextFloor(s, "Block C"), VenueView.nextFloor(s, "")], ["3", "4", "1", "1"]);
});
t("kinds_are_the_schools_list_then_any_other_found_on_a_room", () => {
  assert.deepStrictEqual(VenueView.kinds(fixture()), ["classroom", "lab", "computer lab", "music room", "pe venue"]);
  assert.deepStrictEqual(VenueView.kinds({ venues: [{ room: "A", kind: "" }, { room: "B", kind: "studio" }, { room: "C", kind: "studio" }] }), ["studio"]);
  assert.deepStrictEqual(VenueView.kinds({}), []);
});
t("the_next_room_never_hangs_and_never_prints_an_exponent", () => {
  const big = { venues: [{ room: "R-99999999999999999999", building: "L", floor: 1 }, { room: "R-100000000000000000000", building: "Z", floor: 1 }] };
  assert.strictEqual(VenueView.nextRoom(big, "L", "1").room, "R-100000000000000000001");
  const huge = { venues: [{ room: "R-000000000000000000000001", building: "L", floor: 1 }] };
  assert.strictEqual(VenueView.nextRoom(huge, "L", "1").room, "R-000000000000000000000002");
  assert.strictEqual(VenueView.nextRoom({ venues: [{ room: "99", building: "L", floor: 1 }] }, "L", "1").room, "100");          // a name that is only digits; 99 grows to 100
  const full = { venues: [{ room: "T1", kind: "lab", capacity: 9, building: "L", floor: 2 }] };
  for (let i = 2; i <= 1500; i++) full.venues.push({ room: "T" + i, building: "Z", floor: 1 });
  assert.deepStrictEqual(VenueView.nextRoom(full, "L", "2"), { room: "", kind: "lab", capacity: 9 });                          // a thousand names in a row are used: no suggestion
});
t("a_name_with_a_space_at_its_end_still_gives_the_next_name", () => {
  assert.strictEqual(VenueView.nextRoom({ venues: [{ room: "B2-10 ", building: "B", floor: 2 }] }, "B", "2").room, "B2-11");
});
t("kinds_that_are_not_a_list_count_as_none", () => {
  assert.deepStrictEqual(VenueView.kinds({ school: { room_kinds: "classroom, lab" }, venues: [{ room: "A", kind: "studio" }] }), ["studio"]);
  assert.deepStrictEqual(VenueView.nextRoom({ school: { room_kinds: "classroom" }, venues: [] }, "B", "1"), { room: "", kind: "classroom", capacity: null });
});
t("places: the named blocks with their floors, as the view orders them", () => {
  assert.deepStrictEqual(VenueView.places(fixture()), [{ block: "Block A", floors: ["3", "G"] }, { block: "Block B", floors: ["2", "1"] }]);   // a room with no block is in none; a floor with no name is not a floor
  const s = fixture(); s.venues.push({ _id: "v9", room: "A-x", building: "Block A" });
  assert.deepStrictEqual(VenueView.places(s)[0], { block: "Block A", floors: ["3", "G"] });
  assert.deepStrictEqual(VenueView.places({}), []);
});
t("move: the rooms take the block and the floor; an empty one takes the key away", () => {
  const s = fixture();
  assert.strictEqual(VenueView.move(s, [6, 0, 99, -1, "x"], " Block C ", " 2 "), 2);   // rooms that are not there are passed over
  assert.deepStrictEqual([s.venues[6].building, s.venues[6].floor, s.venues[0].building, s.venues[0].floor], ["Block C", "2", "Block C", "2"]);
  assert.strictEqual(VenueView.move(s, [0], "", ""), 1); assert.strictEqual("building" in s.venues[0], false); assert.strictEqual("floor" in s.venues[0], false);
  assert.strictEqual(VenueView.move(s, [0], "", ""), 0);   // already there: nothing changes
  assert.strictEqual(VenueView.move(s, [1], "Block B", 1), 0);   // the same place written another way (" Block B ", "1")
  assert.strictEqual(VenueView.move(s, [3, 4], "Block B", "3"), 2); assert.deepStrictEqual(VenueView.places(s).find(b => b.block === "Block B").floors, ["3", "2", "1"]);
  assert.strictEqual(VenueView.move({}, [0], "A", "1"), 0); assert.strictEqual(VenueView.move(s, null, "A", "1"), 0);
  assert.deepStrictEqual([s.venues[3].room, s.venues[3].kind, s.venues[3].capacity], ["B2-10", "lab", 30]);   // nothing else of a room changes
});
t("newRooms: the names the Add rooms bar makes, without the ones there already", () => {
  const s = fixture();
  assert.deepStrictEqual(VenueView.newRooms(s, "C1-", 1, 3), { names: ["C1-01", "C1-02", "C1-03"], skipped: 0 });
  assert.deepStrictEqual(VenueView.newRooms(s, "B1-", 1, 3), { names: ["B1-01", "B1-02", "B1-03"], skipped: 0 });   // "B1-1" is another name than "B1-01"
  s.venues.push({ room: " c1-02 " });
  assert.deepStrictEqual(VenueView.newRooms(s, "C1-", "1", "3"), { names: ["C1-01", "C1-03"], skipped: 1 });   // a name there already, in any letters, is passed over
  assert.deepStrictEqual(VenueView.newRooms(s, " Lab ", 9, 11), { names: ["Lab 09", "Lab 10", "Lab 11"], skipped: 0 });   // the prefix as typed, but for spaces before it
  assert.deepStrictEqual(VenueView.newRooms(s, "", 5, 5), { names: ["05"], skipped: 0 });
});
t("newRooms: refused with a sentence", () => {
  const s = fixture();
  assert.deepStrictEqual(VenueView.newRooms(s, "C", 5, 2), { error: "From is after To." });
  assert.deepStrictEqual(VenueView.newRooms(s, "C", "", 2), { error: "Give From and To as whole numbers." });
  assert.deepStrictEqual(VenueView.newRooms(s, "C", 1.5, 2), { error: "Give From and To as whole numbers." });
  assert.deepStrictEqual(VenueView.newRooms(s, "C", -1, 2), { error: "Give From and To as whole numbers." });
  assert.deepStrictEqual(VenueView.newRooms(s, "C", 1, 500), { error: "That is 500 rooms at once. Add at most 200 at a time." });
  assert.deepStrictEqual(VenueView.newRooms({}, "C", 1, 1), { names: ["C01"], skipped: 0 });
});
console.log(n + " cases passed");

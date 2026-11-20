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
  assert.deepStrictEqual(B[1].floors[0].rooms[0], { vi: 2, room: "B2-1", kind: "classroom", capacity: 40, home: ["2R1", "2R9"], only_for: ["Sec 3"], equipment: [], configuration: "", note: "", made_of: [] });
  assert.deepStrictEqual(B[0].floors[0].rooms[0], { vi: 5, room: "Music Room", kind: "music room", capacity: 30, home: [], only_for: [], equipment: ["30 keyboards", "2 amps"], configuration: "cluster seating", note: "by the hall", made_of: [] });
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
const paired = () => { const s = fixture(); s.venues.push({ _id: "v9", room: "B1-1&2", kind: "classroom", capacity: 88, building: "Block B", floor: 1, made_of: ["B1-1", "B1-2"] }); return s; };
t("parts_and_clean_names", () => {
  assert.deepStrictEqual(VenueView.parts(paired()), { "B1-1&2": ["B1-1", "B1-2"] });
  assert.deepStrictEqual(VenueView.parts(fixture()), {});
  assert.strictEqual(VenueView.cleanName("  D&T  Lab 1 "), "D&T Lab 1");
  const s = paired(); s.venues[8].made_of = ["B1-1"]; assert.deepStrictEqual(VenueView.parts(s), {});
});
t("suggested_names", () => {
  assert.strictEqual(VenueView.suggestName(["D&T Lab 1", "D&T Lab 2"]), "D&T Lab 1&2");
  assert.strictEqual(VenueView.suggestName(["E3-2A", "E3-2B"]), "E3-2A&B");
  assert.strictEqual(VenueView.suggestName(["Hall", "Dance Studio"]), "Hall + Dance Studio");
  assert.strictEqual(VenueView.suggestName(["Lab 1", "Lab 2", "Lab 3"]), "Lab 1&2&3");
});
t("can_combine_says_why_not", () => {
  const s = paired(), ix = n => s.venues.findIndex(v => v.room === n);
  assert.deepStrictEqual(VenueView.canCombine(s, [ix("B2-1"), ix("B2-9")]), { ok: true, why: "" });
  assert.strictEqual(VenueView.canCombine(s, [ix("B2-1")]).why, "Tick two or more rooms to combine them.");
  assert.strictEqual(VenueView.canCombine(s, [ix("B2-1"), ix("B2-10")]).why, "Rooms of different kinds cannot be combined.");
  assert.strictEqual(VenueView.canCombine(s, [ix("B1-1"), ix("B2-1")]).why, "B1-1 is already in B1-1&2.");
  assert.strictEqual(VenueView.canCombine(s, [ix("B1-1&2"), ix("B2-1")]).why, "B1-1&2 is a combined venue already.");
  s.rules = [{ scope: "Room", target: "B2-9", rule: "At most N at once", number: 2, strength: "Must" }];
  assert.strictEqual(VenueView.canCombine(s, [ix("B2-1"), ix("B2-9")]).why, "B2-9 takes 2 groups at once, so it cannot be combined.");
});
t("combine_makes_the_row", () => {
  const s = fixture(), vi = VenueView.combine(s, [0, 1]), v = s.venues[vi];
  assert.deepStrictEqual([v.room, v.kind, v.capacity, v.building, String(v.floor), v.made_of], ["B1-1&2", "classroom", 88, "Block B", "1", ["B1-1", "B1-2"]]);
  const f = VenueView.blocks(s).find(b => b.block === "Block B").floors.find(f => f.floor === "1");
  assert.deepStrictEqual(f.rooms.map(r => [r.room, r.made_of]), [["B1-1", []], ["B1-2", []], ["B1-1&2", ["B1-1", "B1-2"]]]);
  assert.deepStrictEqual(VenueView.blocks(s).map(b => [b.block, b.rooms, b.seats]), [["Block A", 2, 50], ["Block B", 5, 198], ["", 1, 0]]);   // the pair adds no room and no seats
  const t2 = fixture(); t2.venues[1].capacity = ""; assert.strictEqual(t2.venues[VenueView.combine(t2, [0, 1])].capacity, null);
  const t3 = fixture(); t3.venues.push({ room: "B1-1&2", kind: "classroom", capacity: 80 });   // the suggested name is already a room (an old single room)
  const v3 = t3.venues[VenueView.combine(t3, [0, 1])]; assert.strictEqual(v3.room, "B1-1&2 (2)"); assert.strictEqual(VenueView.suggestName(v3.made_of), "B1-1&2");
});
t("rename_and_delete_keep_it_whole", () => {
  const s = paired(); assert.strictEqual(VenueView.renameRoom(s, "B1-2", "B1-2x"), 1); assert.deepStrictEqual(s.venues[8].made_of, ["B1-1", "B1-2x"]);
  assert.strictEqual(VenueView.dropRoom(s, "B1-2x"), 1); assert.deepStrictEqual(s.venues[8].made_of, ["B1-1"]);
  assert.deepStrictEqual(VenueView.problems(s).filter(p => p.hard).map(p => [p.vi, p.text, p.hard]), [[8, "B1-1&2: a combined venue needs at least two rooms.", true]]);
  assert.deepStrictEqual(VenueView.problems(s).filter(p => !p.hard).map(p => p.text), ["B1-1&2: 88 seats, but its rooms seat 44 together."]);   // as venue_problems says too
  assert.deepStrictEqual(VenueView.problems(fixture()), []);
});
// tests/test_combined.py broken_ones_are_ordinary_rooms_and_are_reported, case by case: the same texts as ttgen/spec.py venue_problems
const PAIR = "D&T Studio 1&2", S1 = "D&T Studio 1", S2 = "D&T Studio 2";
const studios = () => ({ venues: [{ room: S1, kind: "d&t studio", capacity: 20 }, { room: S2, kind: "d&t studio", capacity: 20 }, { room: "Art Room 1", kind: "art room", capacity: 40 },
  { room: PAIR, kind: "d&t studio", capacity: 40, made_of: [S1, S2] }], rules: [] });
const probs = change => { const s = studios(); change(s, s.venues[3]); return VenueView.problems(s).map(p => [p.text, p.hard]); };
const has = (p, x) => assert.ok(p.some(y => y[0] === x[0] && y[1] === x[1]), JSON.stringify(p));
t("broken_ones_are_ordinary_rooms_and_are_reported", () => {
  assert.deepStrictEqual(VenueView.problems(studios()), []); assert.deepStrictEqual(VenueView.parts(studios()), { [PAIR]: [S1, S2] });
  has(probs((s, v) => { v.made_of = [S1]; }), [`${PAIR}: a combined venue needs at least two rooms.`, true]);
  has(probs((s, v) => { v.made_of = [S1, "Studio 9"]; }), [`${PAIR}: made of Studio 9, which is not on step 1 (Venues).`, true]);
  has(probs(s => s.venues.push({ room: "Other pair", kind: "d&t studio", capacity: 40, made_of: [S2, "Art Room 1"] })), [`${S2} is in more than one combined venue (${PAIR}, Other pair): a room can be in one only.`, true]);
  has(probs(s => s.venues.push({ room: "Big", kind: "d&t studio", capacity: 80, made_of: [PAIR, "Art Room 1"] })), ["Big: made of D&T Studio 1&2, which is a combined venue itself.", true]);
  has(probs((s, v) => { v.made_of = [S1, "Art Room 1"]; }), [`${PAIR}: it and its rooms are of different kinds (art room, d&t studio); they must all be one kind.`, true]);
  has(probs(s => s.rules.push({ scope: "Room", target: S1, rule: "At most N at once", number: 2, strength: "Must", week: "Both", day: "All" })), [`${PAIR}: ${S1} takes 2 groups at once (an "At most N at once" rule); a combined venue and its rooms take one group at a time.`, true]);
  has(probs((s, v) => { v.capacity = null; }), [`${PAIR}: give its seats (seats decide which groups get it).`, false]);
  has(probs((s, v) => { v.capacity = 50; }), [`${PAIR}: 50 seats, but its rooms seat 40 together.`, false]);
  assert.deepStrictEqual(probs((s, v) => { v.capacity = 44; }), []);   // within 10%
});
t("seats_are_read_as_python_int_reads_them", () => {   // int(): "40.0" and text are no seats; " 50 " and 50.9 are 50; 0 is none
  const seats = c => probs((s, v) => { v.capacity = c; });
  assert.deepStrictEqual(seats("40.0"), [[`${PAIR}: give its seats (seats decide which groups get it).`, false]]);
  assert.deepStrictEqual(seats("forty"), [[`${PAIR}: give its seats (seats decide which groups get it).`, false]]);
  assert.deepStrictEqual(seats(0), [[`${PAIR}: give its seats (seats decide which groups get it).`, false]]);
  assert.deepStrictEqual(seats(" 50 "), [[`${PAIR}: 50 seats, but its rooms seat 40 together.`, false]]);
  assert.deepStrictEqual(seats(50.9), [[`${PAIR}: 50 seats, but its rooms seat 40 together.`, false]]);
  assert.deepStrictEqual(probs((s, v) => { v.capacity = 50; s.venues[0].capacity = "20.0"; }), []);   // a room's seats unreadable: no sum to compare
  assert.deepStrictEqual(probs(s => s.rules.push({ scope: "Room", target: " D&T  Studio 1", rule: "At most N at once", number: "2", strength: null })).length, 1);   // a target as typed; no strength is Must
  assert.deepStrictEqual(probs(s => s.rules.push({ scope: "Room", target: S1, rule: "At most N at once", number: 2, strength: "Prefer" })), []);
});
t("a_name_used_twice_counts_as_python_counts_it", () => {   // venue_parts: the last row of a name; venue_problems: the first
  const s = studios(); s.venues.push({ room: PAIR + " " }); assert.deepStrictEqual(VenueView.parts(s), {});
  assert.deepStrictEqual(VenueView.problems({ venues: [{ room: "S1" }, { room: "P", made_of: ["S1", "S1", " S1 "] }] }).map(p => [p.vi, p.text, p.hard]),
    [[1, "P: a combined venue needs at least two rooms.", true], [1, "P: give its seats (seats decide which groups get it).", false]]);
  assert.deepStrictEqual(VenueView.problems({ venues: [null, { room: "S1" }] }), []);
});
t("sync_kinds_a_combined_venue_takes_its_rooms_kind", () => {
  const s = paired(); s.venues[0].kind = "lab"; s.venues[1].kind = "lab";
  assert.ok(VenueView.problems(s).some(p => /different kinds/.test(p.text)));
  assert.strictEqual(VenueView.syncKinds(s), 1); assert.strictEqual(s.venues[8].kind, "lab");
  assert.ok(!VenueView.problems(s).some(p => /different kinds/.test(p.text))); assert.strictEqual(VenueView.syncKinds(s), 0);
  const d = paired(); d.venues[0].kind = "lab"; assert.strictEqual(VenueView.syncKinds(d), 0); assert.strictEqual(d.venues[8].kind, "classroom");   // its rooms differ: left alone
  const b = paired(); b.venues[8].made_of = ["B1-1"]; b.venues[0].kind = "lab"; assert.strictEqual(VenueView.syncKinds(b), 0); assert.strictEqual(b.venues[8].kind, "classroom");   // broken: untouched
  assert.strictEqual(VenueView.syncKinds(fixture()), 0);
  const m = paired(); delete m.venues[0].kind; delete m.venues[1].kind; assert.strictEqual(VenueView.syncKinds(m), 0);   // no kind is classroom
});
// The page's openServer (static/app.js), run as written with the page around it stubbed: a combined venue whose kind is out of
// step with its rooms is put right on the committee's page and in a practice copy, but never on a department head's page,
// where the change would go to the server and be refused ("1 change could not be made")
t("opening_the_setup_syncs_kinds_except_on_a_department_heads_page", () => {
  const src = require("fs").readFileSync(require("path").join(__dirname, "../static/app.js"), "utf8");
  const at = src.indexOf("async function openServer("); assert.ok(at >= 0, "openServer not found in static/app.js");
  const body = src.slice(at, src.indexOf("\n}\n", at) + 2);
  const open = (role, practice) => {
    const srv = paired(); srv.venues[0].kind = "lab"; srv.venues[1].kind = "lab";   // the pair still says classroom
    const S = { practice, spec: null, step: 1 }, saved = [];
    const run = new Function("S", "SYNC", "Sync", "LIST_KEYS", "VenueView", "isHead", "useKind", "unpick", "defaultRoles", "ensureDays", "save",
      body + "; return openServer;")(S, {}, { clone: x => JSON.parse(JSON.stringify(x)) }, ["venues"], VenueView, () => role === "head",
      async () => {}, () => {}, () => false, () => {}, () => saved.push(JSON.parse(JSON.stringify(S.spec))));
    return run({ spec: srv, v: 1 }).then(() => [S.spec.venues[8].kind, saved.length]);
  };
  return Promise.all([open("head", false), open("committee", false), open("head", true)]).then(([head, comm, prac]) => {
    assert.deepStrictEqual(head, ["classroom", 1]);   // left as the server has it: nothing for the server to refuse
    assert.deepStrictEqual(comm, ["lab", 1]);
    assert.deepStrictEqual(prac, ["lab", 1]);         // a practice copy is never sent, so it may be put right
    pending--;
  });
});
let pending = 1;
process.on("beforeExit", () => { assert.strictEqual(pending, 0, "the openServer test did not finish"); });
console.log(n + " cases passed");

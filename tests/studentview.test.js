// Plain-assert tests for static/studentview.js (the working-out of one student's screen): run with `node tests/studentview.test.js`
const assert = require("assert");
const SV = require("../static/studentview.js");
let n = 0; const t = (name, f) => { f(); n++; };
const copy = x => JSON.parse(JSON.stringify(x));

const fixture = () => ({
  classes: [{ class: "3B", level: "Sec 3", size: 30 }, { class: "3C", level: "Sec 3", size: 30 }],
  blocks: [{ block: "Sec 3 English", level: "Sec 3", classes: ["3B", "3C"] }, { block: "Sec 3 Humanities", level: "Sec 3", classes: ["3B", "3C"] },
           { block: "Sec 3 Option A", level: "Sec 3", classes: ["3B", "3C"], everyone: false }],
  lessons: [{ level: "Sec 3", subject: "Mathematics", block: "", classes: ["3B"], teachers: ["Mr Ong"] },
            { level: "Sec 3", subject: "English", block: "Sec 3 English", classes: ["3B", "3C"], teachers: ["Ms Tan"], students: 30 },
            { level: "Sec 3", subject: "English", block: "Sec 3 English", classes: ["3B", "3C"], teachers: ["Mr Lim", ""], students: 30 },
            { level: "Sec 3", subject: "History", block: "Sec 3 Humanities", classes: ["3B", "3C"], teachers: ["Mdm Wong"], students: 2 },
            { level: "Sec 3", subject: "Geography", block: "Sec 3 Humanities", classes: ["3B", "3C"], teachers: ["Mr Goh"], students: "" },
            { level: "Sec 3", subject: "Geography", block: "Sec 3 Humanities", classes: ["3B", "3C"], teachers: ["Ms Siti"], students: "" },
            { level: "Sec 3", subject: "Art", block: "Sec 3 Option A", classes: ["3B", "3C"], teachers: ["Mr Rao"], students: 2 },
            { level: "Sec 3", subject: "Robotics", block: "", classes: ["3B", "3C"], teachers: ["Mrs Lee"], students: 20 },
            { level: "Sec 3", subject: "History", block: "Sec 3 Humanities", classes: ["3C"], teachers: ["Mdm Wong"], students: 30 },
            { level: "Sec 3", subject: "Drama", block: "Sec 3 Option A", classes: ["3B", "3C"], teachers: [], students: 10 },
            { level: "Sec 3", subject: "Music", block: "Sec 3 Music Elective", classes: ["3B"], teachers: ["Ms Ng"], students: "" },
            { level: "Sec 3", subject: "", block: "", classes: [], teachers: [] }],
  students: [{ id: "S1", name: "Aisha Rahman", class: "3B", groups: ["3EL2", "3HIS1", "3CCA1"] },
             { id: "S2", name: "Ben Koh", class: "3B", groups: ["3EL1", "3HIS1", "3ART1"] },
             { id: "S3", name: "Chen Li", class: "3B", groups: ["3EL2", "3GEO1"] },
             { id: "S4", name: "Devi Nair", class: "3C", groups: ["3EL1", "3GEO2"] },
             { id: "S5", name: "Farah Ismail", class: "3B", groups: ["3EL1", "3HIS2", "3OLD1"] },
             { id: "S6", name: "Gopal Menon", class: "3C", groups: ["3EL2", "3GEO2", "3ART1"] }] });
const CODES = ["Entire Class", "3EL1", "3EL2", "3HIS1", "3GEO1", "3GEO2", "3ART1", "3CCA1", "3HIS2", "3DRA1", "3MUS1", ""];
const g = (subject, short, band, classes, teachers, rooms, seats, slots) => ({ subject, short, band, classes, teachers, rooms, seats, slots });
const skeleton = () => ({
  stamp: "s1", days: ["Mon", "Tue", "Wed", "Thu", "Fri"], NP: 8,
  times: [["07:30", "08:05"], ["08:05", "08:40"], ["08:40", "09:15"], ["09:15", "09:50"], ["10:10", "10:45"], ["10:45", "11:20"], ["11:20", "11:55"], ["11:55", "12:30"]],
  classes: { "3B": { level: "Sec 3", codes: [], whole: [[0, 0, 2, "MA", "3B"], [2, 0, 1, "MA", "3B"], [3, 6, 1, "CCE", "3B"]] },
             "3C": { level: "Sec 3", codes: [], whole: [[0, 0, 2, "MA", "3C"]] } },
  groups: { "3EL1": g("English", "EL", "Sec 3 English", ["3B", "3C"], ["Ms Tan"], ["3B"], 40, [[0, 2, 2], [1, 3, 1]]),
            "3EL2": g("English", "EL", "Sec 3 English", ["3B", "3C"], ["Mr Lim"], ["3C"], 40, [[0, 2, 2], [1, 3, 1]]),
            "3GEO1": g("Geography", "GEO", "Sec 3 Humanities", ["3B", "3C"], ["Mr Goh"], ["3D", "Field"], null, [[1, 3, 1], [3, 6, 1]]),
            "3GEO2": g("Geography", "GEO", "Sec 3 Humanities", ["3B", "3C"], ["Ms Siti"], ["Geog Rm"], 4, [[1, 0, 1], [3, 3, 2]]),
            "3HIS1": g("History", "HIS", "Sec 3 Humanities", ["3B", "3C"], ["Mdm Wong"], ["Hist Rm"], 40, [[1, 0, 1], [3, 3, 2]]),
            "3ART1": g("Art", "ART", "Sec 3 Option A", ["3B", "3C"], ["Mr Rao"], ["Art Rm"], 20, [[2, 4, 2]]),
            "3CCA1": g("Robotics", "ROB", "", ["3B", "3C"], ["Mrs Lee"], ["Lab"], 20, [[4, 7, 1]]),
            "3HIS2": g("History", "HIS", "Sec 3 Humanities", ["3C"], ["Mdm Wong"], ["Hist Rm 2"], 40, [[1, 0, 1], [3, 3, 2]]),
            "3OLD1": g("Literature", "LIT", "", ["3B"], ["Mr Yeo"], ["3B"], null, [[2, 6, 1]]) } });
const stu = (spec, id) => spec.students.find(s => s.id === id);
const withBand = (picks, band, code) => { const p = copy(picks); p.band[band] = code; return p; };
const band = (v, name) => v.bands.find(b => b.band === name);
const opt = (v, name, code) => band(v, name).options.find(o => o.code === code);
const HUM = "Sec 3 Humanities", ENG = "Sec 3 English", OPA = "Sec 3 Option A";
const OFF = "3DRA1 is not on the published timetable, so the published timetable will not change for this student until the next publish.";

t("counts_per_group", () => {
  assert.deepStrictEqual(SV.counts(fixture()), { "3EL2": 3, "3HIS1": 2, "3CCA1": 1, "3EL1": 3, "3ART1": 2, "3GEO1": 1, "3GEO2": 2, "3HIS2": 1, "3OLD1": 1 });
  assert.deepStrictEqual(SV.counts({ students: [{ id: "x", groups: ["A", "A", ""] }] }), { A: 1 });
  assert.deepStrictEqual(SV.counts({}), {});
});
t("bands_for_a_class_in_step_5_order", () => {
  assert.deepStrictEqual(SV.bands(fixture(), CODES, "3B"), {
    bands: [{ band: ENG, everyone: true, groups: [{ code: "3EL1", subject: "English", size: 30 }, { code: "3EL2", subject: "English", size: 30 }] },
            { band: HUM, everyone: true, groups: [{ code: "3HIS1", subject: "History", size: 2 }, { code: "3GEO1", subject: "Geography", size: null }, { code: "3GEO2", subject: "Geography", size: null }] },
            { band: OPA, everyone: false, groups: [{ code: "3ART1", subject: "Art", size: 2 }, { code: "3DRA1", subject: "Drama", size: 10 }] },
            { band: "Sec 3 Music Elective", everyone: false, groups: [{ code: "3MUS1", subject: "Music", size: null }] }],
    other: [{ code: "3CCA1", subject: "Robotics", size: 20 }] });
  const c = SV.bands(fixture(), CODES, "3C");
  assert.deepStrictEqual(band(c, HUM).groups.map(x => x.code), ["3HIS1", "3GEO1", "3GEO2", "3HIS2"]);
  assert.strictEqual(band(c, "Sec 3 Music Elective"), undefined);
});
t("an_optional_band_is_marked", () => {
  const b = SV.bands(fixture(), CODES, "3B").bands;
  assert.deepStrictEqual(b.map(x => [x.band, x.everyone]), [[ENG, true], [HUM, true], [OPA, false], ["Sec 3 Music Elective", false]]);
  const spec = fixture(); spec.blocks[2].everyone = true;   // the committee ticked Everyone takes one on an option band
  assert.strictEqual(band(SV.bands(spec, CODES, "3B"), OPA).everyone, true);
  const v = SV.view(fixture(), CODES, skeleton(), stu(fixture(), "S1"), SV.open(fixture(), CODES, stu(fixture(), "S1"), {}));
  assert.strictEqual(band(v, OPA).everyone, false); assert.strictEqual(band(v, OPA).pick, SV.NONE);
});
t("open_puts_a_group_outside_the_class_under_other", () => {
  const spec = fixture(), s = stu(spec, "S5"), p = SV.open(spec, CODES, s, {});
  assert.deepStrictEqual(p, { cls: "3B", band: { [ENG]: "3EL1", [HUM]: "", [OPA]: "", "Sec 3 Music Elective": "" }, other: ["3HIS2", "3OLD1"],
    was: ["3EL1", "3HIS2", "3OLD1"], exemptWas: {} });
  assert.deepStrictEqual(SV.groupsOf(p), ["3EL1", "3HIS2", "3OLD1"]);
  const v = SV.view(spec, CODES, skeleton(), s, p);
  assert.deepStrictEqual(v.other.slice(0, 2), [
    { code: "3CCA1", subject: "Robotics", teacher: "Mrs Lee", room: "Lab", n: 1, size: 20, full: false, over: false, clash: "", on: false, was: false, off: false, why: "" },
    { code: "3HIS2", subject: "History", teacher: "Mdm Wong", room: "Hist Rm 2", n: 1, size: 30, full: false, over: false, clash: "", on: true, was: true, off: false, why: "not a group of class 3B" }]);
});
t("a_group_no_longer_on_step_5_stays_ticked", () => {
  const spec = fixture(), s = stu(spec, "S5"), v = SV.view(spec, CODES, skeleton(), s, SV.open(spec, CODES, s, {}));
  assert.deepStrictEqual(v.other[2], { code: "3OLD1", subject: "Literature", teacher: "Mr Yeo", room: "3B", n: 1, size: null, full: false, over: false, clash: "", on: true, was: true, off: false, why: "not on step 5" });
  assert.deepStrictEqual(SV.apply(s, SV.open(spec, CODES, s, {})), { groups: ["3EL1", "3HIS2", "3OLD1"] });
  const gone = SV.view(spec, CODES, null, s, SV.open(spec, CODES, s, {})).other[2];   // with no skeleton: no subject known
  assert.deepStrictEqual([gone.code, gone.subject, gone.teacher, gone.why], ["3OLD1", "", "", "not on step 5"]);
});
t("the_count_is_as_it_will_be_after_save", () => {
  const spec = fixture(), s = stu(spec, "S1"), p = withBand(SV.open(spec, CODES, s, {}), HUM, "3GEO2"), v = SV.view(spec, CODES, skeleton(), s, p);
  assert.strictEqual(opt(v, HUM, "3HIS1").n, 1); assert.strictEqual(opt(v, HUM, "3GEO2").n, 3);
  assert.strictEqual(opt(v, HUM, "3GEO1").n, 1); assert.strictEqual(opt(v, ENG, "3EL2").n, 3);
  assert.deepStrictEqual([opt(v, HUM, "3HIS1").on, opt(v, HUM, "3HIS1").was, opt(v, HUM, "3GEO2").on, opt(v, HUM, "3GEO2").was], [false, true, true, false]);
  const fresh = { id: "S9", name: "Hana Yusof", class: "3B", groups: [] }, q = withBand(SV.open(spec, CODES, fresh, {}), ENG, "3EL1");
  assert.strictEqual(opt(SV.view(spec, CODES, skeleton(), fresh, q), ENG, "3EL1").n, 4);
});
t("full_and_over", () => {
  const spec = fixture(), chen = stu(spec, "S3"), v = SV.view(spec, CODES, skeleton(), chen, SV.open(spec, CODES, chen, {}));
  const h = opt(v, HUM, "3HIS1"); assert.deepStrictEqual([h.n, h.size, h.full, h.over], [2, 2, true, false]);
  const ben = stu(spec, "S2"), vb = SV.view(spec, CODES, skeleton(), ben, SV.open(spec, CODES, ben, {}));
  const hb = opt(vb, HUM, "3HIS1"); assert.deepStrictEqual([hb.n, hb.size, hb.full, hb.over, hb.on], [2, 2, false, false, true]);
  const aisha = stu(spec, "S1"), va = SV.view(spec, CODES, skeleton(), aisha, withBand(SV.open(spec, CODES, aisha, {}), OPA, "3ART1"));
  const a = opt(va, OPA, "3ART1"); assert.deepStrictEqual([a.n, a.size, a.full, a.over, a.on], [3, 2, false, true, true]);
});
t("a_group_with_no_size_is_never_full", () => {
  const spec = fixture(); spec.students.push({ id: "S7", name: "Ivan Tan", class: "3B", groups: ["3GEO1"] }, { id: "S8", name: "Jia Wei", class: "3B", groups: ["3GEO1"] });
  const aisha = stu(spec, "S1"), v = SV.view(spec, CODES, skeleton(), aisha, SV.open(spec, CODES, aisha, {}));
  const o = opt(v, HUM, "3GEO1"); assert.deepStrictEqual([o.n, o.size, o.full, o.over], [3, null, false, false]);
  const chen = stu(spec, "S3"), c = opt(SV.view(spec, CODES, skeleton(), chen, SV.open(spec, CODES, chen, {})), HUM, "3GEO1");
  assert.deepStrictEqual([c.n, c.size, c.full, c.over, c.on], [3, null, false, false, true]);
});
t("seats_stand_in_for_a_blank_size", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), p = SV.open(spec, CODES, aisha, {});
  const o = opt(SV.view(spec, CODES, skeleton(), aisha, p), HUM, "3GEO2"); assert.deepStrictEqual([o.size, o.n, o.full], [4, 2, false]);
  assert.strictEqual(opt(SV.view(spec, CODES, null, aisha, p), HUM, "3GEO2").size, null);
  const sk = skeleton(); sk.groups["3HIS1"].seats = 1;   // a step 5 number wins over the seats
  assert.strictEqual(opt(SV.view(spec, CODES, sk, aisha, p), HUM, "3HIS1").size, 2);
});
t("a_clash_is_named", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), v = SV.view(spec, CODES, skeleton(), aisha, SV.open(spec, CODES, aisha, {}));
  assert.strictEqual(opt(v, HUM, "3GEO1").clash, "Clashes: Tue period 4, with 3EL2 English");
  const chen = stu(spec, "S3"), vc = SV.view(spec, CODES, skeleton(), chen, SV.open(spec, CODES, chen, {}));
  assert.strictEqual(opt(vc, HUM, "3GEO1").clash, "Clashes: Tue period 4, with 3EL2 English");   // on: the clash it has now
  assert.strictEqual(opt(vc, ENG, "3EL1").clash, "Clashes: Tue period 4, with 3GEO1 Geography");
  assert.strictEqual(opt(vc, ENG, "3EL2").clash, "Clashes: Tue period 4, with 3GEO1 Geography");
  const alone = withBand(SV.open(spec, CODES, chen, {}), ENG, "");
  assert.strictEqual(opt(SV.view(spec, CODES, skeleton(), chen, alone), HUM, "3GEO1").clash, "Clashes: Thu period 7, with CCE");
  assert.strictEqual(opt(vc, HUM, "3HIS1").clash, "");
});
t("two_groups_of_one_band_do_not_clash_as_options", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), v = SV.view(spec, CODES, skeleton(), aisha, SV.open(spec, CODES, aisha, {}));
  assert.strictEqual(opt(v, HUM, "3GEO2").clash, ""); assert.strictEqual(opt(v, HUM, "3HIS1").clash, "");
  assert.strictEqual(opt(v, ENG, "3EL1").clash, "");
});
t("week_and_clashes", () => {
  const sk = skeleton();
  assert.deepStrictEqual(SV.week(sk, "3C", ["3GEO2", "3NONE"]), [{ d: 0, p: 0, n: 2, short: "MA", room: "3C", code: "" },
    { d: 1, p: 0, n: 1, short: "GEO", room: "Geog Rm", code: "3GEO2" }, { d: 3, p: 3, n: 2, short: "GEO", room: "Geog Rm", code: "3GEO2" }]);
  assert.deepStrictEqual(SV.week(null, "3B", ["3EL1"]), []);
  assert.deepStrictEqual(SV.clashes(sk, "3B", ["3EL2", "3GEO1"]), [{ d: 1, p: 3, a: "3EL2", b: "3GEO1" }, { d: 3, p: 6, a: "", b: "3GEO1" }]);
  assert.deepStrictEqual(SV.clashes(sk, "3B", ["3HIS1", "3GEO2"]), [{ d: 1, p: 0, a: "3HIS1", b: "3GEO2" }, { d: 3, p: 3, a: "3HIS1", b: "3GEO2" }, { d: 3, p: 4, a: "3HIS1", b: "3GEO2" }]);
  assert.deepStrictEqual(SV.clashes(null, "3B", ["3HIS1"]), []);
});
t("the_week_marks_new_gone_and_clash", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), v = SV.view(spec, CODES, skeleton(), aisha, withBand(SV.open(spec, CODES, aisha, {}), HUM, "3GEO1"));
  const c = (d, p, n, short, room, code, state, change) => ({ d, p, n, short, room, code, state, change });
  assert.deepStrictEqual(v.cells, [
    c(0, 0, 2, "MA", "3B", "", "same", ""), c(2, 0, 1, "MA", "3B", "", "same", ""), c(3, 6, 1, "CCE", "3B", "", "clash", ""),
    c(0, 2, 2, "EL", "3C", "3EL2", "same", ""), c(1, 3, 1, "EL", "3C", "3EL2", "clash", ""),
    c(1, 3, 1, "GEO", "3D, Field", "3GEO1", "clash", "new"), c(3, 6, 1, "GEO", "3D, Field", "3GEO1", "clash", "new"),
    c(4, 7, 1, "ROB", "Lab", "3CCA1", "same", ""),
    c(1, 0, 1, "HIS", "Hist Rm", "3HIS1", "gone", "gone"), c(3, 3, 2, "HIS", "Hist Rm", "3HIS1", "gone", "gone")]);
  assert.strictEqual(v.summary, "Moves from 3HIS1 History to 3GEO1 Geography. 4 lessons change. 2 clashes.");
  const w = SV.view(spec, CODES, skeleton(), aisha, withBand(SV.open(spec, CODES, aisha, {}), HUM, "3GEO2"));
  assert.deepStrictEqual(w.cells.filter(x => x.state !== "same").map(x => [x.code, x.d, x.p, x.state]),
    [["3GEO2", 1, 0, "new"], ["3GEO2", 3, 3, "new"], ["3HIS1", 1, 0, "gone"], ["3HIS1", 3, 3, "gone"]]);
});
t("summary_for_a_swap", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), v = SV.view(spec, CODES, skeleton(), aisha, withBand(SV.open(spec, CODES, aisha, {}), HUM, "3GEO2"));
  assert.strictEqual(v.summary, "Moves from 3HIS1 History to 3GEO2 Geography. 4 lessons change. No clash.");
  assert.strictEqual(v.changed, true); assert.deepStrictEqual(v.asks, []);
  const p = withBand(withBand(SV.open(spec, CODES, aisha, {}), HUM, "3GEO2"), OPA, "3ART1");
  assert.strictEqual(SV.view(spec, CODES, skeleton(), aisha, p).summary, "Moves from 3HIS1 History to 3GEO2 Geography. Joins 3ART1 Art. 5 lessons change. No clash.");
  const q = copy(SV.open(spec, CODES, aisha, {})); q.other = [];
  assert.strictEqual(SV.view(spec, CODES, skeleton(), aisha, q).summary, "Leaves 3CCA1 Robotics. 1 lesson changes. No clash.");
});
t("summary_when_nothing_changed", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), p = SV.open(spec, CODES, aisha, {}), v = SV.view(spec, CODES, skeleton(), aisha, p);
  assert.strictEqual(v.summary, "Nothing changed."); assert.strictEqual(v.changed, false);
  const back = withBand(withBand(p, HUM, "3GEO2"), HUM, "3HIS1");
  assert.strictEqual(SV.view(spec, CODES, skeleton(), aisha, back).changed, false);
  const farah = stu(spec, "S5"), fp = SV.open(spec, CODES, farah, { [HUM]: true });
  assert.strictEqual(SV.view(spec, CODES, skeleton(), farah, fp).changed, false);
  const un = SV.view(spec, CODES, skeleton(), farah, withBand(fp, HUM, SV.NONE));
  assert.strictEqual(un.changed, true); assert.strictEqual(un.summary, "No longer exempt from Sec 3 Humanities. No lesson changes. No clash.");
  const cls = copy(p); cls.cls = "3C"; assert.strictEqual(SV.view(spec, CODES, skeleton(), aisha, cls).changed, true);
});
t("asks_for_a_clash_a_missing_band_and_a_group_off_the_timetable", () => {
  const spec = fixture(), chen = stu(spec, "S3"), p = SV.open(spec, CODES, chen, {});
  assert.deepStrictEqual(SV.view(spec, CODES, skeleton(), chen, p).asks, ["3GEO1 clashes on Tue period 4 with 3EL2 English.", "3GEO1 clashes on Thu period 7 with CCE."]);
  const q = withBand(withBand(p, ENG, SV.NONE), OPA, "3DRA1"), v = SV.view(spec, CODES, skeleton(), chen, q);
  assert.deepStrictEqual(v.asks, ["3GEO1 clashes on Thu period 7 with CCE.", "No Sec 3 English group is chosen.", OFF]);
  assert.strictEqual(opt(v, OPA, "3DRA1").off, true); assert.strictEqual(opt(v, OPA, "3ART1").off, false);
  assert.strictEqual(v.summary, "Joins 3DRA1 Drama. Leaves 3EL2 English. 2 lessons change. 1 clash.");
});
t("an_exempt_band_asks_nothing", () => {
  const spec = fixture(), farah = stu(spec, "S5");
  assert.deepStrictEqual(SV.view(spec, CODES, skeleton(), farah, SV.open(spec, CODES, farah, {})).asks, ["No Sec 3 Humanities group is chosen."]);
  const p = SV.open(spec, CODES, farah, { [HUM]: true });
  assert.strictEqual(p.band[HUM], SV.EXEMPT); assert.deepStrictEqual(p.exemptWas, { [HUM]: true });
  const v = SV.view(spec, CODES, skeleton(), farah, p);
  assert.strictEqual(band(v, HUM).pick, "exempt"); assert.deepStrictEqual(v.asks, []);
  assert.deepStrictEqual(SV.groupsOf(p), ["3EL1", "3HIS2", "3OLD1"]);
  assert.strictEqual(SV.open(spec, CODES, stu(spec, "S1"), { [HUM]: true }).band[HUM], "3HIS1");   // a group wins over the Note
});
t("most_room_first_within_a_subject", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), p = SV.open(spec, CODES, aisha, {});
  const order = (sp, sk) => band(SV.view(sp, CODES, sk, aisha, p), HUM).options.map(o => o.code);
  assert.deepStrictEqual(order(spec, skeleton()), ["3GEO2", "3GEO1", "3HIS1"]);   // Geography first: the published timetable lists it first
  assert.deepStrictEqual(order(spec, null), ["3HIS1", "3GEO1", "3GEO2"]);         // step 5 order; no size known: by code
  const roomy = fixture(); roomy.lessons[4].students = 10;
  assert.deepStrictEqual(order(roomy, skeleton()), ["3GEO1", "3GEO2", "3HIS1"]);
  const tight = fixture(); tight.lessons[1].students = 2;
  assert.deepStrictEqual(band(SV.view(tight, CODES, skeleton(), aisha, p), ENG).options.map(o => o.code), ["3EL2", "3EL1"]);
  assert.deepStrictEqual(band(SV.view(spec, CODES, skeleton(), aisha, p), ENG).options.map(o => o.code), ["3EL1", "3EL2"]);
});
t("a_two_week_timetable", () => {
  const sk = skeleton();
  sk.days = ["Odd Mon", "Odd Tue", "Odd Wed", "Odd Thu", "Odd Fri", "Even Mon", "Even Tue", "Even Wed", "Even Thu", "Even Fri"];
  sk.classes["3B"].whole = [[9, 0, 1, "MA", "3B"]];
  sk.groups["3EL2"].slots = [[0, 2, 1], [7, 3, 1]]; sk.groups["3GEO1"].slots = [[7, 3, 1]];
  const spec = fixture(), chen = stu(spec, "S3"), v = SV.view(spec, CODES, sk, chen, SV.open(spec, CODES, chen, {}));
  assert.deepStrictEqual(v.cells.map(c => [c.d, c.p, c.code, c.state]), [[9, 0, "", "same"], [0, 2, "3EL2", "same"], [7, 3, "3EL2", "clash"], [7, 3, "3GEO1", "clash"]]);
  assert.strictEqual(opt(v, HUM, "3GEO1").clash, "Clashes: Even Wed period 4, with 3EL2 English");
  assert.deepStrictEqual(v.asks, ["3GEO1 clashes on Even Wed period 4 with 3EL2 English."]);
});
t("with_no_skeleton", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), p = withBand(SV.open(spec, CODES, aisha, {}), HUM, "3GEO2"), v = SV.view(spec, CODES, null, aisha, p);
  assert.deepStrictEqual(v.cells, []);
  assert.deepStrictEqual(opt(v, HUM, "3GEO2"), { code: "3GEO2", subject: "Geography", teacher: "Ms Siti", room: "", n: 3, size: null, full: false, over: false, clash: "", on: true, was: false, off: false });
  assert.strictEqual(opt(v, ENG, "3EL2").teacher, "Mr Lim");   // step 5's teachers, blanks dropped
  assert.strictEqual(opt(v, OPA, "3DRA1").teacher, ""); assert.strictEqual(opt(v, OPA, "3DRA1").off, false);
  assert.strictEqual(opt(v, HUM, "3HIS1").n, 1);
  assert.strictEqual(v.summary, "Moves from 3HIS1 History to 3GEO2 Geography.");
  assert.deepStrictEqual(SV.view(spec, CODES, null, aisha, withBand(p, ENG, SV.NONE)).asks, ["No Sec 3 English group is chosen."]);
  const chen = stu(spec, "S3"); assert.deepStrictEqual(SV.view(spec, CODES, null, chen, SV.open(spec, CODES, chen, {})).asks, []);
});
t("a_new_student_with_no_class", () => {
  const spec = fixture(), fresh = { id: "S9", name: "Hana Yusof", class: "", groups: [] };
  assert.deepStrictEqual(SV.bands(spec, CODES, ""), { bands: [], other: [] });
  assert.deepStrictEqual(SV.bands(spec, CODES, "9Z"), { bands: [], other: [] });
  const p = SV.open(spec, CODES, fresh, {});
  assert.deepStrictEqual(p, { cls: "", band: {}, other: [], was: [], exemptWas: {} });
  assert.deepStrictEqual(SV.view(spec, CODES, skeleton(), fresh, p), { bands: [], other: [], cells: [], summary: "Nothing changed.", asks: [], changed: false });
  const q = copy(p); q.cls = "3B"; const v = SV.view(spec, CODES, skeleton(), fresh, q);
  assert.deepStrictEqual(v.bands.map(b => [b.band, b.pick]), [[ENG, ""], [HUM, ""], [OPA, ""], ["Sec 3 Music Elective", ""]]);
  assert.deepStrictEqual(v.asks, ["No Sec 3 English group is chosen.", "No Sec 3 Humanities group is chosen."]);
  assert.strictEqual(v.summary, "Joins class 3B. 3 lessons change. No clash.");
  assert.deepStrictEqual(v.cells.map(c => c.state), ["new", "new", "new"]);
});
t("apply_keeps_old_order_then_new", () => {
  const spec = fixture(), aisha = stu(spec, "S1"), before = copy(aisha);
  const p = withBand(withBand(SV.open(spec, CODES, aisha, {}), HUM, "3GEO2"), OPA, "3ART1");
  const out = SV.apply(aisha, p);
  assert.deepStrictEqual(out, { groups: ["3EL2", "3CCA1", "3GEO2", "3ART1"] });
  assert.deepStrictEqual(aisha, before); assert.notStrictEqual(out.groups, aisha.groups);
});
t("nothing_is_changed_in_place", () => {
  const spec = fixture(), sk = skeleton(), chen = stu(spec, "S3"), p = withBand(SV.open(spec, CODES, chen, {}), OPA, "3ART1");
  const was = copy([spec, sk, chen, p, CODES]);
  SV.view(spec, CODES, sk, chen, p); SV.apply(chen, p); SV.groupsOf(p); SV.clashes(sk, "3B", ["3EL2", "3GEO1"]);
  assert.deepStrictEqual([spec, sk, chen, p, CODES], was);
});
console.log(`${n} cases passed`);

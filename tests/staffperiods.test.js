// Plain-assert tests for static/staffperiods.js (teacher-only periods on step 6): run with `node tests/staffperiods.test.js`
const assert = require("assert");
const SP = require("../static/staffperiods.js");
let n = 0; const t = (name, f) => { f(); n++; };
const school = { start_time: "07:40", period_minutes: 20, periods_per_day: 26 };
const spec = { school, teachers: [{ name: "Mr Arjun Rao", dept: "English" }, { name: "Mr Farhan Aziz", dept: "Mathematics" }, { name: "Ms Mei Ling Koh", dept: "Science", dept2: "English" }] };
const ZONE = { name: "Zone class", all: false, depts: [], teachers: ["Mr Arjun Rao", "Mr Farhan Aziz"], week: "Both", days: ["Tue"], times: ["15:00", "17:30"], place: "Hall" };

t("people and faults agree with the server's", () => {
  assert.deepStrictEqual(SP.people(spec, ZONE), ["Mr Arjun Rao", "Mr Farhan Aziz"]);
  assert.deepStrictEqual(SP.people(spec, { ...ZONE, teachers: [], depts: ["English"] }), ["Mr Arjun Rao", "Ms Mei Ling Koh"]);
  assert.deepStrictEqual(SP.faults(spec, SP.blank()), [{ hard: true, text: "It has no name." }, { hard: true, text: "Nobody is in it." }, { hard: true, text: "It has no day." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, teachers: ["Mr Gone", "Mr Arjun Rao"] }), [{ hard: false, text: "Mr Gone is not on step 4." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, times: ["15:00", "14:00"] }), [{ hard: true, text: "Its To time is not after its From time." }]);
  assert.deepStrictEqual(SP.faults({ teachers: spec.teachers }, null), []);
});
t("every sentence of the faults", () => {
  const long = "x".repeat(61);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, depts: ["Art"] }), [{ hard: false, text: "Department Art has no teacher." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, name: " " }), [{ hard: true, text: "It has no name." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, name: long }), [{ hard: true, text: "Its name is longer than 60 letters." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, place: long }), [{ hard: true, text: "Its place is longer than 60 letters." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, teachers: [] }), [{ hard: true, text: "Nobody is in it." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, days: [" "] }), [{ hard: true, text: "It has no day." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, times: ["15:00", "x"] }), [{ hard: true, text: "Its From and To times are not times." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, times: ["٣:00", "17:30"] }), [{ hard: true, text: "Its From and To times are not times." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, teachers: "Mr Arjun Rao", days: null }), [{ hard: true, text: "Nobody is in it." }, { hard: true, text: "It has no day." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, teachers: ["Mr Gone"], depts: ["Art"], name: "" }).map(f => f.text),
    ["Mr Gone is not on step 4.", "Department Art has no teacher.", "It has no name.", "Nobody is in it."]);
});
t("the lines under a row", () => {
  assert.strictEqual(SP.whoLine(spec, ZONE), "");
  assert.strictEqual(SP.whoLine(spec, { ...ZONE, all: true }), "3 teachers now. A new teacher is included.");
  assert.strictEqual(SP.whoLine(spec, { ...ZONE, teachers: [], depts: ["English"] }), "2 teachers now.");
  assert.strictEqual(SP.whoLine(spec, { ...ZONE, teachers: [], depts: ["Mathematics"] }), "1 teacher now.");
  assert.strictEqual(SP.blocksLine(school, ZONE), "blocks periods 22 to 25 · after the last period (4.20 pm)");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["14:20", "15:20"] }), "blocks periods 20 to 22");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["15:00", "15:20"] }), "blocks period 22");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["17:00", "18:00"] }), "after the last period (4.20 pm): it blocks no lesson");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["07:00", "08:00"] }), "blocks period 0 · before the first period (7.40 am)");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["06:00", "07:20"] }), "before the first period (7.40 am): it blocks no lesson");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["", "x"] }), "");
});
t("what can still be added", () => {
  assert.deepStrictEqual(SP.options(spec, ZONE), { all: true, depts: ["English", "Mathematics", "Science"], teachers: ["Ms Mei Ling Koh"] });
  assert.deepStrictEqual(SP.options(spec, { ...ZONE, all: true }), { all: false, depts: [], teachers: [] });
});
console.log(`${n} cases passed`);

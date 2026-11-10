// Plain-assert tests for static/choices.js (second choices on step 6): run with `node tests/choices.test.js`
const assert = require("assert");
const Choices = require("../static/choices.js");
let n = 0; const t = (name, f) => { f(); n++; };
const S0 = { scope: "School", target: "Whole school", week: "Both", day: "All", strength: "Must" };
const SET = [
  { key: "once_a_day", label: "Same subject at most once a day (per group)", number: false, rule: Object.assign({}, S0, { rule: "Once a day per group" }) },
  { key: "after_school", label: "After-school slot allowed when a class cannot fit", number: false, rule: null },
  { key: "pe_at_once", label: "Most PE classes at the same time", number: true, rule: Object.assign({}, S0, { scope: "Department", target: "PE", rule: "At most N at once" }) },
  { key: "max_day", label: "Most teaching periods a teacher has in a day", number: true, rule: Object.assign({}, S0, { rule: "Max periods a day" }) },
  { key: "recess", label: "Every teacher gets at least one recess a day", number: false, rule: Object.assign({}, S0, { rule: "At least one recess a day" }) },
  { key: "pe_rain_home", label: "In rain, PE goes to the class's home room", number: false, rule: null },
];
const row = (a, b) => ".".repeat(a) + "RR" + ".".repeat(b);
const fixture = () => ({
  school: { levels: ["Sec 1", "Sec 2", "Sec 3"], start_time: "07:30", period_minutes: 20, periods_per_day: 14, after_school: false },
  day_structure: { "Sec 1": { Monday: "..........", Tuesday: row(7, 5) }, "Sec 2": { Monday: row(7, 5) }, "Sec 3": { Monday: "......WW......" } },
  rules: [
    { _id: "r1", scope: "Level", target: "Sec 1", rule: "Not in periods", strength: "Must" },
    { _id: "r2", scope: "School", target: "", rule: "In words", strength: "Prefer", text: "No PE in the first period" },
    { _id: "r3", scope: "School", target: "Whole school", rule: "Max periods a day", number: 6, strength: "Must" },
    { _id: "r4", scope: "Department", target: "PE", rule: "At most N at once", number: 2, strength: "Must" },
  ],
  choices: [],
});
const rowOf = (c) => Object.assign({ _id: "c" + Math.random() }, c);

t("labels and texts for the three kinds", () => {
  const s = fixture();
  const cr = { kind: "rule", order: 1, rule_id: "r1", fallback: "Prefer" };
  const ct = { kind: "rule", order: 2, rule_id: "r2", fallback: "Drop" };
  const cs = { kind: "setting", order: 3, key: "after_school", second: "Yes" };
  const cc = { kind: "recess", order: 4, level: "Sec 2", window: ["09:00", "11:20"] };
  assert.strictEqual(Choices.itemLabel(s, cr, SET), "Rule: Level · Sec 1 · Not in periods");
  assert.strictEqual(Choices.itemLabel(s, ct, SET), "Rule: T1 · Prefer · No PE in the first period");
  assert.strictEqual(Choices.itemLabel(s, cs, SET), "After-school slot allowed when a class cannot fit");
  assert.strictEqual(Choices.itemLabel(s, cc, SET), "Recess for Sec 2");
  assert.strictEqual(Choices.firstText(s, cr, SET), "As written (Must)");
  assert.strictEqual(Choices.firstText(s, cs, SET), "No");
  assert.strictEqual(Choices.firstText(s, cc, SET), "Fixed at 9.50 to 10.30 (periods 7-8)");
  assert.strictEqual(Choices.firstText(s, { kind: "recess", level: "Sec 3" }, SET), "(no fixed recess)");
  assert.strictEqual(Choices.firstText(s, { kind: "setting", key: "max_day" }, SET), "6");
  s.rules.splice(2, 1);
  assert.strictEqual(Choices.firstText(s, { kind: "setting", key: "max_day" }, SET), "no limit");
  assert.strictEqual(Choices.secondText(s, cr), "Make it Prefer");
  assert.strictEqual(Choices.secondText(s, ct), "Drop it");
  assert.strictEqual(Choices.secondText(s, cs), "Yes");
  assert.strictEqual(Choices.secondText(s, cc), "Floating between 9.00 and 11.20");
  assert.strictEqual(Choices.secondText(s, { kind: "rule", fallback: "Instead", instead: { scope: "Level", target: "Sec 1", rule: "Only in periods" } }), "Instead: Level · Sec 1 · Only in periods");
  assert.strictEqual(Choices.secondText(s, { kind: "rule", fallback: "Instead", instead: { rule: "In words", text: " No maths last " } }), "Instead: No maths last");
  assert.strictEqual(Choices.ruleLabel({ scope: "Level", target: "", subject: "Art", rule: "X" }), "Level · Art · X");
  assert.strictEqual(Choices.typedNo(s, 1), 1);
  assert.strictEqual(Choices.ruleIndex(s, cr), 0);
  assert.strictEqual(Choices.ruleIndex(s, { rule_id: "zz" }), null);
  assert.strictEqual(Choices.itemLabel(s, { kind: "rule", rule_id: "zz" }, SET), "(missing) Rule");
});
t("settingValue and recessFirst", () => {
  const s = fixture();
  assert.strictEqual(Choices.settingValue(s, SET, "after_school"), "No");
  delete s.school.after_school; assert.strictEqual(Choices.settingValue(s, SET, "after_school"), "Yes");
  assert.strictEqual(Choices.settingValue(s, SET, "pe_rain_home"), "No");
  assert.strictEqual(Choices.settingValue(s, SET, "pe_at_once"), 2);
  assert.strictEqual(Choices.settingValue(s, SET, "once_a_day"), "No");
  s.rules[3].strength = "Prefer"; assert.strictEqual(Choices.settingValue(s, SET, "pe_at_once"), "");
  assert.deepStrictEqual(Choices.recessFirst(s, "Sec 2"), { from: 7, to: 8, length: 2, text: "9.50 to 10.30" });
  assert.deepStrictEqual(Choices.recessFirst(s, "Sec 1"), { from: 7, to: 8, length: 2, text: "9.50 to 10.30" });
  assert.strictEqual(Choices.recessFirst(s, "Sec 3"), null);
});
t("candidates leave out items with a choice and the rows that stand for settings", () => {
  const s = fixture();
  assert.deepStrictEqual(Choices.candidates(s, SET), { settings: SET.map(x => x.key), rules: [0, 1], levels: ["Sec 1", "Sec 2"] });
  s.choices = [{ kind: "setting", order: 1, key: "recess", second: "No" }, { kind: "rule", order: 2, rule_id: "r1", fallback: "Drop" }, { kind: "recess", order: 3, level: "Sec 2", window: ["09:00", "11:20"] }];
  const c = Choices.candidates(s, SET);
  assert.deepStrictEqual(c.rules, [1]); assert.deepStrictEqual(c.levels, ["Sec 1"]); assert.ok(c.settings.indexOf("recess") < 0 && c.settings.length === 5);
});
t("newSetting refuses the same value, a blank, and a second choice on an item that has one", () => {
  const s = fixture();
  assert.deepStrictEqual(Choices.newSetting(s, SET, "", "Yes"), { error: "Pick the setting." });
  assert.deepStrictEqual(Choices.newSetting(s, SET, "after_school", " "), { error: "Give the second value." });
  assert.deepStrictEqual(Choices.newSetting(s, SET, "after_school", "No"), { error: "The second choice is the same as the first." });
  assert.deepStrictEqual(Choices.newSetting(s, SET, "max_day", "6"), { error: "The second choice is the same as the first." });
  assert.deepStrictEqual(Choices.newSetting(s, SET, "after_school", "Yes"), { i: 0 });
  assert.deepStrictEqual(s.choices, [{ kind: "setting", order: 1, key: "after_school", second: "Yes" }]);
  assert.deepStrictEqual(Choices.newSetting(s, SET, "after_school", "Yes"), { error: "After-school slot allowed when a class cannot fit already has a second choice." });
  assert.deepStrictEqual(Choices.newSetting(s, SET, "max_day", "7"), { i: 1 });
  assert.strictEqual(s.choices[1].order, 2);
});
t("newRule: Prefer, Instead copies the rule without its id, refuses a second choice", () => {
  const s = fixture();
  assert.deepStrictEqual(Choices.newRule(s, "r1", "Prefer"), { i: 0 });
  assert.deepStrictEqual(Choices.newRule(s, "r1", "Drop"), { error: "Rule: Level · Sec 1 · Not in periods already has a second choice." });
  assert.deepStrictEqual(Choices.newRule(s, "r2", "Instead"), { i: 1 });
  const c = s.choices[1]; assert.strictEqual(c.fallback, "Instead"); assert.strictEqual(c.instead._id, undefined); assert.strictEqual(c.instead.text, "No PE in the first period");
  c.instead.text = "x"; assert.strictEqual(s.rules[1].text, "No PE in the first period");
  assert.ok(Choices.newRule(s, "zz", "Drop").error);
});
t("newRecess refuses a short window, a level with no recess and a bad window", () => {
  const s = fixture();
  assert.deepStrictEqual(Choices.newRecess(s, "Sec 2", "09:00", ""), { error: "Give the window as two times." });
  assert.strictEqual(Choices.newRecess(s, "Sec 2", "09:50", "10:10").error, "The window 9.50 to 10.10 is shorter than the recess (2 periods).");
  assert.strictEqual(Choices.newRecess(s, "Sec 1", "09:00", "11:20").error, undefined);   // Sec 1 has a recess on Tuesday
  assert.strictEqual(Choices.newRecess(s, "Sec 3", "09:00", "11:20").error, "Sec 3 already has a floating recess (W on Day structure).");
  s.school.levels.push("Sec 4"); s.day_structure["Sec 4"] = { Monday: ".........." };
  assert.strictEqual(Choices.newRecess(s, "Sec 4", "09:00", "11:20").error, "Sec 4 has no fixed recess (R on Day structure) to float.");
  const s2 = fixture();
  assert.deepStrictEqual(Choices.newRecess(s2, "Sec 2", "09:00", "11:20"), { i: 0 });
  assert.deepStrictEqual(s2.choices[0], { kind: "recess", order: 1, level: "Sec 2", window: ["09:00", "11:20"] });
  assert.strictEqual(Choices.newRecess(s2, "Sec 2", "09:00", "11:20").error, "Recess for Sec 2 already has a second choice.");
});
t("move renumbers 1..n and refuses the first up and the last down", () => {
  const s = fixture(); s.choices = [{ kind: "setting", key: "recess", second: "No", order: 5 }, { kind: "setting", key: "max_day", second: "7", order: 9 }, { kind: "rule", rule_id: "r1", fallback: "Drop", order: 12 }];
  assert.strictEqual(Choices.move(s, 0, -1), false);
  assert.strictEqual(Choices.move(s, 2, 1), false);
  assert.strictEqual(Choices.move(s, 0, 1), true);
  assert.deepStrictEqual(s.choices.map(c => c.order), [2, 1, 3]);
  assert.deepStrictEqual(Choices.ordered(s).map(x => x.i), [1, 0, 2]);
});
t("moveTo puts a row before another, or last", () => {
  const s = fixture(); s.choices = [{ kind: "x", order: 1 }, { kind: "x", order: 2 }, { kind: "x", order: 3 }, { kind: "x", order: 4 }];
  assert.strictEqual(Choices.moveTo(s, 3, 0), true);
  assert.deepStrictEqual(Choices.ordered(s).map(x => x.i), [3, 0, 1, 2]); assert.deepStrictEqual(s.choices.map(c => c.order), [2, 3, 4, 1]);
  assert.strictEqual(Choices.moveTo(s, 3, 0), false);
  assert.strictEqual(Choices.moveTo(s, 3, null), true);
  assert.deepStrictEqual(Choices.ordered(s).map(x => x.i), [0, 1, 2, 3]);
  assert.strictEqual(Choices.moveTo(s, 3, null), false);
  assert.strictEqual(Choices.moveTo(s, 1, 2), false);
  assert.strictEqual(Choices.moveTo(s, 0, 3), true);
  assert.deepStrictEqual(Choices.ordered(s).map(x => x.i), [1, 2, 0, 3]);
});
t("prune removes choices whose rule is gone", () => {
  const s = fixture(); Choices.newRule(s, "r1", "Drop"); Choices.newRule(s, "r2", "Drop"); Choices.newSetting(s, SET, "recess", "Yes");
  s.rules.splice(0, 1);
  assert.strictEqual(Choices.prune(s), 1);
  assert.deepStrictEqual(s.choices.map(c => c.kind + (c.rule_id || c.key)), ["ruler2", "settingrecess"]);
  assert.strictEqual(Choices.prune(s), 0);
});
t("problems read as Python's do", () => {
  const s = fixture(); s.choices = [
    { kind: "setting", key: "nope", second: "Yes" },
    { kind: "setting", key: "recess", second: "" },
    { kind: "setting", key: "max_day", second: "lots" },
    { kind: "setting", key: "recess", second: "Maybe" },
    { kind: "setting", key: "max_day", second: "6" },
    { kind: "rule", rule_id: "gone", fallback: "Drop" },
    { kind: "rule", rule_id: "r1", fallback: "Soften" },
    { kind: "rule", rule_id: "r1", fallback: "Instead", instead: {} },
    { kind: "recess", level: "Sec 3", window: ["09:00", "11:20"] },
    { kind: "recess", level: "Sec 4", window: ["09:00", "11:20"] },
    { kind: "recess", level: "Sec 2", window: ["09:00"] },
    { kind: "recess", level: "Sec 2", window: ["09:50", "10:10"] },
    { kind: "recess", level: "Sec 2", window: ["07:30", "09:00"] },
    { kind: "recess", level: "Sec 2", window: ["09:00", "11:20"] },
    { kind: "wish" },
    { kind: "recess", level: "Sec 1", window: ["09:50", "10:10"] },
  ];
  s.school.levels.push("Sec 4"); s.day_structure["Sec 4"] = { Monday: ".........." };
  s.day_structure["Sec 2"].Tuesday = ".R" + ".".repeat(12);   // a one-period recess on a later day: only the first run counts
  const p = Choices.problems(s, SET);
  assert.deepStrictEqual(p[0], ["'nope' is not a setting the timetable knows."]);
  assert.deepStrictEqual(p[1], ["The second choice is blank."]);
  assert.deepStrictEqual(p[2], ["The second choice must be a whole number or no limit."]);
  assert.deepStrictEqual(p[3], ["The second choice must be Yes or No."]);
  assert.deepStrictEqual(p[4], ["The second choice is the same as the first."]);
  assert.deepStrictEqual(p[5], ["The rule this choice falls back on is no longer on the setup."]);
  assert.deepStrictEqual(p[6], ["Pick Make it Prefer, Instead or Drop it for the second choice."]);
  assert.deepStrictEqual(p[7], ["The Instead rule is not filled in."]);
  assert.deepStrictEqual(p[8], ["Sec 3 already has a floating recess (W on Day structure)."]);
  assert.deepStrictEqual(p[9], ["Sec 4 has no fixed recess (R on Day structure) to float."]);
  assert.deepStrictEqual(p[10], ["The window is missing or cannot be read."]);
  assert.deepStrictEqual(p[11], ["The window 9.50 to 10.10 is shorter than the recess (2 periods)."]);
  assert.deepStrictEqual(p[12], ["The window 7.30 to 9.00 does not include the recess (9.50 to 10.30)."]);
  assert.strictEqual(p[13], undefined);
  assert.deepStrictEqual(p[14], ["This choice is not a setting, a rule or a recess."]);
  assert.deepStrictEqual(p[15], ["The window 9.50 to 10.10 is shorter than the recess (2 periods)."]);
});
t("setFallback copies the rule for Instead once, and only on a rule choice", () => {
  const s = fixture();
  s.choices = [{ kind: "rule", order: 1, rule_id: "r1", fallback: "Drop" }, { kind: "setting", order: 2, key: "recess", second: "No" }];
  assert.strictEqual(Choices.setFallback(s, 0, "Instead"), true);
  assert.deepStrictEqual(s.choices[0].instead, { scope: "Level", target: "Sec 1", rule: "Not in periods", strength: "Must" });
  s.choices[0].instead.from = 3; Choices.setFallback(s, 0, "Prefer"); Choices.setFallback(s, 0, "Instead");
  assert.strictEqual(s.choices[0].instead.from, 3); assert.strictEqual(s.choices[0].fallback, "Instead");
  assert.strictEqual(Choices.setFallback(s, 1, "Drop"), false); assert.strictEqual(s.choices[1].fallback, undefined);
  assert.strictEqual(Choices.setFallback(s, 5, "Drop"), false);
});
console.log(`${n} cases passed`);

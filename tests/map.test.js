// Plain-assert tests for static/map.js (the department map's logic): run with `node tests/map.test.js`
const assert = require("assert");
const DeptMap = require("../static/map.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { levels: ["Sec 1", "Sec 2"], departments: ["MA", "EL"], bands: {} },
  classes: [{ class: "1A", level: "Sec 1", size: 30 }, { class: "1B", level: "Sec 1", size: 30 }, { class: "2A", level: "Sec 2", size: 30 }],
  subjects: [{ subject: "Mathematics", code: "MA", dept: "MA", periods: { "Sec 1": 6, "Sec 2": 6 } }, { subject: "English Language", code: "EL", dept: "EL", periods: { "Sec 1": 6 } }],
  teachers: [{ _id: "ta", name: "Arjun Nair", short: "Arjun", dept: "MA", role: "EO", allowance: 20, can_teach: [{ subject: "Mathematics", levels: "All" }] },
             { _id: "tb", name: "Priya Menon", short: "Priya", dept: "MA", role: "HOD", allowance: 12, other_duties: 4, can_teach: [] },
             { _id: "tc", name: "Wei Lin Tan", short: "Wei Lin", dept: "EL", role: "EO", allowance: 20, can_teach: [{ subject: "English Language", levels: "All" }, { subject: "Mathematics", levels: "Sec 1" }] },
             { _id: "td", name: "Hafiz Osman", short: "Hafiz", dept: "EL", role: "EO", allowance: 20, can_teach: [] }],
  blocks: [{ _id: "b1", block: "Sec 2 Mathematics", level: "Sec 2", classes: ["2A"] }],
  lessons: [{ _id: "l1", level: "Sec 1", subject: "Mathematics", block: null, classes: ["1A", "1B"], teachers: ["Arjun Nair"], students: 30 },
            { _id: "l2", level: "Sec 2", subject: "Mathematics", block: "Sec 2 Mathematics", classes: ["2A"], teachers: ["Arjun Nair"], students: 15 },
            { _id: "l3", level: "Sec 2", subject: "Mathematics", block: "Sec 2 Mathematics", classes: ["2A"], teachers: ["Arjun Nair", "Wei Lin Tan"], students: 15 },
            { _id: "l4", level: "Sec 1", subject: "English Language", block: null, classes: ["1A"], teachers: [], students: 30 }],
  rules: [], students: [], roles: [{ role: "EO", allowance: 20 }, { role: "HOD", allowance: 12 }] });
const infoOf = spec => spec.lessons.map((x, i) => ({ p: 6, tp: 6 * (x.block ? 1 : x.classes.length), code: x.block ? `2MA${i}` : "Entire Class" }));

t("loads: periods deployed plus other duties against the allowance", () => {
  const L = DeptMap.loads(fixture(), infoOf(fixture()));
  assert.deepStrictEqual(L["Arjun Nair"], { lessons: 24, duties: 0, allowance: 20, total: 24, over: true });
  assert.deepStrictEqual(L["Priya Menon"], { lessons: 0, duties: 4, allowance: 12, total: 4, over: false });
  assert.strictEqual(L["Hafiz Osman"].total, 0);
});
t("roster: the department's teachers in setup order, then the visitors", () => {
  assert.deepStrictEqual(DeptMap.roster(fixture(), "MA", []), [0, 1]);
  assert.deepStrictEqual(DeptMap.roster(fixture(), "MA", ["td", "ta", "nobody"]), [0, 1, 3]);
  assert.deepStrictEqual(DeptMap.unplaced(fixture(), [0, 1, 3]), [1, 3]);
});
t("search finds teachers of other departments by name or short name", () => {
  assert.deepStrictEqual(DeptMap.search(fixture(), "wei", "MA"), [2]);
  assert.deepStrictEqual(DeptMap.search(fixture(), "arjun", "MA"), []);
  assert.deepStrictEqual(DeptMap.search(fixture(), "  ", "MA"), []);
});
t("baskets: one per subject of the department, with teachers from any department", () => {
  assert.deepStrictEqual(DeptMap.baskets(fixture(), "MA"), [{ subject: "Mathematics", teachers: [0, 2] }]);
  assert.deepStrictEqual(DeptMap.staffRoom(fixture(), [0, 1]), [1]);
});
t("classes tab: one card per class of a whole-class row, in level then class order", () => {
  const c = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "classes", "");
  assert.deepStrictEqual(c.map(x => [x.kind, x.li, x.cls, x.periods, x.teachers]), [["class", 0, "1A", 6, ["Arjun Nair"]], ["class", 0, "1B", 6, ["Arjun Nair"]]]);
  assert.deepStrictEqual(DeptMap.cards(fixture(), infoOf(fixture()), "EL", "classes", "Sec 2"), []);
});
t("groups and bands tabs", () => {
  const g = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "groups", "");
  assert.deepStrictEqual(g.map(x => [x.kind, x.li, x.title, x.block]), [["group", 1, "2MA1", "Sec 2 Mathematics"], ["group", 2, "2MA2", "Sec 2 Mathematics"]]);
  const b = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "bands", "");
  assert.strictEqual(b.length, 1); assert.strictEqual(b[0].kind, "band"); assert.strictEqual(b[0].groups.length, 2);
  assert.deepStrictEqual(b[0].twice, ["Arjun Nair"]);
  assert.deepStrictEqual(DeptMap.cards(fixture(), infoOf(fixture()), "EL", "bands", ""), []);
});
t("prune keeps only ids that are still teachers", () => { assert.deepStrictEqual(DeptMap.prune(["tb", "gone", "ta"], fixture()), ["tb", "ta"]); });
t("canTeach honours All, a level and a band of levels", () => {
  const tc = fixture().teachers[2];
  assert.ok(DeptMap.canTeach(tc, "Mathematics", "Sec 1", {})); assert.ok(!DeptMap.canTeach(tc, "Mathematics", "Sec 2", {}));
  assert.ok(DeptMap.canTeach({ can_teach: [{ subject: "Mathematics", levels: "Lower Sec" }] }, "Mathematics", "Sec 2", { "Sec 2": "Lower Sec" }));
  assert.ok(!DeptMap.canTeach({ can_teach: [] }, "Mathematics", "Sec 1", {}));
});
t("deploying to one class of a shared whole-class row splits that class off", () => {
  const s = fixture(); const r = DeptMap.deploy(s, { kind: "class", li: 0, cls: "1B" }, [2], {});
  assert.deepStrictEqual(r, { placed: ["Wei Lin Tan"], already: [], refused: [], split: true });
  assert.deepStrictEqual(s.lessons[0].classes, ["1A"]); assert.deepStrictEqual(s.lessons[0].teachers, ["Arjun Nair"]);
  const nw = s.lessons[4]; assert.deepStrictEqual([nw.classes, nw.teachers, nw.subject, nw.level, nw.students], [["1B"], ["Arjun Nair", "Wei Lin Tan"], "Mathematics", "Sec 1", 30]);
  assert.ok(!("_id" in nw) || nw._id !== "l1");
});
t("deploying to a group adds, never replaces, and says who was already there", () => {
  const s = fixture(); const r = DeptMap.deploy(s, { kind: "group", li: 1 }, [0, 2], {});
  assert.deepStrictEqual(r, { placed: ["Wei Lin Tan"], already: ["Arjun Nair"], refused: [], split: false });
  assert.deepStrictEqual(s.lessons[1].teachers, ["Arjun Nair", "Wei Lin Tan"]);
});
t("a teacher not in the basket is refused, or added to it first when asked", () => {
  const s = fixture(); const r = DeptMap.deploy(s, { kind: "group", li: 1 }, [1], {});
  assert.deepStrictEqual(r.refused, [{ name: "Priya Menon", why: "Priya Menon is not in the Mathematics basket." }]);
  assert.deepStrictEqual(s.lessons[1].teachers, ["Arjun Nair"]);
  const r2 = DeptMap.deploy(s, { kind: "group", li: 1 }, [1], { addToBasket: true });
  assert.deepStrictEqual(r2.placed, ["Priya Menon"]); assert.deepStrictEqual(s.teachers[1].can_teach, [{ subject: "Mathematics", levels: "All" }]);
});
t("more than three on a card: none is placed and the card says so", () => {
  const s = fixture(); s.lessons[2].teachers = ["Arjun Nair", "Wei Lin Tan"]; s.teachers[1].can_teach = [{ subject: "Mathematics", levels: "All" }]; s.teachers[3].can_teach = [{ subject: "Mathematics", levels: "All" }];
  const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [1, 3], {});
  assert.deepStrictEqual(r.placed, []); assert.strictEqual(r.refused.length, 2); assert.strictEqual(r.refused[0].why, "2MA2 would have 4 teachers; three is the most.");
  assert.deepStrictEqual(s.lessons[2].teachers, ["Arjun Nair", "Wei Lin Tan"]);
});
t("undeploy takes a teacher off a card, splitting a shared row first", () => {
  const s = fixture(); assert.strictEqual(DeptMap.undeploy(s, { kind: "class", li: 0, cls: "1A" }, "Arjun Nair"), true);
  assert.deepStrictEqual(s.lessons[0].classes, ["1B"]); assert.deepStrictEqual(s.lessons[0].teachers, ["Arjun Nair"]); assert.deepStrictEqual([s.lessons[4].classes, s.lessons[4].teachers], [["1A"], []]);
  assert.strictEqual(DeptMap.undeploy(s, { kind: "group", li: 1 }, "Nobody"), false);
});
t("baskets: adding and removing a subject", () => {
  const s = fixture(); assert.strictEqual(DeptMap.addToBasket(s, [0, 1, 3], "Mathematics"), 2);
  assert.deepStrictEqual(DeptMap.removeFromBasket(s, 0, "Mathematics"), { lessons: 3 });
  assert.deepStrictEqual(s.teachers[0].can_teach, []); assert.deepStrictEqual(s.lessons[0].teachers, ["Arjun Nair"]);
});
t("a new teacher: defaults, a head's is provisional, no second teacher with the same name", () => {
  const s = fixture(); const r = DeptMap.newTeacher(s, { name: "New Mathematics teacher 1", short: "", dept: "MA", role: "EO", allowance: "" }, s.roles, true);
  assert.deepStrictEqual(r, { i: 4 }); assert.deepStrictEqual(s.teachers[4], { name: "New Mathematics teacher 1", short: "New", dept: "MA", role: "EO", allowance: 20, provisional: "Yes", can_teach: [] });
  assert.deepStrictEqual(DeptMap.newTeacher(s, { name: "  priya   MENON", dept: "MA", role: "EO" }, s.roles, false), { error: "Priya Menon is already a teacher." });
  assert.deepStrictEqual(DeptMap.newTeacher(s, { name: " ", dept: "MA" }, s.roles, false), { error: "Give the teacher a name." });
  assert.strictEqual(s.teachers.length, 5);
});
t("needBasket names who must join the basket first, and one deploy then places them all on the split class", () => {
  const s = fixture(); const card = { kind: "class", li: 0, cls: "1B" };
  assert.deepStrictEqual(DeptMap.needBasket(s, card, [2, 1, 0]), ["Priya Menon"]);   // Wei Lin is in the basket, Arjun is on the row already
  const r = DeptMap.deploy(s, card, [2, 1], { addToBasket: true });
  assert.deepStrictEqual([r.placed, r.split, r.refused], [["Wei Lin Tan", "Priya Menon"], true, []]);
  assert.deepStrictEqual([s.lessons[0].classes, s.lessons[0].teachers], [["1A"], ["Arjun Nair"]]);   // the untouched class keeps its teachers
  assert.deepStrictEqual([s.lessons[4].classes, s.lessons[4].teachers], [["1B"], ["Arjun Nair", "Wei Lin Tan", "Priya Menon"]]);
  assert.strictEqual(s.lessons.length, 5);
});
t("a mixed drop that would go past three takes none, even with the basket question answered yes", () => {
  const s = fixture(); s.teachers[1].can_teach = []; s.teachers[3].can_teach = [];
  const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [0, 1, 3], { addToBasket: true });   // Arjun is on it; Priya and Hafiz need the basket
  assert.deepStrictEqual([r.placed, r.already, r.refused.length], [[], ["Arjun Nair"], 2]);   // refused for the count, before anyone joined the basket
  const r2 = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [1, 3], { addToBasket: true });
  assert.deepStrictEqual(r2.placed, []); assert.strictEqual(r2.refused[0].why, "2MA2 would have 4 teachers; three is the most.");
  assert.deepStrictEqual([s.teachers[1].can_teach, s.teachers[3].can_teach, s.lessons[2].teachers], [[], [], ["Arjun Nair", "Wei Lin Tan"]]);
});
t("deploy with opts.max puts a fourth teacher on and refuses a fifth with the number", () => {
  const s = fixture(); s.teachers[1].can_teach = [{ subject: "Mathematics", levels: "All" }]; s.teachers[3].can_teach = [{ subject: "Mathematics", levels: "All" }];
  s.lessons[2].teachers = ["Arjun Nair", "Wei Lin Tan"];
  const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [1, 3], { max: 4 });
  assert.deepStrictEqual(r.placed, ["Priya Menon", "Hafiz Osman"]); assert.strictEqual(s.lessons[2].teachers.length, 4);
  s.teachers[0].can_teach = [{ subject: "Mathematics", levels: "All" }]; s.teachers.push({ name: "Fifth Person", can_teach: [{ subject: "Mathematics", levels: "All" }] });
  const r2 = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [4], { max: 4 });
  assert.deepStrictEqual(r2.placed, []); assert.strictEqual(r2.refused[0].why, "2MA2 would have 5 teachers; four is the most.");
  assert.strictEqual(DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [4], { max: 6 }).placed.length, 1);
  const r3 = DeptMap.deploy(fixture(), { kind: "group", li: 2, title: "2MA2" }, [1, 3], {});   // no opts.max: three, as before
  assert.deepStrictEqual(r3.placed, []);
});
t("without opts.max a fourth teacher is refused with three is the most", () => {
  const s = fixture(); s.lessons[2].teachers = ["Arjun Nair", "Wei Lin Tan", "Priya Menon"]; s.teachers[3].can_teach = [{ subject: "Mathematics", levels: "All" }];
  const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [3], {});
  assert.strictEqual(r.refused[0].why, "2MA2 would have 4 teachers; three is the most.");
});
t("opts.exempt lets a teacher on with no basket entry, and needBasket does not ask about them", () => {
  const s = fixture(); const card = { kind: "class", li: 0, cls: "1B" }, ex = nm => nm === "Priya Menon";
  assert.deepStrictEqual(DeptMap.needBasket(s, card, [1, 3], {}), ["Priya Menon", "Hafiz Osman"]);
  assert.deepStrictEqual(DeptMap.needBasket(s, card, [1, 3], { exempt: ex }), ["Hafiz Osman"]);
  assert.deepStrictEqual(DeptMap.needBasket(s, card, [1], { exempt: ex }), []);
  const r = DeptMap.deploy(s, card, [1], { exempt: ex });
  assert.deepStrictEqual([r.placed, r.refused], [["Priya Menon"], []]);
  assert.deepStrictEqual(s.teachers[1].can_teach, []);   // exempt is not the basket: nothing is added to it
  const r2 = DeptMap.deploy(s, { kind: "group", li: 1 }, [3], { exempt: ex });   // someone else, outside the basket, is still refused
  assert.strictEqual(r2.refused.length, 1);
});
console.log(`${n} cases passed`);

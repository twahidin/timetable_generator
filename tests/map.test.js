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
t("a teacher of any department with no can_teach is placed at once, and nobody's can_teach is written", () => {
  const s = fixture(); const before = JSON.stringify(s.teachers.map(x => x.can_teach));
  const r = DeptMap.deploy(s, { kind: "group", li: 1 }, [1, 3], {});
  assert.deepStrictEqual([r.placed, r.refused], [["Priya Menon", "Hafiz Osman"], []]);
  assert.deepStrictEqual(s.lessons[1].teachers, ["Arjun Nair", "Priya Menon", "Hafiz Osman"]);
  assert.strictEqual(JSON.stringify(s.teachers.map(x => x.can_teach)), before);   // a stored list is unchanged, an empty one stays empty
  const s2 = fixture(); delete s2.teachers[1].can_teach;
  DeptMap.deploy(s2, { kind: "group", li: 1 }, [1], {}); assert.ok(!("can_teach" in s2.teachers[1]));
});
t("unplaced: the teachers on no lesson row", () => {
  assert.deepStrictEqual(DeptMap.unplaced(fixture(), [0, 1, 2, 3]), [1, 3]);
  assert.deepStrictEqual(DeptMap.unplaced(fixture(), [1]), [1]);
  assert.deepStrictEqual(DeptMap.unplaced(fixture(), [0, 2, 9]), []);
  const s = fixture(); s.teachers[1].can_teach = [{ subject: "Mathematics", levels: "All" }];   // a stored list does not count as a lesson
  assert.deepStrictEqual(DeptMap.unplaced(s, [0, 1]), [1]);
  s.lessons[3].teachers = ["Priya Menon"]; assert.deepStrictEqual(DeptMap.unplaced(s, [0, 1]), []);
});
t("more than three on a card: none is placed and the card says so", () => {
  const s = fixture(); s.lessons[2].teachers = ["Arjun Nair", "Wei Lin Tan"];
  const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [1, 3], {});
  assert.deepStrictEqual(r.placed, []); assert.strictEqual(r.refused.length, 2); assert.strictEqual(r.refused[0].why, "2MA2 would have 4 teachers; three is the most.");
  assert.deepStrictEqual(s.lessons[2].teachers, ["Arjun Nair", "Wei Lin Tan"]);
});
t("undeploy on the row itself (a group card) takes the teacher off the whole row: no split, the other teachers stay", () => {
  const s = fixture(), n = s.lessons.length;
  assert.strictEqual(DeptMap.undeploy(s, { kind: "group", li: 0 }, "Arjun Nair"), true);   // a row of two classes, as the Groups and bands list shows it
  assert.deepStrictEqual([s.lessons[0].classes, s.lessons[0].teachers, s.lessons.length], [["1A", "1B"], [], n]);
  assert.strictEqual(DeptMap.undeploy(s, { kind: "group", li: 2 }, "Arjun Nair"), true); assert.deepStrictEqual(s.lessons[2].teachers, ["Wei Lin Tan"]);
  assert.strictEqual(DeptMap.undeploy(s, { kind: "group", li: 2 }, "Arjun Nair"), false); assert.strictEqual(DeptMap.undeploy(s, { kind: "group", li: 99 }, "Arjun Nair"), false);
});
t("undeploy takes a teacher off a card, splitting a shared row first", () => {
  const s = fixture(); assert.strictEqual(DeptMap.undeploy(s, { kind: "class", li: 0, cls: "1A" }, "Arjun Nair"), true);
  assert.deepStrictEqual(s.lessons[0].classes, ["1B"]); assert.deepStrictEqual(s.lessons[0].teachers, ["Arjun Nair"]); assert.deepStrictEqual([s.lessons[4].classes, s.lessons[4].teachers], [["1A"], []]);
  assert.strictEqual(DeptMap.undeploy(s, { kind: "group", li: 1 }, "Nobody"), false);
});
t("a new teacher: defaults, a head's is provisional, no second teacher with the same name", () => {
  const s = fixture(); const r = DeptMap.newTeacher(s, { name: "New Mathematics teacher 1", short: "", dept: "MA", role: "EO", allowance: "" }, s.roles, true);
  assert.deepStrictEqual(r, { i: 4 }); assert.deepStrictEqual(s.teachers[4], { name: "New Mathematics teacher 1", short: "New", dept: "MA", role: "EO", allowance: 20, provisional: "Yes" });
  assert.deepStrictEqual(DeptMap.newTeacher(s, { name: "  priya   MENON", dept: "MA", role: "EO" }, s.roles, false), { error: "Priya Menon is already a teacher." });
  assert.deepStrictEqual(DeptMap.newTeacher(s, { name: " ", dept: "MA" }, s.roles, false), { error: "Give the teacher a name." });
  assert.strictEqual(s.teachers.length, 5);
});
t("deploy with opts.max puts a fourth teacher on and refuses a fifth with the number", () => {
  const s = fixture(); s.lessons[2].teachers = ["Arjun Nair", "Wei Lin Tan"];
  const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [1, 3], { max: 4 });
  assert.deepStrictEqual(r.placed, ["Priya Menon", "Hafiz Osman"]); assert.strictEqual(s.lessons[2].teachers.length, 4);
  s.teachers.push({ name: "Fifth Person" });
  const r2 = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [4], { max: 4 });
  assert.deepStrictEqual(r2.placed, []); assert.strictEqual(r2.refused[0].why, "2MA2 would have 5 teachers; four is the most.");
  assert.strictEqual(DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [4], { max: 6 }).placed.length, 1);
  const r3 = DeptMap.deploy(fixture(), { kind: "group", li: 2, title: "2MA2" }, [1, 3], {});   // no opts.max: three, as before
  assert.deepStrictEqual(r3.placed, []);
});
t("without opts.max a fourth teacher is refused with three is the most", () => {
  const s = fixture(); s.lessons[2].teachers = ["Arjun Nair", "Wei Lin Tan", "Priya Menon"];
  const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [3], {});
  assert.strictEqual(r.refused[0].why, "2MA2 would have 4 teachers; three is the most.");
});
t("the refusal says the number: three, four, five, six", () => {
  [[3, "three"], [4, "four"], [5, "five"], [6, "six"]].forEach(([m, w]) => {
    const s = fixture(); s.lessons[2].teachers = Array.from({ length: m }, (_, k) => "Person " + k);
    const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [1], m === 3 ? {} : { max: m });
    assert.strictEqual(r.refused[0].why, `2MA2 would have ${m + 1} teachers; ${w} is the most.`);
  });
});
/* a second fixture for the department page: a Mathematics department with three subjects in an order that is not alphabetical,
   a band with a group of another department, a teacher with a second department, a level the school does not list */
const pageFixture = () => ({
  school: { levels: ["Sec 1", "Sec 2"], departments: ["MA", "SC"], bands: {} },
  classes: [{ class: "1B", level: "Sec 1", size: 28 }, { class: "1A", level: "Sec 1", size: 30 }, { class: "1C", level: "Sec 1" },
            { class: "2A", level: "Sec 2", size: 32 }, { class: "2B", level: "Sec 2", size: 30 }],
  subjects: [{ subject: "Mathematics", code: "MA", dept: "MA" }, { subject: "Science", code: "SC", dept: "SC" }, { subject: "Statistics", code: "ST", dept: "MA" },
             { subject: "Additional Mathematics", code: "AM", dept: "MA" }],
  teachers: [{ _id: "ta", name: "Ann Lee", short: "Ann", dept: "MA" }, { _id: "tb", name: "Bo Chan", short: "Bo", dept: "MA" },
             { _id: "tc", name: "Cy Wong", short: "Cy", dept: "SC", dept2: "MA" }, { _id: "td", name: "Di Ross", short: "Di", dept: "SC" }],
  blocks: [{ _id: "b1", block: "Sec 2 Option", level: "Sec 2", classes: ["2A", "2B"] }],
  lessons: [
    { level: "Sec 1", subject: "Mathematics", block: null, classes: ["1A", "1B"], teachers: ["Ann Lee"], students: 58 },        // 0
    { level: "Sec 1", subject: "Mathematics", block: null, classes: ["1C"], teachers: [] },                                    // 1
    { level: "Sec 1", subject: "Statistics", block: null, classes: ["1A"], teachers: ["Bo Chan"] },                            // 2
    { level: "Sec 2", subject: "Mathematics", block: null, classes: ["2A"], teachers: ["Ann Lee"] },                           // 3
    { level: "Sec 2", subject: "Additional Mathematics", block: "Sec 2 Option", classes: ["2A"], teachers: ["Bo Chan", "Cy Wong"], students: 24 },   // 4
    { level: "Sec 2", subject: "Statistics", block: "Sec 2 Option", classes: ["2B"], teachers: ["Bo Chan"], students: "" },     // 5
    { level: "Sec 2", subject: "Science", block: "Sec 2 Option", classes: ["2A"], teachers: ["Di Ross"], students: 22 },        // 6
    { level: "Sec 2", subject: "Mathematics", block: "Loose", classes: ["2B"], teachers: ["Ann Lee"], students: 20 },           // 7 (a block no band names)
    { level: "Sec 1", subject: "Statistics", block: "Old band", classes: ["1C"], teachers: ["Cy Wong"], students: 18 },         // 8
    { level: "Sec 9", subject: "Mathematics", block: null, classes: ["9Z"], teachers: ["Ann Lee"] },                           // 9 (a level the school does not list)
    { level: "Sec 2", subject: "Statistics", block: null, classes: ["2B"], teachers: [] },                                     // 10
    { level: "Sec 1", subject: "Science", block: null, classes: ["1A"], teachers: ["Di Ross"] }                                // 11
  ], rules: [], students: [], roles: [] });
const shape = P => P.map(l => [l.level, l.sections.map(x => x.kind === "band" ? "band:" + x.title : x.subject)]);
const key = c => c.kind + "|" + c.li + "|" + (c.cls || "");
const cardsOf = P => { const out = []; P.forEach(l => l.sections.forEach(x => (x.cards || x.groups).forEach(c => out.push(c)))); return out; };

t("roster and search count a second department", () => {
  const s = pageFixture();
  assert.deepStrictEqual(DeptMap.roster(s, "MA", []), [0, 1, 2]);
  assert.deepStrictEqual(DeptMap.roster(s, "SC", []), [2, 3]);
  assert.deepStrictEqual(DeptMap.roster(s, "MA", ["td", "ta"]), [0, 1, 2, 3]);
  assert.deepStrictEqual(DeptMap.search(s, "cy", "MA"), []);
  assert.deepStrictEqual(DeptMap.search(s, "cy", "EL"), [2]);
  assert.deepStrictEqual(DeptMap.search(s, "di", "MA"), [3]);
  s.teachers[2].dept2 = "SC";   // the same as home: none
  assert.deepStrictEqual(DeptMap.roster(s, "MA", []), [0, 1]);
});
t("the page: levels first, then subjects in step 3's order, a band as a lane at its first subject's place", () => {
  assert.deepStrictEqual(shape(DeptMap.page(pageFixture(), infoOf(pageFixture()), "MA", "")), [
    ["Sec 1", ["Mathematics", "Statistics"]],
    ["Sec 2", ["Mathematics", "Statistics", "band:Sec 2 Option"]],     // Additional Mathematics has only band groups, so no section of its own
    ["Sec 9", ["Mathematics"]]]);
  const s = pageFixture(); s.subjects = [s.subjects[3], s.subjects[0], s.subjects[1], s.subjects[2]];   // Additional Mathematics first: the lane follows it
  assert.deepStrictEqual(shape(DeptMap.page(s, infoOf(s), "MA", ""))[1], ["Sec 2", ["band:Sec 2 Option", "Mathematics", "Statistics"]]);
  const s2 = pageFixture(); s2.subjects = [s2.subjects[0], s2.subjects[1], s2.subjects[3], s2.subjects[2]];   // Additional Mathematics before Statistics: the lane sits at Additional Mathematics
  assert.deepStrictEqual(shape(DeptMap.page(s2, infoOf(s2), "MA", ""))[1], ["Sec 2", ["Mathematics", "band:Sec 2 Option", "Statistics"]]);
});
t("a subject's section: its class cards in the class list's order, then its groups in no band", () => {
  const P = DeptMap.page(pageFixture(), infoOf(pageFixture()), "MA", "");
  const s1 = P[0].sections, s2 = P[1].sections;
  assert.deepStrictEqual(s1[0].cards.map(c => [c.kind, c.li, c.cls || c.title]), [["class", 0, "1B"], ["class", 0, "1A"], ["class", 1, "1C"]]);
  assert.deepStrictEqual(s1[1].cards.map(c => [c.kind, c.li, c.cls || c.title]), [["class", 2, "1A"], ["group", 8, "2MA8"]]);
  assert.deepStrictEqual(s2[0].cards.map(c => [c.kind, c.li, c.cls || c.title]), [["class", 3, "2A"], ["group", 7, "2MA7"]]);
  assert.deepStrictEqual(s2[1].cards.map(c => [c.kind, c.li, c.cls || c.title]), [["class", 10, "2B"]]);
  const c = s1[0].cards[0];
  assert.deepStrictEqual([c.subject, c.level, c.periods, c.teachers, c.block, c.title], ["Mathematics", "Sec 1", 6, ["Ann Lee"], null, "1B"]);
  const g = s2[0].cards[1];
  assert.deepStrictEqual([g.subject, g.level, g.periods, g.teachers, g.block], ["Mathematics", "Sec 2", 6, ["Ann Lee"], "Loose"]);
});
t("a class card shows the class's size, a group card the group's students, and neither when blank", () => {
  const P = DeptMap.page(pageFixture(), infoOf(pageFixture()), "MA", "");
  const by = {}; cardsOf(P).forEach(c => { by[key(c)] = c.students; });
  assert.deepStrictEqual(by, { "class|0|1B": 28, "class|0|1A": 30, "class|1|1C": null, "class|2|1A": 30, "group|8|": 18,
    "class|3|2A": 32, "group|7|": 20, "class|10|2B": 30, "group|4|": 24, "group|5|": null, "class|9|9Z": null });
});
t("a lane holds only this department's groups, and names a teacher on two of them", () => {
  const P = DeptMap.page(pageFixture(), infoOf(pageFixture()), "MA", "");
  const lane = P[1].sections[2];
  assert.deepStrictEqual([lane.kind, lane.bi, lane.title], ["band", 0, "Sec 2 Option"]);
  assert.deepStrictEqual(lane.groups.map(g => [g.li, g.title, g.subject, g.teachers]), [[4, "2MA4", "Additional Mathematics", ["Bo Chan", "Cy Wong"]], [5, "2MA5", "Statistics", ["Bo Chan"]]]);
  assert.deepStrictEqual(lane.twice, ["Bo Chan"]);
  const sc = DeptMap.page(pageFixture(), infoOf(pageFixture()), "SC", "");   // the other department sees only its own group of the band
  assert.deepStrictEqual(shape(sc), [["Sec 1", ["Science"]], ["Sec 2", ["band:Sec 2 Option"]]]);
  assert.deepStrictEqual(sc[1].sections[0].groups.map(g => g.li), [6]); assert.deepStrictEqual(sc[1].sections[0].twice, []);
});
t("one level only; a department with no lessons; a row with no subject, no level or a level the school does not list", () => {
  const s = pageFixture(), inf = infoOf(s);
  assert.deepStrictEqual(DeptMap.page(s, inf, "MA", "Sec 2").map(l => l.level), ["Sec 2"]);
  assert.deepStrictEqual(DeptMap.page(s, inf, "MA", "Sec 2")[0].sections.length, 3);
  assert.deepStrictEqual(DeptMap.page(s, inf, "MA", "Sec 9").map(l => l.level), ["Sec 9"]);
  assert.deepStrictEqual(DeptMap.page(s, inf, "MA", "Sec 3"), []);
  assert.deepStrictEqual(DeptMap.page(s, inf, "PE", ""), []);
  assert.doesNotThrow(() => DeptMap.page({ lessons: [null, {}, { subject: "Mathematics", level: "Sec 9", classes: "x" }] }, [], "MA", ""));
  const odd = { subjects: [{ subject: "Mathematics", dept: "MA" }], lessons: [{ subject: "Mathematics", classes: ["1A"] }, { level: "Sec 1", classes: ["1A"] }] };
  const P = DeptMap.page(odd, [], "MA", "");
  assert.deepStrictEqual(shape(P), [["", ["Mathematics"]]]);   // a row with no level is kept under "", a row with no subject is not on any page
  assert.deepStrictEqual([P[0].sections[0].cards[0].students, P[0].sections[0].cards[0].periods], [null, undefined]);
});
t("every card of the old three tabs is on the page exactly once, for every department", () => {
  const s = pageFixture(), inf = infoOf(s), depts = Array.from(new Set(s.subjects.map(x => x.dept)));
  assert.deepStrictEqual(depts, ["MA", "SC"]);
  depts.forEach(d => {
    const old = DeptMap.cards(s, inf, d, "classes", "").concat(DeptMap.cards(s, inf, d, "groups", "")).map(key).sort();
    const now = cardsOf(DeptMap.page(s, inf, d, "")).map(key).sort();
    assert.ok(old.length > 0); assert.deepStrictEqual(now, old);
    ["Sec 1", "Sec 2", "Sec 9"].forEach(lv => {   // and one level at a time
      const o = DeptMap.cards(s, inf, d, "classes", lv).concat(DeptMap.cards(s, inf, d, "groups", lv)).map(key).sort();
      assert.deepStrictEqual(cardsOf(DeptMap.page(s, inf, d, lv)).map(key).sort(), o);
    });
  });
});
t("a band whose groups sit at two levels has a lane in each, each group once, and twice names a teacher on one group at each level", () => {
  const s = pageFixture();
  s.blocks.push({ _id: "b2", block: "Mixed band", level: "Sec 1", classes: [] });   // its own level is not where its groups are
  s.lessons.push({ level: "Sec 1", subject: "Mathematics", block: "Mixed band", classes: ["1A"], teachers: ["Bo Chan"], students: 10 },    // 12
                 { level: "Sec 2", subject: "Statistics", block: "Mixed band", classes: ["2B"], teachers: ["Bo Chan", "Ann Lee"], students: 12 },   // 13
                 { level: "Sec 2", subject: "Science", block: "Mixed band", classes: ["2B"], teachers: ["Di Ross"] });   // 14, another department
  const P = DeptMap.page(s, infoOf(s), "MA", "");
  const lanes = P.map(l => [l.level, l.sections.filter(x => x.kind === "band" && x.title === "Mixed band")]);
  assert.deepStrictEqual(lanes.map(([l, a]) => [l, a.length]), [["Sec 1", 1], ["Sec 2", 1], ["Sec 9", 0]]);
  assert.deepStrictEqual(lanes[0][1][0].groups.map(g => g.li), [12]); assert.deepStrictEqual(lanes[1][1][0].groups.map(g => g.li), [13]);
  assert.deepStrictEqual(lanes[0][1][0].twice, ["Bo Chan"]); assert.deepStrictEqual(lanes[1][1][0].twice, ["Bo Chan"]);   // over every level, as cards(..., "bands") does
  const all = cardsOf(P).map(key), old = DeptMap.cards(s, infoOf(s), "MA", "classes", "").concat(DeptMap.cards(s, infoOf(s), "MA", "groups", "")).map(key);
  assert.deepStrictEqual(all.sort(), old.sort()); assert.strictEqual(new Set(all).size, all.length);
  assert.deepStrictEqual(DeptMap.cards(s, infoOf(s), "MA", "bands", "").find(b => b.title === "Mixed band").twice, ["Bo Chan"]);
  assert.deepStrictEqual(DeptMap.page(s, infoOf(s), "MA", "Sec 2").map(l => l.level), ["Sec 2"]);   // one level: its lane only
});
t("a band at Sec 1 whose groups are all at Sec 2 shows only under Sec 2, each group once", () => {
  const s = pageFixture();
  s.blocks.push({ _id: "b3", block: "Odd band", level: "Sec 1", classes: [] });
  s.lessons.push({ level: "Sec 2", subject: "Mathematics", block: "Odd band", classes: ["2A"], teachers: ["Ann Lee"], students: 5 },    // 12
                 { level: "Sec 2", subject: "Statistics", block: "Odd band", classes: ["2B"], teachers: ["Bo Chan"], students: 6 });    // 13
  const P = DeptMap.page(s, infoOf(s), "MA", ""), at = l => P.find(x => x.level === l).sections.filter(x => x.kind === "band" && x.title === "Odd band");
  assert.strictEqual(at("Sec 1").length, 0); assert.strictEqual(at("Sec 2").length, 1);
  assert.deepStrictEqual(at("Sec 2")[0].groups.map(g => g.li), [12, 13]);
  const all = cardsOf(P).map(key); assert.strictEqual(new Set(all).size, all.length);
  assert.ok(all.includes("group|12|") && all.includes("group|13|"));
});
console.log(`${n} cases passed`);

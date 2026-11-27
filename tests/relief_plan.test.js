// Plain-assert tests for the "free then" list the Relief page draws (Relief.freeList in static/relief-plan.js): run with `node tests/relief_plan.test.js`.
// The page's own scripts run in a small stand-in for the browser (tests/dom.js), against a free-route answer written here.
const assert = require("assert");
const { open, run } = require("./dom.js");

const SAM = "Mr Sam Tan", MAYA = "Ms Maya Lee", RUTH = "Ms Ruth Goh";
const LESSON = { date: "2026-10-13", p: 5, n: 2, classes: ["1A"], subject: "Science", group: "" };
const OLD = "on an exam duty or at an event then", LABEL = "busy then (an exam duty, an event or a teacher-only period)";

function list(busy) {
  const p = open("relief.html", { server: () => ({ status: 200, data: {} }), hash: "" });
  p.run("relief-form.js", "relief.js", "relief-plan.js");
  const data = { groups: [{ title: "Other departments", people: [{ name: RUTH, depts: [], subjects: [], fat: false, week: 1, today: 0, term: 0, marks: [], over: false }] }], teaching: [], busy };
  return p.window.Relief.freeList({ data, x: LESSON, chosen: "", also: new Map(), busy: false, teaching: false, duty: true });
}

run([
  ["the fold counts the busy people and says what they may be busy with", () => {
    const html = list([{ name: SAM, why: "Invigilating: Maths" }, { name: MAYA, why: "Teacher-only period: Staff meeting" }]);
    assert.ok(html.includes(`the 2 ${LABEL}`), html);
    assert.ok(!html.includes(OLD), html);
    assert.ok(html.includes(`${SAM} (Invigilating: Maths), ${MAYA} (Teacher-only period: Staff meeting)`), html);
  }],
  ["no one busy shows no fold", () => {
    assert.ok(!list([]).includes("busy then"));
  }],
]);

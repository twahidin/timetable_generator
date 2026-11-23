const assert = require("assert");
const AdminView = require("../static/adminview.js");
let n = 0; const t = (name, f) => { f(); n++; };

/* made-up people, in the shape GET /api/admin/people sends */
const P = (name, group, x, more) => Object.assign({ name, group, depts: [], staff_only: false, off: false, gives: [], strong: false,
  extras: Object.assign({ timetable: false, relief: false, exams: null, admin: false }, x || {}) }, more || {});
const ALL = P("Lim Wei Jie", "hod", { timetable: true, relief: true, exams: "2026-12-31", admin: true }, { depts: ["MA"] });
const NONE = P("Chloe Yeo", "teacher", {}, { depts: ["SC"] });
const OFF = P("Marcus Goh", "teacher", {}, { off: true, depts: ["HUM"] });
const OFF_RELIEF = P("Farah Ismail", "teacher", { relief: true }, { off: true, depts: ["EL"] });
const ADDED = P("Nora Pillai", "executive", {}, { staff_only: true });
const EXAMS = P("Siti Aminah", "sh", { exams: "2026-01-05" }, { depts: ["MT"] });
const PEOPLE = [ALL, NONE, OFF, OFF_RELIEF, ADDED, EXAMS];
const names = list => list.map(p => p.name);
const F = o => Object.assign({ q: "", role: "", committee: "", dept: "" }, o);

t("committees: all three and Admin, in order, with the exams day written out", () => {
  assert.deepStrictEqual(AdminView.committees(ALL), [
    { key: "timetable", text: "Timetable committee" }, { key: "relief", text: "Relief team" },
    { key: "exams", text: "Exams and events · to 31 Dec 2026" }, { key: "admin", text: "Admin" }]);
});
t("committees: none gives an empty list", () => {
  assert.deepStrictEqual(AdminView.committees(NONE), []);
  assert.deepStrictEqual(AdminView.committees({ name: "No extras" }), []);
});
t("committees: a passed exams day still shows", () => {
  assert.deepStrictEqual(AdminView.committees(EXAMS), [{ key: "exams", text: "Exams and events · to 5 Jan 2026" }]);
});

t("shown: no filter shows everyone", () => { assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({}))), names(PEOPLE)); });
t("shown: search ignores capitals and spaces around it", () => {
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ q: "  LIM wei " }))), ["Lim Wei Jie"]);
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ q: "zzz" }))), []);
});
t("shown: role and department", () => {
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ role: "teacher" }))), ["Chloe Yeo", "Marcus Goh", "Farah Ismail"]);
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ dept: "MA" }))), ["Lim Wei Jie"]);
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ role: "sh", dept: "MA" }))), []);
});
t("shown: each committee and Admin", () => {
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ committee: "timetable" }))), ["Lim Wei Jie"]);
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ committee: "relief" }))), ["Lim Wei Jie", "Farah Ismail"]);
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ committee: "exams" }))), ["Lim Wei Jie", "Siti Aminah"]);
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ committee: "admin" }))), ["Lim Wei Jie"]);
});
t("shown: switched off people under Switched off, and under No committee only when they have none", () => {
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ committee: "off" }))), ["Marcus Goh", "Farah Ismail"]);
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ committee: "none" }))), ["Chloe Yeo", "Marcus Goh", "Nora Pillai"]);
});
t("shown: filters add up", () => {
  assert.deepStrictEqual(names(AdminView.shown(PEOPLE, F({ committee: "off", q: "farah" }))), ["Farah Ismail"]);
});

const ON_TT = "is on the published timetable, so they cannot be removed: they would come straight back. Switch them off instead.";
t("canRemove: a person added by name can be removed", () => {
  assert.deepStrictEqual(AdminView.canRemove(ADDED, "Lim Wei Jie"), { ok: true, why: "" });
});
t("canRemove: a person on the timetable cannot, with the sentence", () => {
  assert.deepStrictEqual(AdminView.canRemove(NONE, "Lim Wei Jie"), { ok: false, why: `Chloe Yeo ${ON_TT}` });
});
t("canRemove: the admin themselves cannot", () => {
  const me = P("Hafiz Osman", "executive", { timetable: true, admin: true }, { staff_only: true });
  assert.deepStrictEqual(AdminView.canRemove(me, "Hafiz Osman"), { ok: false, why: "You cannot remove yourself." });
});
t("canRemove: the admin on the timetable gets the timetable sentence", () => {
  assert.deepStrictEqual(AdminView.canRemove(ALL, "Lim Wei Jie"), { ok: false, why: `Lim Wei Jie ${ON_TT}` });
});

t("noPassword: a strong line and no password account", () => {
  const p = P("Grace Ong", "hod", {}, { gives: [{ text: "Sees the published timetable and the files.", strong: false }, { text: "Setup: no department ticked yet, so nothing to change.", strong: true }] });
  assert.strictEqual(AdminView.noPassword(p), "The lines marked ✱ need a password account. Grace Ong has none yet.");
  assert.strictEqual(AdminView.noPassword(Object.assign({}, p, { strong: true })), "");
});
t("noPassword: no strong line, nothing to say", () => {
  assert.strictEqual(AdminView.noPassword(P("Arjun Menon", "teacher", {}, { gives: [{ text: "Sees the published timetable and the files.", strong: false }] })), "");
  assert.strictEqual(AdminView.noPassword(P("Arjun Menon", "teacher")), "");
  assert.strictEqual(AdminView.noPassword({ name: "No gives" }), "");
});

t("wholeDay: only a whole date from the year 2000 on", () => {
  assert.strictEqual(AdminView.wholeDay("2026-12-31"), true);
  assert.strictEqual(AdminView.wholeDay("2000-01-01"), true);
  assert.strictEqual(AdminView.wholeDay("2028-02-29"), true);
  assert.strictEqual(AdminView.wholeDay("0002-12-31"), false);   /* Chrome's value at the first digit of a typed year */
  assert.strictEqual(AdminView.wholeDay("0202-12-31"), false);
  assert.strictEqual(AdminView.wholeDay("1999-12-31"), false);
  assert.strictEqual(AdminView.wholeDay(""), false);
  assert.strictEqual(AdminView.wholeDay(null), false);
  assert.strictEqual(AdminView.wholeDay("31/12/2026"), false);
  assert.strictEqual(AdminView.wholeDay("2026-02-30"), false);
  assert.strictEqual(AdminView.wholeDay("2026-13-01"), false);
});

console.log(`adminview: ${n} passed`);

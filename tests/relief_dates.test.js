// Plain-assert tests for the dates of a relief absence (static/relief-form.js): run with `node tests/relief_dates.test.js`.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const window = {}, ctx = vm.createContext({ window, document: { querySelector: () => null } });
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "static", "relief-form.js"), "utf8"), ctx);
const RF = window.ReliefForm;

let n = 0; const t = (name, f) => { try { f(); n++; } catch (e) { console.error("FAIL", name); throw e; } };
const oct = (...x) => x.map(d => `2026-10-${String(d).padStart(2, "0")}`);

/* ---- Calendar, Task 2 ---- */
t("dayRuns: two dates are listed", () => assert.strictEqual(RF.dayRuns(oct(13, 14)), "Tue 13 Oct, Wed 14 Oct"));
t("dayRuns: three in a row is a run", () => assert.strictEqual(RF.dayRuns(oct(12, 13, 14)), "Mon 12 Oct – Wed 14 Oct"));
t("dayRuns: a weekend joins", () => assert.strictEqual(RF.dayRuns(oct(15, 16, 19, 20)), "Thu 15 Oct – Tue 20 Oct"));
t("dayRuns: a missing weekday breaks it", () => assert.strictEqual(RF.dayRuns(oct(21, 22, 26, 27)), "Wed 21 Oct, Thu 22 Oct, Mon 26 Oct, Tue 27 Oct"));
t("dayRuns: unsorted with a duplicate", () => assert.strictEqual(RF.dayRuns(oct(20, 16, 12, 13, 14, 15, 13)), "Mon 12 Oct – Fri 16 Oct, Tue 20 Oct"));
t("dayRuns: none is empty", () => { assert.strictEqual(RF.dayRuns([]), ""); assert.strictEqual(RF.dayRuns(null), ""); });
t("dayRuns: a label names each date", () => assert.strictEqual(RF.dayRuns(oct(12, 13, 14), d => d === "2026-10-12" ? "Today" : RF.day(d)), "Today – Wed 14 Oct"));

console.log(`${n} relief dates tests passed`);

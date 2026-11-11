// The page's split(periods, lesson length) must agree with ttgen.spec.lesson_split and never give a fraction
// (a fraction made every view throw: Array(0.33)). Run with `node tests/split.test.js`.
const assert = require("assert"), fs = require("fs"), path = require("path");
const src = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8");
const line = (src.match(/^function split\(p, L\) \{.*$/m) || [])[0]; assert.ok(line, "split(p, L) not found in static/app.js");
const split = new Function(line.slice(0, line.lastIndexOf("}") + 1) + "; return split;")();   // the function, without the comment after it
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "split_cases.json"), "utf8"));
let n = 0;
for (const [p, L, full, short] of cases) {
  const got = split(p, L);
  assert.ok(Number.isInteger(got[0]) && Number.isInteger(got[1]) && got[0] >= 0 && got[1] >= 0, `split(${p}, ${L}) gave ${JSON.stringify(got)}`);
  assert.deepStrictEqual(got, [full, short], `split(${p}, ${L})`); n++;
}
console.log(`${n} cases passed`);

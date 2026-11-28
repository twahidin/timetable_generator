// Plain-assert tests for static/schooltime.js (a clock time written the school's way): run with `node tests/schooltime.test.js`.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const ST = require("../static/schooltime.js");
let n = 0;
const t = (name, f) => { f(); n++; };

t("text", () => {
  const cases = { "07:45": "7.45", "13:00–14:30": "1.00–2.30", "07:45,08:00": "7.45,8.00", "00:10": "12.10", "12:40": "12.40",
    "2026-10-05": "2026-10-05", "Room 12: 30 seats": "Room 12: 30 seats", "1207:45": "1207:45", "24:00": "24:00", "12:75": "12:75" };
  for (const k of Object.keys(cases)) assert.strictEqual(ST.text(k), cases[k], k);
  assert.strictEqual(ST.text(null), "");
  assert.strictEqual(ST.text(undefined), "");
});

const text = v => ({ nodeType: 3, nodeValue: v, parentNode: null });
const el = (tag, attrs, kids) => {
  const e = { nodeType: 1, tagName: tag, parentNode: null, childNodes: kids, hasAttribute: a => a in attrs, getAttribute: a => (a in attrs ? attrs[a] : null) };
  kids.forEach(k => { k.parentNode = e; });
  return e;
};
t("walk", () => {
  const plain = text("Paper 13:00"), ta = text("13:00"), sc = text("13:00"), opt0 = text("13:00"), opt1 = text("13:00"), ce = text("13:00"), kt = text("13:00"), deep = text("13:00");
  const root = el("DIV", {}, [plain, el("TEXTAREA", {}, [ta]), el("SCRIPT", {}, [sc]), el("SELECT", {}, [el("OPTION", {}, [opt0]), el("OPTION", { value: "x" }, [opt1])]),
    el("P", { contenteditable: "true" }, [ce]), el("SPAN", { "data-keep-time": "" }, [el("B", {}, [kt])]), el("SPAN", {}, [el("B", {}, [deep])])]);
  ST.walk(root);
  assert.strictEqual(plain.nodeValue, "Paper 1.00");
  for (const [x, w] of [[ta, "textarea"], [sc, "script"], [opt0, "option without value"], [ce, "contenteditable"], [kt, "data-keep-time"]]) assert.strictEqual(x.nodeValue, "13:00", w);
  assert.strictEqual(opt1.nodeValue, "1.00", "option with a value");
  assert.strictEqual(deep.nodeValue, "1.00");
  ST.walk(root);
  assert.strictEqual(plain.nodeValue, "Paper 1.00");
  assert.strictEqual(deep.nodeValue, "1.00");
});

t("no lookbehind", () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "static", "schooltime.js"), "utf8");
  assert(!src.includes("(?<!") && !src.includes("(?<="));
});
console.log(`${n} schooltime tests passed`);

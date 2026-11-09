const assert = require("assert");
const People = require("../static/people.js");
let n = 0; const t = (name, f) => { f(); n++; };
const NAMES = Array.from({ length: 200 }, (_, i) => `Teacher ${["Tan", "Lim", "Nair", "Osman", "Koh", "Menon", "Ong", "Lee"][i % 8]} ${i}`);
const sig = p => JSON.stringify(p);

t("the same name gives the same avatar, whatever its capitals or spacing", () => {
  assert.strictEqual(People.key("  TAN   Wei Ming "), "tan wei ming");
  assert.deepStrictEqual(People.avatarParts("TAN  Wei Ming "), People.avatarParts("Tan Wei Ming"));
  assert.strictEqual(People.avatar("Tan Wei Ming", 0, 32), People.avatar(" tan wei  ming", 0, 32));
});
t("hash is 32-bit FNV-1a", () => { assert.strictEqual(People.hash(""), 2166136261); assert.strictEqual(People.hash("a"), 3826002220); });
t("there are enough combinations to tell a staff room apart", () => {
  assert.ok(People.AVATAR_COMBOS >= 100000);
  assert.ok(new Set(NAMES.map(x => sig(People.avatarParts(x)))).size >= 195);
});
t("every part index is inside its list", () => {
  for (const x of NAMES) for (const [k, v] of Object.entries(People.avatarParts(x))) assert.ok(Number.isInteger(v) && v >= 0 && v < People.AVATAR[k].length, `${k} ${v}`);
});
t("a new look changes the avatar and is itself repeatable", () => {
  const changed = NAMES.filter(x => sig(People.avatarParts(x, 1)) !== sig(People.avatarParts(x, 0))).length;
  assert.ok(changed >= 195);
  assert.deepStrictEqual(People.avatarParts("Tan Wei Ming", 3), People.avatarParts("Tan Wei Ming", 3));
});
t("the drawing is one svg of the asked size, with no script and no outside link", () => {
  const s = People.avatar("Tan Wei Ming", 0, 48);
  assert.ok(s.startsWith("<svg") && s.endsWith("</svg>") && s.includes('width="48"') && s.includes('viewBox="0 0 36 36"') && s.includes('aria-hidden="true"'));
  assert.ok(!/script|href|http/i.test(s));
});
t("no name gives a plain disc, not a face", () => {
  for (const x of ["", "   ", null, undefined]) { const s = People.avatar(x); assert.ok(s.startsWith("<svg") && !s.includes("<path")); }
});
t("nothing random is used", () => { const r = Math.random; Math.random = () => { throw new Error("random"); }; try { People.avatar("Lim Hui Min", 2); } finally { Math.random = r; } });
console.log(`${n} cases passed`);

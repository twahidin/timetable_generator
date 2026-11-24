// Plain-assert tests for static/renames.js (step 9's card about renamed teachers): run with `node tests/renames.test.js`
const assert = require("assert");
const Renames = require("../static/renames.js");
let n = 0; const t = (name, f) => { f(); n++; };
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pair = o => Object.assign({ old: "Mdm Lee", new: "New Teacher 3", has: ["Teacher", "username", "password"], account: true, telegram: false,
  joins: true, no_remove: null, needs_admin: false }, o);
const tg = o => pair(Object.assign({ old: "Mr Tan", new: "New Teacher 4", has: ["Telegram"], account: false, telegram: true }, o));

t("gate: nothing to ask, and all picked, let Publish go", () => {
  assert.strictEqual(Renames.gate([], {}), "");
  assert.strictEqual(Renames.gate(null, null), "");
  assert.strictEqual(Renames.gate([pair(), tg()], { "Mdm Lee": "same", "Mr Tan": "different" }), "");
});
t("gate: a pair with no pick holds Publish", () => {
  assert.strictEqual(Renames.gate([pair(), tg()], { "Mdm Lee": "same" }), "Choose for each teacher with a new name first.");
  assert.strictEqual(Renames.gate([pair()], { "Mdm Lee": "maybe" }), "Choose for each teacher with a new name first.");
});
t("gate: a pair that needs an admin comes first", () => {
  assert.strictEqual(Renames.gate([tg(), pair({ needs_admin: true })], {}), "An admin has to publish this one: New Teacher 3's account must follow or be removed.");
});
t("gate: a pick that is not offered (picked before the list changed) says why", () => {
  const p = pair({ no_remove: "You cannot remove your own account." });
  assert.strictEqual(Renames.gate([p], { "Mdm Lee": "different" }), "You cannot remove your own account.");
  assert.strictEqual(Renames.gate([p], { "Mdm Lee": "same" }), "");
});
t("gate: a pair where neither choice is offered says why, not \"Choose\"", () => {
  const p = pair({ joins: false, no_remove: "You cannot remove your own account." });
  assert.strictEqual(Renames.gate([p], {}), "You cannot remove your own account.");
  assert.strictEqual(Renames.gate([tg(), p], {}), "You cannot remove your own account.");
  assert.strictEqual(Renames.gate([p, pair({ old: "Mr Ong", needs_admin: true })], {}), "An admin has to publish this one: New Teacher 3's account must follow or be removed.");
});
t("offers: both, with no note, when nothing stands in the way", () => {
  assert.deepStrictEqual(Renames.offers(pair()), { same: true, different: true, note: "" });
  assert.deepStrictEqual(Renames.offers(tg({ no_remove: "x" })), { same: true, different: true, note: "" });   // no account: nothing to remove
});
t("offers: the new name has their own account", () => {
  assert.deepStrictEqual(Renames.offers(pair({ joins: false })),
    { same: true, different: true, note: "New Teacher 3 already has their own account: Mdm Lee's account is removed either way." });
});
t("offers: an account that cannot be removed, the new name with none of their own", () => {
  assert.deepStrictEqual(Renames.offers(pair({ no_remove: "Mdm Lee is the last admin: make another admin first." })),
    { same: true, different: false, note: "Mdm Lee is the last admin: make another admin first." });
});
t("offers: an account that cannot be removed, the new name with their own", () => {
  assert.deepStrictEqual(Renames.offers(pair({ joins: false, no_remove: "You cannot remove your own account." })),
    { same: false, different: false, note: "You cannot remove your own account." });
});
t("card: nothing for no pairs", () => {
  assert.strictEqual(Renames.card([], {}, esc), "");
  assert.strictEqual(Renames.card(null, {}, esc), "");
});
t("card: the heading, each sentence, and the picks", () => {
  const h = Renames.card([pair(), tg()], { "Mdm Lee": "different" }, esc);
  assert.ok(h.includes("New names since the last publish"));
  assert.ok(h.includes("Mdm Lee is now New Teacher 3."));
  assert.ok(h.includes("Mr Tan is now New Teacher 4."));
  assert.ok(h.includes("Teacher · username · password"));
  assert.ok(h.includes("Everything Mdm Lee has goes to New Teacher 3."));
  assert.ok(h.includes("New Teacher 3 starts fresh. Mdm Lee&#39;s account is removed."));
  assert.ok(h.includes("New Teacher 4 starts fresh. Mr Tan&#39;s Telegram link is removed."));
  assert.ok(h.includes("Same person") && h.includes("A different person"));
  assert.ok(/<input type="radio" name="rn-0" id="rn0different" data-rn="0\|different" checked>/.test(h));
  assert.ok(/<input type="radio" name="rn-0" id="rn0same" data-rn="0\|same">/.test(h));
  assert.ok(/<input type="radio" name="rn-1" id="rn1same" data-rn="1\|same">/.test(h) && /<input type="radio" name="rn-1" id="rn1different" data-rn="1\|different">/.test(h));
  assert.ok(!h.includes("disabled"));
  assert.ok(h.includes('id="rn0same"') && h.includes('id="rn0different"') && h.includes('id="rn1same"') && h.includes('id="rn1different"'));   // render() puts focus back by id
});
t("card: never a pick the person did not make", () => {
  assert.ok(!Renames.card([pair(), tg()], {}, esc).includes("checked"));
});
t("card: a choice not offered is disabled, with the note", () => {
  const h = Renames.card([pair({ joins: false, no_remove: "You cannot remove your own account." })], {}, esc);
  assert.ok(/data-rn="0\|same" disabled>/.test(h) && /data-rn="0\|different" disabled>/.test(h));
  assert.ok(h.includes("You cannot remove your own account."));
  const h2 = Renames.card([pair({ joins: false })], {}, esc);
  assert.ok(h2.includes("New Teacher 3 already has their own account: Mdm Lee&#39;s account is removed either way."));
});
t("card: a pair that needs an admin has no inputs and says so", () => {
  const h = Renames.card([pair({ needs_admin: true, has: ["an account"] })], {}, esc);
  assert.ok(!h.includes("<input"));
  assert.ok(h.includes("An admin has to publish this one: New Teacher 3&#39;s account must follow or be removed."));
  assert.ok(h.includes("an account"));
});
t("card: every name is escaped", () => {
  const h = Renames.card([pair({ old: "<script>Old</script>", new: "<i>New</i>", has: ["<u>x</u>"] })], {}, esc);
  assert.ok(!h.includes("<script") && !h.includes("<i>") && !h.includes("<u>"));
  assert.ok(h.includes("&lt;script&gt;Old&lt;/script&gt; is now &lt;i&gt;New&lt;/i&gt;."));
});
t("body: only the pairs with a pick", () => {
  assert.deepStrictEqual(Renames.body([pair(), tg()], { "Mr Tan": "same", "Someone Else": "same" }), { renames: { "Mr Tan": "same" } });
  assert.deepStrictEqual(Renames.body([pair()], { "Mdm Lee": "maybe" }), { renames: {} });
  assert.deepStrictEqual(Renames.body(null, null), { renames: {} });
});
console.log(n + " cases passed");

// Plain-assert tests for static/renames.js (step 9's card about renamed teachers): run with `node tests/renames.test.js`
const assert = require("assert");
const Renames = require("../static/renames.js");
let n = 0; const t = (name, f) => { f(); n++; };
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pair = o => Object.assign({ old: "Mdm Lee", new: "New Teacher 3", has: ["Teacher", "username", "password"], account: true, telegram: false,
  joins: true, no_remove: null, needs_admin: false }, o);
const tg = o => pair(Object.assign({ old: "Mr Tan", new: "New Teacher 4", has: ["Telegram"], account: false, telegram: true }, o));
const k = p => JSON.stringify([p.old, p.new]);
const P1 = k(pair()), P2 = k(tg());
const OWN = "You cannot remove your own account.", ASK = " Ask another admin to publish.";
const NJ = "New Teacher 3 is switched off, so no admin could sign in afterwards: switch New Teacher 3 on first.";

t("gate: nothing to ask, and all picked, let Publish go", () => {
  assert.strictEqual(Renames.gate([], {}), "");
  assert.strictEqual(Renames.gate(null, null), "");
  assert.strictEqual(Renames.gate([pair(), tg()], { [P1]: "same", [P2]: "different" }), "");
});
t("gate: a pair with no pick holds Publish", () => {
  assert.strictEqual(Renames.gate([pair(), tg()], { [P1]: "same" }), "Choose for each teacher with a new name first.");
  assert.strictEqual(Renames.gate([pair()], { [P1]: "maybe" }), "Choose for each teacher with a new name first.");
});
t("gate: a pair that needs an admin comes first", () => {
  assert.strictEqual(Renames.gate([tg(), pair({ needs_admin: true })], {}), "An admin has to publish this one: New Teacher 3's account must follow or be removed.");
});
t("gate: a pick that is not offered (picked before the list changed) says why", () => {
  const p = pair({ no_remove: "You cannot remove your own account." });
  assert.strictEqual(Renames.gate([p], { [P1]: "different" }), "You cannot remove your own account.");
  assert.strictEqual(Renames.gate([p], { [P1]: "same" }), "");
});
t("gate: a pair where neither choice is offered says why, not \"Choose\"", () => {
  const p = pair({ joins: false, no_remove: "You cannot remove your own account." });
  assert.strictEqual(Renames.gate([p], {}), OWN + ASK);
  assert.strictEqual(Renames.gate([tg(), p], {}), OWN + ASK);
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
    { same: false, different: false, note: OWN + ASK });
});
t("card: nothing for no pairs", () => {
  assert.strictEqual(Renames.card([], {}, esc), "");
  assert.strictEqual(Renames.card(null, {}, esc), "");
});
t("card: the heading, each sentence, and the picks", () => {
  const h = Renames.card([pair(), tg()], { [P1]: "different" }, esc);
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
  assert.ok(h.includes(OWN + ASK));
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
t("body: only the pairs with a pick, each as old, new and choice", () => {
  assert.deepStrictEqual(Renames.body([pair(), tg()], { [P2]: "same", [k({ old: "Someone Else", new: "X" })]: "same" }),
    { renames: [{ old: "Mr Tan", new: "New Teacher 4", choice: "same" }] });
  assert.deepStrictEqual(Renames.body([pair(), tg()], { [P1]: "different", [P2]: "same" }),
    { renames: [{ old: "Mdm Lee", new: "New Teacher 3", choice: "different" }, { old: "Mr Tan", new: "New Teacher 4", choice: "same" }] });
  assert.deepStrictEqual(Renames.body([pair()], { [P1]: "maybe" }), { renames: [] });
  assert.deepStrictEqual(Renames.body([pair()], { "Mdm Lee": "same" }), { renames: [] });   // keyed by the old name only: no pick
  assert.deepStrictEqual(Renames.body(null, null), { renames: [] });
});
t("key: the pair, old then new", () => {
  assert.strictEqual(Renames.key(pair()), JSON.stringify(["Mdm Lee", "New Teacher 3"]));
  assert.notStrictEqual(Renames.key(pair()), Renames.key(pair({ new: "Arjun Nair" })));
  assert.notStrictEqual(Renames.key({ old: "a,b", new: "c" }), Renames.key({ old: "a", new: "b,c" }));
});
t("a pick for the old name with another new name is no pick", () => {
  const other = { [k(pair({ new: "Arjun Nair" }))]: "same" };
  assert.strictEqual(Renames.gate([pair()], other), "Choose for each teacher with a new name first.");
  assert.ok(!Renames.card([pair()], other, esc).includes("checked"));
  assert.ok(Renames.card([pair()], { [P1]: "same" }, esc).includes("checked"));
});
t("offers: same person is not offered when the join leaves no admin who can sign in", () => {
  assert.deepStrictEqual(Renames.offers(pair({ no_join: NJ })), { same: false, different: true, note: NJ });
  assert.deepStrictEqual(Renames.offers(pair({ no_join: NJ, no_remove: OWN })), { same: false, different: false, note: NJ + " " + OWN + ASK });
  assert.deepStrictEqual(Renames.offers(pair({ no_join: NJ, joins: false })),          // no join: no_join does not apply
    { same: true, different: true, note: "New Teacher 3 already has their own account: Mdm Lee's account is removed either way." });
  assert.deepStrictEqual(Renames.offers(tg({ no_join: NJ })), { same: true, different: true, note: "" });
  assert.strictEqual(Renames.gate([pair({ no_join: NJ })], { [P1]: "same" }), NJ);
  assert.strictEqual(Renames.gate([pair({ no_join: NJ })], { [P1]: "different" }), "");
  assert.strictEqual(Renames.gate([pair({ no_join: NJ, no_remove: OWN })], {}), NJ + " " + OWN + ASK);
  const h = Renames.card([pair({ no_join: NJ })], {}, esc);
  assert.ok(/data-rn="0\|same" disabled>/.test(h) && /data-rn="0\|different">/.test(h) && h.includes(NJ));
});
t("card: same person where the new name has their own account", () => {
  const h = Renames.card([pair({ joins: false })], {}, esc);
  assert.ok(h.includes("New Teacher 3 already has their own account, so Mdm Lee&#39;s account is removed. A Telegram link still goes to New Teacher 3."));
  assert.ok(!h.includes("Everything Mdm Lee has"));
  assert.ok(Renames.card([tg({ joins: false })], {}, esc).includes("Everything Mr Tan has goes to New Teacher 4."));   // a link only: joins ignored
});
t("card and gate: a pair for someone who is not an admin (joins null) shows no choices", () => {
  const p = pair({ needs_admin: true, joins: null, no_join: null, has: ["an account"] });
  assert.ok(!Renames.card([p], {}, esc).includes("<input"));
  assert.strictEqual(Renames.gate([p], { [P1]: "same" }), "An admin has to publish this one: New Teacher 3's account must follow or be removed.");
  const t2 = tg({ joins: null, no_join: null });
  assert.deepStrictEqual(Renames.offers(t2), { same: true, different: true, note: "" });
  assert.ok(Renames.card([t2], {}, esc).includes("Everything Mr Tan has goes to New Teacher 4."));
});
console.log(n + " cases passed");

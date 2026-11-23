// Plain-assert tests for the Telegram card of the Relief settings page (static/relief-settings.js): run with `node tests/relief_settings.test.js`.
// The page's own HTML and script run in a small stand-in for the browser (tests/dom.js), against answers written here.
const assert = require("assert");
const { open, later, run } = require("./dom.js");

const URL = "/api/relief/telegram", ADMIN = `${URL}/admin`, BASE = "https://ctss.example";
const SAM = "Mr Sam Tan", MAYA = "Ms Maya Lee", EVE = "Ms Evelyn Koh", RUTH = "Ms Ruth Goh";
const NOT_SET = "Not set up yet. The bot's token goes in Railway's variables (TELEGRAM_BOT_TOKEN) of the copy the school uses; then come back here and press Connect. How to make the bot is in docs/DEPLOY.md.";
const SET = "The token is set. Connect points Telegram at this copy of the app.", ONE = "The bot works on one copy of the app only. Connect it on the copy the school uses.", PRACTICE = "Practice mode: nothing is sent to Telegram.";
const ON = `Connected as @made_up_bot since Mon 12 Oct: ${BASE}`, SURE = "Disconnect? Nobody gets messages until it is connected again.";
const ok = data => ({ status: 200, data }), no = (status, error) => ({ status, data: { error } });
const OFF = { token_set: false, practice: false, connected: false, bot: null, base: null, at: null, linked: [], not_linked: [EVE, MAYA, RUTH, SAM], people: 4 };
const TOKEN = Object.assign({}, OFF, { token_set: true });
const link = (name, handle = null, at = "2026-10-12T09:15:00+08:00") => ({ name, handle, at });
const CONNECTED = Object.assign({}, TOKEN, { connected: true, bot: "made_up_bot", base: BASE, at: "2026-10-12T08:00:00+08:00", linked: [link(MAYA), link(SAM, "sam_made_up")], not_linked: [EVE, RUTH] });
const SETTINGS = { settings: { rules: ["Use planned relief first."], limits: { fat_per_day: 3, other_per_day: null, never: [] }, times: { fill_at: "15:30", remind_at: "15:00", report_every: 15, weekly_day: "Fri", weekly_at: "15:00" },
  calendar: { terms: [], holidays: [] }, fat_role: "", missing: [], saved_at: "", saved_by: "" }, lists: { management: [], team: [], added: [] }, can_admin: false, people: [], roles: [], weeks: 2, can_save: true, can_codes: true };

/* the settings page; api: "GET admin", "POST connect", … -> an answer, a promise of one, or a function of the call */
async function opened(api, settings = ok(SETTINGS)) {
  const p = open("relief-settings.html", { server: call => {
    if (!call.url.startsWith(URL)) return settings;
    const a = p.api[`${call.method} ${call.url.slice(URL.length + 1)}`];
    return typeof a === "function" ? a(call) : a;
  } });
  p.api = api;
  p.run("relief-settings.js");
  await p.settle();
  p.card = () => p.text("#telegram");
  p.top = () => p.text("#tgTop");
  p.live = () => p.all("#telegram [aria-live]").map(e => `${e.id}: ${p.text(e)}`);
  p.sent = () => p.calls.filter(c => c.url.startsWith(URL)).map(c => `${c.method} ${c.url.slice(URL.length + 1)}${c.body && Object.keys(c.body).length ? " " + JSON.stringify(c.body) : ""}`);
  p.buttons = () => p.all("#telegram button").map(b => p.text(b) + (b.disabled ? " (off)" : ""));
  p.row = name => p.all("#telegram li").find(li => p.text(li).includes(name));
  p.in = (name, label) => p.click([...p.row(name).querySelectorAll("button")].find(b => p.text(b) === label));
  return p;
}
const all = []; const t = (name, f) => all.push([name, f]);
const none = p => { assert.strictEqual(p.$("#telegram").innerHTML, ""); assert.ok(p.$("#telegram").hidden, "no empty region called Telegram"); };

t("nothing for whoever cannot read it, and no way off the page", async () => {
  for (const a of [no(403, "No."), no(401, "Please sign in again."), { status: 401 }]) { const p = await opened({ "GET admin": a }); none(p); assert.strictEqual(p.location.href, ""); assert.ok(p.text("#main").includes("Relief rules"), "the settings are there"); }
});
t("it cannot be read just now: why, and Try again", async () => {
  for (const [a, text] of [[no(500, "Made up."), "Made up."], [new Error("x"), "Could not reach the server. Check the connection and try again."], [{ status: 503 }, "Something went wrong. Try again."]]) {
    const p = await opened({ "GET admin": a }); assert.strictEqual(p.card(), `Telegram ${text} Try again`); assert.ok(p.$("#tgTop .msg.bad")); p.api["GET admin"] = ok(TOKEN); await p.click("#telegram button", "Try again"); assert.strictEqual(p.card(), `Telegram ${SET} ${ONE} Connect the bot`);
    assert.strictEqual(p.focus(), p.find("button", "Connect the bot"));
  }
  const p = await opened({ "GET admin": no(500, "Made up.") }), wait = later(); p.api["GET admin"] = wait.answer; await p.click("#telegram button", "Try again"); assert.deepStrictEqual(p.buttons(), ["Try again (off)"]); wait.give(403, { error: "No." }); await p.settle(); none(p);
});
t("the settings cannot be read: the card does not need them", async () => {
  const p = await opened({ "GET admin": ok(TOKEN) }, no(409, "Publish the timetable first.")); assert.ok(p.text("#main").includes("Publish the timetable first.")); assert.ok(p.card().includes(SET));
});
t("the card's place is hidden until there is something in it, and again when there is not", async () => {
  const wait = later(), p = await opened({ "GET admin": wait.answer });
  none(p);
  wait.give(500, { error: "Made up." });
  await p.settle();
  assert.ok(!p.$("#telegram").hidden);
  p.api["GET admin"] = no(403, "No.");
  await p.click("#telegram button", "Try again");
  none(p);
  const q = await opened({ "GET admin": ok(TOKEN) });
  assert.ok(!q.$("#telegram").hidden);
});
t("what the settings say of the reporting officer", async () => {
  const p = await opened({ "GET admin": ok(OFF) });
  assert.ok(p.text("#main").includes("Reporting officer Is told on Telegram, when they have linked it, when someone who names them asks for relief."));
  assert.ok(!p.text("#main").includes("Is told when someone"));
});
t("no token", async () => {
  const p = await opened({ "GET admin": ok(OFF) }); assert.strictEqual(p.card(), `Telegram ${NOT_SET}`); assert.deepStrictEqual(p.buttons(), []); assert.strictEqual(p.text("#telegram h2"), "Telegram"); assert.deepStrictEqual(p.sent(), ["GET admin"]);
});
t("a token, not connected; Connect the bot", async () => {
  const wait = later(), p = await opened({ "GET admin": ok(TOKEN), "POST connect": wait.answer }); assert.strictEqual(p.card(), `Telegram ${SET} ${ONE} Connect the bot`);
  await p.click("button", "Connect the bot"); assert.deepStrictEqual(p.buttons(), ["Connect the bot (off)"]); await p.click("button", "Connect the bot"); assert.deepStrictEqual(p.sent(), ["GET admin", "POST connect"]);
  wait.give(200, CONNECTED); await p.settle(); assert.strictEqual(p.top(), `${ON} 2 of 4 linked ${ONE}`); assert.deepStrictEqual(p.buttons().slice(0, 2), ["Connect again", "Disconnect"]); assert.strictEqual(p.text("#tgSay"), "Connected."); assert.strictEqual(p.focus(), p.find("button", "Connect again"));
});
t("connected: the lists", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED) }); assert.strictEqual(p.top(), `${ON} 2 of 4 linked ${ONE}`);
  assert.deepStrictEqual(p.all("#telegram summary").map(s => p.text(s)), ["Not linked (2)", "Linked (2)"]); assert.deepStrictEqual(p.all("#telegram details").map(d => d.open), [false, false]);
  assert.deepStrictEqual(p.all("#telegram li").map(li => p.text(li)), [EVE, RUTH, `${MAYA} since Mon 12 Oct Unlink`, `${SAM} @sam_made_up · since Mon 12 Oct Unlink`]);
  const q = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, { linked: [link("Mr Gone Away"), link(MAYA), link(SAM)], not_linked: [], people: 2 })) }); assert.ok(q.top().includes("2 of 2 linked")); assert.deepStrictEqual(q.all("#telegram summary").map(s => p.text(s)), ["Not linked (0)", "Linked (3)"], "whoever left can be unlinked too");
  const r = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, { linked: [] })) }); assert.ok(r.top().includes("2 of 4 linked")); assert.ok(r.card().includes("Linked (0)"));
  for (const odd of [{ linked: null, not_linked: "x", people: null }, { linked: "x", not_linked: null, people: 0 }, { linked: [], not_linked: [], people: 0, at: null, base: null }]) { const s = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, odd)) }); assert.ok(s.top().includes("0 of 0 linked") && !/undefined|NaN|null/.test(s.card()), s.card()); }
  const u = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, { at: null, base: null, linked: [link(SAM, null, null)] })) }); assert.strictEqual(u.top(), `Connected as @made_up_bot 2 of 4 linked ${ONE}`); assert.strictEqual(u.text(u.row(SAM)), `${SAM} Unlink`);
});
t("practice mode is said on top, whatever the state", async () => {
  for (const d of [TOKEN, CONNECTED]) { const p = await opened({ "GET admin": ok(Object.assign({}, d, { practice: true })) }); assert.ok(p.top().startsWith(PRACTICE)); assert.ok(p.$("#tgTop .notice")); }
  for (const d of [OFF, TOKEN, CONNECTED]) { const p = await opened({ "GET admin": ok(d) }); assert.ok(!p.card().includes("Practice")); }
});
t("Connect again", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED), "POST connect": ok(Object.assign({}, CONNECTED, { base: "https://other.example" })) }); await p.click("button", "Connect again"); assert.deepStrictEqual(p.sent(), ["GET admin", "POST connect"]);
  assert.ok(p.top().startsWith("Connected as @made_up_bot since Mon 12 Oct: https://other.example")); assert.strictEqual(p.text("#tgSay"), "Connected."); assert.strictEqual(p.focus(), p.find("button", "Connect again"));
});
t("Disconnect asks first", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED) }); await p.click("button", "Disconnect"); assert.deepStrictEqual(p.sent(), ["GET admin"]); assert.ok(p.card().includes(`${SURE} Disconnect Keep it`)); assert.strictEqual(p.focus(), p.find("button", "Keep it"), "a second Return does not disconnect");
  await p.click("button", "Keep it"); assert.ok(!p.card().includes(SURE)); assert.strictEqual(p.focus(), p.find("button", "Disconnect")); await p.click("button", "Disconnect"); assert.strictEqual((await p.key(p.find("button", "Keep it"), "Escape")).defaultPrevented, true); assert.ok(!p.card().includes(SURE));
  p.api["POST connect"] = ok(CONNECTED); await p.click("button", "Disconnect"); await p.click("button", "Connect again"); assert.ok(!p.card().includes(SURE), "done something else: the question goes"); p.calls.pop();
  const wait = later(); p.api["POST disconnect"] = wait.answer; await p.click("button", "Disconnect"); await p.click("button", "Disconnect"); assert.deepStrictEqual(p.sent(), ["GET admin", "POST disconnect"]); assert.ok(p.buttons().every(b => b.endsWith("(off)")), p.buttons().join());
  await p.click("button", "Disconnect"); await p.click("button", "Keep it"); await p.key(p.find("button", "Keep it"), "Escape"); assert.ok(p.card().includes(SURE)); assert.strictEqual(p.sent().length, 2); wait.give(200, TOKEN); await p.settle();
  assert.strictEqual(p.card(), `Telegram ${SET} ${ONE} Connect the bot`); assert.strictEqual(p.focus(), p.find("button", "Connect the bot"));
});
t("Unlink asks first, in its own row", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED) }), ask = `Stop relief messages to ${SAM}?`; await p.click("#telegram summary", "Linked (2)"); await p.in(SAM, "Unlink"); assert.strictEqual(p.text(p.row(SAM)), `${SAM} @sam_made_up · since Mon 12 Oct ${ask} Unlink Keep it`);
  assert.strictEqual(p.focus(), p.find("button", "Keep it")); assert.ok(p.find('details[data-k="yes"]').open, "the list stays open"); await p.in(SAM, "Keep it"); assert.ok(!p.card().includes(ask)); assert.strictEqual(p.focus(), [...p.row(SAM).querySelectorAll("button")][0]);
  await p.in(MAYA, "Unlink"); await p.in(SAM, "Unlink"); assert.ok(!p.card().includes(`Stop relief messages to ${MAYA}?`), "one question at a time"); await p.click("button", "Disconnect"); assert.ok(!p.card().includes(ask)); await p.click("button", "Keep it"); await p.in(SAM, "Unlink");
  const wait = later(); p.api["POST unlink"] = wait.answer; await p.in(SAM, "Unlink"); assert.deepStrictEqual(p.sent(), ["GET admin", `POST unlink {"name":"${SAM}"}`]); assert.ok(p.buttons().every(b => b.endsWith("(off)"))); await p.in(SAM, "Unlink"); assert.strictEqual(p.sent().length, 2);
  wait.give(200, Object.assign({}, CONNECTED, { linked: [link(MAYA)], not_linked: [EVE, RUTH, SAM] })); await p.settle(); assert.ok(p.top().includes("1 of 4 linked")); assert.deepStrictEqual(p.all("#telegram summary").map(s => p.text(s)), ["Not linked (3)", "Linked (1)"]);
  assert.strictEqual(p.focus(), p.find('details[data-k="yes"] summary')); assert.deepStrictEqual(p.all("#telegram details").map(d => d.open), [false, true]); assert.strictEqual(p.$("#tgSay").innerHTML, "");
});
t("a name that looks like another's, and one with quotes", async () => {
  const odd = `Mr "Sam" O'Tan <b>`, p = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, { linked: [link(odd), link(SAM)] })), "POST unlink": ok(CONNECTED) }); await p.in(odd, "Unlink"); assert.ok(p.row(odd).querySelector(".ask") && !p.row(SAM).querySelector(".ask")); assert.strictEqual(p.focus(), p.find("button", "Keep it"));
  await p.in(odd, "Keep it"); assert.strictEqual(p.focus(), p.row(odd).querySelector("button")); await p.in(odd, "Unlink"); await p.in(odd, "Unlink"); assert.deepStrictEqual(p.calls[p.calls.length - 1].body, { name: odd });
});
t("a refusal is the server's sentence, and what there is now is read again", async () => {
  const off = "Disconnected here, but Telegram did not answer. The app reads and sends nothing now.", p = await opened({ "GET admin": ok(CONNECTED), "POST disconnect": () => { p.api["GET admin"] = ok(TOKEN); return no(502, off); } });
  await p.click("button", "Disconnect"); await p.click("button", "Disconnect"); assert.strictEqual(p.card(), `Telegram ${SET} ${ONE} Connect the bot ${off}`); assert.deepStrictEqual(p.sent(), ["GET admin", "POST disconnect", "GET admin"]); assert.ok(p.$("#tgSay .msg.bad")); assert.strictEqual(p.focus(), p.find("button", "Connect the bot"));
  for (const text of ["Add the bot's token in Railway variables first (TELEGRAM_BOT_TOKEN).", "Telegram needs a secure address: open the app at its https address and press Connect there."]) { p.api["POST connect"] = no(409, text); await p.click("button", "Connect the bot"); assert.strictEqual(p.text("#tgSay"), text); assert.deepStrictEqual(p.buttons(), ["Connect the bot"]); }
  p.api["POST connect"] = ok(CONNECTED); await p.click("button", "Connect the bot"); assert.strictEqual(p.text("#tgSay"), "Connected."); assert.ok(p.$("#tgSay .msg.ok"));
  const gone = "That person has no Telegram linked."; p.api["POST unlink"] = () => { p.api["GET admin"] = ok(Object.assign({}, CONNECTED, { linked: [link(MAYA)], not_linked: [EVE, RUTH, SAM] })); return no(404, gone); }; await p.in(SAM, "Unlink"); await p.in(SAM, "Unlink"); assert.strictEqual(p.text("#tgSay"), gone); assert.ok(p.card().includes("Linked (1)") && !p.card().includes("Stop relief"));
  p.api["POST unlink"] = new Error("x"); await p.in(MAYA, "Unlink"); await p.in(MAYA, "Unlink"); assert.strictEqual(p.text("#tgSay"), "Could not reach the server. Check the connection and try again."); assert.ok(p.row(MAYA).querySelector(".ask"), "the question is still there"); assert.strictEqual(p.focus(), p.find("button", "Keep it")); assert.ok(p.buttons().every(b => !b.endsWith("(off)")));
  await p.in(MAYA, "Keep it"); assert.strictEqual(p.text("#tgSay"), "", "and the sentence goes with it");
});
t("a question about what is no more does not come back", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED), "POST disconnect": () => { p.api["GET admin"] = ok(TOKEN); return no(502, "x"); } }); await p.click("button", "Disconnect"); await p.click("button", "Disconnect");
  p.api["POST connect"] = () => { p.api["GET admin"] = ok(CONNECTED); return no(502, "No answer."); }; await p.click("button", "Connect the bot"); assert.ok(p.top().startsWith(ON) && !p.card().includes(SURE));
  p.api["POST unlink"] = () => { p.api["GET admin"] = ok(Object.assign({}, CONNECTED, { linked: [link(MAYA)] })); return no(404, "Gone."); }; await p.in(SAM, "Unlink"); await p.in(SAM, "Unlink"); p.api["GET admin"] = ok(CONNECTED); p.api["POST connect"] = no(502, "x"); await p.click("button", "Connect again"); assert.ok(p.row(SAM) && !p.card().includes("Stop relief"));
  p.api["POST unlink"] = () => { p.api["GET admin"] = ok(TOKEN); return no(502, "x"); }; await p.in(SAM, "Unlink"); await p.in(SAM, "Unlink"); p.api["POST connect"] = () => { p.api["GET admin"] = ok(CONNECTED); return no(502, "x"); }; await p.click("button", "Connect the bot"); assert.ok(p.row(SAM) && !p.card().includes("Stop relief"));
  p.api["POST unlink"] = () => { p.api["GET admin"] = ok(Object.assign({}, CONNECTED, { linked: "x" })); return no(502, "x"); }; await p.in(SAM, "Unlink"); await p.in(SAM, "Unlink"); assert.ok(!p.card().includes("Stop relief")); assert.ok(p.buttons().every(b => !b.endsWith("(off)")));
});
t("the focus: where it was, in the card or not, unless what had it is gone", async () => {
  const start = async () => { const p = await opened({ "GET admin": ok(CONNECTED) }), wait = later(); p.api["POST connect"] = wait.answer; await p.click("button", "Connect again"); return [p, () => { wait.give(200, Object.assign({}, CONNECTED, { linked: [link(MAYA)], not_linked: [EVE, RUTH, SAM] })); return p.settle(); }]; };
  let [p, give] = await start(); p.find('textarea[data-rule="0"]').focus(); await give(); assert.strictEqual(p.focus(), p.find('textarea[data-rule="0"]'), "in the form");
  for (const k of ["no", "yes"]) { [p, give] = await start(); p.find(`details[data-k="${k}"] summary`).focus(); await give(); assert.strictEqual(p.focus(), p.find(`details[data-k="${k}"] summary`), k); }
  [p, give] = await start(); p.focused = null; await give(); assert.strictEqual(p.focus(), p.find("button", "Connect again"));
  p = await opened({ "GET admin": ok(CONNECTED), "POST connect": ok(CONNECTED) }); await p.in(SAM, "Unlink"); p.find("button", "Disconnect").focus(); await p.key(p.focus(), "Escape"); assert.strictEqual(p.focus(), p.find("button", "Disconnect")); await p.click("button", "Connect again"); assert.strictEqual(p.focus(), p.find("button", "Connect again"));
  await p.in(SAM, "Unlink"); const maya = () => p.row(MAYA).querySelector("button"), was = maya(); was.focus(); await p.key(was, "Escape"); assert.notStrictEqual(maya(), was, "the list was drawn again"); assert.strictEqual(p.focus(), maya(), "and Maya's button has the focus still");
});
t("what was said goes when something else is asked for", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED), "POST connect": no(502, "No answer.") }), wait = later(); await p.click("button", "Connect again"); assert.strictEqual(p.text("#tgSay"), "No answer."); p.api["POST connect"] = wait.answer; await p.click("button", "Connect again"); assert.strictEqual(p.text("#tgSay"), ""); wait.give(200, CONNECTED); await p.settle();
  assert.strictEqual(p.text("#tgSay"), "Connected."); await p.click("button", "Disconnect"); assert.strictEqual(p.text("#tgSay"), "");
});
t("off while it is read again after a refusal; what cannot be read again stays as it was", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED), "POST connect": no(502, "No answer.") }), wait = later(); p.api["GET admin"] = wait.answer; await p.click("button", "Connect again"); assert.ok(p.buttons().every(b => b.endsWith("(off)"))); wait.give(500, { error: "x" }); await p.settle();
  assert.ok(p.top().startsWith(ON)); assert.strictEqual(p.text("#tgSay"), "No answer."); assert.ok(p.buttons().every(b => !b.endsWith("(off)")));
});
t("signed out: said, with a way to sign in that does not leave the page", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED) }); p.api["GET admin"] = p.api["POST connect"] = no(401, "Please sign in again."); await p.click("button", "Connect again"); assert.ok(p.text("#tgSay").startsWith("Please sign in again."));
  const a = p.find("#tgSay a"); assert.deepStrictEqual([a.getAttribute("href"), a.getAttribute("target")], ["/login", "_blank"]); assert.strictEqual(p.location.href, ""); assert.ok(p.top().startsWith(ON));
});
t("what is typed in the settings is never lost, and is not saved by this card", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED), "POST connect": ok(CONNECTED), "POST unlink": ok(CONNECTED), "POST disconnect": no(502, "x") }); await p.type('textarea[data-rule="0"]', "A rule not saved yet."); await p.type("#limFat", "5"); const area = p.find('textarea[data-rule="0"]');
  await p.click("button", "Connect again"); await p.in(SAM, "Unlink"); await p.in(SAM, "Unlink"); await p.click("button", "Disconnect"); await p.click("button", "Disconnect"); await p.key(p.find("button", "Keep it"), "Escape");
  assert.strictEqual(p.find('textarea[data-rule="0"]'), area); assert.deepStrictEqual([area.value, p.find("#limFat").value], ["A rule not saved yet.", "5"]); assert.ok(p.text('[data-bar]').includes("Changes not saved.")); assert.ok(p.calls.every(c => c.method !== "PUT"));
  const el = p.find("#tgState"), drawn = p.drawn.filter(x => x === el).length; await p.click('.savebar.first button[data-act="save"]'); assert.deepStrictEqual(p.calls.filter(c => c.method === "PUT").map(c => [c.url, c.body.rules[0], "telegram" in c.body]), [["/api/relief/settings", "A rule not saved yet.", false]]); assert.ok(p.find("#tgState") === el && p.drawn.filter(x => x === el).length === drawn, "nor does Save touch the card");
});
t("only what changes is drawn, and only the lines that change are live, each on its own", async () => {
  const p = await opened({ "GET admin": ok(CONNECTED) });
  assert.deepStrictEqual(p.live(), [`tgState: ${ON}`, "tgCount: 2 of 4 linked", "tgSay: "]);
  assert.ok(p.all("#telegram [aria-live]").every(e => e.getAttribute("aria-live") === "polite"));
  assert.ok(!p.live().join().includes(ONE) && p.card().includes(ONE));
  const state = p.find("#tgState"), count = p.find("#tgCount"), writes = el => p.drawn.filter(x => x === el).length, was = writes(state);
  p.api["POST unlink"] = ok(Object.assign({}, CONNECTED, { linked: [link(MAYA)], not_linked: [EVE, RUTH, SAM] }));
  await p.in(SAM, "Unlink");
  await p.in(SAM, "Unlink");
  assert.strictEqual(p.text(count), "1 of 4 linked");
  assert.strictEqual(writes(state), was, "how it is connected has not changed, and is not said again");
  p.api["POST connect"] = ok(Object.assign({}, CONNECTED, { linked: [link(MAYA)], not_linked: [EVE, RUTH, SAM] }));
  const n = writes(count);
  await p.click("button", "Connect again");
  assert.deepStrictEqual([writes(state), writes(count)], [was, n]);
  assert.strictEqual(p.text("#tgSay"), "Connected.");
  assert.ok(p.find("#tgState") === state && p.find("#tgCount") === count);
  p.api["POST disconnect"] = ok(TOKEN);
  await p.click("button", "Disconnect");
  await p.click("button", "Disconnect");
  assert.deepStrictEqual([p.text("#tgState"), p.text("#tgCount")], [SET, ""]);
  assert.ok(p.buttons().every(x => /[A-Za-z]/.test(x)));
});
t("everything is escaped", async () => {
  const mark = x => `<u title="${x}">'${x}'</u>&`, d = Object.assign({}, CONNECTED, { bot: mark("bot"), base: mark("base"), at: mark("at"), linked: [link(mark("name"), mark("handle"), mark("when"))], not_linked: [mark("free")] });
  const p = await opened({ "GET admin": ok(d), "POST unlink": no(400, mark("refusal")) }); await p.in(mark("name"), "Unlink"); await p.in(mark("name"), "Unlink"); for (const x of ["bot", "base", "at", "name", "handle", "when", "free", "refusal"]) assert.ok(p.card().includes(mark(x)), x); assert.strictEqual(p.all("#telegram u").length, 0);
  const q = await opened({ "GET admin": no(500, mark("error")) }); assert.ok(q.card().includes(mark("error"))); assert.strictEqual(q.all("#telegram u").length, 0);
});

run(all);

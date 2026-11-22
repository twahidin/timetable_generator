// Plain-assert tests for the Link Telegram card on My absences (static/relief-telegram.js): run with `node tests/relief_telegram.test.js`.
// The Relief page's own HTML and scripts run in a small stand-in for the browser (tests/dom.js), against answers written here.
const assert = require("assert");
const { open, later, run } = require("./dom.js");

const NOW = "2026-10-13T07:20:00+08:00", URL = "/api/relief/telegram", CODE = "ABCD-EFGH", BOT = "https://t.me/made_up_bot?start=";
const LINE = "Get your reliefs and reminders on your own Telegram.", OUT = "That code has run out.";
const OFF = { on: true, connected: false, bot: null, linked: false, handle: null, since: null };
const FREE = { on: true, connected: true, bot: "made_up_bot", linked: false, handle: null, since: null };
const LINKED = Object.assign({}, FREE, { linked: true, handle: "sam_made_up", since: "2026-10-12T09:15:00+08:00" });
const ok = data => ({ status: 200, data }), no = (status, error) => ({ status, data: { error } });
const code = (page, text = CODE, left = 900) => ok({ code: text, url: BOT + text, until: page.now / 1000 + left });

/* the Relief page, open on My absences; api: what the Telegram routes answer, "METHOD path" -> an answer, a promise of one, or a function of the call */
async function opened(api, more = {}) {
  const page = open("relief.html", Object.assign({ now: NOW, server: call => {
    const a = page.api[`${call.method} ${call.url.replace(URL, "")}`];
    if (call.url.startsWith(URL)) return typeof a === "function" ? a(call) : a;
    if (call.url === "/api/relief/me") return ok({ name: "Mr Sam Tan", depts: ["Science"], published: true, today: "2026-10-13", can_team: false, can_plan: false, can_settings: false });
    if (call.url === "/api/relief/absences/mine") return ok({ absences: [] });
    return ok(call.url === "/api/relief/people" ? [] : { lessons: [], periods: [], covers: [] });
  } }, more));
  page.api = api;
  page.run("relief-form.js", "relief.js", "relief-telegram.js");
  await page.settle();
  page.reads = () => page.calls.filter(c => c.method === "GET" && c.url === URL).length;
  page.told = (method, at) => page.calls.filter(c => c.method === method && c.url === URL + at).length;
  page.card = () => page.text("#mineTelegram");
  page.body = () => page.text("#tgBody");
  page.buttons = () => page.all("#mineTelegram button").map(b => page.text(b) + (b.disabled ? " (off)" : ""));
  return page;
}
/* ... with a code showing */
async function coded(api, left) {
  const p = await opened(Object.assign({ "GET ": ok(FREE) }, api));
  p.api["POST /code"] = p.api["POST /code"] || (() => code(p, CODE, left));
  await p.click("button", "Link Telegram");
  return p;
}
const has = (p, ...texts) => texts.forEach(x => assert.ok(p.card().includes(x), `${x} not in: ${p.card()}`));
const hasNot = (p, ...texts) => texts.forEach(x => assert.ok(!p.card().includes(x), `${x} in: ${p.card()}`));
const all = []; const t = (name, f) => all.push([name, async () => { await f(); }]);
const nowhere = (p, text) => assert.ok(!p.root.outerHTML.includes(text), `${text} is still on the page`);

t("not connected, or the status cannot be read: nothing at all", async () => {
  for (const a of [ok(OFF), ok(Object.assign({}, LINKED, { connected: false })), ok({}), ok(null), ok([]), no(401, "Please sign in again."), no(403, "No."), no(500, "x"), no(503, "x"), new Error("nobody"), { status: 200 }]) {
    const p = await opened({ "GET ": a });
    assert.strictEqual(p.$("#mineTelegram").innerHTML, "", JSON.stringify(a));
    assert.strictEqual(p.reads(), 1); assert.ok(p.text("#mineList").includes("No absences yet."), "the absences are as they were");
    await p.tick(60000); assert.strictEqual(p.reads(), 1, "and it is not asked again by itself");
  }
});
t("connected, not linked", async () => {
  const p = await opened({ "GET ": ok(FREE) });
  assert.strictEqual(p.card(), `Telegram ${LINE} Link Telegram`); assert.strictEqual(p.all("#tgBody .bar").length, 1, "no empty line"); assert.strictEqual(p.text("#mineTelegram h2"), "Telegram"); assert.deepStrictEqual(p.buttons(), ["Link Telegram"]);
  assert.strictEqual(p.$("#tgBody").getAttribute("aria-live"), "polite"); await p.tick(60000); assert.strictEqual(p.reads(), 1, "no code: nothing is read by itself");
});
t("the card is above the absences, whichever script is ready first", async () => {
  let p = await opened({ "GET ": ok(FREE) }); assert.ok(p.$("#pane-mine").innerHTML.indexOf("mineTelegram") < p.$("#pane-mine").innerHTML.indexOf("mineList"));
  p = open("relief.html", { now: NOW, server: c => ok(c.url === URL ? FREE : c.url === "/api/relief/me" ? { name: "Mr Sam Tan", today: "2026-10-13" } : { absences: [] }) });
  p.run("relief-form.js", "relief.js"); await p.settle(); assert.strictEqual(p.$("#mineTelegram").innerHTML, "");
  p.run("relief-telegram.js"); await p.settle(); assert.strictEqual(p.text("#mineTelegram"), `Telegram ${LINE} Link Telegram`);
});
t("another tab first: it is read when My absences is shown, each time", async () => {
  const p = await opened({ "GET ": ok(FREE) }, { hash: "#ask" });
  assert.strictEqual(p.reads(), 0); await p.click("#tab-mine"); assert.strictEqual(p.reads(), 1); has(p, "Link Telegram");
  const mine = () => p.calls.filter(c => c.url === "/api/relief/absences/mine").length;
  p.api["GET "] = ok(LINKED); await p.click("#tab-ask"); assert.strictEqual(p.reads(), 1); assert.strictEqual(mine(), 1); await p.click("#tab-mine"); assert.strictEqual(p.reads(), 2); assert.strictEqual(mine(), 2, "the absences too"); has(p, "Linked as @sam_made_up since Mon 12 Oct.");
  p.api["GET "] = new Error("x"); await p.click("#tab-ask"); await p.click("#tab-mine"); assert.strictEqual(p.$("#mineTelegram").innerHTML, "", "cannot be read any more");
  p.api["GET "] = ok(FREE); await p.click("#tab-mine"); has(p, "Link Telegram");
});
t("Link Telegram: the steps, the code, and where the focus goes", async () => {
  const wait = later(), p = await opened({ "GET ": ok(FREE), "POST /code": wait.answer });
  await p.click("button", "Link Telegram"); assert.deepStrictEqual(p.buttons(), ["Link Telegram (off)"]); await p.click("button", "Link Telegram"); assert.strictEqual(p.told("POST", "/code"), 1, "pressed twice");
  wait.give(200, code(p).data); await p.settle();
  assert.strictEqual(p.body(), `1. Open the bot 2. Press Start there. Or send this code to @made_up_bot: ${CODE} The code works once and runs out in 15 minutes. Cancel`);
  const a = p.find("#tgBody a"); assert.deepStrictEqual([a.getAttribute("href"), a.getAttribute("target"), a.getAttribute("rel"), p.text(a)], [BOT + CODE, "_blank", "noopener", "Open the bot"]);
  const c = p.find("#tgBody .codeline"); assert.ok(c.classes().includes("tg-code")); assert.strictEqual(c.textContent, CODE); assert.strictEqual(p.focus(), a); assert.deepStrictEqual(p.buttons(), ["Cancel"]);
});
t("the code is nowhere but in the card", async () => {
  const p = await coded(); has(p, CODE);
  assert.deepStrictEqual([p.stored, p.location.hash, p.location.search, p.location.href], [undefined, "#mine", "", ""]); assert.ok(!p.document.title.includes(CODE));
  assert.strictEqual(p.root.outerHTML.split(CODE).length - 1, 2, "the link and the code"); assert.ok(p.calls.every(c => !JSON.stringify(c).includes(CODE)));
  await p.click("button", "Cancel"); nowhere(p, CODE);
});
t("while it shows, the status is read every 5 seconds, and it says Linked by itself", async () => {
  const p = await coded(); assert.strictEqual(p.reads(), 1);
  await p.tick(4999); assert.strictEqual(p.reads(), 1); await p.tick(1); assert.strictEqual(p.reads(), 2); await p.tick(10000); assert.strictEqual(p.reads(), 4);
  const el = p.find(".tg-code"); await p.tick(5000); assert.strictEqual(p.find(".tg-code"), el, "nothing is drawn again while nothing has changed: what is selected stays"); assert.strictEqual(p.focus(), p.find("#tgBody a"));
  p.api["GET "] = ok(LINKED); await p.tick(5000); assert.strictEqual(p.card(), "Telegram Linked as @sam_made_up since Mon 12 Oct. Unlink"); nowhere(p, CODE);
  assert.strictEqual(p.focus(), p.find("#mineTelegram h2"), "what had the focus is gone: the heading has it"); const n = p.reads(); await p.tick(60000); assert.strictEqual(p.reads(), n, "and is not read again");
});
t("the focus elsewhere is left there", async () => {
  const p = await coded(); p.find("#tab-ask").focus(); p.api["GET "] = ok(LINKED); await p.tick(5000); has(p, "Linked as"); assert.strictEqual(p.focus(), p.find("#tab-ask"));
  const q = await opened({ "GET ": ok(FREE) }), step = later(); q.api["POST /code"] = step.answer; await q.click("button", "Link Telegram"); q.find("#tab-ask").focus(); step.give(200, code(q).data); await q.settle(); has(q, CODE); assert.strictEqual(q.focus(), q.find("#tab-ask"));
  const r = await opened({ "GET ": ok(FREE) }), none = later(); r.api["POST /code"] = none.answer; await r.click("button", "Link Telegram"); r.focused = null; none.give(200, code(r).data); await r.settle(); assert.strictEqual(r.focus(), r.find("#tgBody a"), "nowhere: it is put back");
});
t("a press beside the buttons does nothing", async () => {
  for (const st of [FREE, LINKED]) { const p = await opened({ "GET ": ok(st) }); await p.click(p.$("#tgBody")); await p.click(p.$("#mineTelegram h2")); assert.strictEqual(p.calls.filter(c => c.url.startsWith(URL)).length, 1); }
});
t("the tab shown while a code shows: read at once, and then every 5 seconds from there, never twice over", async () => {
  const p = await coded(); await p.tick(2000); await p.click("#tab-mine"); assert.strictEqual(p.reads(), 2); await p.tick(4999); assert.strictEqual(p.reads(), 2); await p.tick(1); assert.strictEqual(p.reads(), 3); await p.tick(10000); assert.strictEqual(p.reads(), 5);
  const wait = later(); await p.tick(1000); p.api["GET "] = wait.answer; await p.click("#tab-mine"); assert.strictEqual(p.reads(), 6); await p.show(false); wait.give(200, FREE); await p.settle(); p.api["GET "] = ok(FREE); await p.tick(20000); assert.strictEqual(p.reads(), 6); await p.show(true); assert.strictEqual(p.reads(), 7);
  await p.tick(1000); await p.click("button", "Cancel"); await p.tick(60000); assert.strictEqual(p.reads(), 7, "cancelled between two");
});
t("only while the tab is on screen", async () => {
  const p = await coded(); await p.show(false); await p.tick(60000); assert.strictEqual(p.reads(), 1, "the browser's tab is hidden");
  await p.show(true); assert.strictEqual(p.reads(), 2, "back: at once"); await p.tick(5000); assert.strictEqual(p.reads(), 3); has(p, CODE);
  await p.click("#tab-ask"); await p.tick(60000); assert.strictEqual(p.reads(), 3, "another tab of the page"); await p.show(false); await p.show(true); assert.strictEqual(p.reads(), 3);
  await p.click("#tab-mine"); assert.strictEqual(p.reads(), 4); has(p, CODE); await p.tick(5000); assert.strictEqual(p.reads(), 5);
  await p.show(false); p.api["GET "] = ok(LINKED); await p.tick(20000); has(p, CODE); await p.show(true); has(p, "Linked as @sam_made_up"); nowhere(p, CODE);
});
t("a hidden page that comes back twice reads once at a time", async () => {
  const p = await coded(), wait = later(); p.api["GET "] = wait.answer; await p.tick(5000); assert.strictEqual(p.reads(), 2); await p.tick(30000); assert.strictEqual(p.reads(), 2, "the next waits for the answer");
  wait.give(200, FREE); await p.settle(); p.api["GET "] = ok(FREE); await p.tick(5000); assert.strictEqual(p.reads(), 3);
});
t("past its time: it has run out, and a new one can be had", async () => {
  const p = await coded(); await p.tick(899000); has(p, CODE); await p.tick(5000); assert.strictEqual(p.body(), `${OUT} Get a new code`); nowhere(p, CODE);
  const n = p.reads(); assert.strictEqual(n, 181); await p.tick(60000); assert.strictEqual(p.reads(), n); p.api["POST /code"] = () => code(p, "WXYZ-2345");
  await p.click("button", "Get a new code"); has(p, "WXYZ-2345", "The code works once"); hasNot(p, OUT, CODE); await p.tick(5000); assert.strictEqual(p.reads(), n + 1);
  await p.click("button", "Cancel"); assert.strictEqual(p.card(), `Telegram ${LINE} Link Telegram`);
  const q = await coded(); await q.tick(905000); has(q, OUT); q.api["GET "] = ok(LINKED); await q.click("#tab-mine"); has(q, "Linked as"); q.api["GET "] = ok(FREE); await q.click("#tab-mine"); assert.strictEqual(q.card(), `Telegram ${LINE} Link Telegram`, "linked since: that one is not spoken of any more");
});
t("a link made just before it ran out is seen", async () => {
  const p = await coded(); await p.tick(899000); p.api["GET "] = ok(LINKED); await p.tick(5000); has(p, "Linked as"); hasNot(p, OUT);
});
t("it runs out when the status cannot be read too, and off screen", async () => {
  let p = await coded(); p.api["GET "] = new Error("x"); await p.tick(890000); has(p, CODE); await p.tick(15000); assert.strictEqual(p.body(), `${OUT} Get a new code`);
  p = await coded(); await p.show(false); await p.tick(3600000); await p.show(true); assert.strictEqual(p.body(), `${OUT} Get a new code`); nowhere(p, CODE);
});
t("its time is the server's, unless this device's clock cannot be right", async () => {
  let p = await coded({}, 30); await p.tick(25000); has(p, CODE); await p.tick(5000); assert.strictEqual(p.body(), `${OUT} Get a new code`);
  for (const left of [-1, -86400, 0, 901, 86400, NaN]) {
    p = await coded({}, left); has(p, CODE); await p.tick(895000); has(p, CODE); await p.tick(5000); assert.strictEqual(p.body(), `${OUT} Get a new code`, left);
  }
});
t("Cancel: the code goes, nothing more is read, and a late answer changes nothing", async () => {
  const p = await coded(), wait = later(); p.api["GET "] = wait.answer; await p.tick(5000); const n = p.reads();
  await p.click("button", "Cancel"); assert.strictEqual(p.card(), `Telegram ${LINE} Link Telegram`); nowhere(p, CODE); assert.strictEqual(p.focus(), p.find("button", "Link Telegram"));
  wait.give(200, OFF); await p.settle(); has(p, "Link Telegram"); await p.tick(60000); assert.strictEqual(p.reads(), n);
});
t("a status that fails while a code shows keeps it; the bot disconnected takes the card away", async () => {
  const p = await coded();
  for (const a of [new Error("x"), no(500, "x"), no(401, "Please sign in again.")]) { p.api["GET "] = a; await p.tick(5000); has(p, CODE); }
  p.api["GET "] = ok(FREE); await p.tick(5000); has(p, CODE); p.api["GET "] = ok(OFF); await p.tick(5000); assert.strictEqual(p.$("#mineTelegram").innerHTML, ""); nowhere(p, CODE);
  const n = p.reads(); await p.tick(60000); assert.strictEqual(p.reads(), n); p.api["GET "] = ok(FREE); await p.click("#tab-mine"); assert.strictEqual(p.card(), `Telegram ${LINE} Link Telegram`, "the old code does not come back");
});
t("linked: with and without a handle; Unlink asks first", async () => {
  let p = await opened({ "GET ": ok(Object.assign({}, LINKED, { handle: null })) }); assert.strictEqual(p.card(), "Telegram Linked since Mon 12 Oct. Unlink");
  p = await opened({ "GET ": ok(LINKED) }); assert.strictEqual(p.card(), "Telegram Linked as @sam_made_up since Mon 12 Oct. Unlink");
  await p.click("button", "Unlink"); assert.strictEqual(p.card(), "Telegram Linked as @sam_made_up since Mon 12 Oct. Stop relief messages to this Telegram? Unlink Keep it"); assert.strictEqual(p.told("DELETE", "/link"), 0, "only asked");
  assert.strictEqual(p.focus(), p.find("button", "Keep it"), "a second Return does not unlink"); await p.click("button", "Keep it"); assert.deepStrictEqual(p.buttons(), ["Unlink"]); assert.strictEqual(p.focus(), p.find("button", "Unlink"));
  await p.click("button", "Unlink"); await p.key(p.find("button", "Keep it"), "a"); assert.deepStrictEqual(p.buttons(), ["Unlink", "Keep it"]); assert.strictEqual((await p.key(p.find("button", "Keep it"), "Escape")).defaultPrevented, true); assert.deepStrictEqual(p.buttons(), ["Unlink"]); assert.strictEqual(p.focus(), p.find("button", "Unlink"));
  const wait = later(); p.api["DELETE /link"] = wait.answer; await p.click("button", "Unlink"); await p.click("button", "Unlink"); assert.deepStrictEqual(p.buttons(), ["Unlink (off)", "Keep it (off)"]);
  await p.click("button", "Unlink"); await p.click("button", "Keep it"); assert.strictEqual(p.told("DELETE", "/link"), 1); wait.give(200, FREE); await p.settle();
  assert.strictEqual(p.card(), `Telegram ${LINE} Link Telegram`); assert.strictEqual(p.focus(), p.find("button", "Link Telegram")); assert.strictEqual(p.told("DELETE", "/link"), 1);
});
t("the question stays while the tab is read again, and goes when it is linked no more", async () => {
  const p = await opened({ "GET ": ok(LINKED) }); await p.click("button", "Unlink"); await p.click("#tab-ask"); await p.click("#tab-mine"); has(p, "Stop relief messages to this Telegram?");
  p.api["GET "] = ok(FREE); await p.click("#tab-mine"); assert.strictEqual(p.card(), `Telegram ${LINE} Link Telegram`); p.api["GET "] = ok(LINKED); await p.click("#tab-mine"); assert.deepStrictEqual(p.buttons(), ["Unlink"]);
});
t("a refusal is the server's sentence, and the button is there again", async () => {
  const p = await opened({ "GET ": ok(FREE) });
  for (const [a, text] of [[no(409, "Telegram is not connected yet."), "Telegram is not connected yet."], [no(500, "Made up."), "Made up."], [new Error("x"), "Could not reach the server. Check the connection and try again."]]) {
    p.api["POST /code"] = a; await p.click("button", "Link Telegram"); has(p, LINE, text); assert.ok(p.$("#tgBody .msg.bad")); assert.deepStrictEqual(p.buttons(), ["Link Telegram"]); assert.strictEqual(p.focus(), p.find("button", "Link Telegram"));
  }
  p.api["POST /code"] = no(401, "Please sign in again."); await p.click("button", "Link Telegram"); has(p, "Please sign in again."); const a = p.find("#tgBody .msg a"); assert.deepStrictEqual([a.getAttribute("href"), a.getAttribute("target")], ["/login", "_blank"]);
  p.api["POST /code"] = () => code(p); await p.click("button", "Link Telegram"); has(p, CODE); hasNot(p, "Please sign in again."); await p.tick(5000); assert.ok(p.reads() > 1);
  const q = await opened({ "GET ": ok(LINKED), "DELETE /link": no(503, "Not now.") }); await q.click("button", "Unlink"); await q.click("button", "Unlink"); has(q, "Linked as @sam_made_up", "Not now.", "Keep it"); assert.deepStrictEqual(q.buttons(), ["Unlink", "Keep it"]);
  assert.strictEqual(q.focus(), q.find("button", "Keep it")); await q.click("button", "Keep it"); hasNot(q, "Not now."); assert.deepStrictEqual(q.buttons(), ["Unlink"]);
});
t("a refusal goes when the tab is shown again", async () => {
  const p = await opened({ "GET ": ok(FREE), "POST /code": no(409, "Telegram is not connected yet.") }); await p.click("button", "Link Telegram"); has(p, "Telegram is not connected yet.");
  await p.click("#tab-ask"); await p.click("#tab-mine"); assert.strictEqual(p.card(), `Telegram ${LINE} Link Telegram`);
});
t("a step on its way is not overtaken by a status read before it, or asked for during it", async () => {
  const p = await opened({ "GET ": ok(FREE) }), old = later(), step = later(); p.api["GET "] = old.answer; await p.click("#tab-mine"); p.api["POST /code"] = step.answer;
  await p.click("button", "Link Telegram"); const n = p.reads(); await p.click("#tab-ask"); await p.click("#tab-mine"); assert.strictEqual(p.reads(), n); step.give(200, code(p).data); await p.settle(); has(p, CODE); old.give(200, OFF); await p.settle(); has(p, CODE);
  const q = await opened({ "GET ": ok(LINKED) }), late = later(); q.api["DELETE /link"] = ok(FREE); await q.click("button", "Unlink"); q.api["GET "] = late.answer; await q.click("#tab-mine"); await q.click("button", "Unlink"); has(q, "Link Telegram"); late.give(200, LINKED); await q.settle(); has(q, "Link Telegram");
});
t("a code that comes when the tab is not on screen waits for it", async () => {
  const p = await opened({ "GET ": ok(FREE) }), step = later(); p.api["POST /code"] = step.answer; await p.click("button", "Link Telegram"); await p.click("#tab-ask"); step.give(200, code(p).data); await p.settle();
  assert.strictEqual(p.focus(), p.find("#tab-ask"), "the focus is not taken"); const n = p.reads(); await p.tick(30000); assert.strictEqual(p.reads(), n); await p.click("#tab-mine"); has(p, CODE); assert.strictEqual(p.reads(), n + 1);
});
t("everything is escaped", async () => {
  const mark = x => `<u title="${x}">'${x}'</u>&`;
  const p = await opened({ "GET ": ok(Object.assign({}, FREE, { bot: mark("bot") })) }); p.api["POST /code"] = ok({ code: mark("code"), url: `https://t.me/"><u>x</u>`, until: p.now / 1000 + 900 });
  await p.click("button", "Link Telegram"); has(p, mark("bot"), mark("code")); assert.strictEqual(p.find("#tgBody a").getAttribute("href"), `https://t.me/"><u>x</u>`); assert.strictEqual(p.all("#mineTelegram u").length, 0);
  p.api["GET "] = ok(Object.assign({}, LINKED, { handle: mark("handle"), since: mark("since") })); await p.tick(5000); has(p, mark("handle"), mark("since")); assert.strictEqual(p.all("#mineTelegram u").length, 0);
  p.api["DELETE /link"] = no(400, mark("refusal")); await p.click("button", "Unlink"); await p.click("button", "Unlink"); has(p, mark("refusal")); assert.strictEqual(p.all("#mineTelegram u").length, 0);
});
t("every button has its words, and what it sends is what the routes take", async () => {
  const p = await coded(); assert.ok(p.buttons().every(x => /[A-Za-z]/.test(x))); assert.deepStrictEqual(p.calls.filter(c => c.url.startsWith(URL)).map(c => `${c.method} ${c.url}`), [`GET ${URL}`, `POST ${URL}/code`]);
  const q = await opened({ "GET ": ok(LINKED), "DELETE /link": ok(FREE) }); await q.click("button", "Unlink"); await q.click("button", "Unlink"); assert.deepStrictEqual(q.calls.filter(c => c.url.startsWith(URL)).map(c => [c.method, c.url, c.body]), [["GET", URL, undefined], ["DELETE", `${URL}/link`, undefined]]);
});

run(all);

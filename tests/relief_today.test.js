// Plain-assert tests for what Today (static/relief-today.js) shows and does of Telegram: run with `node tests/relief_today.test.js`.
// The Relief page's own HTML and scripts run in a small stand-in for the browser (tests/dom.js), against answers written here.
const assert = require("assert");
const { open, later, run, css } = require("./dom.js");

const NOW = "2026-10-13T07:40:00+08:00", TODAY = "2026-10-13", URL = "/api/relief/today", REMIND = `${URL}/remind`;
const SAM = "Mr Sam Tan", MAYA = "Ms Maya Lee", EVE = "Ms Evelyn Koh", RUTH = "Ms Ruth Goh", TEAM = "Mr Hugo Ong";
const SEES = "Reliefs I'm covering", NOT_ON = `Not on Telegram: they see it in ${SEES}`;
const ok = data => ({ status: 200, data }), no = (status, error) => ({ status, data: { error } });
const told = (state, at = "2026-10-13T07:20:00+08:00") => ({ state, at });
const APPROVED = { by: TEAM, at: "2026-10-13T07:15:00+08:00" };
/* a row of the day: approved to Mr Tan, who is on Telegram */
const row = more => Object.assign({ id: "a1", ckey: "k5", key: "k5", split: false, absent: EVE, classes: ["1A"], subject: "Science", group: "", room: "R1", p: 5, n: 2, start: "10:30", end: "11:30", work_set: true,
  state: "approved", pick: { who: SAM, by: "team", reason: "Chosen by the relief team." }, approved: APPROVED, ack: null, change: null, stale: false, over_now: false, nobody: false, warn: null, stopped: "", duty: "",
  told: told("sent"), linked: true }, more);
const maya = more => row(Object.assign({ ckey: "k2", key: "k2", p: 1, n: 1, start: "08:00", end: "08:30", pick: { who: MAYA, by: "ai", reason: "Teaches Science." } }, more));
const ANY = { waiting: { approved: null }, open: { approved: null, pick: null }, acknowledged: { ack: { by: SAM, at: "2026-10-13T07:30:00+08:00" } }, change: { change: { why: "A talk", at: "2026-10-13T07:30:00+08:00", pick: null, stale: false } }, cancelled: {}, stopped: { stopped: "1A are on an exam" } };
const inState = (state, more) => row(Object.assign({ state }, ANY[state], more));
const day = (rows, more) => Object.assign({ date: TODAY, filling: false, counts: { need: rows.length, waiting: 0, approved: rows.length, unsent: 0, held: 0, acknowledged: 0, change: 0, nobody: 0, open: 0 }, rows, telegram: true }, more);

/* Today, open; p.day: what the day is, or a function of the call */
async function today(d, more = {}) {
  const p = open("relief.html", Object.assign({ now: NOW, hash: "#today", server: call => {
    if (call.url === "/api/relief/me") return ok({ name: TEAM, depts: [], published: true, today: TODAY, can_team: true, can_plan: true, can_settings: false });
    if (call.method === "GET" && call.url.startsWith(`${URL}?`)) return typeof p.day === "function" ? p.day(call) : p.day.status || p.day instanceof Error ? p.day : ok(p.day);
    if (call.url === REMIND) return typeof p.remind === "function" ? p.remind(call) : p.remind;
    return call.url.startsWith("/api/relief/absences/") || call.url.startsWith(URL) ? p.steps || ok({}) : ok(call.url === "/api/relief/people" ? [] : { absences: [], covers: [], lessons: [], periods: [] });
  } }, more));
  p.day = d;
  p.run("relief-form.js", "relief.js", "relief-telegram.js", "relief-today.js");
  await p.settle();
  p.reads = () => p.calls.filter(c => c.method === "GET" && c.url.startsWith(`${URL}?`)).length;
  p.sent = () => p.calls.filter(c => c.url === REMIND).map(c => `${c.method} ${JSON.stringify(c.body)}`);
  p.row = (k = "k5") => p.find(`.td-row[data-ckey="${k}"]`);
  p.state = (k = "k5") => p.text(p.row(k).querySelector(".td-state"));
  p.under = (k = "k5") => { const el = p.row(k).querySelector(".td-under"); return el ? p.text(el) : ""; };
  p.press = (label, k = "k5") => p.click([...p.row(k).querySelectorAll("button")].find(b => p.text(b) === label));
  p.btn = (label, k = "k5") => [...p.row(k).querySelectorAll("button")].find(b => p.text(b) === label) || null;
  p.acts = () => p.all("#tdActs button").map(b => p.text(b) + (b.disabled ? " (off)" : ""));
  p.top = () => p.all("#tdTop .td-top").map(e => p.text(e));
  p.aloud = () => p.text("#tdSaid") || "";
  return p;
}
const BY = `by ${TEAM}, 07:15`;
const ALL = "Remind all not acknowledged";
const all = []; const t = (name, f) => all.push([name, f]);

t("no bot connected: as the page was, whatever the rows say", async () => {
  for (const more of [{ telegram: false }, { telegram: undefined }, { telegram: null }, { telegram: "yes" }, { telegram: 1 }])
    for (const x of [null, "sent", "unsure", "queued", "failed", "dropped"]) {
      const p = await today(day([row({ told: x && told(x) }), maya({ linked: false })], more)), what = JSON.stringify([more, x]);
      assert.strictEqual(p.state(), `Approved: they see it in ${SEES} ${BY} Change`, what); assert.deepStrictEqual(p.acts(), ["Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"], what);
      await p.tick(60000); assert.strictEqual(p.reads(), 1, "nothing is read again"); assert.ok(!p.text("#pane-today").includes("Telegram") && !p.text("#pane-today").includes("Remind") && !p.text("#pane-today").includes("ent"  + " 07"), what);
    }
});
t("what was said of an approved relief, before who approved it", async () => {
  const cases = [[told("sent"), "Sent 07:20"], [told("sent", "2026-10-12T15:00:00+08:00"), "Sent Mon 12 Oct, 15:00"], [told("unsure"), "May not have been sent: remind them"], [told("queued"), "Being sent…"], [told("failed"), "Could not be sent: remind them"],
    [null, "Not sent yet"], [undefined, "Not sent yet"], [told("dropped"), "Not sent yet"], [told("odd"), "Not sent yet"], [told("sent", null), "Sent"]];
  for (const [x, line] of cases) { const p = await today(day([row({ told: x })])); assert.strictEqual(p.state(), `Approved ${line} ${BY} Change Remind`); }
  for (const [x, line] of [[null, NOT_ON], [told("dropped"), NOT_ON], [told("queued"), NOT_ON], [told("unsure"), NOT_ON], [told("failed"), NOT_ON], [told("sent"), "Sent 07:20 · not on Telegram now"]]) {
    const p = await today(day([row({ told: x, linked: false })])); assert.strictEqual(p.state(), `Approved ${line} ${BY} Change`);
  }
  const p = await today(day([row({ approved: null })])); assert.strictEqual(p.state(), "Approved Sent 07:20 Change Remind");
});
t("on a date past, only what is so", async () => {
  const YESTERDAY = "2026-10-12", lines = [[told("sent"), true, "Sent 07:20"], [told("unsure"), true, "May not have been sent"], [told("queued"), true, "Being sent…"], [told("failed"), true, "Could not be sent"], [null, true, "Not sent"], [told("dropped"), true, "Not sent"],
    [null, false, NOT_ON], [told("failed"), false, NOT_ON], [told("sent"), false, "Sent 07:20 · not on Telegram now"]];
  for (const [x, linked, line] of lines) {
    const p = await today(c => ok(day([row({ told: x, linked })], { date: c.url.slice(-10) }))), input = p.find("#tdDate");
    input.value = YESTERDAY;
    for (const f of p.find("#pane-today").on.change) f({ target: input });
    await p.tick(400);
    assert.strictEqual(p.text("#tdTitle"), "Relief on Mon 12 Oct");
    assert.strictEqual(p.state(), `Approved ${line} ${BY}`);
    assert.strictEqual(p.row().querySelectorAll(".td-state .td-warn").length, linked && x && ["unsure", "failed"].includes(x.state) ? 1 : 0);
  }
});
t("what went wrong is marked, the rest is not", async () => {
  for (const [x, bad] of [["sent", 0], ["queued", 0], ["unsure", 1], ["failed", 1], ["dropped", 0]]) { const p = await today(day([row({ told: told(x) })])); assert.strictEqual(p.row().querySelectorAll(".td-state .td-warn").length, bad, x); }
  const p = await today(day([row({ told: told("failed"), linked: false })])); assert.strictEqual(p.row().querySelectorAll(".td-state .td-warn").length, 0);
});
t("the other states say what they said, and have no Remind", async () => {
  for (const state of Object.keys(ANY)) {
    const with_ = await today(day([inState(state)])), without = await today(day([inState(state)], { telegram: false }));
    assert.strictEqual(with_.state(), without.state(), state); assert.ok(!with_.state().includes("Remind") && !with_.state().includes("Sent"), state); assert.deepStrictEqual(with_.acts(), ["Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"], state);
  }
});
t("Remind: what it sends, off while it is on its way, its answer beside the row, and the day read again", async () => {
  const p = await today(day([row(), maya()])), wait = later(); p.remind = wait.answer; await p.press("Remind");
  assert.deepStrictEqual(p.sent(), [`POST {"date":"${TODAY}","covers":[{"id":"a1","ckey":"k5"}]}`]); assert.ok(p.btn("Remind").disabled && p.btn("Change").disabled && !p.btn("Remind", "k2").disabled); await p.press("Remind"); assert.strictEqual(p.sent().length, 1);
  assert.deepStrictEqual(p.acts(), [ALL + " (off)", "Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"], "not all while one is on its way"); assert.strictEqual(p.reads(), 1);
  p.day = day([row({ told: told("queued", NOW) }), maya()]); wait.give(200, { sent: 1, skipped: [] }); await p.settle();
  assert.strictEqual(p.under(), "Reminded."); assert.strictEqual(p.under("k2"), ""); assert.strictEqual(p.reads(), 2); assert.ok(p.state().startsWith("Approved Being sent… by")); assert.ok(p.row().querySelector(".msg.ok")); assert.strictEqual(p.focus(), p.btn("Remind"));
  assert.deepStrictEqual(p.acts(), [ALL, "Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"]);
});
t("Remind: why not, and a refusal", async () => {
  const p = await today(day([row(), maya()]));
  for (const why of ["Sent at 07:38: wait a few minutes.", "Last tried at 07:38: wait a few minutes.", "Nobody to remind.", "Not on Telegram."]) { p.remind = ok({ sent: 0, skipped: [{ ckey: "k5", name: SAM, why }] }); await p.press("Remind"); assert.strictEqual(p.under(), why); assert.ok(p.row().querySelector(".msg.bad")); }
  for (const [a, text] of [[no(409, "Telegram is not connected yet."), "Telegram is not connected yet."], [no(503, "Telegram could not be reached just now. Try again."), "Telegram could not be reached just now. Try again."], [new Error("x"), "Could not reach the server. Check the connection and try again."]]) {
    p.remind = a; await p.press("Remind"); assert.strictEqual(p.under(), text); assert.ok(p.row().querySelector(".msg.bad")); assert.ok(!p.btn("Remind").disabled);
  }
  for (const odd of [{}, null, { sent: 0, skipped: "x" }, { sent: 0, skipped: [] }, { sent: 0, skipped: [null] }]) { p.remind = ok(odd); await p.press("Remind"); assert.strictEqual(p.under(), "", JSON.stringify(odd)); assert.ok(!p.btn("Remind").disabled); }
  p.remind = ok({ sent: 1, skipped: [] }); await p.press("Remind", "k2"); assert.strictEqual(p.under("k2"), "Reminded."); assert.strictEqual(p.under(), "");
});
t("two rows of one cover key are told apart by their absence", async () => {
  const p = await today(day([row(), row({ id: "b2", absent: RUTH })])), second = p.all('.td-row[data-ckey="k5"]')[1]; p.remind = ok({ sent: 1, skipped: [] });
  await p.click([...second.querySelectorAll("button")].find(b => p.text(b) === "Remind")); assert.deepStrictEqual(p.sent(), [`POST {"date":"${TODAY}","covers":[{"id":"b2","ckey":"k5"}]}`]);
  assert.deepStrictEqual(p.all('.td-row[data-ckey="k5"]').map(r => (r.querySelector(".td-under") ? p.text(r.querySelector(".td-under")) : "")), ["", "Reminded."]);
});
t("acknowledged meanwhile: no Remind any more, and the row's first button has the focus", async () => {
  const p = await today(day([row()])); p.remind = () => { p.day = day([inState("acknowledged")]); return ok({ sent: 0, skipped: [{ ckey: "k5", name: SAM, why: "Nobody to remind." }] }); };
  await p.press("Remind"); assert.strictEqual(p.btn("Remind"), null); assert.strictEqual(p.under(), "Nobody to remind."); assert.strictEqual(p.focus(), p.btn("Change")); assert.deepStrictEqual(p.acts(), ["Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"]);
});
t("an answer that comes after the date was moved is not said above the other day's rows", async () => {
  const gives = [[200, { sent: 1, skipped: [] }], [200, { sent: 0, skipped: [{ ckey: "k5", name: SAM, why: "Nobody to remind." }] }], [503, { error: "Telegram could not be reached just now. Try again." }]];
  for (const press of [p => p.press("Remind"), p => p.click("button", ALL)]) {
    for (const [status, data] of gives) {
      const p = await today(day([row()])), wait = later();
      p.remind = wait.answer;
      await press(p);
      await p.click("#tdSeg button", "Tomorrow");
      assert.ok(p.acts().includes(ALL + " (off)"), "one is on its way still");
      wait.give(status, data);
      await p.settle();
      assert.deepStrictEqual(p.top(), [], `${press} ${status}`);
      assert.strictEqual(p.under(), "");
      assert.ok(p.acts().includes(ALL) && !p.btn("Remind").disabled, "and it can be pressed again");
      await p.click("#tdSeg button", "Today");
      assert.deepStrictEqual([p.top(), p.under()], [[], ""]);
      assert.ok(!p.btn("Remind").disabled);
    }
    const p = await today(day([row()])), wait = later();
    p.remind = wait.answer;
    await press(p);
    await p.click("#tdSeg button", "Tomorrow");
    await p.click("#tdSeg button", "Today");
    wait.give(200, { sent: 1, skipped: [] });
    await p.settle();
    assert.ok([...p.top(), p.under()].some(x => x.startsWith("Reminded")), "back on the day it was pressed on: said there");
  }
});
t("Remind is for whoever can be reached, on a date not past; another date says so", async () => {
  const p = await today(day([row({ linked: false, told: null }), maya()])); assert.strictEqual(p.btn("Remind"), null); assert.ok(p.btn("Remind", "k2"));
  p.day = c => ok(day([row(), maya()], { date: c.url.slice(-10) })); await p.click("#tdSeg button", "Tomorrow"); p.remind = ok({ sent: 1, skipped: [] }); await p.press("Remind"); assert.deepStrictEqual(p.sent(), [`POST {"date":"2026-10-14","covers":[{"id":"a1","ckey":"k5"}]}`]);
  await p.click("button", ALL); assert.strictEqual(p.sent()[1], `POST {"date":"2026-10-14","covers":[{"id":"a1","ckey":"k5"},{"id":"a1","ckey":"k2"}]}`);
  const input = p.find("#tdDate"); input.value = "2026-10-12"; for (const f of p.find("#pane-today").on.change) f({ target: input }); await p.tick(400);
  assert.strictEqual(p.text("#tdTitle"), "Relief on Mon 12 Oct"); assert.strictEqual(p.state(), `Approved Sent 07:20 ${BY}`); assert.deepStrictEqual(p.acts(), [ALL + " (off)", "Approve all waiting (off)", "Send out approved (off)", "Fill now (off)", "Refresh"]);
});
t("Remind all: first in its row, when somebody approved can be reached, and only then", async () => {
  for (const [rows, there] of [[[row()], 1], [[row({ linked: false })], 0], [[row({ linked: false }), maya()], 1], [[], 0], [Object.keys(ANY).map((s, i) => inState(s, { ckey: `k${i}` })), 0]]) {
    const p = await today(day(rows)); assert.deepStrictEqual(p.acts(), [...(there ? [ALL] : []), "Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"]);
  }
});
t("nothing else in the row moves when Remind all comes or goes: its place is kept while a bot is connected", async () => {
  const kids = p => p.find("#tdActs").kids.filter(k => k.tag), place = p => kids(p)[0], rest = p => kids(p).slice(1).map(k => `${k.tag} ${k.getAttribute("data-td")}`);
  const ROW = ["button all", "button send-all", "button fill", "button reload"], gap = p => place(p).classes().includes("td-gap") && place(p).tag === "span" && place(p).getAttribute("aria-hidden") === "true" && p.text(place(p)) === ALL;
  const p = await today(day([row()]));
  assert.ok(place(p).getAttribute("data-td") === "remind-all" && p.text(place(p)) === ALL);
  assert.deepStrictEqual(rest(p), ROW);
  p.day = day([inState("acknowledged")]);
  await p.click("button", "Refresh");
  assert.ok(gap(p), "nobody to remind: its place, not seen, not read and not to be pressed");
  assert.deepStrictEqual(rest(p), ROW);
  const wait = later();
  p.day = () => wait.answer;
  await p.click("#tdSeg button", "Tomorrow");
  assert.ok(gap(p), "while another day is read");
  wait.give(200, day([row()], { date: "2026-10-14" }));
  await p.settle();
  assert.ok(place(p).getAttribute("data-td") === "remind-all");
  p.day = no(500, "Made up.");
  await p.click("#tdSeg button", "Today");
  assert.ok(gap(p), "nor when it cannot be read");
  const q = await today(day([row()], { telegram: false }));
  assert.deepStrictEqual(kids(q).map(k => k.getAttribute("data-td")), ["all", "send-all", "fill", "reload"], "no bot: no place");
  const first = later(), r = await today(() => first.answer);
  assert.strictEqual(kids(r).length, 4, "not known yet");
  first.give(200, day([inState("acknowledged")]));
  await r.settle();
  assert.ok(gap(r));
  r.day = day([row()], { telegram: false });
  await r.click("button", "Refresh");
  assert.strictEqual(kids(r).length, 4, "no bot any more");
  const box = css("relief.html", ".td-gap"), button = css("style.css", "button");
  assert.ok(box.includes("visibility:hidden"));
  for (const x of ["padding:7px 12px", "1px solid"]) assert.ok(box.includes(x) && button.includes(x), `its place is as large as the button: ${x}`);
  assert.ok(css("relief.html", ".td-acts").includes("justify-content:flex-end"), "the row ends at the right: what comes first moves nothing");
  for (const x of ['.td-acts [data-td="remind-all"]', ".td-gap"]) assert.ok(/margin-right:(\d+)px/.exec(css("relief.html", x))[1] >= 10, "and Approve all's shorter words do not bring it under the pointer");
});
t("on a phone Remind all comes last, and no place is kept for it", () => {
  const PHONE = "(max-width:640px)", button = '.td-acts [data-td="remind-all"]';
  assert.ok(/(^|;)order:1(;|$)/.test(css("relief.html", button, PHONE)), "after the others, which have none");
  assert.ok(css("relief.html", button, PHONE).includes("margin-right:0"));
  assert.ok(css("relief.html", ".td-gap", PHONE).includes("display:none"), "no empty line above the buttons");
  for (const x of [button, ".td-gap"]) {
    assert.ok(!/(^|;)(order|display):/.test(css("relief.html", x)), `${x}: wider than that, first, with its place`);
    assert.strictEqual(css("relief.html", x, "(max-width:760px)"), "");
  }
});
t("at any width there is room between the buttons at the top and the day", () => {
  assert.ok(/margin-bottom:(\d+)px/.exec(css("relief.html", ".td-acts.tg"))[1] >= 10, css("relief.html", ".td-acts.tg"));
});
t("Remind all: what it sends, off while anything is on its way, and what it answers above the rows", async () => {
  const p = await today(day([row(), maya(), row({ ckey: "k7", key: "k7", linked: false }), inState("acknowledged", { ckey: "k8", key: "k8" }), inState("waiting", { ckey: "k9", key: "k9" })])), wait = later(); p.remind = wait.answer;
  await p.click("button", ALL); assert.deepStrictEqual(p.sent(), [`POST {"date":"${TODAY}","covers":[{"id":"a1","ckey":"k5"},{"id":"a1","ckey":"k2"}]}`]);
  assert.deepStrictEqual(p.acts(), [ALL + " (off)", "Approve all waiting (off)", "Send out approved (off)", "Fill now (off)", "Refresh"]); assert.ok(p.btn("Remind").disabled && p.btn("Approve", "k9").disabled); await p.click("button", ALL); assert.strictEqual(p.sent().length, 1);
  const why = "Sent at 07:38: wait a few minutes.";
  wait.give(200, { sent: 1, skipped: [{ ckey: "k2", name: MAYA, why }, { ckey: "k7", name: null, why: "Nobody to remind." }, { ckey: "k8", name: null, why: "Nobody to remind." }, { ckey: "k9", name: MAYA, why }, { ckey: "kx", why: "Not on Telegram." }] }); await p.settle();
  assert.deepStrictEqual(p.top(), ["Reminded 1.", `${MAYA}: ${why}`, "Nobody to remind.", `${MAYA}: ${why}`, "Not on Telegram."]); assert.strictEqual(p.all("#tdTop .msg.bad").length, 4); assert.strictEqual(p.all("#tdTop .msg.ok").length, 1);
  assert.strictEqual(p.under(), ""); assert.strictEqual(p.reads(), 2); assert.strictEqual(p.focus(), p.find("button", ALL)); assert.deepStrictEqual(p.acts(), [ALL, "Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"]);
  p.remind = ok({ sent: 2, skipped: [] }); await p.click("button", ALL); assert.deepStrictEqual(p.top(), ["Reminded 2."], "what was said before goes");
});
t("Remind all: a refusal, an odd answer, and everyone acknowledged by then", async () => {
  const p = await today(day([row()])); p.remind = no(503, "Telegram could not be reached just now. Try again."); await p.click("button", ALL); assert.deepStrictEqual(p.top(), ["Telegram could not be reached just now. Try again."]); assert.ok(p.$("#tdTop .msg.bad")); assert.strictEqual(p.focus(), p.find("button", ALL));
  for (const odd of [null, {}, { sent: "x", skipped: 5 }, { sent: 0, skipped: [null] }]) { p.remind = ok(odd); await p.click("button", ALL); assert.deepStrictEqual(p.top(), ["Nobody to remind."], JSON.stringify(odd)); assert.ok(p.$("#tdTop .msg.bad")); }
  p.remind = () => { p.day = day([inState("acknowledged")]); return ok({ sent: 0, skipped: [{ ckey: "k5", name: SAM, why: "Nobody to remind." }] }); }; await p.click("button", ALL);
  assert.deepStrictEqual(p.top(), [`${SAM}: Nobody to remind.`]); assert.deepStrictEqual(p.acts(), ["Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"]); assert.strictEqual(p.focus(), p.find("#tdActs button", "Refresh"), "its button is gone: the one that does nothing but read");
});
t("Remind all with nobody reminded: the reasons alone, or that there is nobody", async () => {
  const p = await today(day([row(), maya()])), why = "Sent at 07:38: wait a few minutes.", cases = [
    [[], ["Nobody to remind."]],
    [[{ ckey: "k5", name: SAM, why }], [`${SAM}: ${why}`]],
    [[{ ckey: "k5", name: SAM, why }, { ckey: "k2", name: MAYA, why }], [`${SAM}: ${why}`, `${MAYA}: ${why}`]],
    [[{ ckey: "k5", name: null, why: "Nobody to remind." }, { ckey: "k2", name: null, why: "Nobody to remind." }], ["Nobody to remind."]]];
  for (const [skipped, lines] of cases) {
    p.remind = ok({ sent: 0, skipped });
    await p.click("button", ALL);
    assert.deepStrictEqual(p.top(), lines);
    assert.strictEqual(p.all("#tdTop .msg.ok").length, 0);
  }
  p.remind = ok({ sent: 1, skipped: [{ ckey: "k2", name: MAYA, why }] });
  await p.click("button", ALL);
  assert.deepStrictEqual(p.top(), ["Reminded 1.", `${MAYA}: ${why}`]);
});
t("Remind all is off while Approve all, Fill now or a row's step is on its way; they are off while it is", async () => {
  for (const [sel, label] of [["button", "Fill now"], ["button", "Approve all 1 waiting"]]) {
    const p = await today(day([row(), inState("waiting", { ckey: "k9", key: "k9" })], { counts: { waiting: 1 } })), wait = later(); p.steps = wait.answer; await p.click(sel, label);
    assert.ok(p.acts().includes(ALL + " (off)"), label); wait.give(200, { started: true, approved: 1 }); await p.settle(); assert.ok(p.acts().includes(ALL), label);
  }
  const p = await today(day([row(), inState("waiting", { ckey: "k9", key: "k9" })])), one = later(), two = later(); p.steps = one.answer; await p.press("Approve", "k9"); assert.ok(p.acts().includes(ALL + " (off)"));
  p.remind = two.answer; await p.press("Remind"); one.give(200, {}); await p.settle(); assert.ok(p.acts().includes(ALL + " (off)"), "the other is still on its way"); two.give(200, { sent: 1, skipped: [] }); await p.settle(); assert.ok(p.acts().includes(ALL));
});
t("what is being sent is read again every 3 seconds, at most 5 times", async () => {
  const p = await today(day([row({ told: told("queued") })])); assert.strictEqual(p.reads(), 1); await p.tick(2999); assert.strictEqual(p.reads(), 1); await p.tick(1); assert.strictEqual(p.reads(), 2);
  await p.tick(12000); assert.strictEqual(p.reads(), 6); await p.tick(60000); assert.strictEqual(p.reads(), 6, "five times, and no more"); assert.ok(p.state().includes("Being sent…"));
  await p.click("button", "Refresh"); assert.strictEqual(p.reads(), 7); await p.tick(60000); assert.strictEqual(p.reads(), 12, "asked for again: five more");
  p.remind = ok({ sent: 1, skipped: [] }); await p.press("Remind"); assert.strictEqual(p.reads(), 13); await p.tick(60000); assert.strictEqual(p.reads(), 18, "after Remind too");
});
t("it stops once nothing is being sent, and the row says what came of it", async () => {
  const p = await today(day([row({ told: told("queued") }), maya({ told: told("queued") })])); await p.tick(3000); p.day = day([row({ told: told("sent", NOW) }), maya({ told: told("queued") })]); await p.tick(3000); assert.ok(p.state().startsWith("Approved Sent 07:40 by"));
  p.day = day([row({ told: told("sent", NOW) }), maya({ told: told("failed", NOW) })]); await p.tick(3000); assert.strictEqual(p.reads(), 4); await p.tick(60000); assert.strictEqual(p.reads(), 4); assert.ok(p.state("k2").startsWith("Approved Could not be sent: remind them by"));
  for (const r of [row(), row({ told: null }), row({ told: told("unsure") }), row({ told: told("queued"), linked: false }), inState("acknowledged", { told: told("queued") }), inState("change", { told: told("queued") })]) { const q = await today(day([r])); await q.tick(60000); assert.strictEqual(q.reads(), 1, r.state); }
});
t("sent out here: its message is made after the answer, so the day is read again for it too, 5 times at most", async () => {
  const UNSENT = row({ out: "unsent", told: null });
  for (const press of [p => p.press("Send out"), p => p.click("button", "Send out 1 approved")]) {
    const p = await today(day([UNSENT], { counts: { unsent: 1 } })); await p.tick(60000); assert.strictEqual(p.reads(), 1); p.steps = () => { p.day = day([row({ out: "sent", told: null })]); return ok({ sent: 1, at: null, skipped: [] }); }; p.server = (f => c => { const a = f(c); return typeof a === "function" ? a(c) : a; })(p.server);
    await press(p); assert.ok(p.state().startsWith("Approved Not sent yet by")); assert.strictEqual(p.reads(), 2); p.day = day([row({ told: told("queued") })]); await p.tick(3000); assert.ok(p.state().startsWith("Approved Being sent… by")); assert.strictEqual(p.aloud(), "");
    p.day = day([row({ told: told("sent", NOW) })]); await p.tick(3000); assert.ok(p.state().startsWith("Approved Sent 07:40 by")); assert.strictEqual(p.aloud(), `${SAM}, 1A Science P6–P7: Sent 07:40`); assert.strictEqual(p.reads(), 4); await p.tick(60000); assert.strictEqual(p.reads(), 4);
    for (const end of [() => p.press("Remind"), () => p.click("button", ALL)]) { p.remind = ok({ sent: 1, skipped: [] }); p.day = day([row({ told: null })]); const n = p.reads(); await end(); await p.tick(60000); assert.strictEqual(p.reads(), n + 6); }
    await p.click("button", "Refresh"); const n = p.reads(); await p.tick(60000); assert.strictEqual(p.reads(), n, "only after a step here");
    p.remind = no(503, "x"); for (const end of [() => p.press("Remind"), () => p.click("button", ALL)]) { const m = p.reads(); await end(); await p.tick(60000); assert.strictEqual(p.reads(), m + 1, "refused: nothing is to come"); }
  }
  const q = await today(day([row({ out: "unsent", linked: false, told: null }), row({ ckey: "k8", key: "k8", linked: false, told: null })])); q.steps = ok({}); q.day = day([row({ linked: false, told: null }), row({ ckey: "k8", key: "k8", linked: false, told: null })]); await q.press("Send out"); await q.tick(60000); assert.strictEqual(q.reads(), 2, "nobody who can be reached");
  const r = await today(day([UNSENT], { telegram: false })); r.steps = ok({}); r.day = day([row({ told: null })], { telegram: false }); await r.press("Send out"); await r.tick(60000); assert.strictEqual(r.reads(), 2, "no bot");
  const h = await today(day([UNSENT])); h.steps = ok({}); h.day = day([row({ out: "held", goes_at: "2026-10-14T06:45:00+08:00", told: null })]); await h.press("Send out"); await h.tick(60000); assert.strictEqual(h.reads(), 2, "held: it goes later, nothing to wait for");
  h.day = day([row({ out: "sent", told: null })]); await h.click("button", "Refresh"); await h.tick(60000); assert.strictEqual(h.reads(), 3, "gone at its time: not followed, as it was not then");
  for (const [step, label] of [[p => p.press("Approve"), "Approve"], [p => p.click("button", "Approve all 1 waiting"), "Approve all"]]) {
    const a = await today(day([inState("waiting", { told: null })], { counts: { waiting: 1 } })); a.steps = ok({ approved: 1, skipped: [] }); a.day = day([row({ out: "unsent", told: null })]); await step(a); await a.tick(60000); assert.strictEqual(a.reads(), 2, `${label} alone tells nobody: nothing to wait for`);
    const o = await today(day([inState("waiting", { told: null })], { counts: { waiting: 1 } })); o.steps = ok({ approved: 1, skipped: [] }); o.day = day([row({ told: null })]); await step(o); await o.tick(60000); assert.strictEqual(o.reads(), 2, `${label}: not followed, whatever the answer says`);
  }
});
t("what is followed after a step is followed through a Refresh, the tab shown again and a refused step", async () => {
  const UNSENT = row({ out: "unsent", told: null }), between = [p => p.click("button", "Refresh"), async p => { await p.click("#tab-ask"); await p.click("#tab-today"); }, async p => { p.remind = no(503, "x"); await p.press("Remind"); }, async p => { p.steps = no(400, "x"); await p.press("Approve", "k2"); }];
  for (const step of between) {
    const p = await today(day([UNSENT, maya({ state: "waiting", approved: null, told: null })]));
    p.steps = ok({});
    p.day = day([row({ told: null }), maya({ state: "waiting", approved: null, told: null })]);
    await p.press("Send out");
    await step(p);
    const n = p.reads();
    await p.tick(3000);
    assert.strictEqual(p.reads(), n + 1, String(step));
    p.day = day([row({ told: told("sent", NOW) }), maya({ state: "waiting", approved: null, told: null })]);
    await p.tick(3000);
    assert.ok(p.state().startsWith("Approved Sent 07:40 by"));
    assert.strictEqual(p.aloud(), `${SAM}, 1A Science P6–P7: Sent 07:40`);
    await p.tick(60000);
    assert.strictEqual(p.reads(), n + 2, "told: no more");
  }
});
t("it ends when it is told, when the date is changed, and after the 5 reads", async () => {
  const NONE = row({ told: null }), approved = async () => { const p = await today(day([row({ out: "unsent", told: null })])); p.steps = ok({}); p.day = day([NONE]); await p.press("Send out"); return p; };
  let p = await approved();
  await p.tick(15000);
  assert.strictEqual(p.reads(), 7);
  await p.click("button", "Refresh");
  await p.tick(60000);
  assert.strictEqual(p.reads(), 8, "the 5 reads are over");
  p = await approved();
  await p.click("#tdSeg button", "Tomorrow");
  await p.click("#tdSeg button", "Today");
  const n = p.reads();
  await p.tick(60000);
  assert.strictEqual(p.reads(), n, "another date in between");
  p = await approved();
  p.day = day([row({ told: told("queued") })]);
  await p.tick(3000);
  p.day = day([row({ told: told("dropped") })]);
  await p.tick(3000);
  const m = p.reads();
  await p.tick(60000);
  assert.strictEqual(p.reads(), m, "it was told, and is followed no more");
});
t("a row that is gone after its step (split) is followed no more, and the page goes on", async () => {
  const p = await today(day([inState("waiting", { told: null })]));
  p.steps = ok({});
  p.day = day([0, 1].map(i => inState("waiting", { ckey: `k5#${i}`, split: true, p: 5 + i, n: 1, told: null })));
  await p.press("Split");
  await p.press("Split after P6");
  assert.strictEqual(p.all(".td-row[data-ckey]").length, 2);
  assert.ok(p.top()[0].includes("split after P6"), "said above the rows, as before");
  await p.tick(60000);
  assert.strictEqual(p.reads(), 2);
});
t("only the row of the step is followed", async () => {
  const p = await today(day([row({ told: null }), maya({ out: "unsent", told: null })]));
  p.steps = ok({});
  p.day = day([row({ told: null }), maya({ told: null })]);
  await p.press("Send out", "k2");
  p.day = day([row({ told: null }), maya({ told: told("sent", NOW) })]);
  await p.tick(3000);
  assert.strictEqual(p.aloud(), `${MAYA}, 1A Science P2: Sent 07:40`);
  const n = p.reads();
  await p.tick(60000);
  assert.strictEqual(p.reads(), n, "Mr Tan's was not sent before either");
});
t("only on screen; back on screen it is read at once, still five times in all", async () => {
  const p = await today(day([row({ told: told("queued") })])); await p.show(false); await p.tick(60000); assert.strictEqual(p.reads(), 1); await p.show(true); assert.strictEqual(p.reads(), 2); await p.tick(60000); assert.strictEqual(p.reads(), 6);
  await p.show(false); await p.show(true); await p.tick(60000); assert.strictEqual(p.reads(), 6); await p.click("#tab-mine"); await p.tick(60000); assert.strictEqual(p.reads(), 6); await p.click("#tab-today"); assert.strictEqual(p.reads(), 7, "the tab shown: from the start");
  await p.tick(3000); await p.click("#tab-mine"); await p.tick(60000); assert.strictEqual(p.reads(), 8, "another tab of the page");
});
t("a reading that fails ends it, until it is asked for", async () => {
  const p = await today(day([row({ told: told("queued") })])); p.day = no(500, "Made up."); await p.tick(60000); assert.strictEqual(p.reads(), 2); assert.ok(p.top().some(x => x.startsWith("Made up."))); assert.ok(p.state().includes("Being sent…"), "what was there stays");
  p.day = day([row({ told: told("queued") })]); await p.click("#tdTop button", "Try again"); await p.tick(60000); assert.strictEqual(p.reads(), 8);
});
t("while picks are made the day is read as before, and what is being sent is counted from their end", async () => {
  const p = await today(day([row({ told: told("queued") })], { filling: true })); await p.tick(60000); assert.strictEqual(p.reads(), 21, "every 3 seconds, without an end"); p.day = day([row({ told: told("queued") })]); await p.tick(60000); assert.strictEqual(p.reads(), 27);
  const q = await today(day([row()], { filling: true, telegram: false })); await q.tick(30000); assert.strictEqual(q.reads(), 11);
});
t("nothing is drawn again while nothing has changed, and the focus stays", async () => {
  const p = await today(day([row({ told: told("queued") })])), el = p.row(); p.btn("Change").focus(); await p.tick(3000); assert.strictEqual(p.row(), el); assert.strictEqual(p.focus(), p.btn("Change"));
  p.day = day([row()]); await p.tick(3000); assert.notStrictEqual(p.row(), el); assert.strictEqual(p.focus(), p.btn("Change"));
  for (const label of ["Fill now", ALL, "Refresh"]) { const q = await today(day([row({ told: told("queued") })])); q.find("#tdActs button", label).focus(); await q.tick(3000); assert.strictEqual(q.focus(), q.find("#tdActs button", label), label); q.day = day([row()]); await q.tick(3000); assert.strictEqual(q.focus(), q.find("#tdActs button", label), label); }
  p.find("#tab-mine").focus(); p.day = day([row({ told: told("failed") })]); await p.click("button", "Refresh"); p.find("#tab-mine").focus(); await p.tick(3000); assert.strictEqual(p.focus(), p.find("#tab-mine"));
});
t("the buttons at the top are drawn only when something in them changes", async () => {
  const p = await today(day([row({ told: told("queued") })])), els = () => p.all("#tdActs button"), was = els();
  for (let i = 0; i < 3; i++) await p.tick(3000);
  assert.strictEqual(p.reads(), 4);
  els().forEach((b, i) => assert.ok(b === was[i], p.text(b)));
  p.day = day([row()]);
  await p.tick(3000);
  els().forEach((b, i) => assert.ok(b === was[i], "the row alone has changed"));
  p.day = day([inState("acknowledged")]);
  await p.click("button", "Refresh");
  assert.deepStrictEqual(p.acts(), ["Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"]);
});
t("the buttons at the top after a reading that changed nothing: as they are, not as they were drawn during it", async () => {
  const p = await today(day([inState("waiting")], { filling: true, telegram: false })), wait = later();
  p.day = () => wait.answer;
  await p.tick(3000);
  p.steps = later().answer;
  await p.click("button", "Fill now");
  assert.deepStrictEqual(p.acts(), ["Approve all waiting (off)", "Send out approved (off)", "Fill now (off)", "Reading… (off)"], "no bot: as the page was");
  wait.give(200, day([inState("waiting")], { filling: true, telegram: false }));
  await p.settle();
  assert.deepStrictEqual(p.acts(), ["Approve all waiting (off)", "Send out approved (off)", "Fill now (off)", "Refresh"]);
});
t("a row's button pressed while the day is read by itself: Refresh stays as it is", async () => {
  for (const telegram of [false, true]) {
    const p = await today(day([inState("waiting")], { filling: true, telegram })), wait = later();
    p.day = () => wait.answer;
    await p.tick(3000);
    assert.strictEqual(p.reads(), 2);
    p.steps = later().answer;
    await p.press("Approve");
    assert.deepStrictEqual(p.acts(), ["Approve all waiting (off)", "Send out approved (off)", "Fill now", "Refresh"], `telegram ${telegram}`);
  }
  const p = await today(day([row()])), wait = later();
  p.day = () => wait.answer;
  await p.click("button", "Refresh");
  assert.ok(p.acts().includes("Reading… (off)"), "asked for: it says so");
});
t("what came of it is said to who cannot see it, once", async () => {
  const p = await today(day([row({ told: told("queued") }), maya({ told: told("queued") })])), el = p.find("#tdSaid"); assert.ok(el.getAttribute("aria-live") === "polite" && el.classes().includes("vh")); assert.strictEqual(p.aloud(), ""); await p.tick(3000); assert.strictEqual(p.aloud(), "");
  p.day = day([row({ told: told("sent", NOW) }), maya({ told: told("queued") })]); await p.tick(3000); assert.strictEqual(p.aloud(), `${SAM}, 1A Science P6–P7: Sent 07:40`);
  await p.tick(3000); assert.strictEqual(p.aloud(), "", "nothing new: it does not stay to be read"); await p.click("button", "Refresh");
  p.day = day([row({ told: told("sent", NOW) }), maya({ told: told("queued") })], { counts: { need: 3 } }); await p.tick(3000); assert.strictEqual(p.aloud(), ""); assert.ok(p.find("#tdSaid") === el, "the same element: what is written into it is said");
  p.day = day([row({ told: told("sent", NOW) }), maya({ told: told("unsure", NOW) })]); await p.tick(3000); assert.strictEqual(p.aloud(), `${MAYA}, 1A Science P2: May not have been sent: remind them`);
  const q = await today(day([row({ told: told("queued") })])); q.day = day([inState("acknowledged")]); await q.tick(3000); assert.strictEqual(q.aloud(), "", "answered already: the row says so"); const r = await today(day([row({ told: null })])); r.day = day([row()]); await r.click("button", "Refresh"); assert.strictEqual(r.aloud(), "");
});
t("nothing is said while no bot is connected; a row without a name still has its lesson", async () => {
  const p = await today(day([row({ told: told("queued") })], { telegram: false })); p.day = day([row()], { telegram: false }); await p.click("button", "Refresh"); assert.strictEqual(p.aloud(), "");
  p.day = day([row({ told: told("queued"), pick: null })]); await p.click("button", "Refresh"); p.day = day([row({ pick: null })]); await p.tick(3000); assert.strictEqual(p.aloud(), "1A Science P6–P7: Sent 07:20");
});
t("Remind all: the focus elsewhere, or on another tab, is left there", async () => {
  for (const [go, where] of [[p => p.find("#tab-mine").focus(), "#tab-mine"], [p => p.click("#tab-ask"), "#tab-ask"], [p => p.find("#tdDate").focus(), "#tdDate"]]) { const p = await today(day([row()])), wait = later(); p.remind = wait.answer; await p.click("button", ALL); await go(p); wait.give(200, { sent: 1, skipped: [] }); await p.settle(); assert.strictEqual(p.focus(), p.find(where), where); }
  const p = await today(day([row()])), wait = later(); p.remind = wait.answer; await p.click("button", ALL); await p.click("#tab-ask"); p.focused = null; wait.give(200, { sent: 1, skipped: [] }); await p.settle(); assert.strictEqual(p.focus(), "", "not on the screen: nothing is given the focus");
});
t("the lines above the rows are not said again with what came of it, nor the unseen line with them", async () => {
  const q = await today(day([row({ told: told("queued") })]));
  q.remind = ok({ sent: 1, skipped: [] });
  await q.click("button", ALL);
  const top = q.find("#tdTop .td-top");
  q.day = day([row({ told: told("sent", NOW) })]);
  await q.tick(3000);
  assert.ok(q.aloud().endsWith("Sent 07:40") && q.find("#tdTop .td-top") === top);
  assert.strictEqual(q.all("#tdTop .vh").length, 0);
});
t("no bot any more: the unseen line goes", async () => {
  const p = await today(day([row()]));
  p.find("#tdSaid");
  p.day = day([row()], { telegram: false });
  await p.click("button", "Refresh");
  assert.strictEqual(p.$("#tdSaid"), null);
});
t("the lines above the rows are not said again by a reading that changes none of them", async () => {
  const p = await today(day([row({ told: told("queued") })])); p.remind = ok({ sent: 1, skipped: [] }); await p.click("button", ALL); const line = p.find("#tdTop .td-top"); assert.strictEqual(p.text(line), "Reminded 1.");
  p.day = day([row({ told: told("queued") })], { counts: { need: 2 } }); await p.tick(3000); assert.strictEqual(p.find("#tdTop .td-top"), line);
});
t("everything is escaped", async () => {
  const mark = x => `<u title="${x}">'${x}'</u>&`, p = await today(day([row({ pick: { who: mark("who"), by: "team", reason: "" }, approved: { by: mark("by"), at: "2026-10-13T07:15:00+08:00" } })])); assert.ok(p.state().includes(mark("by")));
  p.remind = ok({ sent: 0, skipped: [{ ckey: "k5", name: mark("name"), why: mark("why") }] }); await p.press("Remind"); assert.strictEqual(p.under(), mark("why")); await p.click("button", ALL); assert.deepStrictEqual(p.top(), [`${mark("name")}: ${mark("why")}`]);
  p.remind = no(400, mark("refusal")); await p.press("Remind"); assert.strictEqual(p.under(), mark("refusal")); p.day = day([row({ told: told("queued"), pick: { who: mark("who"), by: "team", reason: "" } })]); await p.click("button", "Refresh"); p.day = day([row({ told: told("sent", "2026-10-12T15:00:00+08:00"), pick: { who: mark("who"), by: "team", reason: "" } })]); await p.tick(3000);
  assert.ok(p.aloud().startsWith(mark("who"))); assert.strictEqual(p.all("#pane-today u").length, 0);
  const q = await today(day([row({ told: told("sent", "<u>1234567T07:20:00") })])); assert.ok(q.state().startsWith("Approved Sent <u>1234567, 07:20 by")); assert.strictEqual(q.all("#pane-today u").length, 0);
});

/* ---- Send-out, Task 3 ---- */
t("Send out: the top button and the row's, what each sends and says", async () => {
  const u = row({ out: "unsent", told: null }), w = inState("waiting", { ckey: "k2", key: "k2", p: 1, n: 1 });
  const p = await today(day([u, w], { counts: { need: 2, waiting: 1, approved: 0, unsent: 1, held: 0, acknowledged: 0, change: 0, nobody: 0, open: 0 } }));
  assert.ok(p.acts().includes("Send out 1 approved") && p.btn("Send out") && !p.btn("Send out", "k2"));
  p.steps = ok({}); await p.press("Send out"); assert.strictEqual(p.under(), "Sent out.");
  assert.deepStrictEqual(p.calls.filter(c => c.url.endsWith("/send-out")).map(c => c.body), [{ who: SAM, approved_at: APPROVED.at }]);
  p.steps = ok({ sent: 1, at: "2026-10-13T06:45:00+08:00", skipped: [] }); await p.click("#tdActs button", "Send out 1 approved");
  assert.deepStrictEqual(p.top(), ["Sent out 1 relief for Tue 13 Oct. They will be sent at 06:45."]);
  const q = await today(day([row({ out: "unsent", told: null, stale: true, warn: "Mr Sam Tan is no longer free then: change it" })])); assert.ok(!q.btn("Send out"));
});
t("Approve and Change say that Send out is next", async () => {
  const p = await today(day([inState("waiting")])); p.steps = ok({}); await p.press("Approve"); assert.strictEqual(p.under(), `${SAM} approved: press Send out to tell them.`);
});
t("Send out all: what it sends, and each one skipped said as Approve all says it", async () => {
  const u = row({ out: "unsent", told: null }), m = maya({ out: "unsent", told: null }), h = row({ ckey: "k8", key: "k8", out: "held", told: null });
  const p = await today(day([u, m, h], { counts: { need: 3, waiting: 0, approved: 0, unsent: 2, held: 1, acknowledged: 0, change: 0, nobody: 0, open: 0 } }));
  p.steps = ok({ sent: 1, at: null, skipped: [{ id: "a1", ckey: "k2", name: MAYA, why: "The pick has changed since you looked: look again before approving." }] });
  await p.click("#tdActs button", "Send out 2 approved");
  assert.deepStrictEqual(p.calls.filter(c => c.url === "/api/relief/today/send-out").map(c => c.body), [{ date: TODAY, covers: [{ id: "a1", ckey: "k5", who: SAM, approved_at: APPROVED.at }, { id: "a1", ckey: "k2", who: MAYA, approved_at: APPROVED.at }] }]);
  assert.deepStrictEqual(p.top(), ["Sent out 1 relief for Tue 13 Oct.", `1A Science P2, ${MAYA}: The pick has changed since you looked: look again before approving.`]);
  assert.strictEqual(p.under("k2"), "The pick has changed since you looked: look again before approving.");
  const z = await today(day([row({ out: "unsent", told: null })], { counts: { unsent: 0 } })); assert.ok(z.acts().includes("Send out approved (off)"));
});
t("Remind and Remind all only for a relief that has reached its teacher", async () => {
  for (const out of ["unsent", "held"]) {
    const p = await today(day([row({ out, told: null })]));
    assert.strictEqual(p.btn("Remind"), null, out); assert.ok(!p.acts().includes(ALL), out);
  }
  const p = await today(day([row({ out: "sent" })])); assert.ok(p.btn("Remind") && p.acts().includes(ALL));
  const q = await today(day([row({ out: "held", told: told("queued") })])); await q.tick(60000); assert.strictEqual(q.reads(), 1, "held: not being sent, nothing to read again for");
});

/* ---- Send-out, Task 5: Today, by state and after the cut-off ---- */
const HOURS = { morning: "06:30", send_from: "06:45", cut_off: "14:00", today: TODAY, next_day: "2026-10-14", past_cut_off: false };
t("by state: not sent out, will be sent at, asked after the cut-off", async () => {
  const p = await today(day([row({ out: "unsent", told: null }), maya({ out: "held", goes_at: "2026-10-13T06:45:00+08:00", told: null }), inState("waiting", { ckey: "k9", key: "k9", asked_after: "14:10" })], { hours: HOURS }));
  assert.ok(p.state().startsWith("Approved Approved · not sent out") && p.state("k2").startsWith("Approved Will be sent at 06:45"));
  assert.ok(p.state("k9").includes("Asked at 14:10, after the cut-off: nobody was pinged"));
  assert.deepStrictEqual(p.top(), ["1 relief sent out: it will be sent at 06:45 on Tue 13 Oct. You can still change it until then."]);
});
t("past the cut-off: the next school day, its line, and the counters", async () => {
  const p = await today(day([], { date: "2026-10-14", hours: Object.assign({}, HOURS, { past_cut_off: true }), counts: { need: 2, waiting: 2, approved: 0, unsent: 0, held: 0, acknowledged: 0, change: 0, nobody: 0, open: 0 } }));
  assert.ok(p.top().includes("Past the cut-off (14:00). Nobody on the team is pinged until the morning message at 06:30. What you send out now is sent at 06:45 on Wed 14 Oct."));
  assert.ok(p.text("#tdSub").includes("After 14:00 the page opens on the next school day") && p.text("#tdCounts").includes("Approved, not sent out"));
  assert.strictEqual(p.calls.find(c => c.url.startsWith(`${URL}?`)).url, `${URL}?`, "the first reading asks for no date");
  assert.deepStrictEqual(p.all("#tdSeg button").map(b => p.text(b)), ["Today", "Tomorrow"]);
});
t("no bot: no room kept under the buttons at the top", () => {
  assert.ok(!/margin-bottom/.test(css("relief.html", ".td-acts")) && /margin-bottom:12px/.test(css("relief.html", ".td-acts.tg")));
});
t("the room under the buttons at the top is kept only while a bot is connected", async () => {
  const p = await today(day([row()])), q = await today(day([row()], { telegram: false }));
  assert.ok(p.find("#tdActs").classList.contains("tg") && !q.find("#tdActs").classList.contains("tg"));
});
t("two reliefs held: the plural, and the earliest time of a later day with its day", async () => {
  const g = "2026-10-14T06:45:00+08:00";
  const p = await today(day([row({ out: "held", goes_at: g, told: null }), maya({ out: "held", goes_at: g, told: null })], { hours: HOURS }));
  assert.deepStrictEqual(p.top(), ["2 reliefs sent out: they will be sent at 06:45 on Wed 14 Oct. You can still change them until then."]);
  assert.ok(p.state().startsWith("Approved Will be sent at Wed 14 Oct, 06:45"), p.state());
});
t("reliefs held for two times: the line names the earliest", async () => {
  const p = await today(day([row({ out: "held", goes_at: "2026-10-14T06:45:00+08:00", told: null }), maya({ out: "held", goes_at: "2026-10-13T06:45:00+08:00", told: null })], { hours: HOURS }));
  assert.deepStrictEqual(p.top(), ["2 reliefs sent out: they will be sent at 06:45 on Tue 13 Oct. You can still change them until then."]);
});
t("before the first answer the page is not called past", async () => {
  const w = later(), p = await today(() => w.answer);
  assert.ok(!p.text("#tdSub").includes("past"), p.text("#tdSub"));
  w.give(200, day([], { hours: HOURS })); await p.settle();
  assert.ok(!p.text("#tdSub").includes("past"));
});
t("no line above the rows when nothing is held, and none about the cut-off on another day", async () => {
  const p = await today(day([row({ out: "unsent", told: null }), row({ ckey: "k8", key: "k8", out: "sent" })], { hours: Object.assign({}, HOURS, { past_cut_off: true }) }));
  assert.deepStrictEqual(p.top(), [], "today's own view, past the cut-off: no line");
  assert.strictEqual(p.state("k8").includes("Approved · not sent out"), false);
  assert.ok(p.text("#tdSub").includes("After 14:00 the page opens on the next school day"));
});
t("a sent row says what it said, with no line of the new states", async () => {
  const p = await today(day([row({ out: "sent" })], { hours: HOURS }));
  assert.strictEqual(p.state(), `Approved Sent 07:20 ${BY} Change Remind`);
});
t("a row not sent out has Send out, Change and no Remind, whether a bot is connected or not", async () => {
  for (const telegram of [true, false]) {
    const p = await today(day([row({ out: "unsent", told: null })], { telegram }));
    assert.strictEqual(p.state(), `Approved Approved · not sent out ${BY} Send out Change`);
    const h = await today(day([row({ out: "held", goes_at: "2026-10-13T06:45:00+08:00", told: null })], { telegram }));
    assert.strictEqual(h.state(), `Approved Will be sent at 06:45 ${BY} Change`);
  }
});
t("a day with a next school day that is not tomorrow is named by its day; no next day, no button", async () => {
  const fri = Object.assign({}, HOURS, { next_day: "2026-10-16" });
  const p = await today(day([], { hours: fri }));
  assert.deepStrictEqual(p.all("#tdSeg button").map(b => p.text(b)), ["Today", "Fri 16 Oct"]);
  await p.click("#tdSeg button", "Fri 16 Oct");
  assert.strictEqual(p.calls.filter(c => c.method === "GET" && c.url.startsWith(`${URL}?`)).pop().url, `${URL}?date=2026-10-16`);
  const q = await today(day([], { hours: Object.assign({}, HOURS, { next_day: null }) }));
  assert.deepStrictEqual(q.all("#tdSeg button").map(b => q.text(b)), ["Today"]);
});
t("the page opens on the server's date, and Refresh keeps the date shown", async () => {
  const p = await today(c => ok(day([], { date: c.url.endsWith("?") ? "2026-10-14" : c.url.slice(-10), hours: HOURS })));
  assert.strictEqual(p.find("#tdDate").value, "2026-10-14"); assert.strictEqual(p.text("#tdTitle"), "Relief on Wed 14 Oct");
  await p.click("#tdActs button", "Refresh");
  assert.strictEqual(p.calls.filter(c => c.method === "GET" && c.url.startsWith(`${URL}?`)).pop().url, `${URL}?date=2026-10-14`);
});

run(all);

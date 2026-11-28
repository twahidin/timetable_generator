// Plain-assert tests for "Change the dates or times" on an absence card (static/relief-change.js): run with `node tests/relief_change.test.js`.
// The Relief page's own HTML runs in a small stand-in for the browser (tests/dom.js), with the real relief-form.js and relief-dates.js;
// the editor alone (a stand-in Relief gives api, json, say and me), and on My absences with the real relief.js, against answers written here.
const assert = require("assert");
const { open, later, run } = require("./dom.js");

const NOW = "2026-10-12T09:00:00+08:00", TODAY = "2026-10-12", TOMORROW = "2026-10-13", PAST = "2026-10-09";
const EVE = "Ms Evelyn Koh", SAM = "Mr Sam Tan", GRACE = "Ms Grace Wong";
const LOOKED = "The request has changed since you looked: look again before saving.";
const ok = data => ({ status: 200, data }), no = (status, error) => ({ status, data: { error } });
const PERIODS = Array.from({ length: 12 }, (_, p) => { const m = 450 + p * 30, t = x => `${String(Math.floor(x / 60)).padStart(2, "0")}:${String(x % 60).padStart(2, "0")}`; return { p, start: t(m), end: t(m + 30) }; });
const weekdays = (from, to) => { const out = []; for (let d = new Date(from + "T00:00:00Z"); d <= new Date(to + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + 1)) if (d.getUTCDay() % 6) out.push(d.toISOString().slice(0, 10)); return out; };
const DAYS = { today: TODAY, days: weekdays(TODAY, "2026-11-20"), off: {} };
const per = (p, n) => (n > 1 ? `P${p + 1}–P${p + n}` : `P${p + 1}`);
const item = (key, date, p, n, title, line) => ({ key, date, p, n, title, periods: per(p, n), line });
const answer = more => Object.assign({ kept: [], added: [], gone: [], earlier: 0, dates: [TODAY], periods: null, unchanged: false, day_periods: PERIODS }, more);
const rec = more => Object.assign({ id: "a1", teacher: EVE, by: EVE, how: "asked", dates: [TODAY], periods: null, reason: "Medical", reason_text: "", remarks: "", cancelled: null, acknowledged: null,
  lessons: [{ key: "k5", date: TODAY, p: 5, n: 2, classes: ["1A"], subject: "Science", group: "", room: "R1", start: "10:00", end: "11:00", needed: true, covers: [], work: {} }] }, more);
const A_PREVIEW = item("k5", TOMORROW, 5, 2, "1A Science", "Mr Sam Tan stays (approved)");
const SOME = answer({ dates: [TOMORROW], kept: [A_PREVIEW], added: [item("k9", TOMORROW, 8, 1, "2C Science", "a relief teacher will be picked")],
  gone: [item("k2", TODAY, 1, 1, "2A Science", "Mr Sam Tan is told the relief is no longer needed")] });

let RF0 = null;   /* the pure helpers, from a page of their own */
function pure() {
  if (RF0) return RF0;
  const p = open("relief.html", { now: NOW, server: () => ok({}) });
  p.run("relief-form.js", "relief-dates.js", "relief-change.js");
  p.window.ReliefForm.setToday(TODAY);
  return (RF0 = p.window.ReliefChange);
}
const same = (a, b, msg) => assert.deepStrictEqual(JSON.parse(JSON.stringify(a)), b, msg);   /* a value from the page's own context */

/* a stand-in for relief.js's api: through the page's server, answered as Relief.api answers */
const apiOf = p => async (url, o = {}) => {
  const call = { method: o.method || "GET", url, body: o.body === undefined ? undefined : JSON.parse(o.body) };
  p.calls.push(call);
  const a = await p.server(call);
  if (a instanceof Error) return { ok: false, status: 0, error: "Could not reach the server. Check the connection and try again." };
  const data = a.data === undefined ? undefined : JSON.parse(JSON.stringify(a.data));
  return a.status >= 200 && a.status < 300 ? { ok: true, status: a.status, data } : { ok: false, status: a.status, error: (data && data.error) || "Something went wrong. Try again." };
};
const PREVIEW = id => `/api/relief/absences/${id}/change/preview`, SAVE = id => `/api/relief/absences/${id}/change`;
function serve(p, call) {   /* p.preview, p.save: an answer, a promise of one, an Error, a function of the call, or a preview's own data */
  const give = a => (typeof a === "function" ? give(a(call)) : a instanceof Error || (a && (a.status || typeof a.then === "function")) ? a : ok(a));
  if (call.url === "/api/relief/school-days") return ok(DAYS);
  if (call.url.endsWith("/change/preview")) return give(p.preview);
  if (call.url.endsWith("/change")) return give(p.save);
  return null;
}
const previews = p => p.calls.filter(c => c.url.endsWith("/change/preview"));
const saves = p => p.calls.filter(c => c.method === "POST" && c.url.endsWith("/change"));
const fireChange = el => { const e = { type: "change", target: el }; for (let x = el; x; x = x.parent) (x.on.change || []).slice().forEach(f => f(e)); };
async function choose(p, sel, v) { const el = p.find(sel); el.value = String(v); fireChange(el); await p.settle(); }

/* the editor alone, open on r; me: who is signed in; preview / save: the answers (or functions of the call) */
async function editor(r, { me = EVE, preview = answer({ unchanged: true }), save = ok({}) } = {}) {
  const p = open("relief.html", { now: NOW, server: call => serve(p, call) });
  Object.assign(p, { preview, save, done: [] });
  p.run("relief-form.js", "relief-dates.js", "relief-change.js");
  const RF = p.window.ReliefForm;
  RF.setToday(TODAY);
  p.window.Relief = { me: { name: me }, api: apiOf(p), json: (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }),
    say: m => (m && m.text ? `<span class="msg ${m.bad ? "bad" : "ok"}" role="status">${RF.esc(m.text)}</span>` : "") };
  p.document.body.insertAdjacentHTML("beforeend", `<div id="rcBox"></div>`);
  p.ed = p.window.ReliefChange.mount(p.$("#rcBox"), r, { onDone: (got, said) => p.done.push([got, said]) });
  await p.settle();
  p.box = () => p.text("#rcBox");
  p.saveBtn = () => p.find("#rcBox button", "Save the change");
  p.pressed = what => p.all(`#rcBox button[data-rc="${what}"]`).filter(b => b.getAttribute("aria-pressed") === "true").map(b => p.text(b));
  return p;
}
const has = (p, ...texts) => texts.forEach(x => assert.ok(p.box().includes(x), `${x} not in: ${p.box()}`));
const hasNot = (p, ...texts) => texts.forEach(x => assert.ok(!p.box().includes(x), `${x} in: ${p.box()}`));

const all = []; const t = (name, f) => all.push([name, f]);

/* ---------------------------------------------------------------- initial, body, lines */
t("initial: today, tomorrow, and picked dates without the past ones", async () => {
  const RC = pure();
  same(RC.initial(rec({ dates: [TODAY] }), TODAY), { day: "today", picked: [TODAY], away: "whole", from: null, to: null });
  same(RC.initial(rec({ dates: [TOMORROW] }), TODAY), { day: "tomorrow", picked: [TOMORROW], away: "whole", from: null, to: null });
  same(RC.initial(rec({ dates: ["2026-10-14", PAST] }), TODAY), { day: "pick", picked: ["2026-10-14"], away: "whole", from: null, to: null });
  same(RC.initial(rec({ dates: [TODAY, TOMORROW] }), TODAY), { day: "pick", picked: [TODAY, TOMORROW], away: "whole", from: null, to: null });
  same(RC.initial(rec({ dates: [PAST, TODAY] }), TODAY), { day: "today", picked: [TODAY], away: "whole", from: null, to: null });
  same(RC.initial(rec({ periods: [5, 11] }), TODAY), { day: "today", picked: [TODAY], away: "some", from: 5, to: 11 });
});
t("body: the dates as Ask for relief gives them; periods null for the whole day", async () => {
  const RC = pure(), s = more => Object.assign({ day: "today", picked: ["2026-10-16", "2026-10-14"], away: "whole", from: null, to: null }, more);
  same(RC.body(s(), TODAY), { dates: [TODAY], periods: null });
  same(RC.body(s({ day: "tomorrow" }), TODAY), { dates: [TOMORROW], periods: null });
  same(RC.body(s({ day: "pick" }), TODAY), { dates: ["2026-10-14", "2026-10-16"], periods: null });
  same(RC.body(s({ day: "pick", picked: [] }), TODAY), { dates: [], periods: null });
  same(RC.body(s({ away: "some", from: 5, to: 11 }), TODAY), { dates: [TODAY], periods: [5, 11] });
});
t("lines: kept, added, no longer needed, then the earlier lessons", async () => {
  const RC = pure(), p = answer({ kept: [item("k5", TOMORROW, 5, 2, "1A Science", "Mr Sam Tan stays (approved)")], added: [item("k9", "2026-10-16", 1, 3, "2C Science", "a relief teacher will be picked")],
    gone: [item("k2", TODAY, 3, 1, "2A Science", "Mr Sam Tan is told the relief is no longer needed")], earlier: 2 });
  same(RC.lines(p), [
    { mark: "✔", text: "Kept: Tue 13 Oct P6–P7, 1A Science · Mr Sam Tan stays (approved)" },
    { mark: "➕", text: "Added: Fri 16 Oct P2–P4, 2C Science · a relief teacher will be picked" },
    { mark: "✖", text: "No longer needed: Mon 12 Oct P4, 2A Science · Mr Sam Tan is told the relief is no longer needed" },
    { mark: "", text: "2 earlier lessons stay as they were." }]);
  same(RC.lines(answer({ earlier: 1 })), [{ mark: "", text: "1 earlier lesson stays as it was." }]);
  same(RC.lines(answer({})), []);
});

/* ---------------------------------------------------------------- the editor */
t("it opens on the record's own dates and times: nothing changes yet, nothing to save", async () => {
  const p = await editor(rec());
  same(previews(p).map(c => [c.method, c.url, c.body]), [["POST", PREVIEW("a1"), { dates: [TODAY], periods: null }]]);
  has(p, "Change the dates or times", "Dates", "Today", "Tomorrow", "Pick dates", "Away for", "Whole day", "Some periods", "What this change does", "Nothing changes yet.", "Reason for the change (optional)", "Save the change", "Close");
  same(p.pressed("day"), ["Today"]); same(p.pressed("away"), ["Whole day"]);
  assert.ok(p.saveBtn().disabled, "nothing to save");
  assert.strictEqual(p.find("#rcBox input[data-rc=\"why\"]").getAttribute("maxlength"), "200");
  hasNot(p, "is told on Telegram");
  assert.strictEqual(p.ed.dirty(), false);
});
t("Tomorrow: the preview, lesson by lesson; Save sends the shown keys and the reason", async () => {
  const p = await editor(rec());
  p.preview = answer({ dates: [TOMORROW], kept: [A_PREVIEW], added: [item("k9", TOMORROW, 8, 1, "2C Science", "a relief teacher will be picked")],
    gone: [item("k2", TODAY, 1, 1, "2A Science", "Mr Sam Tan is told the relief is no longer needed")], earlier: 0 });
  await p.click("#rcBox button", "Tomorrow");
  same(previews(p)[1].body, { dates: [TOMORROW], periods: null });
  has(p, "✔ Kept: Tue 13 Oct P6–P7, 1A Science · Mr Sam Tan stays (approved)", "➕ Added: Tue 13 Oct P9, 2C Science · a relief teacher will be picked",
    "✖ No longer needed: Mon 12 Oct P2, 2A Science · Mr Sam Tan is told the relief is no longer needed");
  hasNot(p, "Nothing changes yet.", "earlier");
  assert.ok(!p.saveBtn().disabled);
  assert.strictEqual(p.ed.dirty(), true);
  await p.type("#rcBox input[data-rc=\"why\"]", "  Back in school on Mon after all ");
  const saved = rec({ dates: [TOMORROW] });
  p.save = ok(saved);
  await p.click(p.saveBtn());
  same(saves(p).map(c => [c.url, c.body]), [[SAVE("a1"), { dates: [TOMORROW], periods: null, why: "Back in school on Mon after all", shown: { added: ["k9"], gone: ["k2"] } }]]);
  same(p.done, [[saved, "Changed."]]);
});
t("while the preview is read, and while saving, Save cannot be pressed", async () => {
  const p = await editor(rec()), wait = later();
  p.preview = () => wait.answer;
  await p.click("#rcBox button", "Tomorrow");
  assert.ok(p.saveBtn().disabled); has(p, "Reading what this change does…");
  wait.give(200, SOME); await p.settle();
  assert.ok(!p.saveBtn().disabled);
  const s = later(); p.save = () => s.answer;
  await p.click(p.saveBtn());
  assert.ok(p.find("#rcBox button", "Saving…").disabled && p.find("#rcBox button", "Close").disabled);
  await p.click("#rcBox button", "Today");
  assert.strictEqual(previews(p).length, 2, "nothing is read again while saving");
  s.give(200, rec({ dates: [TOMORROW] })); await p.settle();
  assert.strictEqual(saves(p).length, 1); assert.strictEqual(p.done.length, 1);
});
t("the newest answer wins", async () => {
  const p = await editor(rec()), first = later(), second = later();
  p.preview = () => (previews(p).length === 2 ? first.answer : second.answer);
  await p.click("#rcBox button", "Tomorrow");
  await p.click("#rcBox button", "Today");
  second.give(200, answer({ unchanged: true })); await p.settle();
  first.give(200, SOME); await p.settle();
  has(p, "Nothing changes yet."); hasNot(p, "Kept:");
  assert.ok(p.saveBtn().disabled);
});
t("a refusal shows its sentence in the preview's place, and Save waits", async () => {
  const p = await editor(rec());
  p.preview = no(400, "You already have an absence then.");
  await p.click("#rcBox button", "Tomorrow");
  has(p, "You already have an absence then."); hasNot(p, "Nothing changes yet.", "Kept:");
  assert.ok(p.saveBtn().disabled);
  p.preview = () => new Error("nobody answers");
  await p.click("#rcBox button", "Today");
  has(p, "Could not reach the server");
  p.preview = answer({ unchanged: true });
  await p.click("#rcBox button", "Try again");
  has(p, "Nothing changes yet.");
});
t("Some periods: from and to over the answer's periods; the preview waits for both", async () => {
  const p = await editor(rec());
  await p.click("#rcBox button", "Some periods");
  assert.strictEqual(previews(p).length, 1, "nothing is read until from and to are chosen");
  has(p, "Choose the periods first: from and to.");
  assert.ok(p.saveBtn().disabled);
  assert.strictEqual(p.text(p.find("#rcBox select[data-per=\"from\"]").querySelector("option[value=\"5\"]")), "P6 (10:00)");
  p.preview = answer({ periods: [5, 6], gone: [item("k2", TODAY, 1, 1, "2A Science", "nobody was approved yet")] });
  await choose(p, "#rcBox select[data-per=\"from\"]", 5);
  assert.strictEqual(previews(p).length, 1);
  await choose(p, "#rcBox select[data-per=\"to\"]", 6);
  same(previews(p)[1].body, { dates: [TODAY], periods: [5, 6] });
  has(p, "✖ No longer needed: Mon 12 Oct P2, 2A Science · nobody was approved yet");
  assert.ok(!p.saveBtn().disabled);
});
t("a record away for some periods opens on them", async () => {
  const p = await editor(rec({ periods: [5, 11] }));
  same(previews(p)[0].body, { dates: [TODAY], periods: [5, 11] });
  same(p.pressed("away"), ["Some periods"]);
  assert.strictEqual(p.find("#rcBox select[data-per=\"from\"]").querySelector("option[selected]").getAttribute("value"), "5");
  assert.strictEqual(p.find("#rcBox select[data-per=\"to\"]").querySelector("option[selected]").getAttribute("value"), "11");
});
t("Pick dates: the calendar holds the record's dates today or later; a day ticked reads the preview again", async () => {
  const p = await editor(rec({ dates: [PAST, "2026-10-14"] }));
  same(previews(p)[0].body, { dates: ["2026-10-14"], periods: null });
  same(p.pressed("day"), ["Pick dates"]);
  assert.ok(p.$('#rcBox .rd-d[data-d="2026-10-14"]').classList.contains("pick"));
  await p.click('#rcBox .rd-d[data-d="2026-10-15"]');
  same(previews(p)[1].body, { dates: ["2026-10-14", "2026-10-15"], periods: null });
});
t("the request changed since: its sentence, and the preview is read again", async () => {
  const p = await editor(rec(), { preview: SOME });
  p.save = no(400, LOOKED);
  await p.click(p.saveBtn());
  has(p, LOOKED);
  assert.strictEqual(previews(p).length, 2, "read again");
  same(p.done, []);
  assert.ok(!p.saveBtn().disabled, "the new preview may be saved");
});
t("Close: nothing is sent", async () => {
  const p = await editor(rec(), { preview: SOME });
  await p.click("#rcBox button", "Close");
  same(p.done, [[null, ""]]); same(saves(p), []);
});
t("someone else saving it: the absent teacher is told on Telegram", async () => {
  const p = await editor(rec({ how: "planned", by: GRACE }), { me: GRACE });
  has(p, `${EVE} is told on Telegram what changed.`);
});

/* ---------------------------------------------------------------- on My absences (relief.js) */
async function mine(list, more = {}) {
  const p = open("relief.html", { now: NOW, hash: "#mine", server: call => {
    if (call.url === "/api/relief/me") return ok({ name: EVE, depts: ["Science"], published: true, today: TODAY, can_team: false, can_plan: false, can_settings: false });
    if (call.url === "/api/relief/absences/mine") return ok({ absences: p.list });
    if (call.url.startsWith("/api/relief/absences/") && call.url.endsWith("/cancel")) return no(400, "Say why in a line.");
    return serve(p, call) || ok({});
  } });
  Object.assign(p, { list, preview: answer({ unchanged: true }), save: ok({}) }, more);
  p.run("relief-form.js", "relief-dates.js", "relief-change.js", "relief.js");
  await p.settle();
  p.card = id => p.find(`#mineList .ab[data-id="${id}"]`);
  p.btns = id => p.card(id).querySelectorAll("button").map(b => p.text(b));
  return p;
}
const CHANGE = "Change dates or times";

t("the card's button: on a request still to come, never on a backup, a cancelled one or one all past", async () => {
  const p = await mine([rec({ id: "a1" }), rec({ id: "a2", exams: { id: "x1", kind: "exam" } }), rec({ id: "a3", cancelled: { by: EVE, why: "Well again" } }), rec({ id: "a4", dates: [PAST] }),
    rec({ id: "a5", dates: [PAST, TOMORROW] }), rec({ id: "a6", teacher: SAM, by: SAM })]);
  assert.ok(p.btns("a1").includes(CHANGE), p.btns("a1"));
  assert.ok(p.btns("a1").includes("Not needed at all: cancel"));
  for (const id of ["a2", "a3", "a4", "a6"]) assert.ok(!p.btns(id).includes(CHANGE), id);
  assert.ok(p.btns("a5").includes(CHANGE));
  assert.strictEqual(p.card("a1").querySelector('button[data-act="change"]').getAttribute("data-act"), "change");
});
t("pressing it opens the editor under the lessons; Save puts the answered record and says Changed.", async () => {
  const p = await mine([rec({ id: "a1" })]);
  await p.click(p.card("a1").querySelector('button[data-act="change"]'));
  const box = p.card("a1").querySelector(".rc");
  assert.ok(box, "the editor is in the card");
  assert.ok(!p.btns("a1").includes(CHANGE), "no second button while it is open");
  assert.ok(p.focus() && p.text(p.focus()) === "Today", "the focus is on the dates");
  same(previews(p).map(c => c.body), [{ dates: [TODAY], periods: null }]);
  p.preview = SOME;
  await p.click("#mineList .rc button", "Tomorrow");
  p.save = ok(rec({ id: "a1", dates: [TOMORROW], lessons: [Object.assign({}, rec().lessons[0], { date: TOMORROW })] }));
  await p.click("#mineList .rc button", "Save the change");
  assert.ok(!p.card("a1").querySelector(".rc"), "closed once saved");
  assert.ok(p.text(p.card("a1")).includes("Changed."), p.text(p.card("a1")));
  assert.ok(p.text(p.card("a1")).includes("Tue 13 Oct"), "the answered record is drawn");
  assert.strictEqual(p.text(p.focus()), CHANGE);
  await p.click(p.card("a1").querySelector('button[data-act="change"]'));
  same(previews(p).slice(-1)[0].body, { dates: [TOMORROW], periods: null }, "opens on the saved dates");
});
t("one editor open at a time; a redraw of the card keeps what was chosen; Close shuts it", async () => {
  const p = await mine([rec({ id: "a1" }), rec({ id: "a2", dates: [TOMORROW] })]);
  await p.click(p.card("a1").querySelector('button[data-act="change"]'));
  p.preview = SOME;
  await p.click("#mineList .rc button", "Tomorrow");
  await p.type('#mineList .rc input[data-rc="why"]', "Back on Mon");
  await p.click(p.card("a1").querySelector('button[data-act="cancel-ask"]'));   /* the card is drawn again */
  const again = p.card("a1").querySelector(".rc");
  assert.ok(again, "still open");
  assert.deepStrictEqual(again.querySelectorAll('button[data-rc="day"]').filter(b => b.getAttribute("aria-pressed") === "true").map(b => p.text(b)), ["Tomorrow"]);
  assert.strictEqual(again.querySelector('input[data-rc="why"]').value, "Back on Mon");
  assert.ok(p.text(again).includes("Kept: Tue 13 Oct"));
  await p.click(p.card("a2").querySelector('button[data-act="change"]'));
  assert.ok(!p.card("a1").querySelector(".rc") && p.card("a2").querySelector(".rc"), "only the newest is open");
  await p.click("#mineList .rc button", "Close");
  assert.ok(!p.all("#mineList .rc").length);
  assert.strictEqual(p.text(p.focus()), CHANGE);
  same(saves(p), []);
});

run(all);

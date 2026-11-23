// Plain-assert tests for static/plan.js (the Plan with AI page): run with `node tests/plan.test.js`.
// The page is one closure, so each pure helper is cut out of the file by its braces and run on its own. Made-up names only.
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(path.join(__dirname, "..", "static", "plan.js"), "utf8");
function cut(name) {
  const at = SRC.indexOf(`function ${name}(`); assert(at >= 0, name);
  let i = SRC.indexOf("{", at), depth = 0;
  for (; i < SRC.length; i++) { if (SRC[i] === "{") depth++; else if (SRC[i] === "}" && --depth === 0) break; }
  return SRC.slice(at, i + 1);
}
const HELPERS = ["esc", "isLocal", "linkHtml", "readAsTable", "lineHtml", "checklistHtml", "nextWait", "sizeText", "summaryText", "mergeLines", "counterText"];
const H = new Function(`${HELPERS.map(cut).join("\n")}\nreturn { ${HELPERS.join(", ")} };`)();
const { esc, lineHtml, checklistHtml, readAsTable, nextWait, sizeText, summaryText, mergeLines, counterText } = H;

let n = 0; const t = (name, f) => { f(); n++; };
const BAD = `<script>alert("x")</script>`;
const line = o => Object.assign({ n: 1, kind: "me", text: "", step: null, undo: null, buttons: [], table: null, quick: [] }, o);
const noScript = (html, what) => assert(!html.includes("<script"), what + ": a script tag got through");

t("esc escapes the five characters and turns null into nothing", () => {
  assert.strictEqual(esc(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
  assert.strictEqual(esc(null), ""); assert.strictEqual(esc(undefined), ""); assert.strictEqual(esc(3), "3");
});

t("each kind of line is drawn, with a script tag in every text field escaped", () => {
  for (const kind of ["me", "ai", "did", "sys", "list"]) {
    const html = lineHtml(line({ kind, text: BAD + " words", step: kind === "did" ? BAD : null, undo: kind === "did" ? true : null,
      quick: kind === "ai" ? [BAD] : [], buttons: kind === "list" ? [BAD, BAD] : [], list: kind === "list" ? BAD : null,
      table: kind === "list" ? { head: [BAD], rows: [[BAD]] } : null, left: kind === "list" ? [{ line: BAD, text: BAD }] : [] }), true, false);
    noScript(html, kind);
    assert(html.includes("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; words"), kind + ": the text is there, escaped");
    assert(html.includes(`class="ln ${kind}"`), kind + ": its class");
    assert(html.includes('data-n="1"'), kind + ": its n");
  }
});

t("a me line is only the person's words; an unknown kind is drawn as a quiet line", () => {
  const html = lineHtml(line({ kind: "me", text: "Sec 3 whole day" }), true, false);
  assert(html.includes(">Sec 3 whole day<")); assert(!html.includes("<button"));
  assert(lineHtml(line({ kind: "odd", text: "x" }), true, false).includes('class="ln sys"'));
});

t("a did line: a tick, Take it back while it can be, Taken back once it is, neither without a step", () => {
  const can = lineHtml(line({ kind: "did", text: "Put 31 papers in the draft", step: "ab12cd34", undo: true }), false, false);
  assert(can.includes("✓ Put 31 papers in the draft"));
  assert(/<button type="button"[^>]*data-act="undo" data-a="ab12cd34"[^>]*>Take it back<\/button>/.test(can), can);
  assert(!can.includes("Taken back"));
  const done = lineHtml(line({ kind: "did", text: "Put 31 papers in the draft", step: "ab12cd34", undo: false }), false, false);
  assert(done.includes("Taken back")); assert(!done.includes("<button"));
  const plain = lineHtml(line({ kind: "did", text: "Taken back: Put 31 papers in the draft", step: null, undo: false }), true, false);
  assert(plain.includes("✓ Taken back: Put 31 papers")); assert(!plain.includes("<button")); assert(!/>Taken back</.test(plain));
  const busy = lineHtml(line({ kind: "did", text: "x", step: "s1", undo: true }), false, true);
  assert(/data-act="undo"[^>]* disabled/.test(busy), "Take it back waits while the AI works");
});

t("quick answers are drawn only on the last line and not while working, at most four", () => {
  const ai = line({ kind: "ai", text: "Do their lessons stop for the whole day?", quick: ["Whole day", "Part of the day", "Different by level", "Ask me later", "A fifth"] });
  const last = lineHtml(ai, true, false);
  for (const q of ["Whole day", "Part of the day", "Different by level", "Ask me later"])
    assert(last.includes(`<button type="button" data-act="pick" data-a="${q}">${q}</button>`), q);
  assert(!last.includes("A fifth"));
  assert(!lineHtml(ai, false, false).includes("<button"), "not on an earlier line");
  assert(!lineHtml(ai, true, true).includes("<button"), "not while working");
  assert(!lineHtml(line({ kind: "me", quick: ["Whole day"] }), true, false).includes("<button"), "only an ai line has them");
});

t("a list line: its text, its table, its left rows and its two buttons for the list", () => {
  const l = line({ kind: "list", n: 7, text: "26 papers are in. 1 line needs a yes. 2 lines were not put in.",
    table: { head: ["As written", "Read as", "Date", "Start"], rows: [["Sec 3 Maths Paper 1", "Mathematics G2, Mathematics G3", "Wed 7 Oct", "10:00"]] },
    left: [{ line: 22, text: "Sec 2 has no subject called Music." }, { line: null, text: "Sec 5 is not a level of this exam." }],
    buttons: ["Yes, all", "Not now"], list: "0123456789ab" });
  const html = lineHtml(l, false, false);
  assert(html.includes("26 papers are in."));
  assert(html.includes('<th scope="col">As written</th>') && html.includes("<td>Mathematics G2, Mathematics G3</td>"));
  assert(html.includes("<li>Row 22: Sec 2 has no subject called Music.</li>"));
  assert(html.includes("<li>Sec 5 is not a level of this exam.</li>"), "a row with no line number");
  assert(html.includes(`data-act="list" data-a="0123456789ab" data-b="yes">Yes, all</button>`));
  assert(html.includes(`data-act="list" data-a="0123456789ab" data-b="no">Not now</button>`));
  const answered = lineHtml(Object.assign({}, l, { buttons: [], list: null }), true, false);
  assert(!answered.includes("<button") && answered.includes("<table"), "once answered the table stays and the buttons go");
  assert(/data-act="list"[^>]* disabled/.test(lineHtml(l, true, true)), "the buttons wait while the AI works");
  assert(!lineHtml(Object.assign({}, l, { list: null }), true, false).includes("<button"), "no list id, no buttons");
});

t("readAsTable: a real table with the head it gives, nothing without rows", () => {
  const html = readAsTable({ head: ["As written", "Read as"], rows: [["Sec 1 MT P2", "Chinese, Malay, Tamil"], ["Sec 2 Maths", BAD]] });
  assert(html.startsWith('<div class="tablewrap pl-table"><table><thead><tr><th scope="col">As written</th><th scope="col">Read as</th></tr></thead><tbody>'));
  assert.strictEqual((html.match(/<tr>/g) || []).length, 3);
  noScript(html, "table");
  assert.strictEqual(readAsTable(null), ""); assert.strictEqual(readAsTable({ head: ["A"], rows: [] }), ""); assert.strictEqual(readAsTable({}), "");
});

t("checklistHtml: a mark and words by state, the title, the text and Open only for a link of the app's own", () => {
  const items = [
    { key: "what", title: "Exam, levels, dates", state: "done", text: "End-of-Year, Mon 5 Oct to Fri 16 Oct", link: "/exams/ab12#when" },
    { key: "papers", title: "Papers and times", state: "check", text: "33, 1 to check", link: "/exams/ab12#papers" },
    { key: "suggested", title: "Suggested times", state: "todo", text: "None suggested.", link: "" },
    { key: "times", title: "Report time and breaks", state: "last", text: "As last time: 07:30", link: "/exams/ab12#when" },
    { key: "access", title: "Extra time, own room", state: "form", text: "Added in the form on the exam page.", link: "/exams/ab12#access" }];
  const html = checklistHtml(items);
  const lis = html.split("<li").slice(1);
  assert.strictEqual(lis.length, 5);
  assert(lis[0].includes("✓") && lis[0].includes("Done"), "done: a tick");
  assert(lis[1].includes(">To check<")); assert(lis[2].includes(">Still to do<")); assert(lis[3].includes(">As last time<")); assert(lis[4].includes(">On the exam page<"));
  items.forEach((x, i) => { assert(lis[i].includes(x.title), x.key); assert(lis[i].includes(esc(x.text)), x.key + " text"); });
  assert(lis[0].includes('<a href="/exams/ab12#when">Open</a>'));
  assert(!lis[2].includes("Open"), "no link, no Open");
  const odd = checklistHtml([{ title: BAD, state: "done", text: BAD, link: "javascript:alert(1)" }, { title: "x", state: "todo", text: "y", link: "//elsewhere.example/x" },
    { title: "x", state: "todo", text: "y", link: "https://elsewhere.example/x" }]);
  noScript(odd, "checklist");
  assert(!odd.includes("<a "), "a link that does not start with one / is never a link");
  assert(!odd.includes("javascript:") && !odd.includes("elsewhere.example"));
});

t("the poll waits a second while working, not at all when done, 3 s after a failure, and gives up after 5", () => {
  assert.strictEqual(nextWait(true, 0), 1000);
  assert.strictEqual(nextWait(false, 0), null);
  for (const f of [1, 2, 3, 4, 5]) assert.strictEqual(nextWait(true, f), 3000, "failure " + f);
  assert.strictEqual(nextWait(true, 6), null);
  assert.strictEqual(nextWait(false, 6), null);
});

t("the size text", () => {
  assert.strictEqual(sizeText(512), "512 B");
  assert.strictEqual(sizeText(0), "0 B");
  assert.strictEqual(sizeText(48 * 1024), "48 KB");
  assert.strictEqual(sizeText(1.2 * 1024 * 1024), "1.2 MB");
  assert.strictEqual(sizeText(5 * 1024 * 1024), "5.0 MB");
});

t("the phone summary counts the lines that are done", () => {
  const items = ["done", "done", "check", "done", "todo", "last", "last", "done", "last", "form"].map(state => ({ state }));
  assert.strictEqual(summaryText(items), "Filled in so far: 4 of 10");
  assert.strictEqual(summaryText([]), "Filled in so far");
  assert.strictEqual(summaryText(null), "Filled in so far");
});

t("lines are kept in order by n; a later copy of a line replaces it; a whole read replaces them all", () => {
  const a = [{ n: 1, text: "a" }, { n: 2, text: "b", undo: true }];
  const m = mergeLines(a, [{ n: 3, text: "c" }, { n: 2, text: "b", undo: false }], false);
  assert.deepStrictEqual(m.map(x => [x.n, x.undo]), [[1, undefined], [2, false], [3, undefined]]);
  assert.deepStrictEqual(mergeLines(a, [{ n: 2, text: "b" }], true).map(x => x.n), [2]);
  assert.deepStrictEqual(mergeLines(a, null, false).map(x => x.n), [1, 2]);
});

t("the counter shows how many characters of 2,000", () => {
  assert.strictEqual(counterText(1850), "1,850 of 2,000 characters");
});

t("the fixed sentences are on the page, and no em dash in any of its words", () => {
  for (const s of ["Teachers go as codes. A name the app does not know is sent as typed.", "Plan with AI is not set up on this server.",
    "Nothing yet: say what you want to plan.", "The page lost touch with the app. Reload to carry on.", "Give an Excel or Word file, or paste the list.",
    "Start a new talk? The exam stays as it is.", "What would you like to plan?", ">Plan an exam<", ">Plan a common test<", "Carry on: ",
    ">Paste a list<", ">Add a file<", ">Read the list<", ">Back<", ">New talk<", ">Stop<", ">Send<", 'role="log"', 'aria-live="polite"', 'role="status"', 'role="alert"'])
    assert(SRC.includes(s), s);
  const html = fs.readFileSync(path.join(__dirname, "..", "static", "plan.html"), "utf8");
  assert(!SRC.includes("—") && !html.includes("—"), "an em dash");
  assert(!/innerHTML\s*=\s*[a-z]+\.j\b/.test(SRC), "nothing of a reply is put in as HTML whole");
});

console.log(`${n} plan page tests passed`);

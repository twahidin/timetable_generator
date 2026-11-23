"use strict";
/* The Link Telegram card, at the top of My absences (relief.js gives it its place there, and shows it), for everyone: one's own
   Telegram, from /api/relief/telegram, read each time the tab is shown. Nothing is there while no bot is connected or the status
   cannot be read. Not linked: Link Telegram asks for a one-time code and shows how to use it, a link that opens the bot with it and
   the code to send; until it runs out the status is read every 5 seconds, only while the tab is on screen and one read at a time, so
   the card says that it is linked by itself. Linked: since when, and Unlink, which asks first. The code is kept here while it is shown
   and no longer, and nowhere else: whoever reads it can link their own Telegram as this person, so it goes at once when they are signed
   out or may not (401, 403) and when the page is left (pagehide: the browser may keep the page; opening the bot does not leave it); a
   lost connection or a failing server keeps it. Only what changes is drawn, so a code being selected, and the focus, stay; the line
   alone is a live region (tgLine): the steps and the question are where the focus goes, and say() says a refusal itself. */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day, say = R.say;
  const API = "/api/relief/telegram", EVERY = 5000, MOST = 15 * 60;   /* MOST: seconds a code is good for */
  const WRONG = "Something went wrong. Try again.";
  /* st: the status shown, null for none; code: {code, url, until (by this device's clock)} while it is shown; out: one has run out;
     ask: Unlink asks; busy: a step is on its way; msg: what the server refused; seq: counts reads, steps and leaving the page, an
     answer that is not the last one's is dropped; reading: the seq of the last read; html: what is drawn under the line */
  const C = { box: null, st: null, code: null, out: false, ask: false, busy: false, msg: null, seq: 0, reading: null, timer: 0, html: "" };

  const secs = () => Date.now() / 1000;
  const onScreen = () => R.cur === "mine" && document.visibilityState !== "hidden";
  const find = act => C.box.querySelector(`[data-tg="${act}"]`);

  /* ---------------------------------------------------------------- what is shown */
  function button(act, label, cls) {
    return `<button type="button" class="${cls}" data-tg="${act}"${C.busy ? " disabled" : ""}>${esc(label)}</button>`;
  }

  function line(st) {   /* what is said of it; nothing while the steps are shown */
    if (st.linked) return `${st.handle ? `Linked as @${st.handle} since` : "Linked since"} ${day(st.since)}.`;
    return C.code ? "" : C.out ? "That code has run out." : st.blocked ? `Your Telegram was unlinked on ${day(st.blocked)}: the bot was blocked there. Unblock it in Telegram, then link again.` : "Get your reliefs and reminders on your own Telegram.";
  }

  function linked() {
    if (!C.ask) return `<div class="bar">${button("ask", "Unlink", "small")}</div>`;
    const q = "Stop relief messages to this Telegram?";
    return `<div class="ab-ask" role="group" aria-label="${esc(q)}"><span class="q">${esc(q)}</span>${button("unlink", "Unlink", "small danger")}${button("keep", "Keep it", "small")}</div>`;
  }

  function steps(st) {   /* no link for what is no https address: practice mode has none */
    const open = C.code.url.startsWith("https://") ? `<p class="tg-line tg-open">1. <a class="filebtn primary" data-tg="open" href="${esc(C.code.url)}" target="_blank" rel="noopener">Open the bot</a></p><p class="tg-line">2. Press Start there.</p>` : "";
    return `${open}<p class="tg-line">Or send this code to @${esc(st.bot)}: <span class="codeline tg-code">${esc(C.code.code)}</span></p>
      <p class="tg-line small muted">The code works once and runs out in 15 minutes.</p><div class="bar">${button("cancel", "Cancel", "small")}</div>`;
  }

  function view(st) {
    const what = st.linked ? linked() : C.code ? steps(st) : `<div class="bar">${button("link", C.out ? "Get a new code" : "Link Telegram", "primary")}</div>`;
    return what + (C.msg ? `<div class="bar">${say(C.msg)}</div>` : "");
  }

  function paint() {
    if (!C.st) {
      if (C.html) C.box.innerHTML = C.html = "";
      return;
    }
    if (!C.html) C.box.innerHTML = `<div class="card tg"><h2 id="tgTitle" tabindex="-1">Telegram</h2><p class="tg-line" id="tgLine" aria-live="polite"></p><div id="tgBody"></div></div>`;
    const said = C.box.querySelector("#tgLine"), text = line(C.st), html = view(C.st);
    if (said.textContent !== text) said.textContent = text;
    if (html === C.html) return;
    const body = C.box.querySelector("#tgBody"), a = document.activeElement, had = a && body.contains(a);
    body.innerHTML = C.html = html;
    if (had && !C.busy) (find(a.dataset.tg) || C.box.querySelector("#tgTitle")).focus({ preventScroll: true });
  }

  function focus(...acts) {   /* after a step: the first of these there is, unless the focus has moved on elsewhere */
    const a = document.activeElement, el = acts.map(find).find(Boolean);
    if (el && onScreen() && (!a || a === document.body || C.box.contains(a))) el.focus({ preventScroll: true });
  }

  /* ---------------------------------------------------------------- the server */
  function set(st) {   /* the status as the server gave it, null when it could not be read */
    C.st = st && st.connected ? st : null;
    if (!C.st || C.st.linked) { C.code = null; C.out = false; }
    if (!C.st || !C.st.linked) C.ask = false;
  }

  function stop() { clearTimeout(C.timer); C.timer = 0; }

  function schedule() {   /* while a code shows; also once after its time, to see a link made in the last seconds */
    if (C.code && onScreen()) C.timer = setTimeout(() => { C.timer = 0; if (onScreen()) read(); }, EVERY);
  }

  async function read() {
    if (C.reading === C.seq) return;   /* one is on its way, and nothing has happened since */
    const seq = C.reading = ++C.seq;
    stop();
    const r = await R.api(API);
    if (seq !== C.seq) return;   /* a step was taken, or the page left, since */
    C.reading = null;
    if (r.ok) set(r.data);
    else if (!C.code || r.status === 401 || r.status === 403) set(null);   /* else a code that shows stays: it may be in use */
    if (C.code && secs() >= C.code.until) { C.code = null; C.out = true; }
    paint();
    schedule();
  }

  async function step(method, url, done, ...then) {   /* one step; done(answer): false when it is not whole; then: where the focus goes */
    const seq = ++C.seq;
    C.busy = true; C.msg = null; paint();
    const r = await R.api(url, { method });
    if (seq !== C.seq) return;   /* the page was left since */
    C.busy = false;
    if (!r.ok) C.msg = { text: r.error, bad: true, status: r.status };
    else if (done(r.data) === false) C.msg = { text: WRONG, bad: true };
    paint();
    focus(...then);
    schedule();
  }

  function coded(d) {   /* until is the server's; a device whose clock cannot be right counts from now */
    if (!d || ![d.code, d.url].every(x => typeof x === "string" && x)) return false;
    const left = d.until - secs();
    C.out = false;
    C.code = { code: d.code, url: d.url, until: secs() + (left > 0 && left <= MOST ? left : MOST) };
  }

  function left() {   /* the page is left: no code stays on it, nor comes to it late */
    ++C.seq;
    stop();
    C.code = null; C.busy = false;
    paint();
  }

  function shown() {
    if (C.busy) return;   /* the step on its way will say */
    C.msg = null;
    read();
  }

  function asking(on) {
    C.ask = on; C.msg = null; paint();
    focus(on ? "keep" : "ask");
  }

  /* ---------------------------------------------------------------- events */
  function onClick(e) {
    const b = e.target.closest("button[data-tg]");
    if (!b || b.disabled) return;
    switch (b.dataset.tg) {
      case "link": step("POST", `${API}/code`, coded, "open", "cancel", "link"); return;
      case "cancel": ++C.seq; stop(); C.code = null; paint(); focus("link"); return;
      case "ask": asking(true); return;
      case "keep": asking(false); return;
      case "unlink": step("DELETE", `${API}/link`, set, "link", "keep"); return;
    }
  }

  function onKey(e) {
    if (e.key === "Escape" && C.ask && !C.busy) { e.preventDefault(); asking(false); }
  }

  document.addEventListener("visibilitychange", () => { if (C.code && onScreen() && !C.timer) read(); });
  window.addEventListener("pagehide", left);
  window.addEventListener("pageshow", e => { if (e.persisted && R.cur === "mine") shown(); });   /* a page the browser kept */

  R.linkCard({
    init(box) {
      C.box = box;
      box.addEventListener("click", onClick);
      box.addEventListener("keydown", onKey);
      read();
    },
    shown,
  });
})();

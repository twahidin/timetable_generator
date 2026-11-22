"use strict";
/* The Link Telegram card, at the top of My absences (relief.js gives it its place there, and shows it), for everyone: one's own
   Telegram, from /api/relief/telegram, read each time the tab is shown. Nothing is there while no bot is connected or the status
   cannot be read. Not linked: Link Telegram asks for a one-time code and shows how to use it, a link that opens the bot with it and
   the code to send; until it runs out the status is read every 5 seconds, only while the tab is on screen, so the card says that it
   is linked by itself. Linked: since when, and Unlink, which asks first. The code is kept here while it is shown and no longer, and
   nowhere else. Only what changes is drawn, so a code being selected, and the focus, stay. */
(function () {
  const R = window.Relief, RF = window.ReliefForm, esc = RF.esc, day = RF.day, say = R.say;
  const API = "/api/relief/telegram", EVERY = 5000, MOST = 15 * 60;   /* MOST: seconds a code is good for */
  /* st: the status shown, null for none; code: {code, url, until (by this device's clock)} while it is shown; out: one has run out;
     ask: Unlink asks; busy: a step is on its way; msg: what the server refused; html: what is drawn */
  const C = { box: null, st: null, code: null, out: false, ask: false, busy: false, msg: null, seq: 0, timer: 0, html: "" };

  const secs = () => Date.now() / 1000;
  const onScreen = () => R.cur === "mine" && document.visibilityState !== "hidden";
  const find = act => C.box.querySelector(`[data-tg="${act}"]`);

  /* ---------------------------------------------------------------- what is shown */
  function button(act, label, cls) {
    return `<button type="button" class="${cls}" data-tg="${act}"${C.busy ? " disabled" : ""}>${esc(label)}</button>`;
  }

  function linked(st) {
    const since = `${st.handle ? `Linked as @${st.handle} since` : "Linked since"} ${day(st.since)}.`;
    if (!C.ask) return `<div class="bar"><span>${esc(since)}</span>${button("ask", "Unlink", "small")}</div>`;
    const q = "Stop relief messages to this Telegram?";
    return `<p class="tg-line">${esc(since)}</p><div class="ab-ask" role="group" aria-label="${esc(q)}"><span class="q">${esc(q)}</span>${button("unlink", "Unlink", "small danger")}${button("keep", "Keep it", "small")}</div>`;
  }

  function steps(st) {
    return `<p class="tg-line">1. <a class="filebtn" data-tg="open" href="${esc(C.code.url)}" target="_blank" rel="noopener">Open the bot</a></p><p class="tg-line">2. Press Start there.</p>
      <p class="tg-line">Or send this code to @${esc(st.bot)}: <span class="codeline tg-code">${esc(C.code.code)}</span></p>
      <p class="tg-line small muted">The code works once and runs out in 15 minutes.</p><div class="bar">${button("cancel", "Cancel", "small")}</div>`;
  }

  function view(st) {
    const line = st.linked ? linked(st) : C.code ? steps(st)
      : C.out ? `<p class="tg-line">That code has run out.</p><div class="bar">${button("link", "Get a new code", "primary")}</div>`
        : `<p class="tg-line">Get your reliefs and reminders on your own Telegram.</p><div class="bar">${button("link", "Link Telegram", "primary")}</div>`;
    return line + (C.msg ? `<div class="bar">${say(C.msg)}</div>` : "");
  }

  function paint() {
    if (!C.st) {
      if (C.html) C.box.innerHTML = C.html = "";
      return;
    }
    const html = view(C.st);
    if (html === C.html) return;
    if (!C.html) C.box.innerHTML = `<div class="card tg"><h2 id="tgTitle" tabindex="-1">Telegram</h2><div id="tgBody" aria-live="polite"></div></div>`;
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
    const seq = ++C.seq;
    stop();
    const r = await R.api(API);
    if (seq !== C.seq) return;   /* read again, or a step taken, since */
    if (r.ok) set(r.data);
    else if (!C.code) set(null);   /* a code that shows stays: it may be in use */
    if (C.code && secs() >= C.code.until) { C.code = null; C.out = true; }
    paint();
    schedule();
  }

  async function step(method, url, done, ...then) {   /* one step; then: where the focus goes */
    ++C.seq;
    C.busy = true; C.msg = null; paint();
    const r = await R.api(url, { method });
    C.busy = false;
    if (r.ok) done(r.data);
    else C.msg = { text: r.error, bad: true, status: r.status };
    paint();
    focus(...then);
    schedule();
  }

  function coded(d) {   /* until is the server's; a device whose clock cannot be right counts from now */
    const left = d.until - secs();
    C.out = false;
    C.code = { code: d.code, url: d.url, until: secs() + (left > 0 && left <= MOST ? left : MOST) };
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
      case "link": step("POST", `${API}/code`, coded, "open", "link"); return;
      case "cancel": ++C.seq; stop(); C.code = null; paint(); focus("link"); return;
      case "ask": asking(true); return;
      case "keep": asking(false); return;
      case "unlink": step("DELETE", `${API}/link`, set, "link", "keep"); return;
    }
  }

  function onKey(e) {
    if (e.key === "Escape" && C.ask && !C.busy) { e.preventDefault(); asking(false); }
  }

  document.addEventListener("visibilitychange", () => { if (C.code && onScreen() && !C.timer && !C.busy) read(); });

  R.linkCard({
    init(box) {
      C.box = box;
      box.addEventListener("click", onClick);
      box.addEventListener("keydown", onKey);
      read();
    },
    shown() {
      if (C.busy) return;   /* the step on its way will say */
      C.msg = null;
      read();
    },
  });
})();

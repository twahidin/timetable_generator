"use strict";
/* The Relief home (/relief) for a member of staff signed in with their own code. Stage 1: who they are, the way to
   their timetable and, for the relief team, the way to the relief settings. */
(function () {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function paint(me) {
    document.title = `Relief · ${me.name}`;
    $("#title").textContent = `Relief · ${me.name}`;
    $("#settingsLink").hidden = !me.can_settings;
    const note = me.published === false ? `<p class="muted small">The timetable is not published yet.</p>` : "";
    const about = [(me.depts || []).join(", "), me.on_management ? "Management" : "", me.on_team ? "Relief team" : ""].filter(Boolean).join(" · ");
    $("#main").innerHTML = `<div class="card">${about ? `<p class="muted small who">${esc(about)}</p>` : ""}
      ${note}<p>Asking for relief, planning relief and the reliefs you cover arrive here in the next stage.</p></div>`;
  }

  function fail(text) {
    $("#main").innerHTML = `<div class="card"><p class="err" style="color:var(--warn)">${esc(text)}</p><p><a href="/relief">Try again</a></p></div>`;
  }

  async function start() {
    let r;
    try { r = await fetch("/api/relief/me", { cache: "no-store" }); }
    catch (e) { fail("Could not reach the server. Check the connection and try again."); return; }
    if (r.status === 401) { location.href = "/login"; return; }
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { fail(j.error || "Something went wrong."); return; }
    paint(j);
  }
  start();
})();

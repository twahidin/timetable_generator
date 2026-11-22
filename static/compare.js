"use strict";
/* The Compare page (/compare): two timetables of step 8 side by side. Every text on it (a version's name, a class, a teacher, a room, a subject)
   comes from the setup or from what people typed, so the page is built with textContent only, never innerHTML. Comparing only reads. */
(function () {
  const $ = s => document.querySelector(s);
  const AGAIN = "Please sign in again.";
  const CHECKED = "“Checked now” means against the setup as it is today: a version saved before step 5 changed can show warnings it did not have then.";
  const q = new URLSearchParams(location.search);
  const S = { a: q.get("a") || "", b: q.get("b") || "draft", view: q.get("view") || "class", name: q.get("name") || "", mark: true, data: null, token: 0 };

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const k in attrs || {}) {
      if (k === "text") el.textContent = attrs[k];
      else if (k === "class") el.className = attrs[k];
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== false && attrs[k] != null) el.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    }
    for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
    return el;
  }
  function note(text) { const m = $("#msg"); m.replaceChildren(); if (text) m.append(h("div", { class: "msg", text })); }
  const query = () => {
    const p = new URLSearchParams();
    if (S.a) p.set("a", S.a);
    if (S.b) p.set("b", S.b);
    if (S.view) p.set("view", S.view);
    if (S.name) p.set("name", S.name);
    return p.toString();
  };

  async function load(keepName) {
    const my = ++S.token;
    let r, d = null;
    try { r = await fetch("/api/compare?" + query(), { credentials: "same-origin" }); }
    catch (e) { if (my === S.token) note("The server could not be reached. Try again."); return; }
    try { d = await r.json(); } catch (e) { d = null; }
    if (my !== S.token) return;
    if (r.status === 401) { note(AGAIN); return; }
    if (!r.ok || !d) {
      note((d && d.error) || "Something went wrong. Try again.");
      if (S.data) { S.a = S.data.a.src; S.b = S.data.b.src; S.view = S.data.view; S.name = S.data.name; draw(); }   // keep what was shown; the pickers go back to it
      else { $("#card").replaceChildren(h("div", { class: "head" }, h("h2", { text: "Compare" }), backLink())); }
      return;
    }
    note("");
    S.data = d; S.a = d.a.src; S.b = d.b.src; S.view = d.view; S.name = d.name;
    try { history.replaceState(null, "", "/compare?" + query()); } catch (e) { /* the address stays as it was */ }
    draw();
  }

  function backLink() { return h("a", { class: "ghost filebtn", href: "/", text: "Back to step 8" }); }

  function sourcePicker(label, which) {
    const d = S.data, cur = d[which].src;
    const sel = h("select", { "aria-label": label, onchange: e => { S[which] = e.target.value; S.name = ""; load(); } });
    const list = d.sources.slice();
    if (!list.some(s => s.src === cur)) list.push(d[which]);
    for (const s of list) {
      const o = h("option", { value: s.src, text: (which === "a" ? "A · " : "B · ") + s.label });
      if (s.src === cur) o.selected = true;
      sel.append(o);
    }
    return sel;
  }

  function tile(label, big, small) {
    return h("div", { class: "tile" }, h("span", { class: "ab", text: label }), h("b", { text: big }), h("span", { class: "ab", text: small }));
  }

  function whoPicker() {
    const d = S.data, groups = [["class", "Class", "Classes", d.names.classes], ["teacher", "Teacher", "Teachers", d.names.teachers], ["room", "Room", "Rooms", d.names.rooms]];
    const sel = h("select", {
      id: "cmpWho", "aria-label": "Class, teacher or room",
      onchange: e => { const [v, ...rest] = e.target.value.split("|"); S.view = v; S.name = rest.join("|"); load(); }
    });
    for (const [v, word, plural, names] of groups) {
      if (!names.length) continue;
      const g = h("optgroup", { label: plural });
      for (const n of names) {
        const o = h("option", { value: v + "|" + n, text: word + " " + n });
        if (v === d.view && n === d.name) o.selected = true;
        g.append(o);
      }
      sel.append(g);
    }
    return sel;
  }

  /* one week as a table: a row for each period, a column for each day; a lesson fills every period it lasts */
  function grid(week, marks, mark) {
    const slot = {}, hot = new Set();
    const key = (d, p) => d + ":" + p;
    for (const c of week.cells) {
      const mk = marks.some(m => m[0] === c.d && m[1] === c.p);
      for (let p = c.p; p < c.p + Math.max(c.n, 1); p++) {
        (slot[key(c.d, p)] = slot[key(c.d, p)] || []).push(c);
        if (mk) hot.add(key(c.d, p));
      }
    }
    const head = h("tr", null, h("th", { text: "" }), week.days.map(d => h("th", { text: d })));
    const body = [];
    for (let p = 0; p < week.NP; p++) {
      const t = week.times && week.times[p];
      const tr = h("tr", null, h("th", { class: "p", text: t ? `${p} · ${t[0]}` : String(p) }));
      for (let d = 0; d < week.days.length; d++) {
        const cs = slot[key(d, p)] || [];
        const shorts = [...new Set(cs.map(c => c.short))];
        const cls = [!cs.length && "free", cs.some(c => c.block) && "bd", hot.has(key(d, p)) && "ch"].filter(Boolean).join(" ");
        const tip = cs.map(c => [c.what, c.teachers.join(" & "), c.room].filter(Boolean).join(" · ")).join("\n");
        tr.append(h("td", { class: cls, title: tip || null, text: cs.length ? shorts.join(" / ") : "·" }));
      }
      body.push(tr);
    }
    return h("div", { class: "tt" + (mark ? " mark" : "") }, h("table", null, h("tbody", null, head, body)));
  }

  function draw() {
    const d = S.data, t = d.totals, card = $("#card");
    const pair = a => `${a[0]} → ${a[1]}`;
    const lines = d.lines.length
      ? h("ul", { class: "difflist small" }, d.lines.map(l => h("li", { text: l })))
      : h("p", { class: "nodiff small", text: "Nothing differs for " + d.name + "." });
    card.replaceChildren(
      h("div", { class: "head" }, h("h2", { text: "Compare" }), backLink()),
      h("div", { class: "pick" }, sourcePicker("First timetable", "a"), h("span", { class: "muted", text: "with" }), sourcePicker("Second timetable", "b")),
      h("div", { class: "tiles" },
        tile("Lessons at another time", String(t.moved), "of " + t.lessons),
        tile("Teacher different", String(t.teacher), "lessons"),
        tile("Room different", String(t.room), "lessons"),
        tile("Critical", pair(t.critical), "A → B"),
        tile("Warnings", pair(t.warnings), "A → B"),
        tile("Teachers’ longest day", pair(t.longest), "periods, A → B")),
      h("p", { class: "small muted", text: CHECKED }),
      h("div", { class: "pick" },
        h("b", { class: "small", text: "Show" }), whoPicker(),
        h("label", null, h("input", { type: "checkbox", checked: S.mark, onchange: e => { S.mark = e.target.checked; draw(); } }), "mark what differs"),
        h("span", { class: "small muted", text: "Orange = not the same in A and B." })),
      h("div", { class: "grids" },
        h("div", null, h("b", { class: "small", text: "A · " + d.a.label }), grid(d.weeks.a, d.marks.a, S.mark)),
        h("div", null, h("b", { class: "small", text: "B · " + d.b.label }), grid(d.weeks.b, d.marks.b, S.mark))),
      h("h3", { text: "What differs for " + d.name }),
      lines,
      h("div", { class: "acts" },
        h("a", { class: "filebtn", href: "/api/compare.xlsx?" + new URLSearchParams({ a: d.a.src, b: d.b.src }).toString(), text: "Download the differences (Excel)" })),
      h("p", { class: "small muted", text: "Every difference can also be downloaded as a list (Excel), class by class." }));
  }

  load();
})();

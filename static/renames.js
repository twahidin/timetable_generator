/* Step 9's card about the teachers renamed since the last publish: for each pair (an old name on the timetable published
   now, the name its row has now) with an account or a Telegram link, the same person or a different person.
   The pairs are the server's (GET /api/draft/renames); picks = { old: "same" | "different" }, made only by the person.
   Plain functions, no page access, so they run under Node (tests/renames.test.js). */
var Renames = (function () {
  "use strict";
  var CHOICES = ["same", "different"];
  function list(v) { return Array.isArray(v) ? v.filter(function (p) { return p && typeof p === "object"; }) : []; }
  function pickOf(picks, old) {
    var v = picks && typeof picks === "object" && Object.prototype.hasOwnProperty.call(picks, old) ? picks[old] : null;
    return CHOICES.indexOf(v) >= 0 ? v : null;
  }
  function adminText(p) { return "An admin has to publish this one: " + p.new + "'s account must follow or be removed."; }

  /* which choices this pair can take, and the sentence that says why one cannot (or what happens either way) */
  function offers(p) {
    var acc = !!p.account, nr = p.no_remove ? String(p.no_remove) : "";
    var different = !(acc && nr), same = !(acc && !p.joins && nr);
    var note = !same || !different ? nr
      : acc && !p.joins ? p.new + " already has their own account: " + p.old + "'s account is removed either way." : "";
    return { same: same, different: different, note: note };
  }

  /* "" when Publish may go; else the first that applies: a pair only an admin can publish, a pair with neither choice offered, a pair with no pick (a pick not
     offered, made before the list changed, is the reason it is not) */
  function gate(pairs, picks) {
    var ps = list(pairs), i, p, k;
    for (i = 0; i < ps.length; i++) if (ps[i].needs_admin) return adminText(ps[i]);
    for (i = 0; i < ps.length; i++) { k = offers(ps[i]); if (!k.same && !k.different) return k.note; }   // nothing to pick: why, not "Choose"
    for (i = 0; i < ps.length; i++) if (!pickOf(picks, ps[i].old)) return "Choose for each teacher with a new name first.";
    for (i = 0; i < ps.length; i++) {
      p = ps[i]; k = pickOf(picks, p.old);
      if (!offers(p)[k]) return offers(p).note || "Choose for each teacher with a new name first.";
    }
    return "";
  }

  function card(pairs, picks, esc) {
    var ps = list(pairs);
    if (!ps.length) return "";
    var rows = ps.map(function (p, i) {
      var has = (Array.isArray(p.has) ? p.has : []).map(function (w) { return esc(w); }).join(" · ");
      var head = "<p><b>" + esc(p.old + " is now " + p.new + ".") + "</b>" + (has ? ' <span class="muted small">' + has + "</span>" : "") + "</p>";
      if (p.needs_admin) return '<div class="rnpair">' + head + '<p class="muted small">' + esc(adminText(p)) + "</p></div>";
      var o = offers(p), cur = pickOf(picks, p.old);
      var radio = function (v, label, says) {
        return '<div><label class="radio"><input type="radio" name="rn-' + i + '" id="rn' + i + v + '" data-rn="' + i + "|" + v + '"' + (cur === v ? " checked" : "")
          + (o[v] ? "" : " disabled") + "> " + esc(label) + '</label> <span class="muted small">' + esc(says) + "</span></div>";
      };
      return '<div class="rnpair">' + head
        + radio("same", "Same person", "Everything " + p.old + " has goes to " + p.new + ".")
        + radio("different", "A different person", p.new + " starts fresh. " + p.old + (p.account ? "'s account is removed." : "'s Telegram link is removed."))
        + (o.note ? '<p class="muted small">' + esc(o.note) + "</p>" : "") + "</div>";
    }).join("");
    return '<div class="card rncard" style="margin-top:12px"><h3>' + esc("New names since the last publish") + "</h3>" + rows + "</div>";
  }

  /* the publish request's body: the picks of the pairs shown, and nothing else */
  function body(pairs, picks) {
    var out = {};
    list(pairs).forEach(function (p) { var k = pickOf(picks, p.old); if (k) out[p.old] = k; });
    return { renames: out };
  }

  return { gate: gate, offers: offers, card: card, body: body };
})();
if (typeof module !== "undefined") module.exports = Renames;

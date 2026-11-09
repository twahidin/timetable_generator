/* People: pure helpers for the teacher list. No document, no window, no
   randomness: functions over strings and plain objects, so Node can test them.
   Avatars: a small flat cartoon face drawn from a name alone. Every part comes
   from the name's hash (and an optional "look" number), never from a guess about
   the person. */
var People = (function () {
  "use strict";

  function key(name) {
    return String(name == null ? "" : name).trim().toLowerCase().replace(/\s+/g, " ");
  }

  // 32-bit FNV-1a, unsigned.
  function hash(text) {
    var h = 2166136261;
    var s = String(text);
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h >>> 0;
  }

  // Final mix so neighbouring names do not land on neighbouring parts.
  function mix(h) {
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b) >>> 0;
    h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35) >>> 0;
    h ^= h >>> 16;
    return h >>> 0;
  }

  var FRINGE = "M9 15 C9 8 13 5.5 18 5.5 C23 5.5 27 8 27 15 C24 12 21 10.5 18 10.5 C15 10.5 12 12 9 15 Z";
  var HAIR = [
    { back: "", front: "" },
    { back: "", front: FRINGE },
    { back: "", front: "M9 15 C8.5 7 14 4.5 19 5.5 C24 6 27.5 9 27 15 C25 11 21 10 15 11.5 C12 12.3 10 13.5 9 15 Z" },
    { back: "M7 31 C5 18 7 5 18 5 C29 5 31 18 29 31 Z", front: FRINGE },
    { back: '<circle cx="18" cy="4.5" r="3.5"/>', front: FRINGE },
    { back: '<circle cx="10" cy="11" r="4"/><circle cx="14" cy="7.5" r="4"/><circle cx="18" cy="6.5" r="4"/>' +
      '<circle cx="22" cy="7.5" r="4"/><circle cx="26" cy="11" r="4"/>', front: "" },
    { back: "", front: "M9 14 L9 7 L13 10 L15 4.5 L18 9 L21 4.5 L23 10 L27 7 L27 14 C24 11.5 21 10.5 18 10.5 C15 10.5 12 11.5 9 14 Z" },
    { back: "M7 22 C6 8 11 5 18 5 C25 5 30 8 29 22 Z", front: FRINGE },
    { back: "M25 8 C32 8 33 18 30 24 C29 18 27 14 25 12 Z", front: FRINGE },
    { back: "", front: "M9.5 13.5 C10 8.5 13 6.5 18 6.5 C23 6.5 26 8.5 26.5 13.5 C24 10.5 21 9.5 18 9.5 C15 9.5 12 10.5 9.5 13.5 Z" }
  ];

  var AVATAR = {
    bg: ["#f4b6a6", "#f6d28b", "#bfdc9f", "#9fd8c9", "#9cc9ee", "#b9b6f0", "#e3b0e0", "#f2a9c0",
      "#f0c27a", "#a8d8a0", "#8fd0e0", "#c9c0e8"],
    skin: ["#f9dcc4", "#f1c9a0", "#e0ac7e", "#c68b5b", "#a06a42", "#7a4a2d"],
    hair: HAIR,
    hairColor: ["#2b2118", "#5a3825", "#8a5a2b", "#c99a4b", "#a33b2a", "#8d8d96"],
    glasses: ["none", "round", "square"],
    mouth: ["smile", "grin", "small"],
    top: ["#3b6fb6", "#d1495b", "#2f9e77", "#edae49", "#7b5ea7", "#4a4e69"]
  };
  var ORDER = ["bg", "skin", "hair", "hairColor", "glasses", "mouth", "top"];
  var AVATAR_COMBOS = ORDER.reduce(function (n, k) { return n * AVATAR[k].length; }, 1);

  function avatarParts(name, seed) {
    var text = key(name) + "|" + (seed || 0);
    var a = mix(hash(text)), b = mix(hash(text + "#"));
    var parts = {};
    // Decode each hash as mixed-radix digits: a feeds the first four parts, b the rest.
    [[a, ORDER.slice(0, 4)], [b, ORDER.slice(4)]].forEach(function (g) {
      var v = g[0];
      g[1].forEach(function (k) {
        var len = AVATAR[k].length;
        parts[k] = v % len;
        v = Math.floor(v / len);
      });
    });
    return parts;
  }

  function avatar(name, seed, size) {
    var px = Number(size);
    if (!(px > 0)) px = 32;
    var head = '<svg width="' + px + '" height="' + px + '" viewBox="0 0 36 36" aria-hidden="true">';
    if (!key(name)) return head + '<circle cx="18" cy="18" r="18" fill="#d5d8de"/></svg>';
    var p = avatarParts(name, seed);
    var skin = AVATAR.skin[p.skin], ink = "#2b2b2b", hc = AVATAR.hairColor[p.hairColor];
    var hair = HAIR[p.hair];
    var s = head + '<circle cx="18" cy="18" r="18" fill="' + AVATAR.bg[p.bg] + '"/><g>';
    s += '<path d="M4.6 30 C8 27 13 26 18 26 C23 26 28 27 31.4 30 A18 18 0 0 1 4.6 30 Z" fill="' + AVATAR.top[p.top] + '"/>';
    s += '<rect x="15.5" y="22" width="5" height="5" fill="' + skin + '"/>';
    s += '<g fill="' + hc + '">' + (hair.back ? (hair.back.charAt(0) === "<" ? hair.back : '<path d="' + hair.back + '"/>') : "") + "</g>";
    s += '<circle cx="18" cy="16" r="9" fill="' + skin + '"/>';
    if (hair.front) s += '<path d="' + hair.front + '" fill="' + hc + '"/>';
    s += '<circle cx="14.5" cy="16.5" r="1.1" fill="' + ink + '"/><circle cx="21.5" cy="16.5" r="1.1" fill="' + ink + '"/>';
    if (p.mouth === 0) s += '<path d="M14.5 20.5 Q18 23.5 21.5 20.5" fill="none" stroke="' + ink + '" stroke-width="1.2" stroke-linecap="round"/>';
    else if (p.mouth === 1) s += '<path d="M14.5 20 Q18 25 21.5 20 Z" fill="' + ink + '"/>';
    else s += '<path d="M16 21 Q18 22.3 20 21" fill="none" stroke="' + ink + '" stroke-width="1.2" stroke-linecap="round"/>';
    if (p.glasses === 1)
      s += '<g fill="none" stroke="' + ink + '" stroke-width="0.9"><circle cx="14.5" cy="16.5" r="2.9"/><circle cx="21.5" cy="16.5" r="2.9"/><path d="M17.4 16.5 H18.6"/></g>';
    else if (p.glasses === 2)
      s += '<g fill="none" stroke="' + ink + '" stroke-width="0.9"><rect x="11.6" y="13.9" width="5.8" height="5.2" rx="1"/><rect x="18.6" y="13.9" width="5.8" height="5.2" rx="1"/><path d="M17.4 16.5 H18.6"/></g>';
    return s + "</g></svg>";
  }

  return { key: key, hash: hash, AVATAR: AVATAR, AVATAR_COMBOS: AVATAR_COMBOS,
    avatarParts: avatarParts, avatar: avatar };
})();
if (typeof module !== "undefined") module.exports = People;

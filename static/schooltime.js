/* Writes every clock time shown on a page the school's way ("1.00", not "13:00"). Display only: it rewrites text nodes,
   never attributes or the values of inputs. The same rule as hmAll on the published timetable page. */
var SchoolTime = (function () {
  const RE = /(^|\D)(\d{1,2}):(\d{2})(?!\d)/g;
  const SKIP = { TEXTAREA: 1, SCRIPT: 1, STYLE: 1 };
  const text = s => String(s == null ? "" : s).replace(RE, (w, pre, h, m) => +h < 24 && +m < 60 ? pre + ((+h + 11) % 12 + 1) + "." + m : w);
  const has = (n, a) => !!(n.hasAttribute ? n.hasAttribute(a) : n.getAttribute && n.getAttribute(a) != null);

  /* is the text of this node one that must stay as written? */
  function kept(n) {
    for (let e = n; e; e = e.parentNode) {
      if (e.nodeType !== 1) continue;
      const tag = String(e.tagName || "").toUpperCase();
      if (SKIP[tag] || (tag === "OPTION" && !has(e, "value")) || has(e, "contenteditable") || has(e, "data-keep-time")) return true;
    }
    return false;
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) {
      const v = root.nodeValue, t = text(v);
      if (t !== v && !kept(root)) root.nodeValue = t;
      return;
    }
    if (root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11) return;
    if (root.nodeType === 1 && kept(root)) return;
    const kids = root.childNodes || [];
    for (let i = 0; i < kids.length; i++) walk(kids[i]);
  }

  function watch(root) {
    walk(root);
    if (typeof MutationObserver === "undefined" || !root) return;
    new MutationObserver(list => {
      for (const m of list) {
        if (m.type === "characterData") walk(m.target);
        else for (const n of m.addedNodes || []) walk(n);
      }
    }).observe(root, { childList: true, subtree: true, characterData: true });
  }

  return { text, walk, watch };
})();

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => SchoolTime.watch(document.body));
  else SchoolTime.watch(document.body);
}
if (typeof module !== "undefined" && module.exports) module.exports = SchoolTime;

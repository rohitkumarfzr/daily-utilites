/* Combobox: an accessible autocomplete list for a text input (ARIA 1.2 combobox pattern).
 * Styles are the .combo* rules in theme.css. Load with <script src="../static/combobox.js"></script>.
 *
 *   const combo = new Combobox(document.getElementById("bucket"), {
 *     // Called on every render with the input's text. Return the rows to show:
 *     //   rows:      [{ group: "Recent" } | { value, label?, hits? }]  (hits = matched character positions in label)
 *     //   matched:   total matches, when more exist than rows shown (adds "N more. Keep typing…")
 *     //   count:     footer text, e.g. "12 of 340 buckets match"
 *     //   empty:     text shown when there are no rows
 *     //   preselect: highlight the first row so Enter picks it (default: when the input isn't empty)
 *     source(text) { return Combobox.filter(names, text); },
 *     // Optional. Runs after a pick has set the input; return true to keep the list open (to drill down).
 *     onPick(value) {},
 *     labelledBy: "bucketLabel",   // id of the visible label, for the list
 *   });
 *   combo.refresh();               // re-render if open, e.g. after data arrives
 *   combo.enabled = false;         // behave like a plain input
 *
 * Combobox.match(text, query) and Combobox.filter(values, query, options) rank names made of
 * segments (team-env-assets-prod, reports/2026/): exact, prefix, start of a segment, anywhere,
 * several words in any order, then initials.
 */
(function () {
  const SEPARATORS = "-._/ ";
  const isSep = (c) => c !== undefined && SEPARATORS.includes(c);
  const span = (i, len) => Array.from({ length: len }, (_, k) => i + k);
  let uid = 0;

  function match(text, query) {
    const n = text.toLowerCase();
    const q = query.toLowerCase().trim();
    if (!q) return { score: 0, hits: [] };
    const whole = q.replace(/\s+/g, "");
    if (n === whole) return { score: 1000, hits: span(0, n.length) };
    if (n.startsWith(whole)) return { score: 900 - n.length / 100, hits: span(0, whole.length) };

    let best = null;
    for (let i = n.indexOf(whole); i >= 0; i = n.indexOf(whole, i + 1)) {
      const score = (isSep(n[i - 1]) ? 800 : 600) - i / 100;
      if (!best || score > best.score) best = { score, hits: span(i, whole.length) };
    }
    if (best) return best;

    // several words ("prod assets"): each has to appear, in any order
    const words = q.split(/[\s\-._/]+/).filter(Boolean);
    if (words.length > 1) {
      const hits = new Set();
      let score = 500 - n.length / 100;
      for (const w of words) {
        let at = -1;
        for (let i = n.indexOf(w); i >= 0; i = n.indexOf(w, i + 1)) {
          if (i === 0 || isSep(n[i - 1])) { at = i; break; }
          if (at < 0) at = i;
        }
        if (at < 0) return null;
        if (at > 0 && !isSep(n[at - 1])) score -= 40;
        span(at, w.length).forEach((h) => hits.add(h));
      }
      return { score, hits: [...hits] };
    }

    // letters in order, such as initials ("dap" for data-assets-prod); segment starts first
    if (whole.length < 2) return null;
    const hits = [];
    let from = 0;
    let score = 300 - n.length / 100;
    for (const ch of whole) {
      let j = -1;
      for (let k = from; k < n.length; k++) {
        if (n[k] === ch && (k === from || k === 0 || isSep(n[k - 1]))) { j = k; break; }
      }
      if (j < 0) j = n.indexOf(ch, from);
      if (j < 0) return null;
      // reward initials and runs of letters; letters scattered mid-word rank last
      if (j === 0 || isSep(n[j - 1])) score += 30;
      else if (hits.length && j === from) score += 15;
      else score -= 10;
      hits.push(j);
      from = j + 1;
    }
    return { score, hits };
  }

  /* Rank values against a query. Options:
   *   limit:  rows to return (default 60)
   *   text:   v => the part of v to match on (default: all of it)
   *   offset: v => where that part starts inside v, so hits line up with the shown value
   *   boost:  v => extra score, e.g. for recent items */
  function filter(values, query, { limit = 60, text = (v) => v, offset = () => 0, boost = () => 0 } = {}) {
    const scored = [];
    for (const value of values) {
      const m = match(text(value), query);
      if (!m) continue;
      const shift = offset(value);
      scored.push({ value, hits: m.hits.map((h) => h + shift), score: m.score + boost(value) });
    }
    if (query.trim()) scored.sort((a, b) => b.score - a.score || a.value.localeCompare(b.value));
    return { rows: scored.slice(0, limit), matched: scored.length };
  }

  function highlight(label, hits) {
    const marked = new Set(hits);
    const frag = document.createDocumentFragment();
    let run = "";
    let inMark = false;
    const flush = () => {
      if (run) frag.append(inMark ? Object.assign(document.createElement("mark"), { textContent: run }) : run);
      run = "";
    };
    for (let i = 0; i < label.length; i++) {
      if (marked.has(i) !== inMark) { flush(); inMark = !inMark; }
      run += label[i];
    }
    flush();
    return frag;
  }

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };

  class Combobox {
    constructor(input, { source, onPick, labelledBy, keys = true } = {}) {
      this.input = input;
      this.source = source;
      this.onPick = onPick;
      this.items = [];
      this.active = -1;
      this.isOpen = false;
      this._enabled = true;
      const id = input.id || `combo${++uid}`;

      this.wrap = el("div", "combo");
      input.before(this.wrap);
      this.wrap.append(input);
      this.pop = el("div", "combo-pop");
      this.pop.hidden = true;
      this.list = el("ul", "combo-list");
      this.list.id = `${id}-list`;
      this.list.setAttribute("role", "listbox");
      if (labelledBy) this.list.setAttribute("aria-labelledby", labelledBy);
      this.count = el("span");
      const foot = el("div", "combo-foot");
      foot.append(this.count);
      if (keys) {
        const k = el("span", "keys");
        k.innerHTML = "<kbd>↑</kbd><kbd>↓</kbd> move <kbd>Enter</kbd> pick <kbd>Esc</kbd> close";
        foot.append(k);
      }
      this.pop.append(this.list, foot);
      this.wrap.append(this.pop);
      this.optPrefix = `${id}-opt`;

      input.setAttribute("role", "combobox");
      input.setAttribute("aria-autocomplete", "list");
      input.setAttribute("aria-expanded", "false");
      input.setAttribute("aria-controls", this.list.id);
      input.autocomplete = "off";

      input.addEventListener("input", () => (this.isOpen ? this.render() : this.open()));
      input.addEventListener("focus", () => this.open());
      input.addEventListener("click", () => { if (!this.isOpen) this.open(); });
      input.addEventListener("blur", () => this.close());
      input.addEventListener("keydown", (e) => this._key(e));
      // keep focus in the input while clicking the list
      this.pop.addEventListener("mousedown", (e) => e.preventDefault());
      this.list.addEventListener("click", (e) => {
        const li = e.target.closest(".combo-opt");
        if (li) this.pick(Number(li.dataset.index));
      });
      this.list.addEventListener("mousemove", (e) => {
        const li = e.target.closest(".combo-opt");
        if (li && Number(li.dataset.index) !== this.active) this.setActive(Number(li.dataset.index));
      });
    }

    get enabled() { return this._enabled; }
    set enabled(on) {
      this._enabled = on;
      if (!on) this.close();
      this.input.setAttribute("aria-autocomplete", on ? "list" : "none");
    }

    open() {
      if (!this._enabled || this.input.disabled) return;
      this.isOpen = true;
      this.pop.hidden = false;
      this.input.setAttribute("aria-expanded", "true");
      this.render();
    }

    close() {
      this.isOpen = false;
      this.pop.hidden = true;
      this.input.setAttribute("aria-expanded", "false");
      this.setActive(-1);
    }

    refresh() { if (this.isOpen) this.render({ keepActive: this.active >= 0 }); }

    render({ keepActive = false } = {}) {
      const text = this.input.value;
      const res = this.source(text) || {};
      const rows = res.rows || [];
      const current = text.trim();
      this.items = rows.filter((r) => r.value != null);
      const out = [];
      let idx = 0;
      for (const r of rows) {
        if (r.group) {
          const li = el("li", "combo-group", r.group);
          li.setAttribute("role", "presentation");
          out.push(li);
          continue;
        }
        const li = el("li", "combo-opt");
        li.id = `${this.optPrefix}${idx}`;
        li.dataset.index = idx++;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        const tick = el("span", "tick", r.value === current ? "✓" : "");
        tick.setAttribute("aria-hidden", "true");
        const name = el("span", "name");
        name.append(highlight(r.label ?? r.value, r.hits || []));
        li.append(tick, name);
        out.push(li);
      }
      if (!this.items.length && res.empty) {
        const li = el("li", "combo-empty", res.empty);
        li.setAttribute("role", "presentation");
        out.push(li);
      }
      if (res.matched > this.items.length) {
        const li = el("li", "combo-more", `${(res.matched - this.items.length).toLocaleString()} more. Keep typing to narrow the list.`);
        li.setAttribute("role", "presentation");
        out.push(li);
      }
      this.list.replaceChildren(...out);
      this.count.textContent = res.count || "";
      const preselect = res.preselect ?? current !== "";
      this.setActive(keepActive ? Math.min(this.active, this.items.length - 1)
        : preselect && this.items.length ? 0 : -1);
    }

    setActive(i) {
      this.active = i;
      this.list.querySelectorAll(".combo-opt").forEach((li) => {
        const on = Number(li.dataset.index) === i;
        li.classList.toggle("active", on);
        li.setAttribute("aria-selected", on ? "true" : "false");
        if (on) li.scrollIntoView({ block: "nearest" });
      });
      if (i >= 0) this.input.setAttribute("aria-activedescendant", `${this.optPrefix}${i}`);
      else this.input.removeAttribute("aria-activedescendant");
    }

    pick(i) {
      const item = this.items[i];
      if (!item) return;
      this.input.value = item.value;
      this.input.dispatchEvent(new Event("change", { bubbles: true }));
      if (this.onPick && this.onPick(item.value)) this.render();
      else this.close();
    }

    move(by) {
      if (!this.isOpen) return this.open();
      const n = this.items.length;
      if (!n) return;
      let i = this.active < 0 ? (by > 0 ? 0 : n - 1) : this.active + by;
      i = Math.abs(by) === 1 ? (i + n) % n : Math.max(0, Math.min(n - 1, i));
      this.setActive(i);
    }

    _key(e) {
      if (!this._enabled || e.ctrlKey || e.metaKey) return; // Ctrl+Enter stays with the page
      const open = this.isOpen;
      if (e.key === "ArrowDown") { e.preventDefault(); this.move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); this.move(-1); }
      else if (e.key === "PageDown" && open) { e.preventDefault(); this.move(8); }
      else if (e.key === "PageUp" && open) { e.preventDefault(); this.move(-8); }
      else if (e.key === "Enter" && open && this.active >= 0) { e.preventDefault(); this.pick(this.active); }
      else if (e.key === "Escape" && open) { e.preventDefault(); this.close(); }
      else if (e.key === "Tab") this.close();
    }
  }

  Combobox.match = match;
  Combobox.filter = filter;
  Combobox.highlight = highlight;
  window.Combobox = Combobox;
})();

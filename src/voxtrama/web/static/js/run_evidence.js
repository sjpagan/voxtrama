/*
 * The link between a produced field and the audio it came from, in both
 * directions.
 *
 * One direction already worked: clicking an evidence button seeks the
 * player and highlights the transcript rows that evidence covers. The
 * other did nothing: clicking the segment a claim was extracted from left
 * the claim untouched.
 *
 * Both directions read the SAME two intervals: an evidence button's
 * [start, end) and a row's [start, end). No second source of truth is needed.
 * engine.anchor_index.AnchorIndex's `_interval_for` always returns the first
 * and last *covering* segment's boundaries, never a sub-span, so "this row
 * belongs to that evidence" is the same comparison read from either end.
 *
 * The relation is many-to-many: one claim can span several
 * rows, and one row can feed several claims far apart in the right-hand
 * column. Highlighting all of them while the viewer sees none is the same as
 * highlighting nothing, so the first match is scrolled into view and
 * #vx-output-linked-count reports how many there are. It is a bare number, as
 * the transcript's search count already is, so this module writes no English
 * that would need translating.
 *
 * Exposes one global, `vxEvidence`, instead of a function per behaviour:
 * these files share a single namespace, and a duplicate name silently broke
 * the dropzone.
 */

window.vxEvidence = (function () {
  // Intervals round-trip through JSON, so compare with a small tolerance
  // rather than exactly.
  const EPSILON = 0.05;

  // The rows are the Transcript tab's turns now, and a turn joins
  // several segments, so "belongs to" means overlap, not containment. Two
  // intervals that only touch at a boundary do not overlap.
  function overlaps(a, b) {
    return Math.min(a.end, b.end) - Math.max(a.start, b.start) > EPSILON;
  }

  function intervalOf(element, startKey, endKey) {
    return { start: Number(element.dataset[startKey]), end: Number(element.dataset[endKey]) };
  }

  function evidenceCards() {
    // Only cards that anchored: a claim marked needs_review never
    // gets an interval (components/run_output.html), so the two are already
    // mutually exclusive before this module sees them.
    return [...document.querySelectorAll("#vx-output-list .vx-output__card")]
      .map((card) => ({ card, button: card.querySelector(".vx-output__evidence") }))
      .filter((entry) => entry.button)
      .map((entry) => ({ card: entry.card, ...intervalOf(entry.button, "evidenceStart", "evidenceEnd") }));
  }

  function clear(rows, cards, counter) {
    rows.forEach((row) => row.classList.remove("vx-linked"));
    cards.forEach((entry) => entry.card.classList.remove("vx-output__card--active"));
    if (counter) counter.line.hidden = true;
  }

  function showFirst(elements) {
    if (elements.length) elements[0].scrollIntoView({ block: "center", behavior: "smooth" });
  }

  // Evidence → transcript: the rows one claim was drawn from.
  function rowsFor(rows, evidence) {
    return rows.filter((row) => overlaps(evidence, intervalOf(row, "start", "end")));
  }

  // Transcript → evidence: every claim drawn from one row. Several claims
  // can quote the same passage, so this returns all of them.
  function cardsFor(cards, row) {
    const segment = intervalOf(row, "start", "end");
    return cards.filter((entry) => overlaps(entry, segment));
  }

  function onEvidenceClick(rows, cards, counter, entry) {
    clear(rows, cards, counter);
    entry.card.classList.add("vx-output__card--active");
    const matched = rowsFor(rows, entry);
    matched.forEach((row) => row.classList.add("vx-linked"));
    showFirst(matched);
  }

  function onRowClick(rows, cards, counter, row) {
    clear(rows, cards, counter);
    row.classList.add("vx-linked");
    const matched = cardsFor(cards, row);
    matched.forEach((entry) => entry.card.classList.add("vx-output__card--active"));
    showFirst(matched.map((entry) => entry.card));
    if (counter && matched.length) {
      counter.line.hidden = false;
      counter.value.textContent = matched.length;
    }
  }

  // The sentence lives in components/run_output.html, translated. Only the
  // digit is written here.
  function counterOf() {
    const line = document.getElementById("vx-output-linked");
    const value = document.getElementById("vx-output-linked-count");
    return line && value ? { line, value } : null;
  }

  function init(rows) {
    const cards = evidenceCards();
    const counter = counterOf();
    cards.forEach((entry) => {
      entry.card
        .querySelector(".vx-output__evidence")
        .addEventListener("click", () => onEvidenceClick(rows, cards, counter, entry));
    });
    rows.forEach((row) => {
      row.addEventListener("click", (event) => {
        // The speaker chip and the segment list open their own panels.
        if (!event.target.closest("details")) onRowClick(rows, cards, counter, row);
      });
    });
  }

  return { init };
})();

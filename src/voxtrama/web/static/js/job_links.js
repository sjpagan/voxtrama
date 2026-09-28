/*
 * The curved lines from the bubble a verified card was drawn from to
 * that card, in the card's own colour. Both columns
 * scroll on their own, so the lines are redrawn on every scroll of
 * either, on resize, when a tab opens and when a bubble's segments open
 * or close. A line whose bubble or card is scrolled out of sight is not
 * drawn, rather than drawn pointing at nothing. Pure decoration over the
 * evidence the card already states in words: aria-hidden, and nothing
 * depends on it.
 */
(function () {
  const area = document.getElementById("vx-run-result");
  const turnsList = document.getElementById("vx-turns");
  const cardsList = document.getElementById("vx-output-list");
  if (!area || !turnsList || !cardsList) return;
  const SVG = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(SVG, "svg");
  svg.classList.add("vx-links");
  svg.setAttribute("aria-hidden", "true");
  area.append(svg);
  const turns = [...turnsList.querySelectorAll(".vx-turn")];
  const cards = [...cardsList.querySelectorAll(".vx-output__card[data-evidence-start]")];

  function turnAt(seconds) {
    return turns.find((turn) => seconds >= Number(turn.dataset.start) - 0.05 && seconds < Number(turn.dataset.end));
  }

  function inside(rect, box) {
    const middle = rect.top + rect.height / 2;
    return middle >= box.top && middle <= box.bottom;
  }

  function add(name, attributes) {
    const element = document.createElementNS(SVG, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    svg.append(element);
  }

  function draw() {
    svg.replaceChildren();
    if (!area.offsetParent) return;
    const origin = area.getBoundingClientRect();
    svg.setAttribute("width", origin.width);
    svg.setAttribute("height", origin.height);
    const turnsBox = turnsList.getBoundingClientRect();
    const cardsBox = cardsList.getBoundingClientRect();
    cards.forEach((card) => {
      const turn = turnAt(Number(card.dataset.evidenceStart));
      if (!turn) return;
      const bubble = turn.querySelector(".vx-turn__bubble").getBoundingClientRect();
      const time = turn.querySelector(".vx-turn__time").getBoundingClientRect();
      const head = card.getBoundingClientRect();
      if (!inside(bubble, turnsBox) || !inside({ top: head.top, height: 56 }, cardsBox)) return;
      const x1 = Math.max(bubble.right, turn.classList.contains("vx-turn--right") ? time.right : 0) + 6 - origin.left;
      const y1 = bubble.top + bubble.height / 2 - origin.top;
      const x2 = head.left - origin.left;
      const y2 = head.top + 28 - origin.top;
      const bend = Math.max(24, (x2 - x1) / 2);
      const color = getComputedStyle(card.querySelector(".vx-output__kind")).color;
      add("path", { d: `M${x1},${y1} C${x1 + bend},${y1} ${x2 - bend},${y2} ${x2},${y2}`, stroke: color });
      add("circle", { cx: x1, cy: y1, r: 4, fill: color });
      add("circle", { cx: x2, cy: y2, r: 4, fill: color });
    });
  }

  let pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      draw();
    });
  }

  turnsList.addEventListener("scroll", schedule);
  cardsList.addEventListener("scroll", schedule);
  window.addEventListener("resize", schedule);
  window.addEventListener("scroll", schedule, { passive: true });
  document.querySelectorAll(".vx-tabs__radio").forEach((radio) => radio.addEventListener("change", schedule));
  turnsList.addEventListener("toggle", schedule, true);
  schedule();
})();

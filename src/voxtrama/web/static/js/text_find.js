/*
 * The one search of the job view: Transcript,
 * Explore and Recap each hold a .vx-find (components/text_find.html).
 * Every match of the typed word is marked, the current one stands out,
 * and the arrows (or Enter, Shift+Enter) move between them: «2 of 5».
 * «of» comes translated from the page (data-of). Marks are
 * nodes over the page's own text, never HTML, and nothing typed leaves
 * the page. A line hidden by another filter (Explore's speaker) is not
 * searched. That filter sends "vx-find:refresh" to search again.
 */
(function () {
  function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function markInto(element, text, query, marks) {
    element.textContent = "";
    if (!query) {
      element.textContent = text;
      return;
    }
    let last = 0;
    for (const match of text.matchAll(new RegExp(escapeRegExp(query), "ig"))) {
      element.append(text.slice(last, match.index));
      const mark = document.createElement("mark");
      mark.textContent = match[0];
      element.append(mark);
      marks.push(mark);
      last = match.index + match[0].length;
    }
    element.append(text.slice(last));
  }

  // From a match to its moment in the audio: the player moves, and waits.
  function follow(mark) {
    const line = mark.closest("[data-start]");
    const player = document.getElementById("vx-run-player");
    if (line && player) player.currentTime = Number(line.dataset.start);
  }

  function init(box) {
    const scope = document.querySelector(box.dataset.findScope);
    if (!scope) return;
    const input = box.querySelector(".vx-find__input");
    const count = box.querySelector(".vx-find__count");
    const clear = box.querySelector(".vx-find__clear");
    const steps = [...box.querySelectorAll(".vx-find__step")];
    const texts = [...scope.querySelectorAll(box.dataset.findTexts)];
    const original = texts.map((element) => element.textContent);
    let marks = [];
    let current = -1;

    function markAll() {
      const query = input.value.trim();
      marks = [];
      texts.forEach((element, index) => {
        const searched = query && !element.closest("[hidden]");
        markInto(element, original[index], searched ? query : "", marks);
      });
    }

    function show(index, moved) {
      marks.forEach((mark) => mark.classList.remove("vx-mark--current"));
      current = marks.length ? (index + marks.length) % marks.length : -1;
      const query = input.value.trim();
      count.textContent = query ? `${marks.length ? current + 1 : 0} ${count.dataset.of} ${marks.length}` : "";
      steps.forEach((step) => (step.disabled = marks.length < 2));
      clear.hidden = !query;
      if (current < 0) return;
      marks[current].classList.add("vx-mark--current");
      marks[current].scrollIntoView({ block: "nearest", behavior: "smooth" });
      if (moved) follow(marks[current]);
    }

    const search = () => {
      markAll();
      show(0, false);
    };
    input.addEventListener("input", search);
    scope.addEventListener("vx-find:refresh", search);
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      show(current + (event.shiftKey ? -1 : 1), true);
    });
    steps.forEach((step) =>
      step.addEventListener("click", () => show(current + Number(step.dataset.step), true))
    );
    clear.addEventListener("click", () => {
      input.value = "";
      search();
      input.focus();
    });
  }

  document.querySelectorAll(".vx-find").forEach(init);
})();

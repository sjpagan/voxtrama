/*
 * The run page's terminal panel: appends `log` SSE lines as they
 * arrive, and wires "Stop run" to POST /runs/{id}/cancel. It is the one
 * button on this page that needs a network call instead of a plain <form>,
 * since that route answers JSON, not a redirect a browser could
 * land on. Split from run_page.js like run_activity.js and run_vitality.js:
 * one context per file.
 *
 * The last line is picked out in CSS (:last-of-type,
 * components/_run_terminal.scss) instead of a class this module moves on
 * every append: one fewer DOM write per line.
 *
 * Wrapped in a function of its own: these scripts share one global
 * namespace, and a name declared at the top level here could silently
 * overwrite a twin in another file. What other modules need is exported
 * on `window` explicitly.
 */

(function () {
  // The panel stays scrolled to its bottom at all times. Only this many
  // lines are kept in the DOM, so a run lasting hours does not grow the
  // page without bound. It is the same limit
  // api.routes.run_page.LOG_TAIL_LINES applies to a fresh page load, applied
  // here to what accumulates live on top of it.
  const MAX_VISIBLE_LINES = 200;

  function appendLines(lines) {
    const log = document.getElementById("vx-terminal-log");
    if (!log) return;
    for (const line of lines) {
      const span = document.createElement("span");
      span.className = "vx-terminal__line";
      span.textContent = line;
      log.appendChild(span);
      log.appendChild(document.createTextNode("\n"));
    }
    const spans = log.querySelectorAll(".vx-terminal__line");
    for (let i = 0; i < spans.length - MAX_VISIBLE_LINES; i++) {
      const trailingNewline = spans[i].nextSibling;
      if (trailingNewline) trailingNewline.remove();
      spans[i].remove();
    }
    log.scrollTop = log.scrollHeight;
  }

  function stopRun(runId) {
    const button = document.getElementById("vx-run-stop");
    if (!button) return;
    button.disabled = true;
    // Explaining a network hiccup is not this module's job. The run's state
    // (the badge, the chain) in the end tells the truth, over the SSE
    // connection this button does not touch.
    fetch(`/runs/${runId}/cancel`, { method: "POST" }).finally(() => {
      button.disabled = false;
    });
  }

  function hide() {
    const panel = document.getElementById("vx-run-terminal");
    if (panel) panel.hidden = true;
  }

  function init(runId) {
    const button = document.getElementById("vx-run-stop");
    if (button) button.addEventListener("click", () => stopRun(runId));
  }

  window.VxRunTerminal = { appendLines, hide, init };
})();

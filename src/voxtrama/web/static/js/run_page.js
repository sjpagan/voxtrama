/*
 * The run page's live behaviour. No build chain, no dependency:
 * EventSource is native to every browser this app targets, which is
 * why the SSE route (api.routes.run_events) exists instead of a websocket
 * that would need a library on this side too.
 *
 * Carries no English text of its own: code review caught a first version
 * that did (`{pending: "Waiting", ...}`, `event.state` written straight
 * into the DOM), both silently bypassing the translation catalogue. Every
 * label this module shows comes from components/run_labels.html's
 * `label_catalog()` (a hidden list, already `{% trans %}`-translated,
 * rendered once per page), so this stays a renderer of *state*, not a second
 * source of words. The step chain's "N of total" count follows the
 * same rule: refreshStepProgress() counts the [data-step-id] elements this
 * module just updated instead of keeping a running total that could drift
 * from them. Activity numbers (run_activity.js), vitality (run_vitality.js),
 * the terminal panel (run_terminal.js) and the SSE connection
 * (run_events_connection.js) are separate concerns: this module hands
 * each its slice of one message.
 */

(function () {
  let LABELS = null;

  function buildLabelCatalog() {
    const catalog = { step: {}, run: {}, done: {} };
    document.querySelectorAll("#vx-state-labels li").forEach((li) => {
      catalog[li.dataset.catalog][li.dataset.state] = li.textContent;
    });
    document.querySelectorAll("#vx-done-labels li").forEach((li) => {
      catalog.done[li.dataset.step] = li.textContent;
    });
    return catalog;
  }

  const STATE_TONES = { succeeded: "success", running: "warning" };

  function setBadgeTone(el, tone) {
    el.classList.remove("vx-badge--success", "vx-badge--warning");
    if (tone) el.classList.add(`vx-badge--${tone}`);
  }

  function setRunState(state) {
    document.getElementById("vx-run-state-label").textContent = LABELS.run[state] || state;
    setBadgeTone(document.getElementById("vx-run-state"), STATE_TONES[state] || null);
  }

  function setStepState(row, state) {
    row.dataset.stepState = state;
    const done = state === "succeeded" && LABELS.done[row.dataset.stepId];
    row.querySelector("[data-step-label-text]").textContent = done || LABELS.step[state] || state;
    setBadgeTone(row.querySelector("[data-step-badge]"), STATE_TONES[state] || null);
  }

  // A `progress` event only names the step now running
  // (event.step_id/step_index), never the chain's other rows. In the defect
  // this closes, every row this function once flipped to "running" stayed
  // that way, since nothing later moved a finished one to "succeeded".
  // step_index is 0-based and matches [data-step-id] in DOM order (both
  // follow RunStep.position, and rendering.run_page's docstring says why nothing
  // here is a second source for that order): a row before it is done, the row
  // at it is running, everything after has not been reached. One exception is
  // not handled: a step skipped by its own condition
  // (engine.step_loop.blocked_by_condition) is never announced, so its
  // position is silently passed over instead of named "skipped" here.
  // RunEvent carries no per-step array to tell the two apart from this event
  // alone, so a skipped row reads as "succeeded" until the run reaches final
  // and the page reloads (below) to the render that gets it right.
  function applyStepChain(stepIndex) {
    if (stepIndex === null || stepIndex === undefined) return;
    document.querySelectorAll("[data-step-id]").forEach((row, index) => {
      if (index < stepIndex) setStepState(row, "succeeded");
      else if (index === stepIndex) setStepState(row, "running");
      else setStepState(row, "pending");
    });
  }

  // "3 of 5" is a count of DOM state, not a second source of truth:
  // every [data-step-id] already carries the data-step-state setStepState
  // above just wrote, so this counts those instead of tracking a running
  // total that could drift. Only the number moves (engine.step_progress's
  // "current, capped at total" rule, reapplied here in JS because the DOM
  // changed, not the row rendering.run_page.py sent). The translated "of"
  // beside it (pages/run.html's {% trans %}) is never touched, so this writes
  // no English either.
  const TERMINAL_STEP_STATES = new Set(["succeeded", "failed", "skipped"]);

  function refreshStepProgress() {
    const current = document.getElementById("vx-run-progress-current");
    if (!current) return;
    const rows = document.querySelectorAll("[data-step-id]");
    const total = rows.length;
    if (total === 0) return;
    let done = 0;
    rows.forEach((row) => {
      if (TERMINAL_STEP_STATES.has(row.dataset.stepState)) done += 1;
    });
    current.textContent = Math.min(done + 1, total);
  }

  function renderProgressEvent(event) {
    if (event.final) {
      // A final event names only the last step announced, never the whole
      // chain: only the server-rendered page gets every step right. That page
      // replaces this one in place, without a reload (see becomeFinal() below).
      window.VxRunVitality.stop();
      becomeFinal();
      return;
    }
    setRunState(event.state);
    applyStepChain(event.step_index);
    refreshStepProgress();
    window.VxRunActivity.stopTiming();
    if (event.activity) {
      const a = event.activity;
      const percent = a.total ? (a.done / a.total) * 100 : null;
      const parts = a.unit === "windows";
      const total =
        a.total === null || parts ? "" : window.VxRunActivity.formatValue(a.unit, a.total);
      const done = parts
        ? window.VxRunActivity.formatParts(a.done, a.total)
        : window.VxRunActivity.formatValue(a.unit, a.done);
      const busy = percent === null || (parts && a.done < a.total);
      window.VxRunActivity.showActivity(event.message || "", done, total, percent, busy);
      window.VxRunActivity.startTiming(event.step_started_at, a.done, a.total);
    } else if (event.step_started_at) {
      // A step with nothing to count shows what it does and for how
      // long, never its timeout as if it were the end of a bar.
      window.VxRunActivity.showActivity(event.message || "", "", "", null);
      window.VxRunActivity.startTiming(event.step_started_at, 0, null);
    }
  }

  // The concluded page is fetched and swapped in: its <main> replaces this
  // one, and the scripts only it needs (the result's) are started, in order.
  // Any failure falls back to the plain reload this module used to do.
  async function becomeFinal() {
    try {
      const response = await fetch(window.location.href, { headers: { Accept: "text/html" } });
      const next = new DOMParser().parseFromString(await response.text(), "text/html");
      const fresh = next.querySelector("main");
      const current = document.querySelector("main");
      if (!response.ok || !fresh || !current) throw new Error("no page");
      const loaded = new Set([...document.scripts].map((script) => script.src));
      current.replaceWith(fresh);
      document.title = next.title;
      fresh.querySelectorAll("script[src]").forEach((inert) => {
        const src = new URL(inert.getAttribute("src"), window.location.href).href;
        if (loaded.has(src)) return;
        const script = document.createElement("script");
        script.src = src;
        script.async = false;
        document.body.append(script);
      });
    } catch (error) {
      window.location.reload();
    }
  }

  function renderLogEvent(event) {
    window.VxRunTerminal.appendLines(event.lines);
  }

  function init() {
    const page = document.getElementById("vx-run-page");
    if (page.dataset.runFinal === "true") return;
    LABELS = buildLabelCatalog();
    window.VxRunTerminal.init(page.dataset.runId);
    window.VxRunEventsConnection.connect(
      page.dataset.runId, page.dataset.logOffset, renderProgressEvent, renderLogEvent
    );
    window.VxRunVitality.start(page.dataset.runId);
  }

  init();
})();

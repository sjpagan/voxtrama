/*
 * The run page's SSE connection: opens api.routes.run_events,
 * resuming it from wherever this page's first paint already got to, and
 * passes each message to the callbacks run_page.js hands in. Split from
 * run_page.js, which owns what a message means, to stay under the
 * project's file-length limit. This file only opens and reconnects the one connection.
 *
 * Wrapped in a function of its own: these scripts share one global
 * namespace, and a name declared at the top level here could silently
 * overwrite a twin in another file. What other modules need is exported on
 * `window` explicitly.
 */

(function () {
  // Toggled by the SSE connection's `error`/`open` events. Separate from
  // #vx-run-vitality (run_vitality.js), which asks whether the *worker* is
  // still there: a server or network gone is a fact about the connection, and
  // neither badge can stand in for the other (found in code review: a silent
  // connection loss looked just like a run quietly working, the confusion
  // vitality exists to remove, coming back by another route).
  // EventSource drops and reopens by itself (a proxy closing an idle
  // stream, a laptop waking up); the badge flashed on every such blip. It
  // shows only when the connection stays down for longer than a reconnect.
  const VX_LOST_AFTER_MS = 10000;
  let vxLostTimer = null;

  function setConnectionLost(lost) {
    const badge = document.getElementById("vx-run-connection");
    if (!lost) {
      if (vxLostTimer !== null) clearTimeout(vxLostTimer);
      vxLostTimer = null;
      badge.hidden = true;
      return;
    }
    if (vxLostTimer === null) {
      vxLostTimer = setTimeout(() => {
        badge.hidden = false;
      }, VX_LOST_AFTER_MS);
    }
  }

  function alive() {
    setConnectionLost(false);
    if (window.VxRunVitality) window.VxRunVitality.noteLife();
  }

  // `logOffset` (rendering.run_page.RunPageView's field): how many
  // bytes of run.log this page already rendered into #vx-terminal-log. A
  // plain EventSource cannot set the `Last-Event-ID` header a *reconnect*
  // sends by itself (api.routes.run_log_stream.log_tail_for reads that too),
  // and on this first connection there is no prior message to echo. So this
  // carries the same value as `?last_event_id=`, read the same way server
  // side, only so the terminal panel's first paint is never sent a second
  // time.
  function connect(runId, logOffset, onProgress, onLog) {
    const source = new EventSource(`/runs/${runId}/events?last_event_id=${logOffset || 0}`);
    source.addEventListener("open", () => setConnectionLost(false));
    source.addEventListener("error", () => setConnectionLost(true));
    source.addEventListener("progress", (message) => {
      alive();
      const event = JSON.parse(message.data);
      onProgress(event);
      if (event.final) source.close();
    });
    // The terminal panel's lines, on this same connection instead of a
    // second EventSource for the same run (api.routes.run_events's docstring
    // says why).
    source.addEventListener("log", (message) => {
      alive();
      onLog(JSON.parse(message.data));
    });
  }

  window.VxRunEventsConnection = { connect };
})();

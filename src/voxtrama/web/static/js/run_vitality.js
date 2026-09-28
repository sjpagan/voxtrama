/*
 * Polls GET /runs/{id}/vitality so the run page can tell a worker that
 * stopped answering from one still working. Separate from run_page.js's SSE
 * handling because it runs at its own, slower pace: the queue backend costs
 * one round trip per call, not something to hit several times a second the
 * way the SSE stream polls progress.json (api.routes.run_vitality's
 * docstring).
 *
 * The live terminal panel changes what this badge is *for*, not how it
 * works. With that panel showing run.log lines as they arrive, an advancing
 * line is already proof of life. This poll now covers the one case a moving
 * log cannot rule out: a worker that dies between two log lines (a
 * generative call's silent wait, the "21 seconds" measured on
 * extract_concepts, stretched to minutes on a slower model), with nothing
 * left to write the next line. The
 * two signals cannot contradict each other: this route only answers `gone`
 * once the queue confirms the job behind `run.job_id` is no longer there,
 * which cannot be true of a log still advancing. No code here keeps that
 * true. It follows from what api.routes.run_vitality asks the queue.
 *
 * Exposed as window.VxRunVitality: loaded before run_page.js (both `defer`,
 * run in document order, since there is no bundler to wire them otherwise),
 * which starts it and stops it once its SSE stream reports `final: true`.
 *
 * Wrapped in a function of its own: these scripts share one global
 * namespace, and a name declared at the top level here could silently
 * overwrite a twin in another file. What other modules need is exported
 * on `window` explicitly.
 */

(function () {
  const VX_VITALITY_POLL_MS = 5000;
  // The badge showed during a ten-minute model call on a working run.
  // It now needs the queue to say `gone` three polls running *and* the run
  // to have sent nothing for a minute: a log line or a progress event is
  // proof of life that one answer from the queue cannot outweigh.
  const VX_GONE_POLLS = 3;
  const VX_QUIET_MS = 60000;
  let vxVitalityTimer = null;
  let vxGoneCount = 0;
  let vxLastLife = Date.now();

  function vxApplyVitality(vitality) {
    vxGoneCount = vitality === "gone" ? vxGoneCount + 1 : 0;
    const quiet = Date.now() - vxLastLife > VX_QUIET_MS;
    document.getElementById("vx-run-vitality").hidden = !(vxGoneCount >= VX_GONE_POLLS && quiet);
  }

  function vxPollVitality(runId) {
    fetch(`/runs/${runId}/vitality`)
      .then((response) => response.json())
      .then((body) => vxApplyVitality(body.vitality))
      .catch(() => {}); // a network hiccup says nothing either way, see engine.vitality's UNKNOWN
  }

  window.VxRunVitality = {
    noteLife() {
      vxLastLife = Date.now();
      vxGoneCount = 0;
      document.getElementById("vx-run-vitality").hidden = true;
    },
    start(runId) {
      vxPollVitality(runId);
      vxVitalityTimer = setInterval(() => vxPollVitality(runId), VX_VITALITY_POLL_MS);
    },
    stop() {
      if (vxVitalityTimer !== null) clearInterval(vxVitalityTimer);
      vxVitalityTimer = null;
      document.getElementById("vx-run-vitality").hidden = true;
    },
  };
})();

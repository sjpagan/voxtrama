/*
 * Formats and shows the run page's live activity numbers: a step's
 * position within the audio it measures ("12:04 / 18:30"), or how many parts
 * of the transcript a generative step has read ("2 of 4 parts read"). Split from run_page.js,
 * which owns state and connection lifecycle: one context each, both under
 * this project's file-length limit.
 *
 * formatClock/formatBytes mirror cli/progress_lines.py the same way that
 * module mirrors humanize.py. The engine publishes raw seconds and bytes
 * (core formats nothing for a human reader), and a renderer (a terminal
 * there, a browser here) turns those into "12:04" or "461 MB". Neither number
 * is translatable text (translation only applies to words), so nothing here
 * reads a catalogue.
 *
 * Wrapped in a function of its own: these scripts share one global
 * namespace, and a name declared at the top level here could silently
 * overwrite a twin in another file. What other modules need is exported on
 * `window` explicitly.
 */

(function () {
  function formatClock(seconds) {
    const total = Math.max(0, Math.floor(seconds));
    const mm = Math.floor(total / 60);
    return `${mm}:${String(total % 60).padStart(2, "0")}`;
  }

  function formatBytes(bytes) {
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    for (const unit of units) {
      if (value < 1024 || unit === "GB") {
        return unit === "GB" ? `${value.toFixed(1)} GB` : `${Math.round(value)} ${unit}`;
      }
      value /= 1024;
    }
    return `${value.toFixed(1)} GB`;
  }

  function formatValue(unit, value) {
    return unit === "bytes" ? formatBytes(value) : formatClock(value);
  }

  // "2 of 4 parts read": a generative step's windows (engine.window_calls),
  // in the words the template translated.
  function formatParts(done, total) {
    const template = document.getElementById("vx-run-activity").dataset.parts;
    return template.replace("{done}", done).replace("{total}", total);
  }

  function showActivity(message, doneText, totalText, percent, busy = percent === null) {
    document.getElementById("vx-run-activity").hidden = false;
    document.getElementById("vx-activity-message").textContent = message;
    document.getElementById("vx-activity-position").textContent = doneText;
    document.getElementById("vx-activity-total").textContent = totalText;
    const fill = document.getElementById("vx-activity-bar-fill");
    fill.style.width = percent === null ? "0%" : `${Math.min(100, percent)}%`;
    // Nothing measurable, or a model call that reports only when it ends: a
    // bar that moves by itself says "working" where "0%" would look stuck.
    fill.parentElement.classList.toggle("vx-activity__bar--busy", busy);
  }

  // How long the step has been running and roughly how long is left,
  // ticking every second between events. Elapsed counts from the step's own
  // start (progress.json's step_started_at); what is left extrapolates the
  // rate of the last event, so it is shown only once there is a rate to use.
  // The words come translated from the template's data attributes.
  let timingTimer = null;

  function stopTiming() {
    if (timingTimer !== null) clearInterval(timingTimer);
    timingTimer = null;
    const line = document.getElementById("vx-activity-timing");
    if (line) line.hidden = true;
  }

  function startTiming(startedAt, done, total) {
    stopTiming();
    const line = document.getElementById("vx-activity-timing");
    const start = Date.parse(startedAt || "");
    if (!line || Number.isNaN(start)) return;
    const eventAt = Date.now();
    const elapsedAtEvent = (eventAt - start) / 1000;
    const rate = elapsedAtEvent > 10 && done > 0 ? done / elapsedAtEvent : null;
    const tick = () => {
      const now = Date.now();
      let text = line.dataset.elapsed.replace("{time}", formatClock((now - start) / 1000));
      if (rate && total) {
        const left = (total - done) / rate - (now - eventAt) / 1000;
        if (left > 0) text += " \u00b7 " + line.dataset.left.replace("{time}", formatClock(left));
      }
      line.textContent = text;
      line.hidden = false;
    };
    tick();
    timingTimer = setInterval(tick, 1000);
  }

  window.VxRunActivity = {
    formatValue,
    formatParts,
    showActivity,
    startTiming,
    stopTiming,
  };
})();

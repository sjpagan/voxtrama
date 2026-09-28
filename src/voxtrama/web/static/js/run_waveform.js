/*
 * The player's own waveform: fetches the shape of the recording,
 * keeps it in step with playback, and seeks by click or keyboard. The
 * painting itself is run_waveform_draw.js, loaded before this file.
 *
 * It used to compute that shape here, with `fetch` +
 * AudioContext.decodeAudioData over the whole audio file. Measured on a real
 * 21-minute recording: **182 MB downloaded and 232 MB of decoded PCM** held
 * in memory to draw a few hundred bars. That is why the module had a duration
 * ceiling, and why a 21:08 recording, 68 seconds past it, silently drew
 * nothing and looked like a broken player.
 *
 * The levels now come from GET /recordings/{id}/peaks, computed once on
 * the machine that already holds the audio (voxtrama/ingest/peaks.py)
 * and cached beside it: 6 KB of JSON, the same for a minute or an hour.
 * There is no ceiling left to trip over.
 *
 * Carries no English of its own, the rule runs_delete.js follows too:
 * when there is no waveform to draw, the sentence saying so is already
 * in the page, translated, and this module only unhides it.
 *
 * Wrapped in a function of its own: these scripts share one global
 * namespace, and a name declared at the top level here could silently
 * overwrite a twin in another file. What other modules need is exported
 * on `window` explicitly.
 */

(function () {
  function seekTo(canvas, audio, clientX) {
    if (!audio.duration) return;
    const rect = canvas.getBoundingClientRect();
    const fraction = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    audio.currentTime = fraction * audio.duration;
  }

  function initSeek(canvas, audio) {
    canvas.addEventListener("click", (event) => seekTo(canvas, audio, event.clientX));
    // Arrow keys seek too: a control only a mouse can reach does not exist
    // for someone who cannot use one.
    canvas.addEventListener("keydown", (event) => {
      if (!audio.duration) return;
      const step = 5;
      if (event.key === "ArrowRight") {
        audio.currentTime = Math.min(audio.duration, audio.currentTime + step);
      } else if (event.key === "ArrowLeft") {
        audio.currentTime = Math.max(0, audio.currentTime - step);
      } else {
        return;
      }
      event.preventDefault();
    });
  }

  async function fetchLevels(recordingId) {
    const response = await fetch(`/recordings/${recordingId}/peaks`);
    if (!response.ok) throw new Error(String(response.status));
    return (await response.json()).peaks;
  }

  function unavailable(canvas) {
    // Say it, rather than leave an empty box that reads as a fault. The
    // player keeps working: play, volume and seeking from a transcript row
    // or an evidence link live in run_player.js and run_result.js.
    const notice = document.getElementById("vx-player-wave-notice");
    if (notice) notice.hidden = false;
    canvas.hidden = true;
  }

  function init() {
    const canvas = document.getElementById("vx-player-wave");
    const audio = document.getElementById("vx-run-player");
    if (!canvas || !audio || !window.vxWaveformDraw) return;
    initSeek(canvas, audio);

    let levels = null;
    const redraw = () => {
      if (!levels) return;
      const progress = audio.duration ? audio.currentTime / audio.duration : 0;
      window.vxWaveformDraw.draw(canvas, levels, progress);
      canvas.setAttribute("aria-valuenow", String(Math.round(progress * 100)));
    };
    audio.addEventListener("timeupdate", redraw);
    audio.addEventListener("seeked", redraw);
    window.addEventListener("resize", redraw);

    fetchLevels(canvas.dataset.recordingId)
      .then((fetched) => {
        levels = fetched;
        redraw();
      })
      .catch(() => unavailable(canvas));
  }

  // A job followed live gets this script only when it finishes: run_page.js
  // swaps the concluded page in and appends the result's scripts, long after
  // DOMContentLoaded has fired. Waiting for that event alone left the
  // waveform blank until a reload.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

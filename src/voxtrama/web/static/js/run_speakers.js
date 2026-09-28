/*
 * The Speakers tab's «Listen»: plays a
 * speaker's first turns, one after the other, on the job's own player
 * (#vx-run-player), and draws those turns as a small waveform beside the
 * button, filling as they play.
 *
 * Each button carries its turns as `data-clips`, [[start, end], ...] in
 * seconds, a minute at most (rendering.speakers_tab). Nothing is cut on
 * the server: the player seeks to each start and moves on at each end.
 * The levels are the recording's own (GET /recordings/{id}/peaks, the
 * file the big waveform reads), taken only over those turns.
 *
 * Carries no English: the button's two words are data-label-play and
 * data-label-stop, already translated in the page (the rule every script
 * here follows). Started at once when the page has already loaded,
 * because run_page.js may add this script after a job finishes.
 */

(function () {
  let playing = null; // { button, clips, index, heard, total }

  function clipsOf(button) {
    try {
      return JSON.parse(button.dataset.clips || "[]");
    } catch (error) {
      return [];
    }
  }

  function totalOf(clips) {
    return clips.reduce((sum, clip) => sum + (clip[1] - clip[0]), 0);
  }

  function levelsFor(clips, peaks, duration) {
    const levels = [];
    for (const [start, end] of clips) {
      const from = Math.floor((start / duration) * peaks.length);
      const to = Math.max(from + 1, Math.ceil((end / duration) * peaks.length));
      levels.push(...peaks.slice(from, to));
    }
    return levels;
  }

  function canvasOf(button) {
    return button.parentElement.querySelector(".vx-speakers__wave");
  }

  function draw(button, progress) {
    const canvas = canvasOf(button);
    if (canvas && canvas.vxLevels && window.vxWaveformDraw) {
      window.vxWaveformDraw.draw(canvas, canvas.vxLevels, progress);
    }
  }

  function label(button, stop) {
    const span = button.querySelector("span");
    if (span) span.textContent = stop ? button.dataset.labelStop : button.dataset.labelPlay;
    button.setAttribute("aria-pressed", stop ? "true" : "false");
  }

  function stop(audio) {
    if (!playing) return;
    audio.pause();
    label(playing.button, false);
    draw(playing.button, 0);
    playing = null;
  }

  function start(audio, button) {
    const clips = clipsOf(button);
    if (!clips.length) return;
    playing = { button, clips, index: 0, heard: 0, total: totalOf(clips) };
    label(button, true);
    audio.currentTime = clips[0][0];
    audio.play();
  }

  function onTime(audio) {
    if (!playing || audio.seeking) return;
    const [begin, end] = playing.clips[playing.index];
    if (audio.currentTime < begin - 1 || audio.currentTime > end + 2) {
      stop(audio);
      return;
    }
    const inside = Math.min(Math.max(audio.currentTime - begin, 0), end - begin);
    draw(playing.button, (playing.heard + inside) / playing.total);
    if (audio.currentTime < end) return;
    playing.heard += end - begin;
    playing.index += 1;
    if (playing.index >= playing.clips.length) {
      stop(audio);
      return;
    }
    audio.currentTime = playing.clips[playing.index][0];
  }

  async function drawWaves(buttons) {
    const wave = document.getElementById("vx-player-wave");
    if (!wave || !window.vxWaveformDraw) return;
    try {
      const response = await fetch(`/recordings/${wave.dataset.recordingId}/peaks`);
      if (!response.ok) return;
      const body = await response.json();
      buttons.forEach((button) => {
        const canvas = canvasOf(button);
        if (!canvas) return;
        canvas.vxLevels = levelsFor(clipsOf(button), body.peaks, body.duration_seconds || 1);
        draw(button, 0);
      });
    } catch (error) {
      // No levels: the buttons still play.
    }
  }

  function init() {
    const audio = document.getElementById("vx-run-player");
    const buttons = Array.from(document.querySelectorAll(".vx-speakers__play"));
    if (!audio || !buttons.length) return;
    buttons.forEach((button) =>
      button.addEventListener("click", () => {
        const again = playing && playing.button === button;
        stop(audio);
        if (!again) start(audio, button);
      })
    );
    audio.addEventListener("timeupdate", () => onTime(audio));
    // Paused from the player, or moved elsewhere: listening is over.
    audio.addEventListener("pause", () => stop(audio));
    // The tab is hidden on load (a radio button shows it): draw when shown,
    // since a canvas with no size draws nothing.
    const radio = document.getElementById("vx-tab-speakers");
    if (radio) radio.addEventListener("change", () => drawWaves(buttons));
    drawWaves(buttons);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

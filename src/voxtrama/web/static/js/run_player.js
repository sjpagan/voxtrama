/*
 * The player's custom controls: play/pause,
 * elapsed/total time, volume, and the jumps back and forward. All of
 * them drive the same native <audio id="vx-run-player"> element that
 * static/js/run_result.js seeks for a transcript row or an evidence link
 * click. Here only the jumps move it, relative to where it is. The waveform
 * (drawing, and seeking by clicking it) is static/js/run_waveform.js, a
 * separate module: this one still works with no waveform drawn (a long
 * recording past its ceiling), and that one still works with the browser's
 * default controls, which is why the two are separate files.
 *
 * Wrapped in a function of its own: these scripts share one global
 * namespace, and a name declared at the top level here could silently
 * overwrite a twin in another file. What other modules need is exported
 * on `window` explicitly.
 */

(function () {
  function formatTime(seconds) {
    const safe = Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
    const total = Math.floor(safe);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    const pad = (value) => String(value).padStart(2, "0");
    return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${minutes}:${pad(secs)}`;
  }

  // aria-label is read from the button's data-label-play/-pause (both {%
  // trans %}-translated server side in components/run_result.html) instead of
  // set to English here. That is the translation catalogue's rule, the same one
  // static/js/run_page.js's label_catalog() keeps live updates from breaking.
  function initToggle(audio, button) {
    const setState = () => {
      const playing = !audio.paused && !audio.ended;
      button.dataset.playing = playing ? "true" : "false";
      button.setAttribute(
        "aria-label",
        playing ? button.dataset.labelPause : button.dataset.labelPlay
      );
    };
    button.addEventListener("click", () => {
      if (audio.paused) audio.play();
      else audio.pause();
    });
    audio.addEventListener("play", setState);
    audio.addEventListener("pause", setState);
    audio.addEventListener("ended", setState);
    setState();
  }

  function initTime(audio, label) {
    const update = () => {
      label.textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
    };
    audio.addEventListener("timeupdate", update);
    audio.addEventListener("loadedmetadata", update);
    update();
  }

  function initVolume(audio, input) {
    input.addEventListener("input", () => {
      audio.volume = Number(input.value);
    });
  }

  // «60s «10s 10s» 60s», never past either end of the recording.
  function initSkips(audio) {
    document.querySelectorAll(".vx-player__skip").forEach((button) => {
      button.addEventListener("click", () => {
        const end = Number.isFinite(audio.duration) ? audio.duration : Infinity;
        audio.currentTime = Math.min(end, Math.max(0, audio.currentTime + Number(button.dataset.skip)));
      });
    });
  }

  function init() {
    const audio = document.getElementById("vx-run-player");
    if (!audio) return;
    const toggle = document.getElementById("vx-player-toggle");
    const time = document.getElementById("vx-player-time");
    const volume = document.getElementById("vx-player-volume");
    if (toggle) initToggle(audio, toggle);
    if (time) initTime(audio, time);
    if (volume) initVolume(audio, volume);
    initSkips(audio);
  }

  init();
})();

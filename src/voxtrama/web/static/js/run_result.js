/*
 * The result panel's live behaviour. No SSE here, since a
 * succeeded run has nothing left to stream. Only plain client-side pieces
 * (no build chain, no dependency): seeking the <audio> player
 * (static/js/run_player.js's element) to a moment a transcript row or an
 * evidence link names, and Explore's speaker filter. The word search is
 * static/js/text_find.js.
 *
 * The link between a claim and the passage it came from, in both directions,
 * moved to static/js/run_evidence.js when its missing half was written. It
 * was the one part of this file that had to know about both columns, and
 * keeping it here would have pushed the module past the project's 150-line
 * limit.
 *
 * Wrapped in a function of its own, unlike the version before it: these
 * scripts share a single global namespace, where a duplicated `init` or
 * `seekTo` silently overwrites its twin.
 */

(function () {
  function seekTo(seconds) {
    const player = document.getElementById("vx-run-player");
    if (!player) return;
    player.currentTime = seconds;
    player.play();
  }

  // Explore rows, Transcript bubbles and the recap's sources all seek the
  // player the same way: from their own data-start. A click on a bubble's
  // «Original segments» opens that list instead.
  function initSeekable(selector) {
    const rows = [...document.querySelectorAll(selector)];
    rows.forEach((row) => {
      const activate = () => seekTo(Number(row.dataset.start));
      row.addEventListener("click", (event) => {
        if (!event.target.closest("details")) activate();
      });
      row.addEventListener("keydown", (event) => {
        if (event.target !== row || row.tagName === "BUTTON") return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
    });
    return rows;
  }

  function initEvidenceSeek() {
    document.querySelectorAll(".vx-output__evidence").forEach((button) => {
      button.addEventListener("click", () => seekTo(Number(button.dataset.evidenceStart)));
    });
  }

  // Explore's speaker filter: a row shows when it is that
  // speaker's. The word search is static/js/text_find.js, told to
  // search again over the rows still shown.
  function initSpeakerFilter(rows) {
    const speaker = document.getElementById("vx-transcript-speaker");
    const list = document.getElementById("vx-transcript-rows");
    if (!speaker || !list) return;
    speaker.addEventListener("change", () => {
      rows.forEach((row) => (row.hidden = Boolean(speaker.value) && row.dataset.speaker !== speaker.value));
      list.dispatchEvent(new Event("vx-find:refresh"));
    });
  }

  // The job's «Merge pauses under»: the value follows the slider,
  // and the form (a plain GET, components/job_turns.html) is sent once
  // the slider is released.
  function initMerge() {
    const form = document.getElementById("vx-merge-form");
    if (!form) return;
    const slider = form.querySelector("#vx-merge");
    const value = form.querySelector("#vx-merge-value");
    slider.addEventListener("input", () => (value.textContent = slider.value));
    slider.addEventListener("change", () => form.submit());
  }

  // Arriving from a link: a search result names one transcript line
  // (#vx-transcript-row-<segment id>). That line is marked and the player set
  // to its start, without playing. The Jobs menu's Regenerate names the panel
  // that reruns the job (#vx-regenerate), which opens. The line may
  // sit in a tab that is not open, so the tab holding it is opened first.
  function followHash() {
    const target = location.hash ? document.getElementById(location.hash.slice(1)) : null;
    if (!target) return;
    const panel = target.closest(".vx-tabs__panel");
    if (panel) document.getElementById(`vx-tab-${panel.dataset.tab}`).checked = true;
    if (target.tagName === "DETAILS") target.open = true;
    if (target.classList.contains("vx-transcript__row")) {
      target.classList.add("vx-transcript__row--target");
      const player = document.getElementById("vx-run-player");
      if (player) player.currentTime = Number(target.dataset.start);
    }
    target.scrollIntoView({ block: "center" });
  }

  function init() {
    followHash();
    if (!document.getElementById("vx-run-result")) return;
    const rows = initSeekable("#vx-transcript-rows .vx-transcript__row");
    const turns = initSeekable("#vx-turns .vx-turn");
    initSeekable(".vx-recap__source");
    initEvidenceSeek();
    initSpeakerFilter(rows);
    initMerge();
    if (window.vxEvidence) window.vxEvidence.init(turns);
  }

  init();
})();

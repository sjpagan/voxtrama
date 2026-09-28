/*
 * The transcript follows the audio: while the player runs, the
 * bubble being spoken (Transcript tab) and the segment being spoken
 * (Explore tab) are marked, and each list scrolls itself so that line
 * stays in view. Only the list scrolls, never the page. Someone
 * scrolling a list by hand takes it over: following
 * resumes a few seconds after they stop. The marked line also fills from
 * the left as it plays (--vx-progress), so the advance within a sentence
 * shows, not only the jump from one sentence to the next.
 */
(function () {
  const player = document.getElementById("vx-run-player");
  if (!player) return;
  const HAND_PAUSE_MS = 4000;
  const lists = [
    { list: document.getElementById("vx-turns"), selector: ".vx-turn", mark: "vx-turn--now" },
    {
      list: document.getElementById("vx-transcript-rows"),
      selector: ".vx-transcript__row",
      mark: "vx-transcript__row--now",
    },
  ].filter((entry) => entry.list);

  lists.forEach((entry) => {
    entry.items = [...entry.list.querySelectorAll(entry.selector)];
    entry.current = null;
    entry.handUntil = 0;
    entry.selfUntil = 0;
    entry.list.addEventListener("scroll", () => {
      // Our own smooth scroll fires many events. Only later ones are the user's.
      if (Date.now() < entry.selfUntil) return;
      entry.handUntil = Date.now() + HAND_PAUSE_MS;
    });
  });

  function itemAt(items, seconds) {
    return items.find(
      (item) => seconds >= Number(item.dataset.start) && seconds < Number(item.dataset.end)
    );
  }

  // Scrolls the list alone: scrollIntoView would move the page as well.
  function keepInView(entry, item) {
    const list = entry.list;
    const top = item.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
    const bottom = top + item.offsetHeight;
    if (top >= list.scrollTop && bottom <= list.scrollTop + list.clientHeight) return;
    entry.selfUntil = Date.now() + 1000;
    list.scrollTo({ top: Math.max(0, top - list.clientHeight / 3), behavior: "smooth" });
  }

  // How far into the current sentence the audio is, as a share of it.
  function progress(item, seconds) {
    const start = Number(item.dataset.start);
    const length = Number(item.dataset.end) - start;
    const share = length > 0 ? Math.min(1, Math.max(0, (seconds - start) / length)) : 0;
    item.style.setProperty("--vx-progress", `${(share * 100).toFixed(1)}%`);
  }

  function follow() {
    const seconds = player.currentTime;
    lists.forEach((entry) => {
      const item = itemAt(entry.items, seconds) || null;
      if (item) progress(item, seconds);
      if (item === entry.current) return;
      if (entry.current) {
        entry.current.classList.remove(entry.mark);
        entry.current.style.removeProperty("--vx-progress");
      }
      entry.current = item;
      if (!item || item.hidden) return;
      item.classList.add(entry.mark);
      if (!player.paused && Date.now() > entry.handUntil && entry.list.offsetParent) {
        keepInView(entry, item);
      }
    });
  }

  player.addEventListener("timeupdate", follow);
  player.addEventListener("seeked", follow);
})();

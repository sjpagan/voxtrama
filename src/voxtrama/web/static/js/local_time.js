/*
 * Turns every `<time datetime="..." data-local="...">` on the page into
 * the reader's own local time. The server (logs.tail, rendering.jobs) and
 * the SSE stream (api.routes.run_log_stream) only ever publish the raw
 * UTC instant: this is the one place that knows which timezone the person
 * looking at the screen is in, so it is the one that does the conversion,
 * not the core.
 *
 * Runs once on load for what the server already rendered, and again on
 * whatever static/js/run_terminal.js appends live: refresh() takes the
 * subtree to reformat instead of always walking the whole document, so a
 * long-running panel does not re-touch lines it already fixed.
 *
 * Wrapped in a function of its own: these scripts share one global
 * namespace, and a name declared at the top level here could silently
 * overwrite a twin in another file. What other modules need is exported on
 * `window` explicitly.
 */

(function () {
  // What changes here is the timezone, never the shape. Each option set
  // reproduces the very text the server already rendered as a fallback:
  // "23:38:12" for a panel line (fixed width and always 24 hours, so a
  // column of them stays readable) and "Sep 28, 2026" for the Jobs table.
  // Without them a reader would watch the page rewrite itself into a
  // different style the moment the script runs.
  const CLOCK = { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" };
  const DATE = { year: "numeric", month: "short", day: "numeric" };

  const FORMATTERS = {
    clock: (date, locale) => date.toLocaleTimeString(locale, CLOCK),
    date: (date, locale) => date.toLocaleDateString(locale, DATE),
  };

  // The page's own language, not the browser's. The interface language is
  // negotiated server-side and written on <html lang>, and a browser set
  // to another language would otherwise print a day-first numeric date
  // under a column headed "Date" in English. Undefined when the attribute
  // is missing, which is what the formatters read as "use the browser
  // default".
  function pageLocale() {
    return document.documentElement.lang || undefined;
  }

  function refresh(root) {
    const locale = pageLocale();
    root.querySelectorAll("time[datetime][data-local]").forEach((el) => {
      const format = FORMATTERS[el.dataset.local];
      if (!format) return;
      const date = new Date(el.getAttribute("datetime"));
      if (Number.isNaN(date.getTime())) return;
      el.textContent = format(date, locale);
    });
  }

  refresh(document);

  window.VxLocalTime = { refresh };
})();

/*
 * The new-job form on the home page.
 *
 * The form works without this script: the file input takes several
 * files and every field posts its value. What only a script can add is here,
 * with no library:
 *   - dropping files on the Audio card, and the list of parts with their
 *     durations, reordered by dragging and removed one by one. The file input
 *     is rebuilt from that list, so the order posted is the order shown (the
 *     parts are joined in that order, ingest.concat);
 *   - the job name, prefilled from the first file until someone types one;
 *   - the `Default`/`Changed` tag of every Advanced field, the +/- steppers,
 *     the value next to each slider, and the cores the numbers will take.
 *
 * Every sentence comes from the hidden #vx-job-strings list, already
 * translated. "{count}", "{cores}" and "{total}" are replaced
 * here. Wrapped in an IIFE so nothing leaks into the page's shared scope (the
 * reason upload_dropzone.js's header gives).
 */
(function () {
  const form = document.getElementById("vx-new-job");
  if (!form) return;

  const input = document.getElementById("vx-job-files");
  const zone = form.querySelector(".vx-new-job__drop");
  const feedback = document.getElementById("vx-job-feedback");
  const partsBox = document.getElementById("vx-parts");
  const list = document.getElementById("vx-parts-list");
  const summary = document.getElementById("vx-parts-summary");
  const mergeField = document.getElementById("vx-merge-field");
  const template = document.getElementById("vx-part-template");
  const label = document.getElementById("vx-job-label");
  const strings = {};
  document.querySelectorAll("#vx-job-strings li").forEach((li) => {
    strings[li.dataset.key] = li.textContent;
  });

  let parts = [];
  let autoLabel = "";
  const durations = new Map();

  function clock(seconds) {
    const total = Math.round(seconds);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = String(total % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
  }

  function keyOf(file) {
    return `${file.name}|${file.size}|${file.lastModified}`;
  }

  function measure(file) {
    const key = keyOf(file);
    if (durations.has(key)) return;
    durations.set(key, null);
    const audio = new Audio();
    const url = URL.createObjectURL(file);
    audio.preload = "metadata";
    audio.addEventListener("loadedmetadata", () => {
      durations.set(key, audio.duration);
      URL.revokeObjectURL(url);
      render();
    });
    audio.src = url;
  }

  function syncInput() {
    const carrier = new DataTransfer();
    parts.forEach((file) => carrier.items.add(file));
    input.files = carrier.files;
  }

  function prefillLabel() {
    const stem = parts.length ? parts[0].name.replace(/\.[^.]+$/, "") : "";
    if (!label.value || label.value === autoLabel) label.value = stem;
    autoLabel = stem;
  }

  function summaryText() {
    const count = parts.length === 1 ? strings.part : (strings.parts || "").replace("{count}", parts.length);
    const known = parts.map((file) => durations.get(keyOf(file)));
    if (known.some((value) => value == null)) return `· ${count}`;
    // Tracks recorded together last as long as the longest of them.
    const together = form.querySelector('input[name="parts_mode"][value="tracks"]')?.checked;
    const total = together ? Math.max(...known) : known.reduce((a, b) => a + b, 0);
    return `· ${count} · ${clock(total)}`;
  }

  function render() {
    list.replaceChildren();
    parts.forEach((file, index) => {
      const row = template.content.firstElementChild.cloneNode(true);
      row.dataset.index = index;
      row.querySelector(".vx-part__name").textContent = file.name;
      const seconds = durations.get(keyOf(file));
      row.querySelector(".vx-part__duration").textContent = seconds == null ? "" : clock(seconds);
      row.querySelector(".vx-part__remove").addEventListener("click", () => remove(index));
      list.appendChild(row);
    });
    partsBox.hidden = parts.length === 0;
    mergeField.hidden = parts.length < 2;
    summary.textContent = summaryText();
  }

  form.querySelectorAll('input[name="parts_mode"]').forEach((radio) =>
    radio.addEventListener("change", render)
  );

  function update() {
    syncInput();
    prefillLabel();
    parts.forEach(measure);
    render();
  }

  function add(files) {
    const audio = Array.from(files).filter((file) => file.type.startsWith("audio/"));
    feedback.textContent = audio.length < files.length ? strings["rejected-type"] || "" : "";
    parts = parts.concat(audio);
    update();
  }

  function remove(index) {
    parts.splice(index, 1);
    update();
  }

  let dragged = null;
  list.addEventListener("dragstart", (event) => {
    dragged = Number(event.target.closest(".vx-part").dataset.index);
    event.dataTransfer.effectAllowed = "move";
  });
  list.addEventListener("dragover", (event) => event.preventDefault());
  list.addEventListener("drop", (event) => {
    event.preventDefault();
    const target = event.target.closest(".vx-part");
    if (dragged === null || !target) return;
    const [moved] = parts.splice(dragged, 1);
    parts.splice(Number(target.dataset.index), 0, moved);
    dragged = null;
    update();
  });

  input.addEventListener("change", () => {
    const picked = Array.from(input.files).filter((file) => !parts.includes(file));
    add(picked);
  });
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("vx-dropzone--over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("vx-dropzone--over"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("vx-dropzone--over");
    add(event.dataTransfer.files);
  });

  function isChanged(field) {
    const value = field.value;
    const base = field.dataset.default;
    if (field.type === "number" || field.type === "range") return Number(value) !== Number(base);
    return value !== base;
  }

  function refresh(field) {
    const tag = field.closest(".vx-field")?.querySelector("[data-tag]");
    if (tag) {
      const changed = isChanged(field);
      tag.textContent = changed ? strings.changed : strings.default;
      tag.classList.toggle("vx-tag--changed", changed);
    }
    const output = field.parentElement.querySelector(".vx-range__value");
    if (output) output.textContent = field.dataset.unit ? `${field.value} ${field.dataset.unit}` : field.value;
    showCost();
  }

  function showCost() {
    const cost = document.getElementById("vx-cost");
    if (!cost) return;
    const chunks = Number(form.elements.parallel_chunks.value) || 0;
    const cores = Number(form.elements.cores_per_chunk.value) || 0;
    const total = cost.dataset.total;
    const text = total ? strings["cores-of"].replace("{total}", total) : strings.cores;
    cost.textContent = (text || "").replace("{cores}", chunks * cores);
    cost.classList.toggle("vx-help--warning", Boolean(total) && chunks * cores > Number(total));
  }

  form.querySelectorAll("[data-default]").forEach((field) => {
    field.addEventListener("input", () => refresh(field));
    field.addEventListener("change", () => refresh(field));
  });
  form.querySelectorAll(".vx-stepper__step").forEach((button) => {
    button.addEventListener("click", () => {
      const field = button.parentElement.querySelector("input");
      const next = Number(field.value) + Number(button.dataset.step);
      field.value = Math.min(Number(field.max), Math.max(Number(field.min), next));
      refresh(field);
    });
  });
  showCost();
})();

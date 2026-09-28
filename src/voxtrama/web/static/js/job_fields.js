/*
 * The job fields outside the new-job form: the «Regenerate job»
 * panel draws the same Advanced fields (components/job_fields.html), and
 * its +/- steppers and slider values need the same small help
 * static/js/new_job.js gives them on the home page. The fields work
 * without it. This only keeps the value beside each slider current and
 * makes the two stepper buttons step.
 */
(function () {
  document.querySelectorAll("form.vx-job-options").forEach((form) => {
    form.querySelectorAll('input[type="range"]').forEach((field) => {
      const output = field.parentElement.querySelector(".vx-range__value");
      if (!output) return;
      field.addEventListener("input", () => {
        output.textContent = field.dataset.unit ? `${field.value} ${field.dataset.unit}` : field.value;
      });
    });
    form.querySelectorAll(".vx-stepper__step").forEach((button) => {
      button.addEventListener("click", () => {
        const field = button.parentElement.querySelector("input");
        const next = Number(field.value) + Number(button.dataset.step);
        field.value = Math.min(Number(field.max), Math.max(Number(field.min), next));
      });
    });
  });
})();

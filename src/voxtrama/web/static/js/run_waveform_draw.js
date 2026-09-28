/*
 * Drawing half of the player's waveform: given levels and a position,
 * paint the canvas. Knows nothing about audio, fetching or events
 * (run_waveform.js holds those, and calls in here), nor about how levels
 * become bar heights, which is run_waveform_shape.js.
 *
 * Split from that file for the project's 150-line file ceiling, which the two
 * subjects together crossed. No module system, because there is no build
 * chain: the pair shares one global, declared here and read
 * there, and the page loads this file first.
 */

window.vxWaveformDraw = (function () {
  // Thin rounded bars with air between them. Their heights come from
  // run_waveform_shape.js.
  const BAR_WIDTH_PX = 2;
  const BAR_STEP_PX = 5;

  function barCount(canvas) {
    return Math.max(40, Math.floor(canvas.clientWidth / BAR_STEP_PX));
  }

  // Without this the canvas keeps its default 300px backing store while
  // CSS stretches it, and everything drawn comes out blurred and clipped.
  function sizeToCss(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { ctx, width, height };
  }

  // The colours are the palette's (scss/abstracts/_tokens.scss): the part
  // already heard sweeps from primary to accent, blue to violet. The rest is "wave-rest". This file only paints them.
  function colorsOf(canvas) {
    const style = getComputedStyle(canvas);
    const read = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
    return {
      playedFrom: read("--vx-primary", "#1a7cfc"),
      playedTo: read("--vx-accent", "#7878fc"),
      rest: read("--vx-wave-rest", "rgba(120, 140, 190, 0.35)"),
      head: read("--vx-text", "#ffffff"),
    };
  }

  function strokeBars(ctx, heights, geometry, from, to) {
    const step = geometry.width / heights.length;
    const middle = geometry.height / 2;
    ctx.beginPath();
    for (let i = from; i < to; i++) {
      const half = Math.max(1, (heights[i] * (geometry.height - BAR_WIDTH_PX)) / 2);
      const x = i * step + step / 2;
      ctx.moveTo(x, middle - half);
      ctx.lineTo(x, middle + half);
    }
    ctx.stroke();
  }

  // The part already heard sweeps from primary to accent with a soft glow;
  // the rest is quiet.
  function drawBars(ctx, heights, geometry, colors) {
    const played = Math.round(geometry.progress * heights.length);
    const heard = ctx.createLinearGradient(0, 0, geometry.width, 0);
    heard.addColorStop(0, colors.playedFrom);
    heard.addColorStop(1, colors.playedTo);
    ctx.lineCap = "round";
    ctx.lineWidth = BAR_WIDTH_PX;
    ctx.strokeStyle = colors.rest;
    strokeBars(ctx, heights, geometry, played, heights.length);
    ctx.save();
    ctx.strokeStyle = heard;
    ctx.shadowColor = colors.playedFrom;
    ctx.shadowBlur = 6;
    strokeBars(ctx, heights, geometry, 0, played);
    ctx.restore();
  }

  // The vertical line with a dot on top: the bars
  // say how much has played, not precisely where the head sits.
  function drawPlayhead(ctx, geometry, color) {
    const x = Math.min(geometry.width - 1, Math.max(1, geometry.progress * geometry.width));
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, geometry.height);
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, 3, 3, 0, Math.PI * 2);
    ctx.fill();
  }

  function draw(canvas, levels, progress) {
    const { ctx, width, height } = sizeToCss(canvas);
    ctx.clearRect(0, 0, width, height);
    const geometry = { width, height, progress };
    const colors = colorsOf(canvas);
    drawBars(ctx, window.vxWaveformShape.heightsOf(levels, barCount(canvas)), geometry, colors);
    if (progress > 0) drawPlayhead(ctx, geometry, colors.head);
  }

  return { draw };
})();

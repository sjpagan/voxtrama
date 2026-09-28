/*
 * From the stored levels to the shape the player draws: one
 * height per bar, from the average and the loudest of its buckets, stretched
 * over the recording's own spread. Split from run_waveform_draw.js, which
 * only paints (150-line ceiling). The page loads this file first,
 * and the two share one global each (no build chain).
 */

window.vxWaveformShape = (function () {
  // Each column holds many stored buckets. Its outline is the loudest of
  // them, its body their average: the outline follows every syllable, the
  // body shows how loud the stretch is, as an editor's peak and RMS do.
  function fold(levels, columns) {
    const perColumn = levels.length / columns;
    const peak = new Float32Array(columns);
    const body = new Float32Array(columns);
    for (let column = 0; column < columns; column++) {
      const start = Math.floor(column * perColumn);
      const end = Math.min(levels.length, Math.max(start + 1, Math.floor((column + 1) * perColumn)));
      let sum = 0;
      let top = 0;
      for (let i = start; i < end; i++) {
        sum += levels[i];
        top = Math.max(top, levels[i]);
      }
      peak[column] = top;
      body[column] = end > start ? sum / (end - start) : 0;
    }
    return { peak, body };
  }

  // Averaged over seconds, speech is about equally loud everywhere, and every
  // bar came out near the same height: «always at full». So the shape
  // is stretched over its own spread: the quietest columns sit at the floor,
  // the loudest at the top, and what lies between keeps its order. The curve
  // keeps ordinary speech below the top. The
  // outline never runs far above the body, or a long recording turns into a
  // band at full height again.
  const FLOOR = 0.06;

  function percentile(sorted, fraction) {
    return sorted[Math.min(sorted.length - 1, Math.floor(fraction * (sorted.length - 1)))];
  }

  function windowOf(values, lowFraction, highFraction) {
    const sorted = Float32Array.from(values).sort();
    return [percentile(sorted, lowFraction), percentile(sorted, highFraction)];
  }

  function scaleWith(values, [low, high]) {
    if (high - low < 0.02) return values;
    return values.map((value) => {
      const spread = Math.min(1, Math.max(0, (value - low) / (high - low)));
      return FLOOR + (1 - FLOOR) * spread ** 1.8;
    });
  }

  function stretch(peak, body) {
    const range = windowOf(body, 0.05, 0.99);
    const scaledBody = scaleWith(body, range);
    const scaledPeak = scaleWith(peak, windowOf(peak, 0.05, 0.99)).map((value, i) =>
      Math.min(value, scaledBody[i] * 1.5)
    );
    return [scaledPeak, scaledBody];
  }

  // One height per bar: half the body, half the
  // outline, so neighbouring bars differ the way syllables do,
  // with the two ends tapering to a dot.
  const PEAK_SHARE = 0.5;
  const TAPER = 0.04;
  const HEADROOM = 0.9;

  function heightsOf(levels, bars) {
    const folded = fold(levels, bars);
    const [peak, body] = stretch(folded.peak, folded.body);
    const taper = Math.max(1, Math.round(bars * TAPER));
    return body.map((value, i) => {
      const edge = Math.min(1, (Math.min(i, bars - 1 - i) + 1) / taper);
      return ((1 - PEAK_SHARE) * value + PEAK_SHARE * peak[i]) * (0.25 + 0.75 * edge) * HEADROOM;
    });
  }

  return { heightsOf };
})();

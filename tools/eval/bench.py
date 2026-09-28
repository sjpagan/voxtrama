"""Benchmark executor for the diarization bench.

For every wav under --input and every requested backend: three runs (by
default), each timed and RAM-profiled, then scored against the reference
RTTM *when one exists*. Synthetic fixtures carry one. Real
unlabelled material does not, and the DER is `None` in that case, never
zero: a backend that saw no reference must never be reported as perfect.

When a reference is available, each file/backend pair runs twice:
"estimated" (the backend guesses the speaker count) and "oracle" (given
the true count from the RTTM). The gap between the two isolates counting
error from attribution error. A backend can be good at telling voices
apart and still bad at counting them, which is a different verdict than
confusing two voices it correctly counted.

Each backend lazily loads its model on first use (see `backends/*.py`),
and that load (reading weights off disk, building the network) can
dwarf the diarization work itself. Timing it as part of a run would
compare who loads fastest, not who diarizes best, so each backend gets
one untimed warm-up pass (on the first input file) before any measured
run: the discarded-warm-up approach, chosen over moving initialization
out of the `Backend` protocol, since that protocol has no separate
"load" step to move it to and every backend would need one added just
for this.

Each run's measurement is written as its own JSON file, and a readable
table goes to stdout.
"""

from __future__ import annotations

import argparse
import itertools
import json
import resource
import sys
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

from backends.base import Backend, Segment
from metrics import agreement, der, speaker_count_error, stability
from rttm import read_rttm

DEFAULT_RUNS = 3
DEFAULT_MAX_SPEAKERS = 4
DEFAULT_OUT_DIR = Path(__file__).parent / "results"

# 0.20 .. 0.90 in steps of 0.05, the grid `--sweep-threshold` tries by default.
DEFAULT_SWEEP_THRESHOLDS = [round(0.20 + 0.05 * i, 2) for i in range(15)]

# name -> "module:ClassName", imported lazily so picking one backend never
# pulls in the other's (heavy) dependencies.
BACKEND_REGISTRY: dict[str, str] = {
    "speechbrain-ecapa": "backends.speechbrain_ecapa:SpeechBrainEcapaBackend",
    "resemblyzer": "backends.resemblyzer:ResemblyzerBackend",
}


@dataclass
class RunResult:
    """One (file, backend, mode, run) measurement, also what gets written to JSON."""

    file: str
    backend: str
    mode: str  # "estimated" or "oracle", see module docstring
    run: int
    seconds_per_minute_audio: float
    peak_rss_kb: int
    der: float | None
    speaker_count_error: int | None


def load_backend(name: str) -> Backend:
    """Import a registered backend by name. Deferred so tests never need torch."""
    module_name, class_name = BACKEND_REGISTRY[name].split(":")
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)()


def wav_duration_seconds(wav_path: Path) -> float:
    """Audio duration read from the wav header alone, no decoding needed."""
    with wave.open(str(wav_path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def find_inputs(input_dir: Path) -> list[Path]:
    """Wav files under `input_dir`, each optionally paired with a same-stem .rttm."""
    return sorted(input_dir.glob("*.wav"))


def warm_up(backend: Backend, wav_path: Path, max_speakers: int) -> None:
    """Force `backend`'s lazy model load outside any timed run, discarding the result.

    See the module docstring for why this exists instead of timing the
    first run as-is.
    """
    backend.diarize(wav_path, max_speakers)


def run_once(
    backend: Backend, wav_path: Path, max_speakers: int, n_speakers: int | None = None
) -> tuple[list[Segment], float, int]:
    """One diarization pass: segments, seconds per minute of audio, peak RSS in KB.

    `n_speakers`, when given, runs the backend in oracle mode (see module
    docstring). Left `None`, the backend estimates the speaker count.

    `ru_maxrss` is a whole-process high-water mark (in KB on the Linux
    image this tool ships for). It only ever grows, so a later run in the
    same process reports at least as much as an earlier one. That is an
    accepted limitation of using `resource` instead of forking a fresh
    process per run: precise enough to compare two backends' order of
    magnitude, not precise enough for a per-call delta.
    """
    duration = wav_duration_seconds(wav_path)
    start = time.perf_counter()
    segments = backend.diarize(wav_path, max_speakers, n_speakers)
    elapsed = time.perf_counter() - start
    peak_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    seconds_per_minute = elapsed / (duration / 60) if duration > 0 else 0.0
    return segments, seconds_per_minute, peak_rss_kb


def _bench_mode(
    backend: Backend,
    wav_path: Path,
    runs: int,
    max_speakers: int,
    mode: str,
    n_speakers: int | None,
    reference: list[Segment] | None,
) -> tuple[list[RunResult], float, list[Segment]]:
    """Run `backend` on `wav_path` `runs` times, in a single mode (estimated or oracle)."""
    hypotheses = []
    results = []
    for run in range(1, runs + 1):
        segments, seconds_per_minute, peak_rss_kb = run_once(
            backend, wav_path, max_speakers, n_speakers
        )
        hypotheses.append(segments)
        results.append(
            RunResult(
                file=wav_path.name,
                backend=backend.name,
                mode=mode,
                run=run,
                seconds_per_minute_audio=seconds_per_minute,
                peak_rss_kb=peak_rss_kb,
                der=der(reference, segments) if reference is not None else None,
                speaker_count_error=(
                    speaker_count_error(reference, segments) if reference is not None else None
                ),
            )
        )
    return results, stability(hypotheses), hypotheses[-1]


def bench_file(
    backend: Backend, wav_path: Path, runs: int, max_speakers: int
) -> tuple[list[RunResult], dict[str, float], list[Segment]]:
    """Run `backend` on `wav_path`: "estimated" mode always, "oracle" mode when an RTTM exists.

    DER and speaker-count error are `None` without a reference RTTM next
    to the wav (oracle mode is then skipped entirely: there is no true
    count to give it). Returns the per-run results, the run-to-run
    stability keyed by mode, and the estimated mode's last-run segments
    (used for cross-backend agreement, since that mode reflects what the
    backend does unassisted).
    """
    reference_path = wav_path.with_suffix(".rttm")
    reference = read_rttm(reference_path) if reference_path.exists() else None

    all_results, estimated_stability, estimated_segments = _bench_mode(
        backend, wav_path, runs, max_speakers, "estimated", None, reference
    )
    stabilities = {"estimated": estimated_stability}

    if reference is not None:
        n_speakers = len({s.speaker for s in reference})
        oracle_results, oracle_stability, _ = _bench_mode(
            backend, wav_path, runs, max_speakers, "oracle", n_speakers, reference
        )
        all_results = all_results + oracle_results
        stabilities["oracle"] = oracle_stability

    return all_results, stabilities, estimated_segments


def write_results(results: list[RunResult], out_dir: Path) -> None:
    """One JSON file per run, named so re-running never silently overwrites."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        name = f"{Path(result.file).stem}__{result.backend}__{result.mode}__run{result.run}.json"
        (out_dir / name).write_text(json.dumps(asdict(result), indent=2))


def run_bench(
    input_dir: Path, backends: list[Backend], runs: int, max_speakers: int, out_dir: Path
) -> list[RunResult]:
    """Bench every backend against every wav in `input_dir`. Returns all run results."""
    all_results: list[RunResult] = []
    stabilities: dict[tuple[str, str, str], float] = {}
    agreements: dict[tuple[str, str, str], float] = {}
    inputs = find_inputs(input_dir)
    if inputs:
        for backend in backends:
            warm_up(backend, inputs[0], max_speakers)
    for wav_path in inputs:
        final_segments: dict[str, list[Segment]] = {}
        for backend in backends:
            results, mode_stabilities, estimated_segments = bench_file(
                backend, wav_path, runs, max_speakers
            )
            all_results.extend(results)
            for mode, value in mode_stabilities.items():
                stabilities[(wav_path.name, backend.name, mode)] = value
            final_segments[backend.name] = estimated_segments
        for name_a, name_b in itertools.combinations(sorted(final_segments), 2):
            key = (wav_path.name, name_a, name_b)
            agreements[key] = agreement(final_segments[name_a], final_segments[name_b])
    write_results(all_results, out_dir)
    print_table(all_results, stabilities, agreements)
    return all_results


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def print_table(
    results: list[RunResult],
    stabilities: dict[tuple[str, str, str], float],
    agreements: dict[tuple[str, str, str], float],
) -> None:
    """A readable summary on stdout: one line per (file, backend, mode), then agreement."""
    header = (
        f"{'file':<24} {'backend':<20} {'mode':<10} {'s/min audio':>12} {'peak RSS MB':>12} "
        f"{'DER':>8} {'spk err':>8} {'stability':>10}"
    )
    print(header)
    print("-" * len(header))
    grouped: dict[tuple[str, str, str], list[RunResult]] = {}
    for result in results:
        grouped.setdefault((result.file, result.backend, result.mode), []).append(result)
    for (file, backend, mode), runs in grouped.items():
        _print_row(file, backend, mode, runs, stabilities.get((file, backend, mode)))
    if agreements:
        print()
        print(f"{'file':<24} {'backend a':<18} {'backend b':<18} {'agreement':>10}")
        for (file, name_a, name_b), value in agreements.items():
            print(f"{file:<24} {name_a:<18} {name_b:<18} {value:>10.3f}")


def _print_row(
    file: str, backend: str, mode: str, runs: list[RunResult], stability_value: float | None
) -> None:
    avg_speed = sum(r.seconds_per_minute_audio for r in runs) / len(runs)
    avg_rss_mb = sum(r.peak_rss_kb for r in runs) / len(runs) / 1024
    ders = [r.der for r in runs if r.der is not None]
    avg_der = sum(ders) / len(ders) if ders else None
    spk_errors = [r.speaker_count_error for r in runs if r.speaker_count_error is not None]
    avg_spk_error = sum(spk_errors) / len(spk_errors) if spk_errors else None
    print(
        f"{file:<24} {backend:<20} {mode:<10} {avg_speed:>12.2f} {avg_rss_mb:>12.1f} "
        f"{_fmt(avg_der):>8} {_fmt(avg_spk_error):>8} {_fmt(stability_value):>10}"
    )


@dataclass
class SweepResult:
    """One (backend, threshold) point of the `DISTANCE_THRESHOLD` sweep.

    DER is averaged separately for multi-speaker and mono-speaker cases:
    a mono-speaker reference gives the clustering exactly one true cluster,
    so its DER swings on whether the backend over-splits it, a different
    failure mode than mis-attributing speech between two real speakers.
    Pooling the two into one average would let easy mono cases dilute a
    backend's real multi-speaker error (see `tools/eval/README.md`).
    """

    backend: str
    threshold: float
    n_multi: int
    n_mono: int
    avg_speaker_count_error: float
    avg_der_multi: float | None
    avg_der_mono: float | None


def sweep_threshold(
    input_dir: Path, backends: list[Backend], thresholds: list[float], max_speakers: int
) -> list[SweepResult]:
    """Try each of `thresholds` as each backend's own `DISTANCE_THRESHOLD` in turn.

    Only cases with a reference RTTM are usable (there is nothing to
    tune against otherwise). Each case runs once per threshold, not
    `--runs` times: tuning a threshold needs a coarse signal across many
    cases, not per-run stability on any single one, and this already
    multiplies backends x cases x thresholds.

    `DISTANCE_THRESHOLD` is defined per backend module, not shared (see
    `backends/_windowing.py`'s docstring for why): this patches each
    backend's own module attribute in place for the duration of the
    sweep and restores it afterwards, so the sweep leaves no side effect
    on the modules it borrows.
    """
    cases = [
        (wav_path, read_rttm(wav_path.with_suffix(".rttm")))
        for wav_path in find_inputs(input_dir)
        if wav_path.with_suffix(".rttm").exists()
    ]
    inputs = find_inputs(input_dir)
    if inputs:
        for backend in backends:
            warm_up(backend, inputs[0], max_speakers)

    modules = {backend.name: sys.modules[type(backend).__module__] for backend in backends}
    original_thresholds = {name: module.DISTANCE_THRESHOLD for name, module in modules.items()}
    results: list[SweepResult] = []
    try:
        for threshold in thresholds:
            for backend in backends:
                modules[backend.name].DISTANCE_THRESHOLD = threshold
            for backend in backends:
                spk_errors = []
                der_multi = []
                der_mono = []
                for wav_path, reference in cases:
                    segments = backend.diarize(wav_path, max_speakers)
                    spk_errors.append(speaker_count_error(reference, segments))
                    is_multi = len({s.speaker for s in reference}) > 1
                    (der_multi if is_multi else der_mono).append(der(reference, segments))
                results.append(
                    SweepResult(
                        backend=backend.name,
                        threshold=threshold,
                        n_multi=len(der_multi),
                        n_mono=len(der_mono),
                        avg_speaker_count_error=sum(spk_errors) / len(spk_errors),
                        avg_der_multi=(sum(der_multi) / len(der_multi) if der_multi else None),
                        avg_der_mono=sum(der_mono) / len(der_mono) if der_mono else None,
                    )
                )
    finally:
        for name, module in modules.items():
            module.DISTANCE_THRESHOLD = original_thresholds[name]
    print_sweep_table(results)
    return results


def print_sweep_table(results: list[SweepResult]) -> None:
    """Threshold sweep summary: one line per (backend, threshold), DER split by case type."""
    header = (
        f"{'backend':<20} {'threshold':>9} {'spk err':>8} "
        f"{'DER multi':>10} {'n':>3} {'DER mono':>9} {'n':>3}"
    )
    print(header)
    print("-" * len(header))
    for result in results:
        print(
            f"{result.backend:<20} {result.threshold:>9.2f} "
            f"{result.avg_speaker_count_error:>8.3f} "
            f"{_fmt(result.avg_der_multi):>10} {result.n_multi:>3} "
            f"{_fmt(result.avg_der_mono):>9} {result.n_mono:>3}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="directory of .wav files")
    parser.add_argument(
        "--backends",
        nargs="+",
        required=True,
        choices=sorted(BACKEND_REGISTRY),
        help="backends to run",
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--max-speakers", type=int, default=DEFAULT_MAX_SPEAKERS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--sweep-threshold",
        action="store_true",
        help="tune backends._windowing.DISTANCE_THRESHOLD instead of benching; "
        "prints speaker-count error and estimated-mode DER per threshold, "
        "does not write result JSON files",
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=None,
        help=f"threshold grid for --sweep-threshold (default: {DEFAULT_SWEEP_THRESHOLDS})",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    backends = [load_backend(name) for name in args.backends]
    if args.sweep_threshold:
        thresholds = args.thresholds or DEFAULT_SWEEP_THRESHOLDS
        sweep_threshold(args.input, backends, thresholds, args.max_speakers)
        return
    run_bench(args.input, backends, args.runs, args.max_speakers, args.out)


if __name__ == "__main__":
    main()

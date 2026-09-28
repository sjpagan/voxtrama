# Diarization backend bench

Measures two candidate diarization backends (SpeechBrain ECAPA-TDNN and
Resemblyzer) so the choice between them is made from numbers produced
here, not from someone else's benchmark. This tool picks no winner: it
only produces the measurements the decision needs.

## Build

```sh
docker build -t voxtrama-eval tools/eval
```

Built with **no `HF_TOKEN`** and **no Hugging Face cache mount**, on
purpose: `speechbrain/spkrec-ecapa-voxceleb` is a public model, and the
bench must be reproducible by anyone who clones the repo, not only by
whoever already has a Hugging Face account configured. If a future
backend needs a gated model, that model is disqualified for this bench,
not the constraint.

## Run

```sh
docker run --rm \
  -v "$PWD/tools/eval/fixtures":/data:ro \
  -v "$PWD/tools/eval/results":/app/results \
  -v ~/Voxtrama/eval/hfcache:/root/.cache \
  voxtrama-eval --input /data --backends speechbrain-ecapa resemblyzer
```

`--backends` is **required**. There is no default, on purpose: a run
that silently benched "whatever backends happen to be registered" would
make the reported numbers depend on the codebase's history, not on the
command that produced them.

Mounting a host directory at `/root/.cache` (Hugging Face's default cache
location) keeps `speechbrain/spkrec-ecapa-voxceleb`'s weights on disk
across container runs instead of re-downloading them every time; `~/Voxtrama/eval/hfcache`
above is one convenient host path for it, not a hardcoded requirement: any
writable directory works.

CLI flags:

- `--input <dir>`: directory of `.wav` files. A file paired with a
  same-stem `.rttm` (synthetic fixtures) is scored against it;
  a file without one is timed and profiled but never scored.
- `--backends <name...>`: one or more of `speechbrain-ecapa`,
  `resemblyzer`. Required.
- `--runs`: repetitions per (file, backend) pair, default 3.
- `--max-speakers`: clustering cap passed to both backends, default 4.
- `--out`: where the per-run JSON files go, default `tools/eval/results`.
- `--sweep-threshold`: instead of benching, tunes each backend's own
  `DISTANCE_THRESHOLD` (see below).
- `--thresholds <value...>`: threshold grid for `--sweep-threshold`,
  default `0.20` to `0.90` in steps of `0.05`.

## Reading the output

Each `(file, backend, mode, run)` quadruple gets its own JSON file under
`--out`, plus a summary table on stdout with, per file, backend and mode:

- `mode`: `estimated` (the backend guesses the speaker count, capped at
  `--max-speakers`) or `oracle` (given the true count from the reference
  RTTM). Oracle mode only runs when a reference exists, and isolates
  counting error from attribution error: a high DER in `estimated` next
  to a low one in `oracle` means the backend can tell voices apart but
  miscounts them, a different verdict than confusing two voices it
  counted correctly;
- `s/min audio`: wall-clock seconds spent per minute of input audio;
- `peak RSS MB`: the process's peak resident memory at that point (a
  whole-process high-water mark, so later runs in the same process never
  report less than earlier ones; see `bench.run_once`'s docstring);
- `DER`: Diarization Error Rate against the reference RTTM, **only when
  one exists**; otherwise `n/a`. **A missing reference is never scored as
  zero error**: that would silently claim perfection nothing supports;
- `spk err`: absolute difference between reference and hypothesis
  speaker counts, same "only with a reference" rule as DER. In `oracle`
  mode this should sit at zero by construction; a non-zero value there
  would point at a bug in the clustering cap, not at the backend;
- `stability`: mean pairwise DER between the backend's own repeated runs
  on the same file, computed separately per mode; zero means fully
  deterministic output.

A second table, printed when at least two backends ran on the same file,
reports pairwise **agreement** between backends' outputs (symmetrised
DER, see `metrics.agreement`), useful even without a reference, since it
shows where the two candidates disagree.

**Averaging DER across files mixes two different tasks if any file is
mono-speaker.** With a single true speaker, oracle-mode DER is trivially
0 (there is only one cluster to assign), and the number is not
comparable to a multi-speaker file's DER. Four of this bench's own
fixtures (`calibration-*`) are mono-speaker; pooling them into a DER
average with the eleven multi-speaker ones understates the real error.
Mono-speaker cases stay useful for `spk err`: a backend counting three
speakers in one voice is a real, reportable failure. Just not for DER
averages. `--sweep-threshold`'s table (below) keeps the two separate for
this reason; any other averaging done outside this tool should do the same.

## Tuning `DISTANCE_THRESHOLD`

```sh
docker run --rm \
  -v "$PWD/tools/eval/fixtures":/data:ro \
  -v ~/Voxtrama/eval/hfcache:/root/.cache \
  voxtrama-eval --input /data --backends speechbrain-ecapa resemblyzer --sweep-threshold
```

Runs `estimated`-mode diarization once per (backend, case, threshold),
without writing result JSON files, and prints the average speaker-count
error and DER for each threshold, with DER split into multi-speaker and
mono-speaker cases, per the caveat above. Each backend's
`DISTANCE_THRESHOLD` is tuned independently: the best value found for one
backend need not, and in this bench's own numbers does not, match the
other's. On this bench's 15-case material, the sweep found 0.40 best for
resemblyzer (multi-speaker DER 0.195) and 0.80 best for speechbrain-ecapa
(multi-speaker DER 0.183), the values each backend module now ships
with (see `backends/resemblyzer.py` and `backends/speechbrain_ecapa.py`).
Re-tune on different material before trusting these numbers elsewhere.

## Tests

```sh
pytest tools/eval/test_metrics.py
```

Runs against a fake backend and hand-built segments only: no model
download, no audio decoding, no Docker image required.

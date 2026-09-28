"""Falls back to this machine's own tuning proposal for cpu_threads/num_workers
when Settings does not name them.

Settings.cores_per_chunk/.parallel_chunks are None until the guided setup (or
a VOXTRAMA_* override) writes them (see the comment in config.settings).
transcribe() still has to hand faster-whisper a number in that case, and
falling back to WhisperModel's defaults (cpu_threads=0, meaning
"whatever CTranslate2 picks", num_workers=1) would be the "a
twenty-core server and a four-core laptop behave the same" defect. The
fallback here is instead the same proposal step 2 of the guided setup
shows: this machine's own reading (diagnostics.machine), the tuning
file it selects (tuning.selector) and the core budget that caps its numbers
at what the machine has (tuning.core_budget.plan_for), not a
second, independent guess.

setup.step_defaults.resolve_step_defaults already does this same
computation, but also resolves hardware_profile and reaches into
setup.profile_offers for it. Transcription needs none of that, and
importing that module would pull setup's offer-building machinery into a
package that only wants three numbers. Calling plan_for directly here
makes transcription depend on tuning, not setup: core_budget and
chunk_tuning live under tuning/, which nothing routes back through
engine, and diagnostics/__init__.py does not re-export readiness
(which reaches into transcription.asr for weights_for) since nothing
imports it from there. With both legs of the knot untied, the three
imports below sit at module level like any other, and
tests/test_import_isolation.py is the gate that keeps it that way.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.diagnostics import machine as machine_module
from voxtrama.tuning.core_budget import plan_for
from voxtrama.tuning.selector import select_tuning


def resolve_engine_resources(
    data_dir: Path, cores_per_chunk: int | None, parallel_chunks: int | None
) -> tuple[int, int]:
    """(cpu_threads, num_workers) for WhisperModel: `cores_per_chunk` and
    `parallel_chunks` as given, or this machine's own tuning proposal for
    whichever of the two is None.

    cores_per_chunk becomes cpu_threads: how many cores one WhisperModel
    instance may use. parallel_chunks becomes num_workers: how many such
    instances faster-whisper may run at once. ChunkTuning already
    keeps the two knobs apart for this reason.
    """
    machine = machine_module.read_machine(data_dir)
    tuning = select_tuning(machine)
    plan = plan_for(machine, tuning, cores_per_chunk, parallel_chunks)
    return plan.cores_per_chunk, plan.parallel_chunks

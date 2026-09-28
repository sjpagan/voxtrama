"""How many cores a chunk plan may ask for.

The tuning file's numbers stay a proposal: a person may run more
parallel chunks than it recommends and pay in swap and slowness, because
beyond that limit there is still an outcome, if a worse one.

Cores that do not exist are the other kind of limit. Asking for 32 of
them on a 20-core machine asks for something that is not there, and the
answer cannot be a warning because there is nothing on the far side to
warn about. The same line is drawn for num_ctx above a model's own
maximum (setup.context_cap).
"""

from __future__ import annotations

from voxtrama.diagnostics.machine import MachineReport
from voxtrama.tuning.chunk_tuning import ChunkPlan
from voxtrama.tuning.definition import TuningFile


def available_cores(machine: MachineReport) -> int | None:
    """This machine's own core count for chunk planning.

    Performance cores where the platform separates them, else the
    total: an efficiency core taken for a transcription chunk slows that
    chunk rather than adding to it, as plan_for's docstring says below.
    Pulled out so engine.resource_choice can ask the same question
    plan_for already asks, instead of a second copy of this one-line
    expression that could silently drift from it.
    """
    return machine.performance_cores or machine.cpu_count


def capped_cores(asked: int | None, proposed: int, available: int | None) -> int:
    """`asked` if it is given, never below 1 and never above `available`.

    Unknown hardware caps nothing: a ceiling invented from no reading
    would be exactly the kind of guess about hardware the project never
    makes.
    """
    if asked is None:
        return proposed
    if available is None:
        return max(1, asked)
    return max(1, min(asked, available))


def plan_for(
    machine: MachineReport,
    tuning: TuningFile,
    cores_per_chunk: int | None,
    parallel_chunks: int | None,
) -> ChunkPlan:
    """The plan a request asks for, capped at the cores the machine has.

    Performance cores where the platform separates them: an
    efficiency core taken for a transcription chunk slows that chunk
    rather than adding to it.
    """
    available = available_cores(machine)
    return ChunkPlan(
        cores_per_chunk=capped_cores(cores_per_chunk, tuning.chunking.cores_per_chunk, available),
        parallel_chunks=capped_cores(parallel_chunks, tuning.chunking.parallel_chunks, available),
        recommended_parallel_chunks=tuning.chunking.parallel_chunks,
        available_cores=available,
    )

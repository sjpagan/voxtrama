"""GET /runs/{id}/view's failure-only data: the banner, and what the run produced.

Split out of api.routes.run_page to keep that route's own file under the
project's file size limit, and because this whole module only runs for a Run in
`failed` or `interrupted` state, and every other state calls neither function
below.

`_memory_facts` reads only what the failure banner names (Settings.
cores_per_chunk/parallel_chunks, diagnostics.machine.read_machine and
tuning.selector.select_tuning), deliberately not
transcription.resources.resolve_engine_resources or
setup.core_budget.plan_for. The one difference this leaves on the table:
this "used" figure falls back to the tuning file's own default the same
way the engine does when Settings has not set one, but skips
core_budget's own machine-capping step on top of it. A run that Settings
never configured and whose tuning file recommends more parallel chunks
than this machine has would show the uncapped recommendation here, not
the capped number the engine ran with. Worth reconciling inside those
modules, not guessed at from outside them.
"""

from __future__ import annotations

from dataclasses import replace

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.api.routes.run_transcript_lookup import transcript_for
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models.run import Run
from voxtrama.db.models.transcript import Segment
from voxtrama.diagnostics.machine import read_machine
from voxtrama.manifest.output import RunOutput, read_run_output
from voxtrama.rendering import (
    FailureBanner,
    MemoryFacts,
    ProducedView,
    failure_banner_view,
    produced_view,
)
from voxtrama.rendering.job_turns import job_turns
from voxtrama.rendering.run_produced import PREVIEW_SEGMENT_COUNT
from voxtrama.rendering.run_transcript import transcript_rows
from voxtrama.tuning.selector import select_tuning

GIB = 1024**3
MODEL_SETTINGS_PATH = "/setup/model-ready"
PROCESSING_SETTINGS_PATH = "/setup/local-processing"
_FAILURE_STATES = frozenset({"failed", "interrupted"})


def _memory_facts(settings: Settings) -> MemoryFacts:
    """What this run was configured with, and what this machine's tuning file
    recommends (see the module docstring for what this deliberately does not reach into)."""
    machine = read_machine(settings.data_dir)
    tuning = select_tuning(machine)
    notice = None
    if machine.total_memory_bytes is not None:
        # `parallel_chunks` is always passed, not only where a file's own
        # warning uses it: tuning/apple-silicon.yaml's own sentence names
        # it ("running {parallel_chunks} chunks in parallel..."), tuning/
        # generic.yaml's does not, and str.format() ignores an unused kwarg.
        # Passing it unconditionally beats guessing which shape a given
        # tuning file's own MemoryThreshold.warning was written to.
        notice = tuning.chunking.memory.warning.format(
            recommended_gib=tuning.chunking.memory.recommended_gib,
            actual_gib=round(machine.total_memory_bytes / GIB),
            parallel_chunks=tuning.chunking.parallel_chunks,
        )
    return MemoryFacts(
        used_parallel_chunks=settings.parallel_chunks or tuning.chunking.parallel_chunks,
        used_cores_per_chunk=settings.cores_per_chunk or tuning.chunking.cores_per_chunk,
        recommended_parallel_chunks=tuning.chunking.parallel_chunks,
        recommended_cores_per_chunk=tuning.chunking.cores_per_chunk,
        notice=notice,
    )


def failure_view_for(run: Run, settings: Settings) -> FailureBanner | None:
    """The banner for `run`, or None for any state besides `failed`/`interrupted`.

    The design has no banner for anything else, and
    `cancelled` is a person's own choice, not a failure.
    """
    if str(run.state) not in _FAILURE_STATES or run.error_code is None:
        return None
    return failure_banner_view(
        run.error_code,
        run.error,
        _memory_facts(settings),
        model_settings_href=MODEL_SETTINGS_PATH,
        processing_settings_href=PROCESSING_SETTINGS_PATH,
        retry_href=f"/runs/{run.id}/retry",
    )


def _output(settings: Settings, run_id: str) -> RunOutput | None:
    """The job's output.json, None when missing or unreadable: a broken file
    must not take the failure page down with it."""
    try:
        return read_run_output(get_paths(settings.data_dir).runs_dir, run_id)
    except ValidationError:
        return None


def produced_view_for(session: Session, run_id: str, settings: Settings) -> ProducedView | None:
    """What `run_id` produced worth showing even though it failed later: its Transcript, if
    any, its own or the one it reused."""
    transcript = transcript_for(session, run_id, _output(settings, run_id))
    if transcript is None:
        return None
    segments = session.scalars(
        select(Segment).where(Segment.transcript_id == transcript.id).order_by(Segment.start)
    ).all()
    view = produced_view(list(segments), view_transcript_href="#vx-run-produced")
    if view is None:
        return None
    preview = list(segments)[:PREVIEW_SEGMENT_COUNT]
    return replace(
        view, turns=job_turns(tuple(transcript_rows(preview)), settings.pause_merge_seconds)
    )

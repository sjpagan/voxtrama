"""GET /runs/{id}/view's own succeeded-run data: the transcript and the
extracted output.

Split out of api.routes.run_page for the same reason api.routes.
run_page_failure is: this whole module runs for a Run in `succeeded`
state only, and every other state calls neither function below.
run_page_failure.py itself is "what a failed run produced",
untouched here, a different state and a different page section.

Reads the whole Transcript (rendering.run_produced's own preview stops at
PREVIEW_SEGMENT_COUNT. A concluded run's own page is where the rest
lives) and, when they exist yet, manifest.json and
output.json. Both are written by manifest.writer/manifest.output as a run
goes, so a run that just turned `succeeded` could in theory still be
missing one for a moment. That is treated like a run's own log tail
(logs.tail.tail_lines): not fatal to the page.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.api.routes.run_regenerate import regenerate_form
from voxtrama.api.routes.run_transcript_lookup import transcript_for
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models.run import Run
from voxtrama.db.models.transcript import Segment
from voxtrama.db.segment_speaker import speaker_choices
from voxtrama.db.speaker_naming import recording_speakers
from voxtrama.engine.catalog import WorkflowNotFoundError, load_named_workflow
from voxtrama.manifest.edits import apply_edits, read_edits
from voxtrama.manifest.output import RunOutput, read_run_output
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.rendering import ResultView, result_view
from voxtrama.rendering.run_output import TEXT_FIELDS
from voxtrama.rendering.run_result import ResultSource
from voxtrama.rendering.workflow_produces import default_title
from voxtrama.workflow.errors import WorkflowError

logger = logging.getLogger(__name__)

# The same bounds Settings and RunChoices put on pause_merge_seconds.
PAUSE_MIN, PAUSE_MAX = 0.1, 10.0


@dataclass(frozen=True)
class ViewRequest:
    """What the address asks of the view: `?tab=` and `?merge=`."""

    tab: str | None = None
    merge: float | None = None


def _segments(session: Session, run_id: str, output: RunOutput | None) -> list[Segment]:
    """Every Segment of the job's Transcript, in start order: the whole
    transcript, not run_produced.produced_view's own eight-line preview.
    A reused transcript counts (api.routes.run_transcript_lookup).
    """
    transcript = transcript_for(session, run_id, output)
    if transcript is None:
        return []
    return list(
        session.scalars(
            select(Segment).where(Segment.transcript_id == transcript.id).order_by(Segment.start)
        )
    )


def manifest_of(runs_dir: Path, run_id: str) -> Manifest | None:
    """The run's own manifest.json, or None when it is missing or unreadable.

    Never raises: a broken manifest must not take the whole page down.
    manifest.writer.write_run_manifest's own docstring makes the same
    choice on the write side, for the same run.
    """
    path = manifest_path(runs_dir, run_id)
    if not path.is_file():
        return None
    try:
        return Manifest.model_validate_json(path.read_bytes())
    except ValidationError:
        logger.warning("run %s has a manifest.json that fails validation", run_id)
        return None


def _output(runs_dir: Path, run_id: str) -> RunOutput | None:
    """The run's own output.json, tolerating the same two failure shapes as
    `manifest_of` above rather than the 500 api.routes.runs raises for its
    own JSON resource, since this is an HTML page, not that API."""
    try:
        output = read_run_output(runs_dir, run_id)
    except ValidationError:
        logger.warning("run %s has an output.json that fails validation", run_id)
        return None
    # With a person's corrections laid over it; output.json itself stays.
    return apply_edits(output, read_edits(runs_dir, run_id), TEXT_FIELDS) if output else None


def workflow_title(name: str) -> str:
    try:
        return load_named_workflow(name).title or default_title(name)
    except (WorkflowNotFoundError, WorkflowError):
        return default_title(name)


def _pause(requested: float | None, manifest: Manifest | None, settings: Settings) -> float:
    """The address's «Merge pauses under» first (the slider), then the job's own, then Settings."""
    if requested is not None and PAUSE_MIN <= requested <= PAUSE_MAX:
        return requested
    chosen = manifest.choices.pause_merge_seconds if manifest is not None else None
    return chosen or settings.pause_merge_seconds


def result_view_for(
    session: Session, settings: Settings, run: Run, view: ViewRequest | None = None
) -> ResultView | None:
    """None for any state besides `succeeded`. Every other state has its
    own section (the live chain, or the failure banner)."""
    if str(run.state) != "succeeded":
        return None
    view = view or ViewRequest()
    runs_dir = get_paths(settings.data_dir).runs_dir
    recording_id = run.recording_id
    manifest = manifest_of(runs_dir, run.id)
    output = _output(runs_dir, run.id)
    source = ResultSource(
        segments=_segments(session, run.id, output),
        manifest=manifest,
        output=output,
        workflow_title=workflow_title(run.workflow_name),
        default_detail=settings.summary_detail,
        named=recording_speakers(session, recording_id) if recording_id else None,
    )
    return result_view(
        source,
        audio_src=f"/recordings/{recording_id}/audio" if recording_id else None,
        recording_id=recording_id,
        pause=_pause(view.merge, manifest, settings),
        tab=view.tab,
        regenerate=regenerate_form(run, manifest, settings) if recording_id else None,
        people=tuple(speaker_choices(session, recording_id)) if recording_id else (),
    )

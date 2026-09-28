"""What one step of a run hands to the next.

Separate from the steps themselves so that adding a built-in does not mean
editing the thing every built-in depends on.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep
from voxtrama.db.models.transcript import Transcript
from voxtrama.ingest.resample import resampled_sibling
from voxtrama.manifest.evidence import ClaimCount
from voxtrama.providers.base import ModelProvenance
from voxtrama.workflow.choices import RunChoices


@dataclass
class ExecutionContext:
    """What a step reads from the steps before it, and writes for those after.

    Passed by reference and mutated: the transcription step produces a
    Transcript that diarisation then labels, and copying it between steps
    would mean two objects that can disagree about the same run.
    """

    session: Session
    run: Run
    recording: Recording | None = None
    transcript: Transcript | None = None
    # Filled by the engine before the first step, so a step never has to
    # rebuild the same paths from settings.
    audio_path: Path | None = None
    # One entry per step that has already run, keyed by the step's id
    # instead of a flat namespace: two steps naming the same field (both
    # writing "transcript_id", say) must not clobber each other, and a
    # condition reading steps.<id>.<key> needs the id to disambiguate
    # anyway.
    produced: dict[str, dict[str, Any]] = field(default_factory=dict)
    # The same RunStep objects record_planned_steps returned, keyed by step
    # id, not a copy of their state. engine.progress mutates row.state in
    # place as a run goes (mark_running, mark_succeeded, ...), and a
    # condition reading steps.<id>.state must see that mutation
    # without anything propagating it into a second place.
    step_rows: dict[str, RunStep] = field(default_factory=dict)
    # Per step_id, not cumulative: a retry must overwrite its step's entry
    # instead of adding to it. engine.preparation fills this in, from
    # engine.anchoring's count, before EvidenceNotAnchored can rise.
    evidence: dict[str, ClaimCount] = field(default_factory=dict)
    # Per step_id, for the same reason as evidence above: a retry overwrites
    # its step's provenance instead of piling a second one on top. The run
    # manifest reads this to write steps[].
    models: dict[str, ModelProvenance] = field(default_factory=dict)
    # Which step is running right now, set by engine.preparation before it
    # calls the step's function. A StepFunction receives only this context,
    # never its own Step, so a step that has something to file under its
    # id (a generative one recording where its model ran) would
    # otherwise have to read it out of the logging context.
    # That context exists to be observed, not to carry domain data: a step
    # run outside it fails with a bare KeyError instead of saying what is
    # missing, and every later skill would copy the coupling.
    current_step_id: str | None = None
    # How a step reports where it has got to, inside itself: a label, the
    # unit that position is counted in, how far in, and the total when it is
    # known. One channel, not one per kind of activity a step might have (a
    # download, a transcription): two fields would force a reader to decide
    # which one wins. The engine supplies it. A step with nothing to report
    # ignores it. Core does not know who renders this: it publishes, it does
    # not display.
    report_activity: ActivityReporter | None = None
    # Never None: a run that chose nothing gets RunChoices(),
    # every field None or empty. Same reasoning as `produced` and
    # `evidence` above defaulting to `{}` instead of None, so a built-in
    # step never has to write `if ctx.choices is None` before reading a
    # field of it.
    choices: RunChoices = field(default_factory=RunChoices)
    # Step id -> who declared it `local_only` above its skill ("step
    # s", "workflow w"), filled by engine.preparation from the workflow.
    kept_local: dict[str, str] = field(default_factory=dict)
    # Step id -> the instructions a custom workflow wrote for that step in
    # place of its skill's prompt (workflow.instructions), from engine.preparation.
    instructions: dict[str, str] = field(default_factory=dict)


# A step returns what it produced instead of writing it into the context:
# the engine validates that value against the step's Skill before anything
# downstream can see it (engine.validation), so a built-in never publishes
# something its own output_schema forbids.
StepFunction = Callable[[ExecutionContext], dict[str, Any]]

# (label, unit, done, total when known). unit is "bytes" or "seconds"
ActivityReporter = Callable[[str, str, float, float | None], None]


class StepPreconditionError(RuntimeError):
    """A step ran without what an earlier step was supposed to give it."""


def audio_path_for(recording: Recording) -> Path:
    """Where on disk the steps of a run should read `recording`'s audio from.

    stored_path is relative to the data directory, so that a backup
    restored on a machine where that directory sits elsewhere still
    resolves. If ingest.local_file wrote a 16 kHz mono sibling next to it
    a run reads that copy, never `recording.stored_path` itself,
    which stays whatever the caller gave Voxtrama so that
    `recording.content_sha256` keeps meaning what it always has.
    """
    original = get_paths(get_settings().data_dir).data_dir / recording.stored_path
    resampled = resampled_sibling(original)
    return resampled if resampled.exists() else original


def build_context(session: Session, run: Run) -> ExecutionContext:
    """Assemble what the steps of this run read from and write to."""
    recording = None
    audio_path = None
    if run.recording_id is not None:
        recording = session.scalar(select(Recording).where(Recording.id == run.recording_id))
        if recording is not None:
            audio_path = audio_path_for(recording)
    choices = RunChoices.model_validate(run.choices or {})
    return ExecutionContext(
        session=session, run=run, recording=recording, audio_path=audio_path, choices=choices
    )

"""The transcribe built-in, and the progress-reporting helper both extractive steps share.

Split from engine.builtin (the project's file-length limit). That module keeps
the two Skill declarations and the registries that tie every built-in
together. This module is only transcribe's StepFunction, mirroring
engine.generative, the same split for the generative side. diarize's
StepFunction lives in engine.diarize_step, split out in turn once adding
step provenance pushed this file past the same limit.
"""

from __future__ import annotations

from typing import Any

from voxtrama.config.settings import get_settings
from voxtrama.db.models.transcript import Transcript
from voxtrama.engine.context import ExecutionContext, StepPreconditionError
from voxtrama.engine.progress import record_provenance
from voxtrama.workflow.choices import context_for_transcription


def progress_hook(ctx: ExecutionContext, label: str, unit: str):
    """Adapt the engine's reporter to the (done, total) callback a step passes down.

    The label and unit are added here instead of by the step: a step knows
    what it is fetching or measuring, the engine knows which run is
    watching, and neither needs the other's vocabulary. Public because
    engine.diarize_step uses it too.
    """
    reporter = ctx.report_activity
    if reporter is None:
        return None
    return lambda done, total: reporter(label, unit, done, total)


def run_transcribe(ctx: ExecutionContext) -> dict[str, Any]:
    """Transcribe the run's Recording and persist the Transcript it produces."""
    from voxtrama.transcription import transcribe

    if ctx.recording is None:
        raise StepPreconditionError("transcribe: the run has no Recording")

    # The run's choice wins over the machine's setting. The
    # setting is what a run that chose nothing falls back to.
    hardware_profile = ctx.choices.hardware_profile or get_settings().hardware_profile
    transcript = transcribe(
        ctx.recording,
        hardware_profile,
        progress_hook(ctx, "ASR model", "bytes"),
        progress_hook(ctx, "audio", "seconds"),
        # Passed through as chosen, possibly None. transcribe() is
        # the one place that falls Settings back to this machine's tuning
        # proposal (transcription.resources), so the run's choice becomes
        # the outermost level of that fallback chain instead of a second
        # copy of it.
        cores_per_chunk=ctx.choices.cores_per_chunk,
        parallel_chunks=ctx.choices.parallel_chunks,
        context=context_for_transcription(ctx.choices.context),  # Cut for Whisper
        language=ctx.choices.output_language,  # The recap's language
    )
    # Which run and step produced this Transcript, so
    # engine.reconcile_manifest can resolve it by more than a recency
    # guess once this same Recording is transcribed again.
    transcript.produced_by_run_id = ctx.run.id
    transcript.produced_by_step_id = ctx.current_step_id
    ctx.session.add(transcript)
    ctx.session.flush()
    ctx.transcript = transcript
    _record_transcribe_provenance(ctx, transcript)
    return {"transcript_id": transcript.id}


def _record_transcribe_provenance(ctx: ExecutionContext, transcript: Transcript) -> None:
    """Write transcribe's model/provider/host onto its row.

    Split out of run_transcribe only to stay under the project's 40-line
    limit. The values are the decision that matters:

    `provider` is "local", not None. faster-whisper running in this same
    process, on this machine, is a fact about where the model ran, and
    None on this column means "we never recorded this step's provenance"
    (a pre-0013 row, or a step that asks no model anything). Folding "ran
    locally" into that None would make the field mean two things
    depending on the step, which the promise to re-run a run on the
    same terms cannot afford.

    `host` stays None, as an answer, not a gap: an in-process model has
    no host to contact, unlike a generative step behind providers.ollama.

    `profile_check_skipped` is False, not None: "skipped" exists
    only for a *remote* provider, whose memory cannot be read
    from here, so only its declaration can be trusted. A model running in
    this process has nothing to declare and verify separately (what is
    loaded here is what ran), so there is no verification gap to skip.
    False means what it means for a local Ollama call: not skipped.
    """
    record_provenance(
        ctx.session,
        ctx.step_rows[ctx.current_step_id],
        model=transcript.model_name,
        model_revision=transcript.model_revision,
        provider="local",
        host=None,
        profile_check_skipped=False,
    )

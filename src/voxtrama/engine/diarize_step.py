"""The diarize built-in: speaker labels, and where the model that produced them ran.

Split from engine.extractive_steps (the project's file-length limit), once
its provenance-recording docstring pushed that file past it. That
module's docstring has the rest of the split's reasoning.
"""

from __future__ import annotations

from typing import Any

from voxtrama.config.settings import get_settings
from voxtrama.engine.context import ExecutionContext, StepPreconditionError
from voxtrama.engine.extractive_steps import progress_hook
from voxtrama.engine.progress import record_provenance
from voxtrama.weights import ecapa_weights


def run_diarize(ctx: ExecutionContext) -> dict[str, Any]:
    """Label every Segment of the run's Transcript with who spoke it."""
    from voxtrama.diarization import assign_speakers, reapply_known_speakers
    from voxtrama.diarization.encoder import MODEL_SOURCE

    if ctx.transcript is None:
        raise StepPreconditionError("diarize: no Transcript to label, transcribe it first")
    if ctx.audio_path is None:
        raise StepPreconditionError("diarize: the run has no audio to read")

    # The run's ceiling wins over the machine's setting, as with
    # engine.extractive_steps.run_transcribe's hardware_profile.
    max_speakers = ctx.choices.max_speakers or get_settings().max_speakers
    assign_speakers(
        ctx.transcript,
        ctx.audio_path,
        get_settings().models_dir,
        max_speakers=max_speakers,
        on_download=progress_hook(ctx, "speaker model", "bytes"),
        on_progress=progress_hook(ctx, "audio", "seconds"),
    )
    # Restore whatever name a human already gave this Recording's
    # speakers, before anything else here reads speaker_label. A run with
    # no Recording to key that lookup on (ctx.recording is None) has never
    # had the chance to be named either.
    if ctx.recording is not None:
        reapply_known_speakers(ctx.session, ctx.recording.id, ctx.transcript)
    ctx.session.flush()
    _record_diarize_provenance(ctx, MODEL_SOURCE)
    return {"transcript_id": ctx.transcript.id, "speaker_estimate": ctx.transcript.speaker_estimate}


def _record_diarize_provenance(ctx: ExecutionContext, model_source: str) -> None:
    """Write diarize's model onto its row.

    `model` is diarization.encoder.MODEL_SOURCE, a Hugging Face repo id.
    It is not read off the Transcript, which carries the ASR's model, not
    ECAPA's. diarize labels an existing Transcript and owns no row of its
    own to hold this.

    `provider`, `host` and `profile_check_skipped` follow the reasoning of
    engine.extractive_steps._record_transcribe_provenance: ECAPA-TDNN runs
    in this same process too, so "local", None and False mean the same
    things here as there.

    `model_revision` is None, a *third* meaning for None across these five
    columns, distinct from the other two:

    - None on the whole row means this step's provenance was never
      recorded (a pre-0013 row, or a step that asks no model anything).
    - None on `host` alone means "no host to contact", an in-process
      model's honest answer, not a gap.
    - None on `model_revision` alone, with `model` set, was what every
      diarize row said until, for security, the ECAPA weights were pinned
      (weights.fetch.ecapa_weights). Older rows keep it: the weights they
      ran were whatever the Hub's main held that day.
    """
    record_provenance(
        ctx.session,
        ctx.step_rows[ctx.current_step_id],
        model=model_source,
        model_revision=ecapa_weights().revision,  # pinned for security
        provider="local",
        host=None,
        profile_check_skipped=False,
    )

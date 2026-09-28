"""ManifestChoices: what the run itself chose, not what it ran with.

Split from schema.py to keep that file under the project's size limit, the
same reason ManifestEvidence lives in evidence.py rather than there.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from voxtrama.workflow.choices import ASR_CONTEXT_CHARS, RunChoices


class ManifestChoices(BaseModel):
    """What the run itself chose, not what it ran with.

    `environment` says which hardware_profile a run used, this says whether
    that was a choice or the machine's own setting. None and {} both mean
    "not chosen", the same reading RunChoices() gives a run that chose
    nothing. The generative model used stays out of this section:
    steps[] will carry it, and recording it here too would give it
    two sources for the same value, which run_views.py's docstring
    already forbids.
    """

    model_config = ConfigDict(extra="forbid")
    hardware_profile: str | None
    generative_model: str | None
    step_skills: dict[str, str]  # step_id -> "name@version"
    # The same "None/chosen" reading as hardware_profile above,
    # extended to diarize's own opt-out and the two engine.resource_choice
    # already checked before this run was accepted. cores_per_chunk/
    # parallel_chunks' *effective* values already live on environment
    # (cpu_threads/num_workers). This only says whether they
    # were a choice, the same split hardware_profile already draws between
    # this section and environment.
    diarize: bool | None
    max_speakers: int | None
    cores_per_chunk: int | None
    parallel_chunks: int | None
    # The new-job form's own three (see RunChoices).
    context: str | None = None
    # Whether transcription got only the first
    # ASR_CONTEXT_CHARS of it (the generative steps always get it whole).
    context_cut_for_transcription: bool | None = None
    summary_detail: int | None = None
    pause_merge_seconds: float | None = None
    # What the engine deduced when no context was declared
    # (Run.deduced_context), so the manifest says what was used and where
    # it came from. None when declared, or when no model step ran.
    context_deduced: str | None = None
    # The language the job chose for its recap; None keeps
    # the transcript's own.
    output_language: str | None = None
    retention_days: int | None = None  # The job's own limit
    provider: str | None = None  # The provider the job named, if it did


def choices_info(choices: RunChoices, deduced: str | None = None) -> ManifestChoices:
    """What the run itself chose, not what it ran with. See ManifestChoices.

    Lives next to ManifestChoices, not in manifest.sections: it moved here
    once it gained four more fields to set, pushing that file past
    the project's line limit. That module's docstring never listed "choices"
    among the sections it builds anyway.
    """
    step_skills = {
        step_id: f"{ref.skill}@{ref.skill_version}" for step_id, ref in choices.step_skills.items()
    }
    return ManifestChoices(
        hardware_profile=choices.hardware_profile,
        generative_model=choices.generative_model,
        step_skills=step_skills,
        diarize=choices.diarize,
        max_speakers=choices.max_speakers,
        cores_per_chunk=choices.cores_per_chunk,
        parallel_chunks=choices.parallel_chunks,
        context=choices.context,
        context_cut_for_transcription=(
            len(choices.context) > ASR_CONTEXT_CHARS if choices.context else None
        ),
        summary_detail=choices.summary_detail,
        pause_merge_seconds=choices.pause_merge_seconds,
        context_deduced=deduced or None,
        output_language=choices.output_language,
        retention_days=choices.retention_days,
        provider=choices.provider,
    )

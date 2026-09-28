"""RunChoices: what one execution chose (the third level).

A Skill declares what is always true of a capability. A Workflow's
StepAllows (workflow.definition) declares what a run is permitted to
choose for a given step. This module is the third level: what a
particular run *did* choose, out of what was permitted.

None is not a convenience default here. It is what makes a choice
distinguishable from a machine default. A manifest has to
tell "the run chose base explicitly" apart from "the run chose nothing
and base is this machine's setting", and only a field that can be absent,
not merely equal to the default, can say that. RunChoices(), every field
None or empty, is a run that chose nothing at all.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Reused from transcription.profiles rather than re-declared: it is the
# same Literal Settings.hardware_profile already uses, and importing it
# does not create a cycle (transcription does not depend on workflow).
from voxtrama.transcription.profiles import HardwareProfile
from voxtrama.workflow.definition import SkillRef


class RunChoices(BaseModel):
    """What one run chose: a hardware profile, a generative model, per-step skills,
    and whether and how far to diarise, and how many cores/threads to spend.

    Three were named at first, and no others until a need was shown.
    A preview section is that need: a run may scope out of the machine's own
    diarisation ceiling and thread budget without touching Settings, the same
    way it already scopes out of the machine's hardware_profile.

    diarize=False is not "diarise faster" or "diarise less accurately": it
    is "do not diarise at all", and every Segment stays anonymous
    (person_id never set). That is a change to the *result*, not a
    performance knob, which is why it is checked like a skill choice
    (engine.diarize_choice) rather than silently degrading a step that
    still runs. A run must never pretend
    to have done less than it was asked.
    """

    model_config = ConfigDict(extra="forbid")

    hardware_profile: HardwareProfile | None = None
    generative_model: str | None = None
    step_skills: dict[str, SkillRef] = Field(default_factory=dict)
    # None: no run-level opinion. The workflow's own diarize step, if it has
    # one, still runs. False: skip it for this run even though the workflow
    # declares it (engine.diarize_choice drops the step and refuses the
    # request outright when another step depends on it: the transcript
    # cannot go anonymous out from under a step that reads speakers). True
    # records an explicit "yes" for the manifest, same effect as
    # None but distinguishable from "chose nothing" once it is read back.
    diarize: bool | None = None
    # The ceiling this run's own diarisation may report, overriding
    # Settings.max_speakers for this run alone. None falls back to
    # the machine's setting, same as hardware_profile above.
    max_speakers: int | None = Field(default=None, ge=1)
    # This run's own cores_per_chunk/parallel_chunks (the two Settings
    # fields), scoped to one execution. None falls back to Settings, which
    # itself falls back to this machine's own tuning proposal
    # (transcription.resources.resolve_engine_resources). The run choice
    # is a fourth, outermost level of the same fallback chain, not a
    # second one. Checked against what the machine has
    # (engine.resource_choice) before the run is accepted: asking for more
    # threads than exist is refused, never silently capped the way
    # tuning.core_budget.capped_cores caps Settings' own numbers. A run
    # that explicitly asked for a number gets told why it cannot have it,
    # rather than a different number it never chose.
    cores_per_chunk: int | None = Field(default=None, ge=1)
    parallel_chunks: int | None = Field(default=None, ge=1)
    # What the new-job form adds. `context` is the declared context
    # (names, acronyms, topics) handed to Whisper as its initial
    # prompt. Empty or None transcribes without one. `summary_detail` is
    # the 1-5 depth put into the summarize prompt. `pause_merge_seconds`
    # is the silence under which two segments of one speaker read as one
    # turn in the job view. None falls back to Settings for all three.
    context: str | None = Field(default=None, max_length=2000)
    summary_detail: int | None = Field(default=None, ge=1, le=5)
    pause_merge_seconds: float | None = Field(default=None, ge=0.1, le=10.0)
    # The language the generative steps write in, a code of
    # workflow.output_languages. None keeps the transcript's own.
    output_language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")
    # Days this job's data stays. It can only shorten the installation's
    # and the workflow's limits (workflow.retention). None sets no limit.
    retention_days: int | None = Field(default=None, ge=1, le=36500)
    # One of the providers configured on the machine, by name, never a
    # URL (providers.registry). None is the installation's default one.
    provider: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]{1,64}$")


# Whisper reads its initial_prompt as the text that came just
# before the audio, and only its last couple of hundred tokens count. The
# declared context is cut here, at 600 characters, and the manifest says
# when it was (manifest.choices).
ASR_CONTEXT_CHARS = 600


def context_for_transcription(context: str | None) -> str | None:
    """The part of the declared context the transcription model is given."""
    return context[:ASR_CONTEXT_CHARS] if context else None

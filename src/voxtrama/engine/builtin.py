"""The steps the engine can run today, and their skill declarations.

Two are Python, extractive skills that inspect a transcript instead of
sampling a model. Their StepFunctions live in engine.extractive_steps
(transcribe) and engine.diarize_step (diarize), split apart to stay under
the project's file-length limit. summarize comes from a file instead,
via engine.skill_catalog.builtin_generative_registry, which never raises:
a broken file becomes a step that fails only once a run names it, instead
of a product that will not start.

Each built-in also declares itself as a Skill: the workflow loader
validates every step against a skill registry, and refuses one it does not know.
"""

from __future__ import annotations

from voxtrama.engine.context import StepFunction
from voxtrama.engine.diarize_step import run_diarize
from voxtrama.engine.extractive_steps import run_transcribe
from voxtrama.engine.skill_catalog import builtin_generative_registry
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.skill import ContextRequirement, ModelClass, ModelProfile, Privacy, Skill

# The schemas below describe what each built-in consumes and produces.
# engine.validation checks every return value of the functions further down
# against its skill's output_schema, so a built-in that stops matching its
# declaration fails the run.
_AUDIO_IN = {
    "type": "object",
    "properties": {"recording_id": {"type": "string"}},
    "required": ["recording_id"],
}
_TRANSCRIPT_OUT = {
    "type": "object",
    "properties": {"transcript_id": {"type": "string"}},
    "required": ["transcript_id"],
}
_DIARIZE_OUT = {
    "type": "object",
    "properties": {
        "transcript_id": {"type": "string"},
        "speaker_estimate": {"type": "integer"},
    },
    "required": ["transcript_id", "speaker_estimate"],
}


TRANSCRIBE = Skill(
    name="transcribe",
    version="1.0.0",
    input_schema=_AUDIO_IN,
    output_schema=_TRANSCRIPT_OUT,
    context_requirements=[],
    # Extractive: it writes down what is in the audio. "Generative" is
    # reserved for a model producing content of its own, and the
    # difference decides whether a failed step may be retried at all.
    model_class=ModelClass.EXTRACTIVE,
    minimum_model_profile=ModelProfile.LOW,
    evidence_required=False,
    # 0.0 deliberately: what confidence means and which threshold may
    # gate needs_review is an open decision. A number picked here would
    # quietly become that decision.
    minimum_confidence=0.0,
    review_required=False,
    retention_policy="follows_recording",
    supported_audio_languages=[],
    privacy=Privacy.LOCAL_ONLY,
)

DIARIZE = Skill(
    name="diarize",
    version="1.0.0",
    input_schema=_TRANSCRIPT_OUT,
    output_schema=_DIARIZE_OUT,
    context_requirements=[ContextRequirement.SEGMENTS],
    model_class=ModelClass.EXTRACTIVE,
    minimum_model_profile=ModelProfile.LOW,
    evidence_required=False,
    minimum_confidence=0.0,
    review_required=False,
    retention_policy="follows_recording",
    supported_audio_languages=[],
    privacy=Privacy.LOCAL_ONLY,
)


# Built once at import time, same as TRANSCRIBE and DIARIZE above.
_GENERATIVE_STEPS, _GENERATIVE_SKILLS = builtin_generative_registry()

BUILTIN_STEPS: dict[str, StepFunction] = {
    "transcribe": run_transcribe,
    "diarize": run_diarize,
    **_GENERATIVE_STEPS,
}

BUILTIN_SKILLS: SkillRegistry = {
    TRANSCRIBE.name: {TRANSCRIBE.version: TRANSCRIBE},
    DIARIZE.name: {DIARIZE.version: DIARIZE},
    **_GENERATIVE_SKILLS,
}

"""The typed declaration of a Skill (core, not persisted).

This declares the fields a skill must have. No skill is implemented
here, and none is executed: this module defines only the shape,
generated into schemas/skill-v1.json by
scripts/generate_workflow_schemas.py.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from voxtrama.workflow.retention import POLICY_PATTERN

# The value output_language may take instead of a language code, meaning
# "whatever language the audio turned out to be". No ISO code
# names that concept, so it is spelled out rather than guessed.
SAME_AS_AUDIO = "same_as_audio"


class ModelClass(StrEnum):
    """What kind of model a Skill runs."""

    EXTRACTIVE = "extractive"
    GENERATIVE = "generative"


class ModelProfile(StrEnum):
    """The hardware profiles, which minimum_model_profile refers to."""

    LOW = "low"
    BASE = "base"
    HIGH = "high"


# The profiles' own ordering: "low" may run where "high" is required, never the
# reverse. Lives here, next to ModelProfile itself, rather than inside
# engine.choice_check (which needs it to reject a run choice) or an api
# route (which needs the same threshold to say what is offered): this
# module is a leaf both already import, so sharing it here creates no
# cycle, and the two callers read the one ranking instead of keeping two
# copies that could silently drift apart.
PROFILE_RANK: dict[str, int] = {"low": 0, "base": 1, "high": 2}


class Determinism(StrEnum):
    """The three determinism values a Run step can declare."""

    DETERMINISTIC = "deterministic"
    SAME_HOST = "same_host"
    NON_DETERMINISTIC = "non_deterministic"


class Privacy(StrEnum):
    """Whether a Skill may let content leave the local machine."""

    ANY = "any"
    LOCAL_ONLY = "local_only"


class ContextRequirement(StrEnum):
    """What a Skill needs beyond its input_schema."""

    SEGMENTS = "segments"
    METADATA = "metadata"
    MEMORY = "memory"


# Extractive skills cannot fabricate an evidence, because
# they only ever point at text that is already there. Generative ones
# sample, so their output varies between runs on the same host.
_MODEL_CLASS_TO_DETERMINISM = {
    ModelClass.EXTRACTIVE: Determinism.SAME_HOST,
    ModelClass.GENERATIVE: Determinism.NON_DETERMINISTIC,
}


class Skill(BaseModel):
    """The typed declaration of a skill.

    deterministic is not a field: it follows from model_class, and is
    exposed as a computed property so the two values cannot diverge.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    context_requirements: list[ContextRequirement] = Field(default_factory=list)
    model_class: ModelClass
    minimum_model_profile: ModelProfile
    evidence_required: bool
    minimum_confidence: float = Field(ge=0, le=1)
    review_required: bool
    # `follows_recording` or a number of days, `30d` (workflow.retention).
    retention_policy: str = Field(pattern=POLICY_PATTERN)
    output_language: str = SAME_AS_AUDIO
    # Empty means "every audio language".
    supported_audio_languages: list[str] = Field(default_factory=list)
    privacy: Privacy

    @computed_field
    @property
    def deterministic(self) -> Determinism:
        """The determinism the manifest records for a step running this skill."""
        return _MODEL_CLASS_TO_DETERMINISM[self.model_class]

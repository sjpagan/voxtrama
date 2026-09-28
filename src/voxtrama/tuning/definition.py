"""The typed shape of a tuning/*.yaml file.

Generated into schemas/tuning-v1.json by scripts/generate_workflow_schemas.py,
the same way workflow.definition.Workflow and workflow.skill.Skill are.
Read that script before hand-editing the JSON file.

Two things live in every file: `applies_to`, the conditions
tuning.selector checks a MachineReport against, and the execution
parameters themselves (asr, chunking, diarization, generative), which
this module only carries as data. Nothing here is read by the engine yet
(a caller is meant to pass these numbers to transcription.asr and
diarization.encoder instead of their own hardcoded ones).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AcceleratorCondition(StrEnum):
    """The three values diagnostics.accelerator.detect_accelerator can produce.

    "none" is not the same as leaving `accelerator` unset on
    TuningConditions: unset means the file does not care, "none" means the
    file requires a machine that reports no accelerator at all.
    """

    CUDA = "cuda"
    MPS = "mps"
    NONE = "none"


class TuningConditions(BaseModel):
    """Which machines a tuning file applies to, in the machine reading's own vocabulary.

    Every field left unset is a condition the file does not declare.
    tuning.selector turns "declared and satisfied" into a specificity
    score, and an unset field never counts against or for a machine.
    """

    model_config = ConfigDict(extra="forbid")

    architecture: str | None = None
    accelerator: AcceleratorCondition | None = None
    unified_memory: bool | None = None


class ModelTuning(BaseModel):
    """faster-whisper's own two knobs for one hardware profile."""

    model_config = ConfigDict(extra="forbid")

    model_size: str
    compute_type: str


class AsrProfiles(BaseModel):
    """One ModelTuning per hardware profile: low/base/high, never a fourth."""

    model_config = ConfigDict(extra="forbid")

    low: ModelTuning
    base: ModelTuning
    high: ModelTuning


class AsrTuning(BaseModel):
    """What transcription.asr would need beyond the profile table it hardcodes today."""

    model_config = ConfigDict(extra="forbid")

    device: str
    profiles: AsrProfiles


class MemoryThreshold(BaseModel):
    """A recommended amount of memory, and the sentence for a machine short of it.

    The interface that shows this never computes it: the
    sentence is already whole here, missing only the one number a live
    MachineReport supplies: `warning.format(recommended_gib=...,
    actual_gib=...)`.
    """

    model_config = ConfigDict(extra="forbid")

    recommended_gib: float
    warning: str


class ChunkTuning(BaseModel):
    """How this platform class splits a recording into parallel chunks."""

    model_config = ConfigDict(extra="forbid")

    parallel_chunks: int = Field(ge=1)
    cores_per_chunk: int = Field(ge=1)
    memory: MemoryThreshold


class DiarizationTuning(BaseModel):
    """The device diarization.encoder should ask torch for, in place of its hardcoded "cpu"."""

    model_config = ConfigDict(extra="forbid")

    device: str


class GenerativeTuning(BaseModel):
    """Whether a local generative model fits alongside transcription here.

    No device field: generative models always run through
    Ollama, local or remote, which manages its own device. There is
    nothing here for Voxtrama to hand it.
    """

    model_config = ConfigDict(extra="forbid")

    memory: MemoryThreshold
    # The order of magnitude a single generative call
    # needs on this machine class, before config.settings.Settings.
    # provider_timeout_seconds gives up on it. Declared here, per machine,
    # because the value depends on the machine. Settings does not
    # read it live yet, so today every file below
    # carries the same number, taken from one measurement, until
    # a platform-specific one exists.
    timeout_seconds: int = Field(gt=0)


class TuningFile(BaseModel):
    """One tuning/*.yaml: the execution parameters picked instead of hand-coding.

    See tuning/__init__.py for why deducing this file is not guessing the
    hardware profile, which is never done.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    applies_to: TuningConditions = Field(default_factory=TuningConditions)
    asr: AsrTuning
    chunking: ChunkTuning
    diarization: DiarizationTuning
    generative: GenerativeTuning

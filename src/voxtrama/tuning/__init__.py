"""Chooses the tuning/*.yaml file an installation's machine should run with.

The flow: read the machine (architecture, cores,
accelerator, unified memory), pick the tuning/ file that declares itself
for that machine, and hand back the execution parameters it carries:
device, compute type, model per hardware profile, how many chunks run in
parallel and what each is budgeted, the diarization device, and whether a
local generative model is comfortable alongside all of it. Adding a
platform becomes writing a file, not editing transcription/profiles.py or
the device= literal in transcription/asr.py.

This deliberately stops at choosing: nothing here calls transcription.asr
or diarization.encoder with these numbers, and asr.py is untouched.

The boundary, spelled out because it is easy to miss: the project
forbids guessing the hardware **profile** (low/base/high) from the
host, because a wrong guess degrades quality without saying so. That
choice stays a person's, explicit, in VOXTRAMA_HARDWARE_PROFILE. Nothing
here touches that. What gets deduced instead is narrower and one layer
below: given whichever profile a person already chose, which *file* of
low-level parameters (a device string, a compute type, a chunk count) fits
this host. Those numbers were already going to run on this machine either
way: profiles.PROFILES has no per-host variant today, so every machine
gets the same one regardless of what it has. Picking a better file for a
known machine class is not a decision reserved for a person. The
decision it reserves is still made explicitly, and every number this
module proposes stays visible and correctable, not applied silently.
"""

from __future__ import annotations

from voxtrama.tuning.definition import (
    AcceleratorCondition,
    AsrProfiles,
    AsrTuning,
    ChunkTuning,
    DiarizationTuning,
    GenerativeTuning,
    MemoryThreshold,
    ModelTuning,
    TuningConditions,
    TuningFile,
)
from voxtrama.tuning.errors import (
    TuningConflictError,
    TuningError,
    TuningNotFoundError,
    TuningValidationError,
)
from voxtrama.tuning.selector import select_tuning

__all__ = [
    "AcceleratorCondition",
    "AsrProfiles",
    "AsrTuning",
    "ChunkTuning",
    "DiarizationTuning",
    "GenerativeTuning",
    "MemoryThreshold",
    "ModelTuning",
    "TuningConditions",
    "TuningConflictError",
    "TuningError",
    "TuningFile",
    "TuningNotFoundError",
    "TuningValidationError",
    "select_tuning",
]

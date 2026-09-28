"""The part of a run's job_timeout its generative steps need.

engine.timeout sized the job for transcription and diarisation only. On
a 54-minute recording with qwen3:4b each window of the recap took about
ten minutes: four generative steps of several windows each can outlast
that budget, and the queue then kills a job that was working, throwing
the transcript's minutes away with it. This adds, for every generative
step, the most its calls may take: each call is already bounded by
Settings.provider_timeout_seconds, and the windows go
Settings.parallel_windows at a time (engine.window_calls). Like every
other term of the budget it errs on the side of too much: a worker held
longer only sits idle, a job killed mid-way loses what it had done.
"""

from __future__ import annotations

import math

from voxtrama.config.settings import Settings
from voxtrama.engine.transcript_windows import TOLERANCE, WINDOW_CHARS
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.skill import ModelClass

# Characters of transcript per minute of speech, rounded up: fast Italian
# runs at about 160 words a minute, six characters each with the space.
CHARACTERS_PER_MINUTE = 1000


def windows_for(duration_seconds: float) -> int:
    """How many windows engine.transcript_windows will cut, at most, for this much audio."""
    characters = duration_seconds / 60 * CHARACTERS_PER_MINUTE
    return max(1, math.ceil(characters / (WINDOW_CHARS * (1 - TOLERANCE))))


def generative_allowance(
    workflow: Workflow | None, duration_seconds: float, settings: Settings
) -> int:
    """Seconds to add to the job for `workflow`'s generative steps; 0 without any."""
    if workflow is None:
        return 0
    from voxtrama.engine.builtin import BUILTIN_SKILLS  # the registry imports the engine

    steps = sum(
        1
        for step in workflow.steps
        if (skill := BUILTIN_SKILLS.get(step.skill, {}).get(step.skill_version)) is not None
        and skill.model_class == ModelClass.GENERATIVE
    )
    rounds = math.ceil(windows_for(duration_seconds) / settings.parallel_windows)
    return math.ceil(steps * rounds * settings.provider_timeout_seconds)

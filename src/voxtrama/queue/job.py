"""Value types shared by every Queue implementation and by the core."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

JobId = NewType("JobId", str)


class JobState(StrEnum):
    """The lifecycle a queued job goes through."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Progress:
    """A point-in-time snapshot of how far a job has advanced."""

    current_step: int
    total_steps: int
    message: str

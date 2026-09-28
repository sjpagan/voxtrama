"""The shape of a run's published state: what it says, not how.

Split from engine.progress_file to stay under the project's file-length limit:
that module is the I/O (read, write, atomic replace), this is only the data
it moves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Activity:
    """Where a step has got to inside itself, in its own unit rather than a percentage.

    Percentages are computed by whoever displays them: a reader that only
    gets "63%" cannot tell 63% of 480 MB from 63% of 3 GB, and on a slow
    connection that difference is what matters. `name` is the bare
    noun ("ASR model", "audio"); the verb belongs to whoever composes the
    message (engine.activity_words, or engine.timeout_message writing
    its own).
    """

    name: str
    unit: str
    done: float
    total: float | None = None


@dataclass(frozen=True)
class ProgressState:
    """What a run is doing right now, as the engine last published it.

    `activity` and `ceiling_seconds` are the two ways a step in progress can
    say so: `activity` where there is a loop to measure it from, and
    `ceiling_seconds` (its declared timeout) where there is none, as in a
    single blocking call to a generative provider. Only one is meaningful
    for a step at a time, so there is no third field to say which wins.
    This also has no `download` field any more (`activity` replaces it):
    engine.progress_file.read_progress pays the cost of that rename.
    """

    run_id: str
    state: str
    step_total: int = 0
    step_index: int | None = None
    step_id: str | None = None
    message: str | None = None
    activity: Activity | None = None
    ceiling_seconds: float | None = None
    step_started_at: str | None = None  # when the step began publishing activity
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
